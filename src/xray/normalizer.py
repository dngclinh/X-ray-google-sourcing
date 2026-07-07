"""Generic text normalization utilities for the X-ray engine.

Pure, profession-agnostic string helpers shared by extraction and
glossary lookup: whitespace cleanup, Unicode-safe case folding,
phrase-boundary matching, case-insensitive dedup, and Boolean-term
quoting.

Per CLAUDE.md section 4 (category 1, generic deterministic logic), this
module must never encode profession-specific knowledge or semantic
inference — only structural, deterministic text operations. Term lists,
synonyms, and other knowledge belong in `knowledge/` and are consumed
through `src/xray/glossary.py`, not here.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse any run of whitespace to a single space and strip ends."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def casefold_key(text: str) -> str:
    """Unicode-safe key for case-insensitive comparison/matching.

    Applies NFKC normalization before casefolding so that different
    Unicode encodings of the same text (e.g. a precomposed accented
    letter vs. the equivalent base letter + combining mark) and
    different casings compare equal. Whitespace is also normalized so
    that incidental spacing differences don't affect the key.
    """
    normalized = unicodedata.normalize("NFKC", text)
    return normalize_whitespace(normalized).casefold()


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(normalize_whitespace(phrase))
    # Allow flexible internal whitespace (the escaped literal spaces
    # become "\ ") while keeping every other character literal.
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def contains_phrase(text: str, phrase: str) -> bool:
    """True if `phrase` occurs in `text` on whole phrase boundaries.

    Matching is Unicode-aware and case-insensitive (via NFKC + casefold
    on both sides), but a phrase never matches as a mere substring of a
    larger word — e.g. "ram" does not match inside "program". An empty
    phrase never matches.
    """
    if not phrase.strip():
        return False
    return _phrase_pattern(casefold_key(phrase)).search(casefold_key(text)) is not None


def dedupe_preserve_order(terms: Iterable[str]) -> list[str]:
    """Case-insensitive, Unicode-safe dedup that keeps original display terms.

    The first occurrence of each term (by `casefold_key`) is kept in its
    original display form; later occurrences that only differ in case or
    Unicode form are dropped. Relative order of first appearance is
    preserved (stable dedup).
    """
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        key = casefold_key(term)
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result


def quote_boolean_term(term: str) -> str:
    """Wrap a multi-word Boolean term in double quotes for X-ray syntax.

    Whitespace is normalized first. Single-word terms are returned
    unquoted. A term already fully wrapped in double quotes is returned
    unchanged rather than being quoted again.
    """
    normalized = normalize_whitespace(term)
    if len(normalized) >= 2 and normalized.startswith('"') and normalized.endswith('"'):
        return normalized
    if " " in normalized:
        return f'"{normalized}"'
    return normalized
