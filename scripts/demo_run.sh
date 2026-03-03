#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src python run_pipeline.py --config configs/pipeline_config.json
