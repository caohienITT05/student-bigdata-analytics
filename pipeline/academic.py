from pyspark.sql import functions as F, types as T

from pipeline.common import canonical, read_csv, typed, profile, write_parquet, save_json


def build_academic(spark, root, config, manifest, clean, curated, reports, smoke=False):
    metadata = {r["file"]: r for r in manifest["files"]}
    frames, qualities = [], []
    for source in config["sources"]:
        entry = metadata[source["file"]]
        header = entry["csv"]["columns"]
        if source["name"] == "kaggle_test" and "Target" in header:
            raise ValueError("Kaggle test must not contain Target; refusing inferred/replacement labels")
        raw = read_csv(spark, root / source["file"], header, 200 if smoke else None)
        types = {name: "double" if any(term in name for term in ("grade", "Unemployment", "Inflation", "GDP")) else "long"
                 for name in header if name != "Target"}
        frame = typed(raw, types, ["id"] if "id" in header else [])
        quality = profile(raw, frame, header, ["id"] if "id" in header else [])
        quality.update({"file": source["file"], "encoding": entry["csv"]["encoding"], "delimiter": entry["csv"]["delimiter"],
                        "is_synthetic": source["is_synthetic"], "category_policy": config["code_policy"]})
        # Codes remain literal values; no unverified mapping is applied.
        frame = frame.select(*[F.col(name).alias(canonical(name)) for name in header], "_issues", "_raw_record", "_malformed")
        if "id" in header:
            frame = frame.withColumn("source_record_id", F.col("id").cast("string"))
            if quality["duplicate_key_excess"] or quality["missing_key_rows"]:
                raise ValueError(f"Cannot create unambiguous technical ID for {source['name']}; source IDs missing/duplicated")
        else:
            # The small original single-file CSV has no natural ID. Enumerate Spark's input
            # order; same bytes and scan partitioning give the same physical record number.
            schema = T.StructType(frame.schema.fields + [T.StructField("_source_row", T.LongType(), False)])
            frame = spark.createDataFrame(frame.rdd.zipWithIndex().map(lambda pair: tuple(pair[0]) + (pair[1] + 1,)), schema)
            frame = frame.withColumn("source_record_id", F.lit(None).cast("string"))
        filename = source["file"].rsplit("/", 1)[-1]
        suffix = F.col("source_record_id") if "id" in header else F.concat(F.lit("row:"), F.col("_source_row").cast("string"))
        frame = frame.withColumn("record_id", F.concat(F.lit(source["name"] + ":" + filename + ":"), suffix))
        if "Target" not in frame.columns:
            frame = frame.withColumn("Target", F.lit(None).cast("string"))
        frame = (frame.withColumn("source", F.lit(source["name"])).withColumn("source_file", F.lit(source["file"]))
                 .withColumn("is_synthetic", F.lit(source["is_synthetic"])).withColumn("has_target", F.col("Target").isNotNull())
                 .withColumn("code_namespace", F.lit(source["name"])))
        frame = frame.withColumn("_issues", F.when(F.col("Target").isNotNull() & ~F.col("Target").isin("Dropout", "Enrolled", "Graduate"),
                                                  F.array_union("_issues", F.array(F.lit("unknown_target")))).otherwise(F.col("_issues")))
        write_parquet(frame, clean / source["name"])
        write_parquet(frame.filter(F.size("_issues") > 0), clean / "quarantine" / source["name"])
        frames.append(spark.read.parquet(str(clean / source["name"])))
        qualities.append(quality)
        raw.unpersist()
        print("ACADEMIC SOURCE", source["name"], quality["rows"], flush=True)
    union = frames[0]
    for frame in frames[1:]:
        union = union.unionByName(frame, allowMissingColumns=True)
    write_parquet(union, curated / "academic_records")
    check = spark.read.parquet(str(curated / "academic_records"))
    total = check.count()
    expected = sum(q["rows"] for q in qualities)
    assert total == expected, (total, expected)
    assert check.select("record_id").distinct().count() == total, "Duplicate technical record_id"
    assert check.filter((F.col("source") == "kaggle_test") & (F.col("Target").isNotNull() | F.col("has_target"))).count() == 0
    save_json(reports / "quality_academic.json", {"sources": qualities, "union_rows": total, "retained_all_input_rows": total == expected,
        "schema": check.schema.jsonValue(), "policy": config["code_policy"],
        "id_policy": "Namespace source:file:id for supplied IDs; original source uses stable technical CSV row number, not a real student ID.",
        "schema_differences": {s["name"]: metadata[s["file"]]["csv"]["columns"] for s in config["sources"]},
        "label_policy": "Original observed, Kaggle synthetic; test Target remains null; never use sample_submission or legacy predictions.",
        "units": {"age_at_enrollment": "Years", "sem1_grade/sem2_grade": "0–20; zero is observed, not missing",
                  "sem*_enrolled/approved": "Curricular unit counts", "categories": "Literal source-scoped codes; no verified cross-source codebook"},
        "rules": ["No imputation", "No row deduplication", "Missing source-only columns remain null", "Codes are source scoped"]})
    return {"input_rows": expected, "output_rows": total, "sources": {s["name"]: q["rows"] for s, q in zip(config["sources"], qualities)}}
