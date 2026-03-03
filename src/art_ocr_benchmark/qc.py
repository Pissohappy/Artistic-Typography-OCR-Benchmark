from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .io_utils import write_jsonl


def _parse_ppm_dimensions(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="ascii") as f:
        magic = f.readline().strip()
        if magic != "P3":
            return None
        dims = f.readline().strip().split()
        if len(dims) != 2:
            return None
        return int(dims[0]), int(dims[1])


def run_qc(manifest_rows: list[dict], run_dir: Path) -> tuple[list[dict], dict]:
    failures: list[dict] = []
    text_to_split: dict[str, set[str]] = defaultdict(set)

    for row in manifest_rows:
        flags: list[str] = []
        text = row.get("text", {})
        image = row.get("image", {})
        if not text.get("normalized_text"):
            flags.append("empty_text")

        img_path = run_dir / image.get("image_relpath", "")
        if not img_path.exists():
            flags.append("missing_image_path")
        else:
            dims = _parse_ppm_dimensions(img_path)
            if dims is None:
                flags.append("invalid_image_format")
            else:
                w, h = dims
                if w < 32 or h < 32 or w > 4096 or h > 4096:
                    flags.append("abnormal_dimensions")

        required_paths = [
            ("charboxes_path", run_dir / "charboxes"),
            ("mask_path", run_dir / "masks"),
        ]
        for field, _default_dir in required_paths:
            p = row.get("groundtruth", {}).get(field)
            if p and not (run_dir / p).exists():
                flags.append(f"missing_{field}")

        if not row.get("generation", {}).get("render_route"):
            flags.append("missing_metadata_generation")

        text_id = text.get("text_id")
        split = row.get("split")
        if text_id and split:
            text_to_split[text_id].add(split)

        row.setdefault("qc", {})
        row["qc"]["flags"] = flags
        row["qc"]["is_valid"] = len(flags) == 0
        row["qc"].setdefault("ocr_backread_score", None)
        if flags:
            failures.append({"record_id": row.get("record_id"), "flags": flags})

    leak_count = 0
    for text_id, splits in text_to_split.items():
        if len(splits) > 1:
            leak_count += 1
            failures.append({"record_id": f"text_id::{text_id}", "flags": ["split_leak"]})

    summary = {
        "total_records": len(manifest_rows),
        "valid_records": sum(1 for r in manifest_rows if r.get("qc", {}).get("is_valid")),
        "invalid_records": sum(1 for r in manifest_rows if not r.get("qc", {}).get("is_valid")),
        "split_leak_text_ids": leak_count,
    }

    qc_dir = run_dir / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(qc_dir / "failures.jsonl", failures)
    with (qc_dir / "qc_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return failures, summary
