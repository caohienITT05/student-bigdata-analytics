from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from multisource import store
from multisource.catalog import source_catalog

router = APIRouter(prefix="/api/multi", tags=["Precomputed Spark SQL"])
Source = Literal["all", "original", "kaggle_train", "kaggle_test"]


@router.get("/catalog")
def catalog():
    return source_catalog()


def academic_filter(source):
    clauses, params = ["1=1"], []
    if source != "all":
        clauses.append("source=?")
        params.append(source)
    return " AND ".join(clauses), params


def oulad_filter(module, presentation):
    clauses, params = ["scope='full'"], []
    # Exact CUBE slice: rollups provide correct distinct learner counts.
    for column, value in (("code_module", module), ("code_presentation", presentation)):
        clauses.append(column + (" IS NULL" if value == "all" else "=?"))
        if value != "all":
            params.append(value)
    return " AND ".join(clauses), params


def reject_removed_filters(request, names):
    if any(name in request.query_params for name in names):
        raise HTTPException(422, "Bộ lọc này đã được loại bỏ khỏi API.")


@router.get("/status")
def status():
    available = store.ready()
    result = {"ready": available, "mode": "File xuất sẵn từ Spark SQL; không kết nối MySQL/MongoDB trực tiếp",
              "message": "Kết quả toàn bộ dữ liệu" if available else "Chưa có batch đầy đủ. Chạy scripts/run-pipeline.ps1 -Stage all."}
    if available:
        result.update({"metadata": store.dashboard_metadata(), "runs": {s: store.run_brief(s) for s in ("a", "oulad", "sql")}, "quality": store.quality_brief()})
        with store.database() as db:
            result["modules"] = [r[0] for r in db.execute("SELECT DISTINCT code_module FROM b_population WHERE code_module IS NOT NULL ORDER BY 1")]
            result["presentations"] = [r[0] for r in db.execute("SELECT DISTINCT code_presentation FROM b_population WHERE code_presentation IS NOT NULL ORDER BY 1")]
    return result


@router.get("/academic/summary")
def academic_summary(request: Request, source: Source = "all"):
    reject_removed_filters(request, ("labels", "kind"))
    where, params = academic_filter(source)
    with store.database() as db:
        result = {name: store.rows(db, table, where, params, order) for name, table, order in (
            ("sources", "a_summary", "source"), ("targets", "a_target", "source,target"),
            ("histograms", "a_histograms", "metric,bin_order,source"))}
    sources = result["sources"]
    total = sum(r["records"] for r in sources)
    labelled = sum(r["labelled_records"] for r in sources)
    result["totals"] = {"records": total, "observed": sum(r["records"] for r in sources if not r["is_synthetic"]),
                        "synthetic": sum(r["records"] for r in sources if r["is_synthetic"]), "labelled": labelled,
                        "unlabelled": total - labelled, "flagged": sum(r["flagged_records"] for r in sources)}
    result["filters"] = {"source": source}
    return result


@router.get("/oulad/summary")
def oulad_summary(request: Request, module: str = Query("all", pattern=r"^(all|[A-Z]{3})$"),
                  presentation: str = Query("all", pattern=r"^(all|[0-9]{4}[A-Z])$")):
    reject_removed_filters(request, ("scope",))
    where, params = oulad_filter(module, presentation)
    with store.database() as db:
        populations = store.rows(db, "b_population", where, params, limit=1,
            columns=("code_module", "code_presentation", "enrolments", "unique_learners", "clicks", "clicks_undefined_enrolments", "no_activity_enrolments"))
        outcomes = store.rows(db, "b_results", where, params, "final_result",
            columns=("code_module", "code_presentation", "final_result", "enrolments", "clicks", "mean_clicks", "mean_active_days", "mean_resources", "pre_start_clicks", "no_activity_enrolments"))
        weekly = store.rows(db, "b_weekly", where, params, "week,final_result",
            columns=("code_module", "code_presentation", "week", "final_result", "active_enrolments", "clicks", "enrolment_active_days", "mean_resources", "last_activity_day"))
    count = populations[0]["enrolments"] if populations else 0
    for row in outcomes:
        row["enrolment_percent"] = round(100 * row["enrolments"] / count, 2) if count else None
    return {"population": populations[0] if populations else None, "outcomes": outcomes, "weekly": weekly,
            "filters": {"module": module, "presentation": presentation}}


@router.get("/reports/{name}")
def quality_report(name: str):
    if name not in ("quality_academic", "quality_oulad", "sources_manifest", "run_a", "run_oulad", "run_sql", "dashboard_metadata"):
        raise HTTPException(404, "Báo cáo không tồn tại")
    value = store.dashboard_metadata() if name == "dashboard_metadata" else store.run_brief(name[4:]) if name.startswith("run_") else store.report(name)
    if value is None:
        raise HTTPException(404, "Báo cáo chưa được tạo")
    return value
