from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .io_utils import write_jsonl
from .length_buckets import LengthBucketStrategy
from .schemas import CorpusRecord
from .text_normalizer import count_graphemes, normalize_text


def build_corpus(raw_rows: Iterable[dict], out_path: Path, bucket_strategy: LengthBucketStrategy, language_default: str = "en") -> list[CorpusRecord]:
    seen: set[tuple[str, str]] = set()
    records: list[CorpusRecord] = []
    idx = 1
    for row in raw_rows:
        raw_text = row["raw_text"]
        language = row.get("language", language_default)
        normalized = normalize_text(raw_text)
        if not normalized:
            continue
        dedup_key = (language, normalized)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        grapheme_count = count_graphemes(normalized, language)
        word_count = len(normalized.split()) if normalized else 0
        char_count = len(normalized)

        record = CorpusRecord(
            text_id=f"TXT_{idx:06d}",
            raw_text=raw_text,
            normalized_text=normalized,
            language=language,
            script=row.get("script", "Latin"),
            source_type=row.get("source_type", "instruction_template"),
            semantic_type=row.get("semantic_type", "semantic"),
            prompt_style=row.get("prompt_style", "plain"),
            grapheme_count=grapheme_count,
            char_count=char_count,
            word_count=word_count,
            length_bucket=bucket_strategy.assign(grapheme_count),
            version="v1",
        )
        records.append(record)
        idx += 1

    write_jsonl(out_path, (r.to_dict() for r in records))
    return records
