from __future__ import annotations

from pathlib import Path

from .io_utils import write_jsonl
from .schemas import CorpusRecord, ManifestRecord, PlanRecord


def build_manifest(*, corpus: list[CorpusRecord], plans: list[PlanRecord], render_outputs: dict[str, dict], run_id: str, run_dir: Path, config_version: str = "v1") -> list[dict]:
    text_index = {r.text_id: r for r in corpus}
    rows: list[dict] = []
    for idx, plan in enumerate(plans, start=1):
        text = text_index[plan.text_id]
        render = render_outputs[plan.plan_id]

        record = ManifestRecord(
            record_id=f"REC_{idx:06d}",
            run_id=run_id,
            split=plan.split,
            text={
                "text_id": text.text_id,
                "raw_text": text.raw_text,
                "normalized_text": text.normalized_text,
                "language": text.language,
                "source_type": text.source_type,
                "semantic_type": text.semantic_type,
                "grapheme_count": text.grapheme_count,
                "word_count": text.word_count,
                "length_bucket": text.length_bucket,
            },
            groundtruth={
                "gt_text_exact": text.raw_text,
                "gt_text_normalized": text.normalized_text,
                "task_type": "ocr",
                "charboxes_path": None,
                "mask_path": None,
            },
            image={
                "image_relpath": render["image_relpath"],
                "width": render["width"],
                "height": render["height"],
                "format": render["format"],
                "background_type": render["background_type"],
            },
            generation={
                "render_route": plan.render_route,
                "engine_primary": render["engine_primary"],
                "engine_secondary": render["engine_secondary"],
                "seed": plan.seed,
                "template_id": render["template_id"],
                "font_id": render["font_id"],
                "font_class": plan.font_class,
                "layout_type": plan.layout_type,
                "layout_meta": render["layout_meta"],
                "style_meta": render["style_meta"],
                "degradation_meta": render["degradation_meta"],
            },
            provenance={
                "config_version": config_version,
                "route_version": "v1",
                "template_version": "v1",
                "normalization_version": "v1",
            },
            qc={"is_valid": True, "flags": [], "ocr_backread_score": None},
        )
        rows.append(record.to_dict())

    manifests_dir = run_dir / "manifests"
    write_jsonl(manifests_dir / "all.jsonl", rows)
    for split in ("train", "val", "test"):
        write_jsonl(manifests_dir / f"{split}.jsonl", (r for r in rows if r["split"] == split))
    return rows
