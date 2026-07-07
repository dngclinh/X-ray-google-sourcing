"""Tests for src/xray/models.py.

Covers only what the module claims to do: default values, isolation of
mutable default fields between instances, and confidence validation.
No extraction or query-assembly behavior is tested here (there is none
in this module).
"""

from __future__ import annotations

import pytest

from src.xray.models import PrioritizedTerms, QueryVariants, SearchSpec


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_prioritized_terms_defaults():
    terms = PrioritizedTerms()
    assert terms.must == []
    assert terms.important == []
    assert terms.nice_to_have == []


def test_search_spec_defaults():
    spec = SearchSpec()
    assert spec.source == ""
    assert spec.titles == []
    assert spec.core_functions == []
    assert spec.industries == []
    assert spec.skills == PrioritizedTerms()
    assert spec.locations == []
    assert spec.languages == PrioritizedTerms()
    assert spec.company_types == PrioritizedTerms()
    assert spec.exclusions == []
    assert spec.job_family is None
    assert spec.specialization is None
    assert spec.confidence == {}
    assert spec.warnings == []
    assert spec.matched_signals == {}


def test_query_variants_defaults():
    variants = QueryVariants()
    assert variants.strict == ""
    assert variants.balanced == ""
    assert variants.broad == ""
    assert variants.hidden_titles == ""


# ---------------------------------------------------------------------------
# Isolation of mutable default fields
# ---------------------------------------------------------------------------


def test_prioritized_terms_mutable_fields_are_isolated():
    a = PrioritizedTerms()
    b = PrioritizedTerms()

    a.must.append("Python")
    a.important.append("Django")
    a.nice_to_have.append("Docker")

    assert b.must == []
    assert b.important == []
    assert b.nice_to_have == []
    assert a.must is not b.must
    assert a.important is not b.important
    assert a.nice_to_have is not b.nice_to_have


def test_search_spec_mutable_fields_are_isolated():
    a = SearchSpec()
    b = SearchSpec()

    a.titles.append("Backend Engineer")
    a.core_functions.append("Software Engineering")
    a.industries.append("Fintech")
    a.locations.append("Berlin")
    a.exclusions.append("Recruiter")
    a.warnings.append("heuristic core function")
    a.confidence["core_functions"] = 0.5
    a.matched_signals["core_functions"] = ["backend"]
    a.skills.must.append("SQL")

    assert b.titles == []
    assert b.core_functions == []
    assert b.industries == []
    assert b.locations == []
    assert b.exclusions == []
    assert b.warnings == []
    assert b.confidence == {}
    assert b.matched_signals == {}
    assert b.skills.must == []

    # Nested PrioritizedTerms instances must also be distinct objects.
    assert a.skills is not b.skills
    assert a.languages is not b.languages
    assert a.company_types is not b.company_types


def test_search_spec_shared_prioritized_terms_type_is_independent_per_field():
    spec = SearchSpec()
    assert spec.skills is not spec.languages
    assert spec.skills is not spec.company_types
    assert spec.languages is not spec.company_types


# ---------------------------------------------------------------------------
# Confidence validation
# ---------------------------------------------------------------------------


def test_search_spec_accepts_valid_confidence_values():
    spec = SearchSpec(confidence={"core_functions": 0.0, "industries": 1.0, "titles": 0.42})
    assert spec.confidence == {"core_functions": 0.0, "industries": 1.0, "titles": 0.42}


@pytest.mark.parametrize("bad_value", [-0.01, 1.01, -1, 2, 100])
def test_search_spec_rejects_out_of_range_confidence(bad_value):
    with pytest.raises(ValueError):
        SearchSpec(confidence={"core_functions": bad_value})


@pytest.mark.parametrize("bad_value", ["high", None, [0.5], True, False])
def test_search_spec_rejects_non_numeric_confidence(bad_value):
    with pytest.raises(ValueError):
        SearchSpec(confidence={"core_functions": bad_value})
