import json
import re
import sqlite3
from decimal import Decimal
from contextlib import closing
from pathlib import Path

from pipeline.common import save_json, write_parquet, now


def export_sql(spark, root, config, curated, reports):
    required = ("academic_records", "oulad_enrolments", "oulad_weekly")
    if not all((curated / name).exists() for name in required):
        raise FileNotFoundError("Run both academic and OULAD stages before Spark SQL export")
    academic = spark.read.parquet(str(curated / "academic_records"))
    full = spark.read.parquet(str(curated / "oulad_enrolments"))
    weekly = spark.read.parquet(str(curated / "oulad_weekly"))
    for name, frame in (("academic", academic), ("oulad_full", full), ("oulad_profile", full),
                        ("oulad_weekly", weekly)):
        frame.createOrReplaceTempView(name)
    database = curated / "dashboard.sqlite"
    pending = curated / "dashboard.pending.sqlite"
    if pending.exists():
        pending.unlink()
    tables = {}
    with closing(sqlite3.connect(pending)) as connection:
        for branch in ("academic", "oulad"):
            text = (root / "sql" / (branch + ".sql")).read_text(encoding="utf-8")
            sections = re.split(r"(?m)^-- table: ([a-z_]+)\s*$", text)
            for i in range(1, len(sections), 2):
                name, sql = sections[i], sections[i + 1].strip()
                frame = spark.sql(sql)
                write_parquet(frame.coalesce(2), curated / "aggregates" / name)
                frame = spark.read.parquet(str(curated / "aggregates" / name))
                count = frame.count()
                if count > 50000:
                    raise ValueError(f"Serving result too large to export: {name}, {count}; aggregate further")
                columns = frame.columns
                kinds = ["INTEGER" if field.dataType.simpleString() in ("bigint", "long", "int", "smallint", "tinyint", "boolean") else "REAL" if field.dataType.simpleString() in ("double", "float") or field.dataType.simpleString().startswith("decimal(") else "TEXT" for field in frame.schema.fields]
                connection.execute('CREATE TABLE "' + name + '" (' + ",".join('"' + col + '" ' + kind for col, kind in zip(columns, kinds)) + ")")
                insert = 'INSERT INTO "' + name + '" VALUES (' + ",".join("?" for _ in columns) + ")"
                buffer = []
                # Only bounded SQL summaries; never collect studentVle/events to driver.
                for row in frame.toLocalIterator():
                    buffer.append(tuple(float(value) if isinstance(value, Decimal) else value for value in row))
                    if len(buffer) == 200:
                        connection.executemany(insert, buffer)
                        buffer = []
                if buffer:
                    connection.executemany(insert, buffer)
                dimensions = [c for c in ("source", "has_target", "code_module", "code_presentation", "scope") if c in columns]
                if dimensions:
                    connection.execute('CREATE INDEX "' + name + '_filters" ON "' + name + '" (' + ",".join('"' + c + '"' for c in dimensions) + ")")
                tables[name] = {"rows": count, "columns": columns, "sql_file": "sql/" + branch + ".sql", "units": "counts, percentages, grade/click/day measures as named"}
                print("SPARK SQL EXPORT", name, count, flush=True)
        connection.commit()
        assert connection.execute("SELECT SUM(records) FROM a_summary").fetchone()[0] == academic.count()
        assert connection.execute("SELECT SUM(records) FROM a_target WHERE source='kaggle_test' AND target IS NOT NULL").fetchone()[0] in (0, None)
        assert connection.execute("SELECT COUNT(*) FROM b_population WHERE scope<>'full'").fetchone()[0] == 0
    pending.replace(database)  # Publish only a complete, verified database.
    metadata = {"processed_at": now(), "mode": "Spark local batch; API reads exported summaries, no job per request",
                "database": "data/curated/dashboard.sqlite", "tables": tables,
                "code_policy": config["code_policy"],
                "oulad_label_note": "Withdrawn = rút học phần; Fail = không đạt; Pass = đạt; Distinction = đạt mức xuất sắc. Không đồng nhất với thôi học đại học.",
                "non_causal_note": "Các khác biệt là quan sát trong từng nguồn, không chứng minh quan hệ nhân quả."}
    save_json(reports / "dashboard_metadata.json", metadata)
    return {"tables": tables, "serving_database_bytes": database.stat().st_size}
