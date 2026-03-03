from __future__ import annotations

import json
import re
import struct
from collections import defaultdict
from pathlib import Path

from .io_utils import write_jsonl


def _svg_dimensions(path: Path) -> tuple[int, int] | None:
    content = path.read_text(encoding="utf-8", errors="ignore")
    m_w = re.search(r'width="(\d+)', content)
    m_h = re.search(r'height="(\d+)', content)
    if not m_w or not m_h:
        return None
    return int(m_w.group(1)), int(m_h.group(1))


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        ihdr_len = f.read(4)
        chunk_type = f.read(4)
        if chunk_type != b"IHDR":
            return None
        data = f.read(13)
        width, height = struct.unpack(">II", data[:8])
        _ = ihdr_len
        return width, height


def _image_dimensions(path: Path) -> tuple[int, int] | None:
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return _svg_dimensions(path)
    if suffix == ".png":
        return _png_dimensions(path)
    return None


def _blank_check(path: Path) -> bool:
    if path.suffix.lower() == ".svg":
        content = path.read_text(encoding="utf-8", errors="ignore")
        return "<text" not in content
    return False


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
            dims = _image_dimensions(img_path)
            if dims is None:
                flags.append("invalid_image_format")
            else:
                w, h = dims
                if w < 32 or h < 32 or w > 4096 or h > 4096:
                    flags.append("abnormal_dimensions")
            if _blank_check(img_path):
                flags.append("blank_image")

        for field in ("charboxes_path", "mask_path"):
            p = row.get("groundtruth", {}).get(field)
            if p and not (run_dir / p).exists():
                flags.append(f"missing_{field}")

        generation = row.get("generation", {})
        required_generation = ["render_route", "engine_primary", "seed", "layout_type"]
        missing = [k for k in required_generation if generation.get(k) in (None, "")]
        if missing:
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
