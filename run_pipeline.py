from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.art_ocr_benchmark.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run artistic OCR benchmark data pipeline")
    parser.add_argument("--config", type=Path, default=Path("configs/pipeline_config.json"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    run_pipeline(args.config)


if __name__ == "__main__":
    main()
