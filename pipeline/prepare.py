"""Verify and arrange explicitly configured inputs; never search other folders."""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ("dataset.csv", "mysql_demographics.csv", "mongodb_behaviors.json", "flat_grades.csv", "final_dataset.csv", "student_predictions.csv", "best_student_model.pkl", "label_encoder.pkl", "split_data.py", "import_data.py", "etl_pipeline.py", "train_models.py", "eda_analysis.py", "docker-compose.yml")


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes project: {relative}")
    return path


def csv_metadata(path):
    # Streaming only: no Pandas, no complete CSV held in memory.
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(8192)
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        stream.seek(0)
        reader = csv.reader(stream, delimiter=delimiter)
        columns = next(reader)
        count = 0
        malformed = 0
        for row in reader:
            count += 1
            malformed += len(row) != len(columns)
    return {"encoding": "utf-8-sig", "delimiter": delimiter, "rows": count, "column_count": len(columns), "columns": columns, "malformed_width_rows": malformed}


def transfer(root, incoming, destination, move):
    source, target = inside(root, incoming), inside(root, destination)
    if not source.exists() and not target.exists():
        raise FileNotFoundError(f"Required input not found: {incoming} or {destination}")
    before = checksum(source if source.exists() else target)
    if target.exists():
        if checksum(target) != before:
            raise ValueError(f"Different content already exists at {destination}; refusing overwrite")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if checksum(target) != before:
        raise ValueError(f"Copy verification failed: {destination}")
    if move and source.exists() and source != target:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", incoming], cwd=root, capture_output=True).returncode == 0
        if tracked:
            raise ValueError(f"Tracked input requires reference audit before moving: {incoming}")
        source.unlink()  # Only the named, checksum-verified incoming file.
    return before


def prepare(root=ROOT):
    root = root.resolve()
    config = json.loads((root / "config/data_sources.json").read_text(encoding="utf-8-sig"))
    report_dir = inside(root, config["paths"]["reports"])
    for relative in config["paths"].values():
        inside(root, relative).mkdir(parents=True, exist_ok=True)
    manifest_path = report_dir / "sources_manifest.json"
    prior = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    rows = []
    targets = [(s["incoming"], s["file"], s["move"], s["name"]) for s in config["sources"]]
    oulad = config["oulad"]
    targets += [(f"{oulad['incoming']}/{f}", f"{oulad['directory']}/{f}", True, "oulad") for f in oulad["files"]]
    old_entries = {row["file"]: row for row in prior.get("files", [])}
    for incoming, destination, move, name in targets:
        verified = transfer(root, incoming, destination, move)
        old = old_entries.get(destination)
        metadata = old.get("csv") if old and old["sha256"] == verified["sha256"] else None
        if destination.endswith(".csv") and metadata is None:
            metadata = csv_metadata(inside(root, destination))
        rows.append({"source": name, "file": destination, **verified, "csv": metadata})
    incoming_dir = inside(root, oulad["incoming"])
    if incoming_dir.exists() and not any(incoming_dir.iterdir()):
        incoming_dir.rmdir()  # Never recursive: only an actually empty directory.
    protected = {file: checksum(inside(root, file)) for file in LEGACY}
    if prior.get("legacy") and protected != prior["legacy"]:
        raise ValueError("Legacy artifact changed since preparation; inspect before continuing")
    content = {"prepared_at": datetime.now(timezone.utc).isoformat(), "files": rows, "legacy": protected,
               "policy": "Copies/checksums verified. Original root dataset and legacy artifacts preserved. No imports or training executed."}
    if rows == prior.get("files") and protected == prior.get("legacy"):
        content["prepared_at"] = prior["prepared_at"]
    manifest_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"inputs": [{"file": r["file"], "rows": r["csv"]["rows"] if r["csv"] else None} for r in rows], "manifest": str(manifest_path)}, ensure_ascii=False))
    return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    prepare(args.root)
