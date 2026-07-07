"""Deterministic validation of `SearchSpec` and `QueryVariants`.

Runs a fixed set of generic, structural checks over an already-produced
`(SearchSpec, QueryVariants)` pair — evidence gaps, cross-field leakage,
duplicate/empty Boolean groups, variant-narrowing relationships, and
gross structural malformation — and reports them as a flat list of
typed `ValidationIssue`s.

Per the task's rule, every issue is a non-fatal `"warning"` unless the
assembled Boolean string is itself structurally broken (missing its
`site:` prefix, unbalanced parentheses, or a dangling trailing Boolean
operator), which is reported as `"error"`. Errors and warnings are
independent: an error never suppresses or upgrades an unrelated
warning, and a warning never blocks validation from completing
(CLAUDE.md's general "state limitations plainly, don't fail silently"
posture, applied to review rather than extraction).

This module contains no profession-specific rules — every check is
generic across job families, reusable regardless of which knowledge
pack (if any) produced the input. It does not re-run extraction,
family detection, or query assembly; it only reads what it's given.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.xray.models import QueryVariants, SearchSpec

#: A query longer than this is "suspiciously long" — past the point
#: where LinkedIn/Google search boxes realistically stay usable.
MAX_REASONABLE_QUERY_LENGTH = 500

#: Generic (non-profession-specific) structural signals that a JD is
#: describing a language-proficiency requirement — CEFR level codes,
#: plus a small fixed set of English proficiency/label phrases mirroring
#: the ones `extractor.py` uses to *confirm* a language match. Here they
#: instead flag the case where such a cue exists but nothing was
#: confirmed, e.g. because the paired language name wasn't recognized.
_CEFR_LEVEL_RE = re.compile(r"(?i)\b[ABC][12]\b")
_LANGUAGE_CUE_SUBSTRINGS = (
    "fluent in",
    "fluency in",
    "proficient in",
    "proficiency in",
    "native speaker of",
    "working knowledge of",
    "-speaking",
    "language requirements",
    "language skills",
)

_SOURCE_PREFIX_RE = re.compile(r"^site:\S+\s*")


@dataclass(frozen=True)
class ValidationIssue:
    """One validation finding.

    `variant` names which of strict/balanced/broad/hidden_titles the
    issue concerns, or is `None` for a `SearchSpec`-level or cross-
    variant issue.
    """

    code: str
    message: str
    severity: str = "warning"  # "warning" | "error"
    variant: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def is_structurally_valid(self) -> bool:
        """False only when a structurally-fatal issue (an error) is present."""
        return not self.errors


def _iter_variants(variants: QueryVariants) -> list[tuple[str, str]]:
    return [
        ("strict", variants.strict),
        ("balanced", variants.balanced),
        ("broad", variants.broad),
        ("hidden_titles", variants.hidden_titles),
    ]


def _extract_clauses(variant: str) -> list[str]:
    """Split an assembled query into its top-level `AND`-joined clauses.

    Strips the leading `site:...` source prefix first, so a bare source
    with no real clauses correctly yields `[]` rather than a single
    spurious "clause" consisting of just the source.
    """
    if not variant:
        return []
    body = _SOURCE_PREFIX_RE.sub("", variant, count=1)
    if not body:
        return []
    return [clause.strip() for clause in body.split(" AND ") if clause.strip()]


def _term_in_text(term: str, text: str) -> bool:
    return term in text or f'"{term}"' in text


# ---------------------------------------------------------------------------
# SearchSpec-level checks
# ---------------------------------------------------------------------------


def _check_missing_title_evidence(spec: SearchSpec) -> list[ValidationIssue]:
    if spec.titles:
        return []
    return [
        ValidationIssue(
            code="missing_title_evidence",
            message="No target title evidence was extracted.",
        )
    ]


def _check_missing_core_function_or_industry_evidence(spec: SearchSpec) -> list[ValidationIssue]:
    if spec.core_functions or spec.industries:
        return []
    return [
        ValidationIssue(
            code="missing_core_function_or_industry_evidence",
            message="No core-function or industry evidence was extracted.",
        )
    ]


def _check_no_discriminating_skill_evidence(spec: SearchSpec) -> list[ValidationIssue]:
    if spec.skills.must or spec.skills.important or spec.skills.nice_to_have:
        return []
    return [
        ValidationIssue(
            code="no_discriminating_skill_evidence",
            message="No skill evidence was extracted to discriminate candidates.",
        )
    ]


def _has_language_cue(source: str) -> bool:
    if _CEFR_LEVEL_RE.search(source):
        return True
    lowered = source.lower()
    return any(cue in lowered for cue in _LANGUAGE_CUE_SUBSTRINGS)


def _check_language_cue_without_language(spec: SearchSpec) -> list[ValidationIssue]:
    if not _has_language_cue(spec.source):
        return []
    if spec.languages.must or spec.languages.important or spec.languages.nice_to_have:
        return []
    return [
        ValidationIssue(
            code="language_cue_without_extracted_language",
            message=(
                "A language-proficiency cue was found in the source JD, but no "
                "language requirement was extracted."
            ),
        )
    ]


def _check_ambiguous_job_family(spec: SearchSpec) -> list[ValidationIssue]:
    if spec.job_family is not None:
        return []
    if any("ambiguous" in warning.lower() for warning in spec.warnings):
        return [
            ValidationIssue(
                code="ambiguous_job_family",
                message="Job family detection was ambiguous; no family was selected.",
            )
        ]
    return []


def _check_unsupported_job_family(spec: SearchSpec) -> list[ValidationIssue]:
    if spec.job_family is not None:
        return []
    if any("no job family matched" in warning.lower() for warning in spec.warnings):
        return [
            ValidationIssue(
                code="unsupported_job_family",
                message="No supported job family matched this job description.",
            )
        ]
    return []


def _check_location_supplied_but_not_represented(
    spec: SearchSpec, variants: QueryVariants
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for name, text in _iter_variants(variants):
        for location in spec.locations:
            if not _term_in_text(location, text):
                issues.append(
                    ValidationIssue(
                        code="location_not_represented",
                        message=(
                            f"Location {location!r} was supplied but does not appear "
                            f"in the {name} query."
                        ),
                        variant=name,
                    )
                )
    return issues


def _check_location_leakage(spec: SearchSpec) -> list[ValidationIssue]:
    location_keys = {term.casefold() for term in spec.locations}
    if not location_keys:
        return []
    issues: list[ValidationIssue] = []
    for group_name, terms in (
        ("titles", spec.titles),
        ("skills.must", spec.skills.must),
        ("skills.important", spec.skills.important),
        ("skills.nice_to_have", spec.skills.nice_to_have),
    ):
        for term in terms:
            if term.casefold() in location_keys:
                issues.append(
                    ValidationIssue(
                        code="location_leaked_into_non_location_group",
                        message=(
                            f"Location term {term!r} incorrectly appears in the "
                            f"{group_name} group."
                        ),
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# Per-variant QueryVariants checks
# ---------------------------------------------------------------------------


def _check_structural_validity(name: str, text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not text.startswith("site:"):
        issues.append(
            ValidationIssue(
                code="structurally_invalid_missing_source",
                message=f"{name}: query does not start with a 'site:' source prefix.",
                severity="error",
                variant=name,
            )
        )
    if text.count("(") != text.count(")"):
        issues.append(
            ValidationIssue(
                code="structurally_invalid_unbalanced_parentheses",
                message=f"{name}: unbalanced parentheses in the assembled query.",
                severity="error",
                variant=name,
            )
        )
    if text.rstrip().endswith(("AND", "OR", "NOT")):
        issues.append(
            ValidationIssue(
                code="structurally_invalid_dangling_operator",
                message=f"{name}: query ends with a dangling Boolean operator.",
                severity="error",
                variant=name,
            )
        )
    return issues


def _check_duplicate_groups(name: str, text: str) -> list[ValidationIssue]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for clause in _extract_clauses(text):
        if clause in seen and clause not in duplicates:
            duplicates.append(clause)
        seen.add(clause)
    return [
        ValidationIssue(
            code="duplicate_group",
            message=f"{name}: duplicate Boolean group {clause!r} appears more than once.",
            variant=name,
        )
        for clause in duplicates
    ]


def _check_empty_groups(name: str, text: str) -> list[ValidationIssue]:
    if "()" not in text:
        return []
    return [
        ValidationIssue(
            code="empty_boolean_group",
            message=f"{name}: query contains an empty Boolean group '()'.",
            variant=name,
        )
    ]


def _check_suspiciously_long(name: str, text: str) -> list[ValidationIssue]:
    if len(text) <= MAX_REASONABLE_QUERY_LENGTH:
        return []
    return [
        ValidationIssue(
            code="suspiciously_long_query",
            message=(
                f"{name}: query is {len(text)} characters, exceeding the "
                f"{MAX_REASONABLE_QUERY_LENGTH}-character guideline."
            ),
            variant=name,
        )
    ]


# ---------------------------------------------------------------------------
# Cross-variant checks
# ---------------------------------------------------------------------------


def _check_strict_narrower_than_balanced(variants: QueryVariants) -> list[ValidationIssue]:
    strict_n = len(_extract_clauses(variants.strict))
    balanced_n = len(_extract_clauses(variants.balanced))
    if strict_n > balanced_n:
        return []
    return [
        ValidationIssue(
            code="strict_not_narrower_than_balanced",
            message=(
                f"Strict ({strict_n} clause(s)) is not narrower than Balanced "
                f"({balanced_n} clause(s))."
            ),
        )
    ]


def _check_balanced_narrower_than_broad(variants: QueryVariants) -> list[ValidationIssue]:
    balanced_n = len(_extract_clauses(variants.balanced))
    broad_n = len(_extract_clauses(variants.broad))
    if balanced_n > broad_n:
        return []
    return [
        ValidationIssue(
            code="balanced_not_narrower_than_broad",
            message=(
                f"Balanced ({balanced_n} clause(s)) is not narrower than Broad "
                f"({broad_n} clause(s))."
            ),
        )
    ]


def _check_hidden_titles_too_similar_to_broad(variants: QueryVariants) -> list[ValidationIssue]:
    hidden_clauses = set(_extract_clauses(variants.hidden_titles))
    broad_clauses = set(_extract_clauses(variants.broad))
    if not hidden_clauses or not hidden_clauses.issubset(broad_clauses):
        return []
    return [
        ValidationIssue(
            code="hidden_titles_too_similar_to_broad",
            message="Hidden Titles contributes no clause that isn't already present in Broad.",
        )
    ]


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def validate(spec: SearchSpec, variants: QueryVariants) -> ValidationResult:
    """Validate a `SearchSpec`/`QueryVariants` pair and return every finding.

    All checks always run — an error from one check never prevents
    other checks (warnings or errors) from also being reported.
    """
    issues: list[ValidationIssue] = []

    issues.extend(_check_missing_title_evidence(spec))
    issues.extend(_check_missing_core_function_or_industry_evidence(spec))
    issues.extend(_check_no_discriminating_skill_evidence(spec))
    issues.extend(_check_language_cue_without_language(spec))
    issues.extend(_check_ambiguous_job_family(spec))
    issues.extend(_check_unsupported_job_family(spec))
    issues.extend(_check_location_supplied_but_not_represented(spec, variants))
    issues.extend(_check_location_leakage(spec))

    for name, text in _iter_variants(variants):
        issues.extend(_check_structural_validity(name, text))
        issues.extend(_check_duplicate_groups(name, text))
        issues.extend(_check_empty_groups(name, text))
        issues.extend(_check_suspiciously_long(name, text))

    issues.extend(_check_strict_narrower_than_balanced(variants))
    issues.extend(_check_balanced_narrower_than_broad(variants))
    issues.extend(_check_hidden_titles_too_similar_to_broad(variants))

    return ValidationResult(issues=tuple(issues))
