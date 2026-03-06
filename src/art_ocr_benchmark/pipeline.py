from __future__ import annotations

import logging
from pathlib import Path

from .corpus_builder import build_corpus
from .io_utils import read_json, read_jsonl, write_jsonl
from .length_buckets import LengthBucketStrategy
from .manifest_builder import build_manifest
from .planner import build_plans
from .qc import run_qc
from .renderers import CommandExecutor, build_renderer

logger = logging.getLogger(__name__)


def run_pipeline(config_path: Path) -> None:
    config = read_json(config_path)
    run_dir = Path(config["paths"]["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_path = Path(config["paths"]["raw_corpus"])
    corpus_out = Path(config["paths"]["corpus_master"])
    plans_out = Path(config["paths"]["plans"])

    raw_rows = read_jsonl(raw_path)
    logger.info("Loaded raw rows: %d", len(raw_rows))

    bucket_strategy = LengthBucketStrategy()
    corpus_records = build_corpus(raw_rows, corpus_out, bucket_strategy)
    logger.info("Corpus normalized records: %d", len(corpus_records))

    plans = build_plans(
        corpus_records,
        plans_out,
        base_seed=config["seed"],
        split_ratios=config["splits"],
    )
    logger.info("Plans generated: %d", len(plans))

    executor = CommandExecutor()
    render_outputs: dict[str, dict] = {}
    for p in plans:
        text = next(c for c in corpus_records if c.text_id == p.text_id)
        renderer = build_renderer(p.render_route, executor)
        result = renderer.render(
            text=text.normalized_text,
            out_dir=run_dir,
            filename_stem=p.plan_id.lower(),
            seed=p.seed,
            layout_type=p.layout_type,
            style_family=p.style_family,
            font_class=p.font_class,
            degradation_profile=p.degradation_profile,
            language=text.language,
        )
        render_outputs[p.plan_id] = result.__dict__

    manifest_rows = build_manifest(
        corpus=corpus_records,
        plans=plans,
        render_outputs=render_outputs,
        run_id=config["run_id"],
        run_dir=run_dir,
        config_version=config.get("config_version", "v1"),
    )

    failures, summary = run_qc(manifest_rows, run_dir)
    write_jsonl(run_dir / "manifests" / "all.jsonl", manifest_rows)
    logger.info("QC done. failures=%d summary=%s", len(failures), summary)
