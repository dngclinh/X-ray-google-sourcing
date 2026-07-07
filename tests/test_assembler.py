"""Tests for src/xray/assembler.py.

Covers deterministic Boolean query assembly against the real,
checked-in generic glossary (needed for LinkedIn `site:` source
resolution). Does not test extraction or family detection — inputs are
hand-built `SearchSpec` instances.
"""

from __future__ import annotations

import pytest

from src.xray.assembler import assemble
from src.xray.glossary import DEFAULT_KNOWLEDGE_DIR, Glossary
from src.xray.models import PrioritizedTerms, QueryVariants, SearchSpec


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return Glossary.load(DEFAULT_KNOWLEDGE_DIR)


def _and_clause_count(query: str) -> int:
    return query.count(" AND ") + 1 if query else 0


def _rich_spec() -> SearchSpec:
    return SearchSpec(
        titles=["Backend Engineer", "Software Engineer"],
        core_functions=["Backend Engineering"],
        industries=["Fintech"],
        skills=PrioritizedTerms(
            must=["Python", "Kubernetes"],
            important=["Docker"],
            nice_to_have=["Terraform"],
        ),
        locations=["Germany"],
        languages=PrioritizedTerms(must=["German"]),
        company_types=PrioritizedTerms(must=["Consultancy"]),
        exclusions=["Recruiter"],
        confidence={"core_functions": 0.8, "industries": 0.3},
    )


# ---------------------------------------------------------------------------
# Strict is narrower than Balanced; Balanced is narrower than Broad
# ---------------------------------------------------------------------------


def test_strict_is_narrower_than_balanced(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    assert _and_clause_count(variants.strict) > _and_clause_count(variants.balanced)


def test_balanced_is_narrower_than_broad(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    assert _and_clause_count(variants.balanced) > _and_clause_count(variants.broad)


def test_strict_includes_mandatory_language_and_company_type_but_others_dont(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    assert "(German)" in variants.strict
    assert "(Consultancy)" in variants.strict
    assert "(German)" not in variants.balanced
    assert "(Consultancy)" not in variants.balanced
    assert "(German)" not in variants.broad
    assert "(Consultancy)" not in variants.broad
    assert "(German)" not in variants.hidden_titles
    assert "(Consultancy)" not in variants.hidden_titles


def test_broad_drops_skill_filtering_entirely(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    assert "Python" not in variants.broad
    assert "Kubernetes" not in variants.broad
    assert "Docker" not in variants.broad


# ---------------------------------------------------------------------------
# Hidden Titles differs meaningfully from Broad
# ---------------------------------------------------------------------------


def test_hidden_titles_omits_title_clause_that_broad_has(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    title_clause = '"Backend Engineer" OR "Software Engineer"'
    assert title_clause in variants.broad
    assert title_clause not in variants.hidden_titles
    assert '"Backend Engineer"' not in variants.hidden_titles
    assert '"Software Engineer"' not in variants.hidden_titles


def test_hidden_titles_adds_skill_evidence_that_broad_lacks(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    assert "Python" in variants.hidden_titles
    assert "Kubernetes" in variants.hidden_titles
    assert "Docker" in variants.hidden_titles
    assert "Terraform" in variants.hidden_titles
    # Confirmed absent from Broad by test_broad_drops_skill_filtering_entirely.


def test_hidden_titles_and_broad_both_carry_evidence_and_location(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    for variant in (variants.broad, variants.hidden_titles):
        assert "Backend Engineering" in variant or "Fintech" in variant
        assert "Germany" in variant


# ---------------------------------------------------------------------------
# ccTLD does not remove location
# ---------------------------------------------------------------------------


def test_cctld_source_still_preserves_location_block(glossary: Glossary):
    spec = SearchSpec(titles=["Backend Engineer"], locations=["Germany"])
    variants = assemble(spec, glossary)

    for variant in (variants.strict, variants.balanced, variants.broad, variants.hidden_titles):
        assert variant.startswith("site:de.linkedin.com/in/")
        assert "Germany" in variant


def test_global_source_when_no_single_verified_country(glossary: Glossary):
    spec = SearchSpec(titles=["Backend Engineer"], locations=["Germany", "Poland"])
    variants = assemble(spec, glossary)

    for variant in (variants.strict, variants.balanced, variants.broad, variants.hidden_titles):
        assert variant.startswith("site:linkedin.com/in/")
        assert not variant.startswith("site:de.linkedin.com")
        assert "Germany" in variant
        assert "Poland" in variant


def test_source_remains_first(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    for variant in (variants.strict, variants.balanced, variants.broad, variants.hidden_titles):
        assert variant.startswith("site:de.linkedin.com/in/")


# ---------------------------------------------------------------------------
# No duplicates or empty groups
# ---------------------------------------------------------------------------


def test_no_empty_parentheses_when_evidence_is_missing(glossary: Glossary):
    spec = SearchSpec(titles=["Backend Engineer"], locations=["Germany"])
    variants = assemble(spec, glossary)

    for variant in (variants.strict, variants.balanced, variants.broad, variants.hidden_titles):
        assert "()" not in variant
        assert "( " not in variant
        assert " )" not in variant


def test_stable_deduplication_of_case_variant_terms(glossary: Glossary):
    spec = SearchSpec(
        titles=["Backend Engineer"],
        skills=PrioritizedTerms(must=["Python", "python", "PYTHON"]),
        locations=["Germany"],
    )
    variants = assemble(spec, glossary)

    assert variants.strict.count("Python") == 1


def test_stable_deduplication_of_duplicate_locations(glossary: Glossary):
    spec = SearchSpec(titles=["Backend Engineer"], locations=["Germany", "germany", "GERMANY"])
    variants = assemble(spec, glossary)

    assert variants.strict.count("Germany") == 1


def test_no_duplicate_exclusion_clauses(glossary: Glossary):
    spec = SearchSpec(
        titles=["Backend Engineer"],
        locations=["Germany"],
        exclusions=["Recruiter", "recruiter"],
    )
    variants = assemble(spec, glossary)

    assert variants.strict.count("NOT") == 1


def test_completely_empty_spec_has_no_dangling_and_or_empty_groups(glossary: Glossary):
    variants = assemble(SearchSpec(), glossary)

    for variant in (variants.strict, variants.balanced, variants.broad, variants.hidden_titles):
        assert "()" not in variant
        assert not variant.endswith("AND")
        assert "AND AND" not in variant
        assert variant == "site:linkedin.com/in/"


# ---------------------------------------------------------------------------
# General rules: quoting, group separation, location isolation
# ---------------------------------------------------------------------------


def test_multiword_terms_are_quoted(glossary: Glossary):
    variants = assemble(_rich_spec(), glossary)
    assert '"Backend Engineer"' in variants.strict
    assert '"Backend Engineering"' in variants.strict


def test_single_word_terms_are_not_quoted(glossary: Glossary):
    spec = SearchSpec(
        titles=["Engineer"],
        skills=PrioritizedTerms(must=["Python"]),
        locations=["Germany"],
    )
    variants = assemble(spec, glossary)
    assert '"Python"' not in variants.strict
    assert "(Python)" in variants.strict


def test_location_terms_never_leak_into_other_groups(glossary: Glossary):
    spec = SearchSpec(
        titles=["Backend Engineer"],
        skills=PrioritizedTerms(must=["Python"]),
        locations=["Germany"],
    )
    variants = assemble(spec, glossary)

    title_and_skill_prefix = variants.strict.split("(Germany)")[0]
    assert "Germany" not in title_and_skill_prefix


def test_assemble_uses_default_glossary_when_none_given():
    spec = SearchSpec(titles=["Backend Engineer"], locations=["Narnia"])
    variants = assemble(spec)
    assert variants.strict.startswith("site:linkedin.com/in/")
    assert isinstance(variants, QueryVariants)


def test_assemble_does_not_mutate_search_spec(glossary: Glossary):
    spec = _rich_spec()
    original_locations = list(spec.locations)
    original_titles = list(spec.titles)

    assemble(spec, glossary)

    assert spec.locations == original_locations
    assert spec.titles == original_titles
