# Artistic Typography OCR / VLM Benchmark Generator (Python 3.11)

一个可复现、可配置、可扩展的数据生成框架，用于将：

`raw corpus -> corpus_master_v1.jsonl -> plans_v1.jsonl -> rendered images -> all.jsonl (+ split manifests + QC)`

完整串联起来。

## 项目结构

```text
.
├── assets/
│   ├── backgrounds/
│   ├── fonts/
│   └── svg_templates/
├── configs/
│   └── pipeline_config.json
├── corpus/
│   ├── normalized/
│   │   └── corpus_master_v1.jsonl
│   ├── raw/
│   │   └── raw_input_v1.jsonl
│   └── splits/
│       └── plans_v1.jsonl
├── run_pipeline.py
├── runs/
│   └── run_0001/
│       ├── charboxes/
│       ├── images/
│       ├── manifests/
│       │   ├── all.jsonl
│       │   ├── test.jsonl
│       │   ├── train.jsonl
│       │   └── val.jsonl
│       ├── masks/
│       └── qc/
│           ├── failures.jsonl
│           └── qc_summary.json
├── scripts/
│   └── demo_run.sh
└── src/
    └── art_ocr_benchmark/
        ├── corpus_builder.py
        ├── io_utils.py
        ├── length_buckets.py
        ├── manifest_builder.py
        ├── pipeline.py
        ├── planner.py
        ├── qc.py
        ├── renderers.py
        ├── schemas.py
        └── text_normalizer.py
```

## 分层设计

1. **Corpus 层**：清洗、标准化、去重、统计、长度分桶，输出 `corpus_master_v1.jsonl`。  
2. **Length Bucket 层**：`LengthBucketStrategy` 独立模块，可替换策略版本。  
3. **Plan 层**：基于 `text_id` 先切 split，再做长度感知 route 分配，输出 `plans_v1.jsonl`。  
4. **Render Route 层**：统一 `Renderer` + route 适配器（当前为 mock/stub，可无外部依赖跑通）。  
5. **Output Manifest 层**：汇总 `all.jsonl` + `train/val/test.jsonl`。  
6. **QC 层**：生成 `failures.jsonl` 与 `qc_summary.json`。

## 渲染路线（当前可运行 mock）

- `route_trdg_basic`: 短文本、单行。
- `route_synthtiger_multiline`: 中长文本、多行。
- `route_synthtiger_svg_im`: 强风格 SVG + 后处理路线占位。

当前默认写入 `.ppm` 占位图，保证流程可跑。后续可在 `renderers.py` 的适配器中接入：

- TRDG
- SynthTIGER
- Inkscape
- ImageMagick

你只需替换：

- 配置对象
- 命令构造器
- 执行器逻辑（`CommandExecutor`）

## 快速开始

```bash
PYTHONPATH=src python run_pipeline.py --config configs/pipeline_config.json
```

或：

```bash
scripts/demo_run.sh
```

## 关键 schema

### CorpusRecord

- `text_id`, `raw_text`, `normalized_text`, `language`, `script`
- `source_type`, `semantic_type`, `prompt_style`
- `grapheme_count`, `char_count`, `word_count`, `length_bucket`, `version`

### PlanRecord

- `plan_id`, `text_id`, `render_route`, `length_bucket`
- `layout_type`, `style_family`, `font_class`, `degradation_profile`
- `split`, `split_policy`, `seed`

### ManifestRecord

- 顶层：`record_id`, `run_id`, `split`
- 子块：`text`, `groundtruth`, `image`, `generation`, `provenance`, `qc`

## QC 检查项

- 文本为空检查
- 图片路径缺失检查
- 图片尺寸异常检查
- 图片格式基础检查
- charboxes/mask 路径缺失检查（若 metadata 标注了路径）
- metadata 完整性基础检查
- split 泄漏检查（同 `text_id` 不可跨 split）

## 可扩展点

- 多语言 grapheme 计数：替换 `text_normalizer.count_graphemes`。
- 分桶策略版本化：新增 bucket strategy class。
- 更复杂计划策略：在 `planner.py` 中按 style/route/length 分层采样。
- 真实外部渲染接入：在 `renderers.py` route adapter 中新增命令执行分支。

## 说明

本仓库第一版以“架构与可复现链路”为优先；即使没有外部渲染引擎，也可生成可训练/可评测清单与可追溯 metadata。
