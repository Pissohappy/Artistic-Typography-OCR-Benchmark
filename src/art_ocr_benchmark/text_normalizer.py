from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = _WS_RE.sub(" ", text)
    return text


def count_graphemes(text: str, language: str) -> int:
    # English-friendly approximation. Replace with language-aware grapheme segmenter in future.
    _ = language
    return len(text)
