from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CorpusRecord:
    text_id: str
    raw_text: str
    normalized_text: str
    language: str
    script: str
    source_type: str
    semantic_type: str
    prompt_style: str
    grapheme_count: int
    char_count: int
    word_count: int
    length_bucket: str
    version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanRecord:
    plan_id: str
    text_id: str
    render_route: str
    length_bucket: str
    layout_type: str
    style_family: str
    font_class: str
    degradation_profile: str
    split: str
    split_policy: str
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ManifestRecord:
    record_id: str
    run_id: str
    split: str
    text: dict[str, Any]
    groundtruth: dict[str, Any]
    image: dict[str, Any]
    generation: dict[str, Any]
    provenance: dict[str, Any]
    qc: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
