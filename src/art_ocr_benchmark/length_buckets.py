from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LengthBucketRule:
    name: str
    min_len: int
    max_len: int


DEFAULT_BUCKETS: tuple[LengthBucketRule, ...] = (
    LengthBucketRule("LB_001_004", 1, 4),
    LengthBucketRule("LB_005_008", 5, 8),
    LengthBucketRule("LB_009_016", 9, 16),
    LengthBucketRule("LB_017_032", 17, 32),
    LengthBucketRule("LB_033_064", 33, 64),
    LengthBucketRule("LB_065_128", 65, 128),
    LengthBucketRule("LB_129_256", 129, 256),
    LengthBucketRule("LB_257_500", 257, 500),
)


class LengthBucketStrategy:
    def __init__(self, rules: tuple[LengthBucketRule, ...] = DEFAULT_BUCKETS, version: str = "v1"):
        self.rules = rules
        self.version = version

    def assign(self, grapheme_count: int) -> str:
        for rule in self.rules:
            if rule.min_len <= grapheme_count <= rule.max_len:
                return rule.name
        return "LB_OOB"
