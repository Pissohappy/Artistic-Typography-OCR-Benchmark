from __future__ import annotations

import random
from pathlib import Path

from .io_utils import write_jsonl
from .schemas import CorpusRecord, PlanRecord


def _split_for_text_id(text_id: str, split_ratios: dict[str, float]) -> str:
    # deterministic split by text_id hash
    val = (sum(ord(c) for c in text_id) % 10000) / 10000
    train_cut = split_ratios["train"]
    val_cut = train_cut + split_ratios["val"]
    if val < train_cut:
        return "train"
    if val < val_cut:
        return "val"
    return "test"


def _route_for_bucket(bucket: str) -> str:
    if bucket in {"LB_001_004", "LB_005_008", "LB_009_016"}:
        return "route_trdg_basic"
    if bucket in {"LB_017_032", "LB_033_064", "LB_065_128"}:
        return "route_synthtiger_multiline"
    return "route_synthtiger_svg_im"


def build_plans(corpus: list[CorpusRecord], out_path: Path, base_seed: int, split_ratios: dict[str, float]) -> list[PlanRecord]:
    plans: list[PlanRecord] = []
    for idx, rec in enumerate(corpus, start=1):
        split = _split_for_text_id(rec.text_id, split_ratios)
        route = _route_for_bucket(rec.length_bucket)
        rec_seed = base_seed + idx
        rng = random.Random(rec_seed)
        layout = "single_line" if route == "route_trdg_basic" else "multiline_block"
        if route == "route_synthtiger_svg_im":
            layout = "svg_artistic"
        style_family = rng.choice(["clean", "decorative", "poster", "graffiti"])
        font_class = rng.choice(["sans", "serif", "display", "handwritten"])
        degradation = rng.choice(["none", "blur_low", "jpeg_light", "noise_medium"])

        plans.append(
            PlanRecord(
                plan_id=f"PLAN_{idx:06d}",
                text_id=rec.text_id,
                render_route=route,
                length_bucket=rec.length_bucket,
                layout_type=layout,
                style_family=style_family,
                font_class=font_class,
                degradation_profile=degradation,
                split=split,
                split_policy="by_text_id_hash_v1",
                seed=rec_seed,
            )
        )
    write_jsonl(out_path, (p.to_dict() for p in plans))
    return plans
