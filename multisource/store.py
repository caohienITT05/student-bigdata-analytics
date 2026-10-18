import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/data_pipeline"
DATABASE = ROOT / "data/curated/dashboard.sqlite"
ACTIVE_TABLES = ("a_summary", "a_target", "a_histograms", "b_population", "b_results", "b_weekly")
JOIN_FIELDS = ("enrolment_key", "cardinality", "input_vle_rows", "joined_vle_rows", "vle_without_enrolment",
               "vle_without_resource", "assessment_without_definition", "assessment_without_enrolment",
               "registration_without_profile", "profiles_without_registration", "profiles_without_course",
               "enrolments", "unique_learners", "no_vle_entire_course")


def report(name):
    path = REPORTS / (name + ".json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def ready():
    run = report("run_sql") or {}
    return DATABASE.exists() and run.get("state") == "completed" and run.get("scope") == "full" and report("dashboard_metadata") is not None


@contextmanager
def database():
    if not ready():
        raise HTTPException(503, "Chưa có kết quả batch đầy đủ. Chạy scripts/run-pipeline.ps1 -Stage all; dữ liệu thử không được dùng cho dashboard.")
    try:
        connection = sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
    except sqlite3.Error as error:
        raise HTTPException(503, "Không mở được bảng kết quả đã xuất.") from error
    try:
        yield connection
    except sqlite3.Error as error:
        raise HTTPException(503, "Bảng kết quả chưa đầy đủ; chạy lại bước Spark SQL.") from error
    finally:
        connection.close()


def rows(connection, table, where, params, order="", limit=1000, offset=0, columns=None):
    # Identifiers come exclusively from the router's fixed whitelist.
    projection = ",".join('"' + column + '"' for column in columns) if columns else "*"
    query = 'SELECT ' + projection + ' FROM "' + table + '" WHERE ' + where
    if order:
        query += " ORDER BY " + order
    query += " LIMIT ? OFFSET ?"
    return [dict(row) for row in connection.execute(query, [*params, limit, offset])]


def dashboard_metadata():
    value = report("dashboard_metadata") or {}
    result = {key: value[key] for key in ("processed_at", "mode", "database", "oulad_label_note", "non_causal_note") if key in value}
    result["tables"] = {name: value["tables"][name] for name in ACTIVE_TABLES if name in value.get("tables", {})}
    # Existing exports remain valid; only the retained fields are advertised.
    projections = {
        "b_population": ("code_module", "code_presentation", "scope", "enrolments", "unique_learners", "clicks", "clicks_undefined_enrolments", "no_activity_enrolments"),
        "b_results": ("code_module", "code_presentation", "scope", "final_result", "enrolments", "clicks", "mean_clicks", "mean_active_days", "mean_resources", "pre_start_clicks", "no_activity_enrolments"),
    }
    for name, columns in projections.items():
        if name in result["tables"]:
            result["tables"][name]["columns"] = [c for c in result["tables"][name]["columns"] if c in columns]
    return result


def run_brief(stage):
    value = report("run_" + stage)
    if value is None:
        return None
    return {key: value[key] for key in ("stage", "state", "scope", "started_at", "completed_at", "elapsed_seconds", "runtime") if key in value}


def quality_brief():
    academic, oulad = report("quality_academic") or {}, report("quality_oulad") or {}
    entries = [(q.get("file"), q) for q in academic.get("sources", [])]
    entries += [("oulad/" + name, q) for name, q in oulad.get("tables", {}).items()]
    return {"sources": [{"file": file, **{k: q.get(k) for k in ("rows", "columns", "flagged_rows", "full_row_duplicate_excess", "duplicate_key_excess", "key", "missing_key_rows")},
                         "missing_cells": sum(c.get("missing_raw", 0) for c in q.get("column_details", []))} for file, q in entries],
            "joins": {key: value for key, value in oulad.get("joins", {}).items() if key in JOIN_FIELDS},
            "reports": ["quality_academic", "quality_oulad", "sources_manifest", "run_a", "run_oulad", "run_sql"]}
