from pyspark import StorageLevel
from pyspark.sql import functions as F

from pipeline.common import (ENROLMENT_KEY as K, TABLE_KEYS, NUMERIC, read_csv, typed, profile,
                             assert_unique, write_parquet, save_json, try_cast)


def activity_aggregate(events):
    good = F.size("_issues") == 0
    return events.groupBy(*K).agg(
        F.count("*").alias("event_rows"),
        F.sum(F.when(good, F.col("sum_click"))).alias("total_clicks"),
        F.countDistinct(F.when(good, F.col("date"))).alias("active_days"),
        F.countDistinct(F.when(good, F.col("id_site"))).alias("resources_used"),
        F.max(F.when(good, F.col("date"))).alias("last_activity_day"),
        F.min(F.when(good, F.col("date"))).alias("first_activity_day"),
        F.sum(F.when(good & (F.col("date") < 0), F.col("sum_click")).otherwise(0)).alias("pre_start_clicks"),
        F.sum(F.when(~good, 1).otherwise(0)).alias("invalid_event_rows"),
        F.sum(F.when(~F.col("_resource_match"), 1).otherwise(0)).alias("unmatched_resource_rows"))


def attach_activity(base, activity):
    result = base.join(activity, K, "left")
    # Zero means no matching event after the full source has been processed.
    for field in ("total_clicks", "active_days", "resources_used", "pre_start_clicks", "invalid_event_rows", "unmatched_resource_rows"):
        result = result.withColumn(field, F.when(F.col("event_rows").isNull(), 0).otherwise(F.col(field)))
    return result.withColumn("event_rows", F.coalesce(F.col("event_rows"), F.lit(0)))


def build_oulad(spark, root, config, manifest, clean, curated, reports, smoke=False):
    metadata = {r["file"]: r for r in manifest["files"]}
    directory = config["oulad"]["directory"]
    tables, qualities = {}, {}
    for name, numeric in NUMERIC.items():
        relative = directory + "/" + name + ".csv"
        entry = metadata[relative]
        limit = 2000 if smoke and name in ("studentVle", "studentAssessment") else None
        raw = read_csv(spark, root / relative, entry["csv"]["columns"], limit)
        types = {col: "double" if col in ("score", "weight") else "long" for col in numeric}
        extra = []
        if name == "studentAssessment":
            extra += [(~try_cast("is_banked", "long").isin(0, 1), "invalid_banked_flag"),
                      ((try_cast("score", "double") < 0) | (try_cast("score", "double") > 100), "score_outside_0_100")]
        if name == "studentVle":
            extra += [(try_cast("sum_click", "long") < 0, "negative_clicks")]
        frame = typed(raw, types, TABLE_KEYS[name], extra)
        quality = profile(raw, frame, entry["csv"]["columns"], TABLE_KEYS[name])
        quality.update({"file": relative, "encoding": entry["csv"]["encoding"], "delimiter": entry["csv"]["delimiter"]})
        qualities[name] = quality
        write_parquet(frame, clean / "oulad" / name)
        write_parquet(frame.filter(F.size("_issues") > 0), clean / "quarantine" / name)
        tables[name] = spark.read.parquet(str(clean / "oulad" / name))
        raw.unpersist()
        print("OULAD SOURCE", name, quality["rows"], "key excess", quality["duplicate_key_excess"], flush=True)
    info, registrations, courses = tables["studentInfo"], tables["studentRegistration"], tables["courses"]
    assessments, submitted, resources, clicks = tables["assessments"], tables["studentAssessment"], tables["vle"], tables["studentVle"]
    for name in ("studentInfo", "studentRegistration", "courses", "assessments", "vle"):
        assert_unique(tables[name], TABLE_KEYS[name], name)
    info_cols = [c for c in info.columns if not c.startswith("_")]
    reg = registrations.select(*K, "date_registration", "date_unregistration", F.lit(True).alias("registration_present"))
    base = info.select(*info_cols).join(reg, K, "left").join(
        courses.select("code_module", "code_presentation", "module_presentation_length"), ["code_module", "code_presentation"], "left")
    base = base.withColumn("record_id", F.concat_ws(":", F.lit("oulad"), "code_module", "code_presentation", F.col("id_student").cast("string")))
    base = base.withColumn("source", F.lit("oulad")).withColumn("source_file", F.lit(directory + "/studentInfo.csv"))
    base = base.persist(StorageLevel.DISK_ONLY)
    assert base.count() == qualities["studentInfo"]["rows"], "Profile/registration/course JOIN multiplied enrolments"
    assert_unique(base, K, "enrolment profile")
    profile_keys = info.select(*K).withColumn("_profile_match", F.lit(True))
    resource_keys = ["id_site", "code_module", "code_presentation"]
    resource = resources.select(*resource_keys, "activity_type", F.lit(True).alias("_resource_match"))
    events = (clicks.join(F.broadcast(resource), resource_keys, "left")
              .join(F.broadcast(profile_keys), K, "left")
              .withColumn("_profile_match", F.coalesce(F.col("_profile_match"), F.lit(False)))
              .withColumn("_resource_match", F.coalesce(F.col("_resource_match"), F.lit(False)))
              .persist(StorageLevel.DISK_ONLY))
    assert events.count() == qualities["studentVle"]["rows"], "VLE resource/profile JOIN multiplied event rows"
    missing_vle_profile = events.filter(~F.col("_profile_match")).count()
    missing_resources = events.filter(~F.col("_resource_match")).count()
    write_parquet(events.filter(~F.col("_profile_match") | ~F.col("_resource_match")), clean / "quarantine" / "vle_links")
    assessment_dim = assessments.select("id_assessment", "code_module", "code_presentation")
    assessment_events = (submitted.join(F.broadcast(assessment_dim), "id_assessment", "left")
                         .join(F.broadcast(profile_keys), K, "left")
                         .withColumn("_profile_match", F.coalesce(F.col("_profile_match"), F.lit(False))).persist(StorageLevel.DISK_ONLY))
    assert assessment_events.count() == qualities["studentAssessment"]["rows"], "Assessment JOIN multiplied submissions"
    missing_assessment = assessment_events.filter(F.col("code_module").isNull()).count()
    missing_assessment_profile = assessment_events.filter(~F.col("_profile_match")).count()
    write_parquet(assessment_events.filter(~F.col("_profile_match")), clean / "quarantine" / "assessment_links")
    matched_events = events.filter(F.col("_profile_match"))
    full = attach_activity(base, activity_aggregate(matched_events)).withColumn("scope", F.lit("full"))
    write_parquet(full, curated / "oulad_enrolments")
    def by_week(frame):
        return frame.filter(F.size("_issues") == 0).withColumn("week", F.floor(F.col("date") / 7).cast("int")).groupBy(*K, "week").agg(
            F.sum("sum_click").alias("clicks"), F.countDistinct("date").alias("active_days"),
            F.countDistinct("id_site").alias("resources"), F.max("date").alias("last_activity_day")).withColumn("scope", F.lit("full"))
    weekly = by_week(matched_events)
    write_parquet(weekly, curated / "oulad_weekly")
    full_check = spark.read.parquet(str(curated / "oulad_enrolments"))
    total = full_check.count()
    assert total == base.count(), "A LEFT JOIN lost learners without interaction"
    assert_unique(full_check, K, "full enrolments")
    unique_people = info.select("id_student").distinct().count()
    no_events = full_check.filter("event_rows = 0").count()
    joins = {
        "enrolment_key": K, "cardinality": "profile 1:1 registration; n:1 course; events n:1 dimension; aggregate before LEFT JOIN",
        "input_vle_rows": qualities["studentVle"]["rows"], "joined_vle_rows": events.count(),
        "vle_without_enrolment": missing_vle_profile, "vle_without_resource": missing_resources,
        "assessment_without_definition": missing_assessment, "assessment_without_enrolment": missing_assessment_profile,
        "registration_without_profile": registrations.join(info.select(*K), K, "left_anti").count(),
        "profiles_without_registration": base.filter(F.col("registration_present").isNull()).count(),
        "profiles_without_course": base.filter(F.col("module_presentation_length").isNull()).count(),
        "enrolments": total, "unique_learners": unique_people, "no_vle_entire_course": no_events,
    }
    save_json(reports / "quality_oulad.json", {"tables": qualities, "joins": joins,
        "documentation": "data/raw/oulad/OULAD.names (Windows-1252 text); CSV header takes precedence where field names differ.",
        "units": {"dates": "Days relative to module/presentation start; negative days are pre-start", "week": "floor(date / 7)",
                  "score": "0–100, observed zero retained, missing score null", "weight": "Assessment weight in percent",
                  "sum_click": "Logged clicks; sum preserved without event deduplication", "identity": "One student × module × presentation per enrolment"},
        "rules": ["Preserve missing dates/scores; missing submission is not score zero",
                  "Negative dates are pre-course; retained, with separate pre_start_clicks",
                  "Do not treat Withdrawn as university dropout; final_result labels kept literally",
                  "Assessment links checked separately; never joined to individual interactions", "Orphan links retained in quarantine",
                  "Zero activity only after fully processing source; invalid activity is flagged",
                  "Final_result is a later outcome used for retrospective description, not an AI prediction"]})
    for cached in (base, events, assessment_events):
        cached.unpersist()
    return {"input_rows": {name: q["rows"] for name, q in qualities.items()}, "output_rows": total,
            "unique_learners": unique_people, "joins": joins}
