"""Arabic-aware search normalisation (ARCHITECTURE.md §2: 'أ/إ/آ→ا, ة→ه, ى→ي, diacritics removed,
lower-cased'). Applied when writing *_search columns; the same function normalises the query term
before the trigram search, so 'احمد' and 'أحمد' match each other.
"""

from __future__ import annotations

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")
_NORMALIZE_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})


def normalize_search_text(value: str) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = _ARABIC_DIACRITICS.sub("", value)
    value = value.translate(_NORMALIZE_MAP)
    return value.strip().lower()
