"""Tests for src/xray/normalizer.py.

Covers only generic, profession-agnostic text operations: whitespace
normalization, Unicode-safe casefold matching, phrase-boundary
matching, case-insensitive dedup, and Boolean-term quoting. No
knowledge/glossary lookups are tested here.
"""

from __future__ import annotations

from src.xray.normalizer import (
    casefold_key,
    contains_phrase,
    dedupe_preserve_order,
    normalize_whitespace,
    quote_boolean_term,
)


# ---------------------------------------------------------------------------
# normalize_whitespace
# ---------------------------------------------------------------------------


def test_normalize_whitespace_collapses_internal_runs():
    assert normalize_whitespace("Backend   Engineer\t\tRole") == "Backend Engineer Role"


def test_normalize_whitespace_collapses_newlines_and_tabs():
    assert normalize_whitespace("Munich\n\nGermany\t \t Team") == "Munich Germany Team"


def test_normalize_whitespace_strips_leading_and_trailing_space():
    assert normalize_whitespace("   Berlin   ") == "Berlin"


def test_normalize_whitespace_empty_string():
    assert normalize_whitespace("   \t\n  ") == ""


# ---------------------------------------------------------------------------
# casefold_key (Unicode-safe case-insensitive matching)
# ---------------------------------------------------------------------------


def test_casefold_key_ascii_case_insensitive():
    assert casefold_key("Germany") == casefold_key("GERMANY") == casefold_key("germany")


def test_casefold_key_munich_umlaut_case_insensitive():
    assert casefold_key("München") == casefold_key("MÜNCHEN") == casefold_key("münchen")


def test_casefold_key_normalizes_combining_vs_precomposed_unicode_forms():
    precomposed = "München"  # U+00DC precomposed Ü
    decomposed = "München"  # u + combining diaeresis
    assert precomposed != decomposed  # sanity check: differ as raw strings
    assert casefold_key(precomposed) == casefold_key(decomposed)


def test_casefold_key_normalizes_whitespace_too():
    assert casefold_key("New   York") == casefold_key("new york")


# ---------------------------------------------------------------------------
# contains_phrase (phrase-boundary matching)
# ---------------------------------------------------------------------------


def test_contains_phrase_matches_whole_word():
    assert contains_phrase("I work in Munich now", "Munich") is True


def test_contains_phrase_is_case_insensitive():
    assert contains_phrase("I WORK IN MUNICH NOW", "munich") is True


def test_contains_phrase_matches_unicode_alias():
    assert contains_phrase("Ich arbeite in München", "Munich") is False
    assert contains_phrase("Ich arbeite in München", "München") is True


def test_contains_phrase_does_not_match_substring_inside_larger_word():
    assert contains_phrase("This is a great program", "ram") is False


def test_contains_phrase_does_not_match_prefix_of_larger_word():
    assert contains_phrase("Newer York City", "New") is False


def test_contains_phrase_matches_multiword_phrase_with_flexible_spacing():
    assert contains_phrase("Relocation to New   York required", "New York") is True


def test_contains_phrase_empty_phrase_never_matches():
    assert contains_phrase("Munich", "") is False
    assert contains_phrase("Munich", "   ") is False


def test_contains_phrase_no_match_when_absent():
    assert contains_phrase("Berlin office", "Munich") is False


# ---------------------------------------------------------------------------
# dedupe_preserve_order (stable, case-insensitive dedup)
# ---------------------------------------------------------------------------


def test_dedupe_preserve_order_removes_case_variants():
    result = dedupe_preserve_order(["Python", "python", "PYTHON", "Java"])
    assert result == ["Python", "Java"]


def test_dedupe_preserve_order_keeps_first_occurrence_display_form():
    result = dedupe_preserve_order(["münchen", "München", "MÜNCHEN"])
    assert result == ["münchen"]


def test_dedupe_preserve_order_preserves_stable_order():
    result = dedupe_preserve_order(["Berlin", "Munich", "berlin", "Warsaw", "munich"])
    assert result == ["Berlin", "Munich", "Warsaw"]


def test_dedupe_preserve_order_empty_input():
    assert dedupe_preserve_order([]) == []


# ---------------------------------------------------------------------------
# quote_boolean_term (multi-word Boolean quoting)
# ---------------------------------------------------------------------------


def test_quote_boolean_term_quotes_multiword_term():
    assert quote_boolean_term("Machine Learning") == '"Machine Learning"'


def test_quote_boolean_term_leaves_single_word_unquoted():
    assert quote_boolean_term("Python") == "Python"


def test_quote_boolean_term_does_not_double_quote_already_quoted_term():
    assert quote_boolean_term('"Machine Learning"') == '"Machine Learning"'


def test_quote_boolean_term_normalizes_whitespace_before_quoting():
    assert quote_boolean_term("Machine   Learning") == '"Machine Learning"'
