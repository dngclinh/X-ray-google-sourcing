"""Tests for src/xray/validator.py.

Covers every warning category the task requires, each with a positive
(issue fires) and negative (issue does not fire) case, plus the
error/warning severity distinction ("non-fatal unless structurally
invalid"). Uses the real assembler + glossary to produce realistic,
guaranteed-internally-consistent `QueryVariants` for the "healthy"
baseline and most negative cases; hand-built `QueryVariants` are used
only where a defect (duplicate clause, empty group, malformed string)
needs to be injected that the real assembler would never produce.
"""

from __future__ import annotations

import pytest

from src.xray.assembler import assemble
from src.xray.glossary import DEFAULT_KNOWLEDGE_DIR, Glossary
from src.xray.models import PrioritizedTerms, QueryVariants, SearchSpec
from src.xray.validator import ValidationResult, validate


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return Glossary.load(DEFAULT_KNOWLEDGE_DIR)


def _codes(result: ValidationResult) -> set[str]:
    return {issue.code for issue in result.issues}


def _healthy_spec(**overrides) -> SearchSpec:
    defaults: dict = dict(
        source="We are hiring a Backend Engineer with Python experience based in Germany.",
        titles=["Backend Engineer"],
        core_functions=["Backend Engineering"],
        industries=["Fintech"],
        skills=PrioritizedTerms(
            must=["Python", "Kubernetes"], important=["Docker"], nice_to_have=["Terraform"]
        ),
        locations=["Germany"],
        languages=PrioritizedTerms(must=["German"]),
        company_types=PrioritizedTerms(must=["Consultancy"]),
        job_family="Software Engineer",
    )
    defaults.update(overrides)
    return SearchSpec(**defaults)


def _assembled(spec: SearchSpec, glossary: Glossary) -> QueryVariants:
    return assemble(spec, glossary)


# ---------------------------------------------------------------------------
# missing title evidence
# ---------------------------------------------------------------------------


def test_missing_title_evidence_warns(glossary: Glossary):
    spec = _healthy_spec(titles=[])
    result = validate(spec, _assembled(spec, glossary))
    assert "missing_title_evidence" in _codes(result)


def test_title_evidence_present_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "missing_title_evidence" not in _codes(result)


# ---------------------------------------------------------------------------
# missing core-function/industry evidence
# ---------------------------------------------------------------------------


def test_missing_core_function_and_industry_evidence_warns(glossary: Glossary):
    spec = _healthy_spec(core_functions=[], industries=[])
    result = validate(spec, _assembled(spec, glossary))
    assert "missing_core_function_or_industry_evidence" in _codes(result)


def test_core_function_or_industry_evidence_present_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "missing_core_function_or_industry_evidence" not in _codes(result)


# ---------------------------------------------------------------------------
# no discriminating skill evidence
# ---------------------------------------------------------------------------


def test_no_discriminating_skill_evidence_warns(glossary: Glossary):
    spec = _healthy_spec(skills=PrioritizedTerms())
    result = validate(spec, _assembled(spec, glossary))
    assert "no_discriminating_skill_evidence" in _codes(result)


def test_skill_evidence_present_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "no_discriminating_skill_evidence" not in _codes(result)


# ---------------------------------------------------------------------------
# language cue found but no language extracted
# ---------------------------------------------------------------------------


def test_language_cue_without_extracted_language_warns(glossary: Glossary):
    spec = _healthy_spec(
        source="Fluent in Klingon is required for this role.",
        languages=PrioritizedTerms(),
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "language_cue_without_extracted_language" in _codes(result)


def test_language_cue_with_extracted_language_does_not_warn(glossary: Glossary):
    spec = _healthy_spec(
        source="Fluent in German is required for this role.",
        languages=PrioritizedTerms(must=["German"]),
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "language_cue_without_extracted_language" not in _codes(result)


def test_no_language_cue_and_no_language_does_not_warn(glossary: Glossary):
    spec = _healthy_spec(languages=PrioritizedTerms())
    result = validate(spec, _assembled(spec, glossary))
    assert "language_cue_without_extracted_language" not in _codes(result)


# ---------------------------------------------------------------------------
# ambiguous job family
# ---------------------------------------------------------------------------


def test_ambiguous_job_family_warns(glossary: Glossary):
    spec = _healthy_spec(
        job_family=None,
        warnings=["Ambiguous job family match between Nova Engineer, Terra Engineer."],
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "ambiguous_job_family" in _codes(result)


def test_resolved_job_family_does_not_warn_ambiguous(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "ambiguous_job_family" not in _codes(result)


# ---------------------------------------------------------------------------
# unsupported job family
# ---------------------------------------------------------------------------


def test_unsupported_job_family_warns(glossary: Glossary):
    spec = _healthy_spec(
        job_family=None,
        warnings=["No job family matched the job description."],
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "unsupported_job_family" in _codes(result)


def test_resolved_job_family_does_not_warn_unsupported(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "unsupported_job_family" not in _codes(result)


# ---------------------------------------------------------------------------
# location supplied but not represented
# ---------------------------------------------------------------------------


def test_location_not_represented_warns():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='site:linkedin.com/in/ ("Backend Engineer")',
        balanced='site:linkedin.com/in/ ("Backend Engineer")',
        broad='site:linkedin.com/in/ ("Backend Engineer")',
        hidden_titles="site:linkedin.com/in/ (Python)",
    )
    result = validate(spec, variants)
    assert "location_not_represented" in _codes(result)


def test_location_represented_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "location_not_represented" not in _codes(result)


# ---------------------------------------------------------------------------
# location terms incorrectly present in title/skill groups
# ---------------------------------------------------------------------------


def test_location_leakage_into_titles_warns(glossary: Glossary):
    spec = _healthy_spec(titles=["Germany"], locations=["Germany"])
    result = validate(spec, _assembled(spec, glossary))
    assert "location_leaked_into_non_location_group" in _codes(result)


def test_location_leakage_into_skills_warns(glossary: Glossary):
    spec = _healthy_spec(
        skills=PrioritizedTerms(must=["Germany"]),
        locations=["Germany"],
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "location_leaked_into_non_location_group" in _codes(result)


def test_no_location_leakage_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "location_leaked_into_non_location_group" not in _codes(result)


# ---------------------------------------------------------------------------
# duplicate groups
# ---------------------------------------------------------------------------


def test_duplicate_group_warns():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='site:linkedin.com/in/ (Python) AND (Python)',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "duplicate_group" in _codes(result)


def test_no_duplicate_groups_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "duplicate_group" not in _codes(result)


# ---------------------------------------------------------------------------
# empty Boolean groups
# ---------------------------------------------------------------------------


def test_empty_boolean_group_warns():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='site:linkedin.com/in/ () AND (Python)',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "empty_boolean_group" in _codes(result)


def test_no_empty_boolean_group_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "empty_boolean_group" not in _codes(result)


# ---------------------------------------------------------------------------
# Strict not narrower than Balanced
# ---------------------------------------------------------------------------


def test_strict_not_narrower_than_balanced_warns():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='site:linkedin.com/in/ (Python)',
        balanced='site:linkedin.com/in/ (Python) AND (Docker)',
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "strict_not_narrower_than_balanced" in _codes(result)


def test_strict_narrower_than_balanced_does_not_warn(glossary: Glossary):
    spec = _healthy_spec(
        skills=PrioritizedTerms(must=["Python", "Kubernetes"], important=["Docker"]),
        languages=PrioritizedTerms(must=["German"]),
        company_types=PrioritizedTerms(must=["Consultancy"]),
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "strict_not_narrower_than_balanced" not in _codes(result)


# ---------------------------------------------------------------------------
# Balanced not narrower than Broad
# ---------------------------------------------------------------------------


def test_balanced_not_narrower_than_broad_warns():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict="",
        balanced='site:linkedin.com/in/ (Python)',
        broad='site:linkedin.com/in/ (Python) AND (Docker)',
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "balanced_not_narrower_than_broad" in _codes(result)


def test_balanced_narrower_than_broad_does_not_warn(glossary: Glossary):
    spec = _healthy_spec(
        skills=PrioritizedTerms(must=["Python", "Kubernetes"], important=["Docker"]),
    )
    result = validate(spec, _assembled(spec, glossary))
    assert "balanced_not_narrower_than_broad" not in _codes(result)


# ---------------------------------------------------------------------------
# Hidden Titles too similar to Broad
# ---------------------------------------------------------------------------


def test_hidden_titles_too_similar_to_broad_warns(glossary: Glossary):
    # No skills at all: Hidden Titles' only clauses (evidence + location)
    # are also both present in Broad, so it adds nothing distinguishing.
    spec = _healthy_spec(skills=PrioritizedTerms())
    result = validate(spec, _assembled(spec, glossary))
    assert "hidden_titles_too_similar_to_broad" in _codes(result)


def test_hidden_titles_sufficiently_different_from_broad_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "hidden_titles_too_similar_to_broad" not in _codes(result)


# ---------------------------------------------------------------------------
# suspiciously long query
# ---------------------------------------------------------------------------


def test_suspiciously_long_query_warns():
    spec = _healthy_spec()
    long_clause = "X" * 600
    variants = QueryVariants(
        strict=f'site:linkedin.com/in/ ("{long_clause}")',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "suspiciously_long_query" in _codes(result)


def test_reasonably_sized_query_does_not_warn(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert "suspiciously_long_query" not in _codes(result)


# ---------------------------------------------------------------------------
# Structural validity (errors, not warnings) + non-fatal coexistence
# ---------------------------------------------------------------------------


def test_missing_source_prefix_is_structural_error():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='("Backend Engineer")',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "structurally_invalid_missing_source" in {i.code for i in result.errors}
    assert result.is_structurally_valid is False


def test_unbalanced_parentheses_is_structural_error():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='site:linkedin.com/in/ ("Backend Engineer"',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "structurally_invalid_unbalanced_parentheses" in {i.code for i in result.errors}
    assert result.is_structurally_valid is False


def test_dangling_operator_is_structural_error():
    spec = _healthy_spec()
    variants = QueryVariants(
        strict='site:linkedin.com/in/ ("Backend Engineer") AND',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)
    assert "structurally_invalid_dangling_operator" in {i.code for i in result.errors}
    assert result.is_structurally_valid is False


def test_healthy_query_has_no_errors(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    assert result.errors == ()
    assert result.is_structurally_valid is True


def test_warnings_remain_non_fatal_alongside_a_structural_error():
    # Missing titles (a warning) plus a missing source prefix (an error)
    # in the same result: the warning must still surface as a warning,
    # not be dropped or escalated because an error is also present.
    spec = _healthy_spec(titles=[])
    variants = QueryVariants(
        strict='("Backend Engineering")',
        balanced="",
        broad="",
        hidden_titles="",
    )
    result = validate(spec, variants)

    codes = _codes(result)
    assert "missing_title_evidence" in codes
    assert "structurally_invalid_missing_source" in codes
    assert "missing_title_evidence" in {i.code for i in result.warnings}
    assert "structurally_invalid_missing_source" in {i.code for i in result.errors}
    assert result.is_structurally_valid is False


# ---------------------------------------------------------------------------
# Does not create profession-specific rules / general sanity
# ---------------------------------------------------------------------------


def test_validate_returns_no_issues_for_a_fully_healthy_spec(glossary: Glossary):
    spec = _healthy_spec()
    result = validate(spec, _assembled(spec, glossary))
    # The rich, fully-populated healthy fixture should trip none of the
    # evidence-gap, leakage, duplicate/empty-group, or narrowing checks.
    assert result.issues == ()
