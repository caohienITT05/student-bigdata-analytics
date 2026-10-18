"""Source field descriptions over the actual headers in the preparation manifest."""
import json

from fastapi import HTTPException
from multisource import store


def source_catalog():
    manifest = store.report("sources_manifest")
    if not manifest:
        raise HTTPException(503, "Chưa có danh mục nguồn. Cần chuẩn bị metadata dữ liệu trước.")
    dictionary = json.loads((store.ROOT / "config/data_dictionary.json").read_text(encoding="utf-8"))
    entries = {item["file"]: item for item in manifest.get("files", [])}
    sources = {source["key"]: {**source, "files": []} for source in dictionary["sources"]}
    for spec in dictionary["files"]:
        entry = entries.get(spec["path"])
        if not entry or not entry.get("csv"):
            raise HTTPException(503, "Metadata nguồn chưa đầy đủ: " + spec["path"])
        csv = entry["csv"]
        headers = csv["columns"]
        # Only columns actually present in this file are shown, including future
        # columns without a description. In particular Kaggle test has no Target.
        descriptions = {field["key"]: field for field in spec["fields"]}
        order = [key for key in descriptions if key in headers]
        order += [key for key in headers if key not in descriptions]
        fields = [descriptions.get(key, {"key": key, "label": key,
                  "type": "Chưa có chú giải", "group": "other"}) for key in order]
        sources[spec["source"]]["files"].append({
            "key": spec["key"], "name": spec["path"].rsplit("/", 1)[-1],
            "path": spec["path"], "rows": csv["rows"], "column_count": len(headers),
            "note": spec["note"], "fields": fields,
        })
    return {"sources": list(sources.values()), "groups": {**dictionary["groups"], "other": "Chưa phân nhóm"}}
