"""Entry point executed by spark-submit; legacy model is never imported."""
import argparse
import json
import platform
import sys
import time
from pathlib import Path

from pyspark.sql import SparkSession

from pipeline.common import now, save_json, fingerprint
from pipeline.academic import build_academic
from pipeline.oulad import build_oulad
from pipeline.export_sql import export_sql
from pipeline.prepare import checksum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--stage", choices=("smoke", "a", "oulad", "sql", "all", "verify"), default="all")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    config = json.loads((root / "config/data_sources.json").read_text(encoding="utf-8-sig"))
    manifest = json.loads((root / "reports/data_pipeline/sources_manifest.json").read_text(encoding="utf-8"))
    smoke = args.stage == "smoke"
    suffix = "/smoke" if smoke else ""
    clean, curated, reports = [root / (config["paths"][name] + suffix) for name in ("clean", "curated", "reports")]
    for path in (clean, curated, reports):
        path.mkdir(parents=True, exist_ok=True)
    digest = fingerprint(root, config, manifest)
    spark = (SparkSession.builder.appName("student-bigdata-batch").master(config["spark"]["master"])
             .config("spark.sql.shuffle.partitions", config["spark"]["shuffle_partitions"])
             .config("spark.sql.files.maxPartitionBytes", config["spark"]["max_partition_bytes"])
             .config("spark.sql.adaptive.enabled", "true").config("spark.sql.session.timeZone", "UTC")
             .config("spark.ui.enabled", "false").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    runtime = {"spark_version": spark.version, "python_version": sys.version, "platform": platform.platform(),
               "java_version": spark.sparkContext._jvm.java.lang.System.getProperty("java.version"),
               "master": spark.sparkContext.master, "driver_memory": spark.sparkContext.getConf().get("spark.driver.memory"),
               "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
               "max_partition_bytes": spark.conf.get("spark.sql.files.maxPartitionBytes"),
               "execution": "Single-machine local Spark inside Docker; not a multi-machine cluster"}
    print("ACTUAL SPARK RUNTIME", json.dumps(runtime), flush=True)
    stages = ("a", "oulad", "sql") if args.stage in ("all", "smoke") else (args.stage,)
    try:
        for stage in stages:
            report_path = reports / ("run_" + stage + ".json")
            prior = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            output_exists = (curated / {"a": "academic_records", "oulad": "oulad_enrolments", "sql": "dashboard.sqlite"}.get(stage, "dashboard.sqlite")).exists()
            if stage != "verify" and not args.force and prior.get("fingerprint") == digest and prior.get("state") == "completed" and output_exists:
                print("UNCHANGED INPUT/CODE; SKIP", stage, flush=True)
                continue
            started = now()
            timer = time.perf_counter()
            if stage == "a":
                result = build_academic(spark, root, config, manifest, clean, curated, reports, smoke)
            elif stage == "oulad":
                result = build_oulad(spark, root, config, manifest, clean, curated, reports, smoke)
            elif stage == "sql":
                for dependency in ("a", "oulad"):
                    prior_dependency = json.loads((reports / ("run_" + dependency + ".json")).read_text(encoding="utf-8"))
                    if prior_dependency["fingerprint"] != digest:
                        raise ValueError(f"{dependency} output is stale; rerun branch first")
                result = export_sql(spark, root, config, curated, reports)
            else:
                academic = spark.read.parquet(str(curated / "academic_records"))
                expected = sum(r["csv"]["rows"] for r in manifest["files"] if r["source"] != "oulad")
                assert academic.count() == expected
                assert academic.select("record_id").distinct().count() == expected
                assert academic.filter("source='kaggle_test' AND (Target IS NOT NULL OR has_target)").count() == 0
                assert academic.filter("code_namespace<>source OR NOT record_id LIKE concat(source, ':%')").count() == 0
                full = spark.read.parquet(str(curated / "oulad_enrolments"))
                input_profiles = next(r["csv"]["rows"] for r in manifest["files"] if r["file"].endswith("studentInfo.csv"))
                assert full.count() == input_profiles
                assert full.select("record_id").distinct().count() == full.count()
                weekly = spark.read.parquet(str(curated / "oulad_weekly"))
                assert weekly.filter("scope<>'full'").count() == 0
                assert full.filter("event_rows=0 AND (total_clicks<>0 OR active_days<>0 OR resources_used<>0)").count() == 0
                quality = json.loads((reports / "quality_oulad.json").read_text(encoding="utf-8"))
                assert quality["joins"]["input_vle_rows"] == quality["joins"]["joined_vle_rows"]
                people = full.select("id_student").distinct().count()
                result = {"academic_rows": expected, "oulad_enrolments": full.count(), "unique_learners": people,
                          "no_activity_kept": full.filter("event_rows=0").count(), "source_scoped_codes": True,
                          "full_course_only": True}
            report = {"stage": stage, "state": "completed", "scope": "sample" if smoke else "full",
                      "fingerprint": digest, "started_at": started, "completed_at": now(),
                      "elapsed_seconds": round(time.perf_counter() - timer, 2), "runtime": runtime, **result}
            save_json(report_path, report)
            print("STAGE COMPLETE", json.dumps(report), flush=True)
        for relative, original in manifest["legacy"].items():
            if checksum(root / relative) != original:
                raise AssertionError("Legacy artifact changed: " + relative)
        print("LEGACY ARTIFACT CHECKSUMS UNCHANGED", flush=True)
    except Exception as error:
        save_json(reports / ("failure_" + args.stage + ".json"),
                  {"state": "failed", "at": now(), "runtime": runtime, "type": type(error).__name__, "message": str(error)})
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
