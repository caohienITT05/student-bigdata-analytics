import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import functions as F, types as T

ENROLMENT_KEY = ["id_student", "code_module", "code_presentation"]
TABLE_KEYS = {
    "courses": ["code_module", "code_presentation"], "assessments": ["id_assessment"],
    "studentInfo": ENROLMENT_KEY, "studentRegistration": ENROLMENT_KEY,
    "studentAssessment": ["id_assessment", "id_student"],
    "studentVle": ENROLMENT_KEY + ["id_site", "date"],
    "vle": ["id_site", "code_module", "code_presentation"],
}
NUMERIC = {
    "courses": ["module_presentation_length"],
    "assessments": ["id_assessment", "date", "weight"],
    "studentInfo": ["id_student", "num_of_prev_attempts", "studied_credits"],
    "studentRegistration": ["id_student", "date_registration", "date_unregistration"],
    "studentAssessment": ["id_assessment", "id_student", "date_submitted", "is_banked", "score"],
    "studentVle": ["id_student", "id_site", "date", "sum_click"],
    "vle": ["id_site", "week_from", "week_to"],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def canonical(name):
    if name == "Target":
        return name
    name = name.replace("Curricular units 1st sem", "sem1").replace("Curricular units 2nd sem", "sem2")
    name = name.replace("Nacionality", "nationality")
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def try_cast(name, dtype):
    quote = chr(96)
    return F.expr("try_cast(" + quote + name.replace(quote, quote + quote) + quote + " as " + dtype + ")")


def read_csv(spark, path, header, limit=None):
    schema = T.StructType([T.StructField(name, T.StringType(), True) for name in header] +
                          [T.StructField("_corrupt_record", T.StringType(), True)])
    frame = (spark.read.option("header", True).option("encoding", "UTF-8").option("nullValue", "?")
             .option("mode", "PERMISSIVE").schema(schema).csv(str(path)))
    if limit:
        frame = frame.limit(limit)
    return frame.persist(StorageLevel.DISK_ONLY)


def typed(raw, numeric_types, key_columns, extra_checks=()):
    fields, issues = [], []
    for name in raw.columns:
        if name == "_corrupt_record":
            continue
        expression = F.col(name)
        if name in numeric_types:
            expression = try_cast(name, numeric_types[name])
            if numeric_types[name] == "double":
                expression = F.when(F.isnan(expression) | (F.abs(expression) == float("inf")), None).otherwise(expression)
            issues.append(F.when(F.col(name).isNotNull() & expression.isNull(), F.lit("invalid_number:" + name)))
        fields.append(expression.alias(name))
    frame = raw.select(*fields, F.col("_corrupt_record"))
    issues += [F.when(F.col(name).isNull(), F.lit("missing_key:" + name)) for name in key_columns]
    issues += [F.when(condition, F.lit(code)) for condition, code in extra_checks]
    issues.append(F.when(F.col("_corrupt_record").isNotNull(), F.lit("malformed_csv")))
    # Numeric checks use the original string frame; other checks reference existing columns.
    frame = raw.select(*fields, F.array_compact(F.array(*issues)).alias("_issues"),
                       F.when(F.col("_corrupt_record").isNotNull(), F.col("_corrupt_record")).alias("_malformed"),
                       F.to_json(F.struct(*[F.col(c) for c in raw.columns if c != "_corrupt_record"])).alias("_raw_record"))
    return frame.withColumn("_raw_record", F.when(F.size("_issues") > 0, F.col("_raw_record")))


def profile(raw, frame, columns, keys):
    # One bounded aggregate to driver; rows/events themselves never collected.
    expressions = [F.count("*").alias("rows"),
                   F.sum(F.when(F.size("_issues") > 0, 1).otherwise(0)).alias("flagged_rows")]
    for i, name in enumerate(columns):
        expressions += [F.sum(F.when(F.col(name).isNull(), 1).otherwise(0)).alias(f"null_{i}"),
                        F.min(name).alias(f"min_{i}"), F.max(name).alias(f"max_{i}")]
    result = frame.agg(*expressions).first().asDict()
    raw_missing = raw.agg(*[F.sum(F.when(F.col(name).isNull(), 1).otherwise(0)).alias(f"raw_null_{i}") for i, name in enumerate(columns)]).first().asDict()
    duplicates = raw.groupBy(*columns).count().filter("count > 1").agg(F.sum(F.col("count") - 1)).first()[0] or 0
    if keys:
        duplicate_keys = raw.groupBy(*keys).count().filter("count > 1").agg(
            F.sum("count").alias("rows"), F.sum(F.col("count") - 1).alias("excess"), F.count("*").alias("groups")).first().asDict()
        missing_keys = frame.filter(F.array_contains(F.array(*[F.col(k).isNull() for k in keys]), True)).count()
    else:
        duplicate_keys, missing_keys = {"rows": 0, "excess": 0, "groups": 0}, None
    details = []
    for i, name in enumerate(columns):
        item = {"column": name, "type": frame.schema[name].dataType.simpleString(),
                "missing_raw": raw_missing[f"raw_null_{i}"] or 0, "missing_clean": result[f"null_{i}"] or 0,
                "min": result[f"min_{i}"], "max": result[f"max_{i}"]}
        if item["type"] == "string" and name not in keys:
            values = [r[0] for r in frame.select(name).distinct().orderBy(name).limit(101).toLocalIterator()]
            item["observed_values"] = values[:100]
            item["values_truncated"] = len(values) > 100
        details.append(item)
    return {"rows": result["rows"], "columns": len(columns), "column_details": details,
            "flagged_rows": result["flagged_rows"] or 0, "full_row_duplicate_excess": duplicates,
            "key": keys, "duplicate_key_rows": duplicate_keys["rows"] or 0,
            "duplicate_key_excess": duplicate_keys["excess"] or 0, "duplicate_key_groups": duplicate_keys["groups"] or 0,
            "missing_key_rows": missing_keys, "missing_markers": ["empty CSV field", "?"],
            "duplicate_policy": "Keep rows; report duplicates. No feature-based deduplication.",
            "zero_policy": "Numeric zero is kept; no imputation."}


def assert_unique(frame, keys, name):
    missing = frame.filter(F.array_contains(F.array(*[F.col(k).isNull() for k in keys]), True)).count()
    duplicate = frame.groupBy(*keys).count().filter("count > 1").limit(1).count()
    if missing or duplicate:
        raise ValueError(f"{name}: ambiguous JOIN key {keys}; missing={missing}, duplicate={duplicate}. No arbitrary deduplication performed.")


def write_parquet(frame, path):
    path = Path(path)
    if not any(segment in ("clean", "curated") for segment in path.parts):
        raise ValueError("Output must belong to new clean/curated pipeline")
    frame.write.mode("overwrite").parquet(str(path))


def fingerprint(root, config, manifest):
    digest = hashlib.sha256()
    digest.update(json.dumps(config, sort_keys=True).encode())
    digest.update(json.dumps(manifest["files"], sort_keys=True).encode())
    for folder in ("pipeline", "sql"):
        for path in sorted((root / folder).glob("*")):
            if path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()
