"""Answer-key text parser (ARCHITECTURE.md §5.3 answer-key preview/apply). Pure functions, no DB
access, so every accepted/rejected format can be unit-tested directly.

Accepted formats (all case-insensitive, A-D only):
    BCAD                    -- compact, no separators
    B C A D                 -- whitespace-separated
    B,C,A,D / B\nC\nA\nD    -- comma or newline separated
    1-B 2-C 3-A 4-D         -- numbered, "-" separator
    1)B 2)C ...              -- numbered, ")" separator
    1.B 2.C ...              -- numbered, "." separator
    1:B 2:C ...              -- numbered, ":" separator

Numbered answers must start at 1 and be consecutive with no gaps or duplicates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEPARATORS_RE = re.compile(r"[\s,;|/\\]+")
_NUMBERED_TOKEN_RE = re.compile(r"^(\d+)\s*[\-:.)]?\s*([A-D])$")


@dataclass
class AnswerKeyParseResult:
    letters: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.letters)


def parse_answer_key(raw: str) -> AnswerKeyParseResult:
    text = (raw or "").strip().upper()
    if not text:
        return AnswerKeyParseResult(errors=["مفتاح الإجابة فارغ"])

    tokens = [t for t in _SEPARATORS_RE.split(text) if t]

    # Try "numbered" mode first: every token must match "N<sep>Letter" for this to count.
    numbered: list[tuple[int, str]] = []
    all_numbered = bool(tokens)
    for tok in tokens:
        match = _NUMBERED_TOKEN_RE.match(tok)
        if match:
            numbered.append((int(match.group(1)), match.group(2)))
        else:
            all_numbered = False
            break

    if all_numbered and numbered:
        numbers = [n for n, _ in numbered]
        max_n = max(numbers)
        expected = set(range(1, max_n + 1))
        if len(set(numbers)) != len(numbers) or set(numbers) != expected:
            missing = sorted(expected - set(numbers))
            extra = sorted(n for n in numbers if n < 1)
            detail = f"أرقام الأسئلة يجب أن تبدأ من 1 وتكون متتالية بدون فجوات (سؤال رقم {max_n} هو الأكبر)"
            if missing:
                detail += f" — أرقام ناقصة: {', '.join(str(m) for m in missing)}"
            if extra:
                detail += " — أرقام غير صحيحة"
            return AnswerKeyParseResult(errors=[detail])
        by_number = dict(numbered)
        return AnswerKeyParseResult(letters=[by_number[i] for i in range(1, max_n + 1)])

    # Not numbered -> letters only, any mix of the supported separators (or none at all).
    compact = _SEPARATORS_RE.sub("", text)
    if compact and all(ch in "ABCD" for ch in compact):
        return AnswerKeyParseResult(letters=list(compact))

    return AnswerKeyParseResult(errors=["تعذر قراءة مفتاح الإجابة. استخدم صيغة مثل BCAD أو 1-B 2-C 3-A 4-D"])
