"""Tests for src/xray/extractor.py.

Covers deterministic JD extraction against the real, checked-in
generic glossary (`Glossary.load`) plus, for profession-specific term
extraction, a synthetic in-test `JobFamilyPack` — no production pack
under `knowledge/job_families/` is loaded or required here. JD text
fixtures live in `tests/fixtures/sample_jds.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.xray.extractor import extract
from src.xray.glossary import DEFAULT_KNOWLEDGE_DIR, Glossary
from src.xray.knowledge_loader import Industry, JobFamilyPack, SkillGroup, TitleGroup
from src.xray.models import PrioritizedTerms
from tests.fixtures.sample_jds import (
    COMPANY_TYPE_NEGATIVE_OUR_CONSULTANCY_JD,
    COMPANY_TYPE_NEGATIVE_WE_ARE_EPC_JD,
    COMPANY_TYPE_POSITIVE_BACKGROUND_JD,
    COMPANY_TYPE_POSITIVE_EXPERIENCE_JD,
    COMPANY_TYPE_POSITIVE_WORKED_EPC_JD,
    LANGUAGE_CEFR_JD,
    LANGUAGE_FALSE_POSITIVE_COMPANY_JD,
    LANGUAGE_FALSE_POSITIVE_NATIVE_CLOUD_JD,
    LANGUAGE_FALSE_POSITIVE_SPEAKING_CONFERENCE_JD,
    LANGUAGE_FALSE_POSITIVE_VERSION_JD,
    LANGUAGE_FLUENT_MULTI_JD,
    LANGUAGE_MUST_JD,
    LANGUAGE_NICE_JD,
    LANGUAGE_OPTIONAL_NOT_MUST_JD,
    LANGUAGE_PREFERRED_JD,
    LANGUAGE_SPEAKING_JD,
    LOCATION_JD,
    PACK_TERMS_JD,
    PRIORITY_CUES_JD,
    SENIORITY_JD,
    TITLE_LABEL_JD,
    TITLE_TRIGGER_JD,
)


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return Glossary.load(DEFAULT_KNOWLEDGE_DIR)


def _software_engineer_pack() -> JobFamilyPack:
    return JobFamilyPack(
        source_path=Path("tests/synthetic-pack"),
        family="Software Engineer",
        family_signals=("software engineer",),
        titles=(
            TitleGroup(
                id="core",
                group_type="role_type",
                terms=("Software Engineer", "Backend Engineer"),
                weight=0.6,
            ),
        ),
        specializations=(),
        specialization_signals={},
        industries=(Industry(id="fintech", name="Fintech", terms=("fintech",), weight=0.3),),
        skill_groups=(
            SkillGroup(
                id="languages",
                name="Programming Languages",
                terms=("Python", "Kubernetes"),
                weight=0.3,
            ),
        ),
        hidden_title_signals=(),
        exclusions=(),
        local_market_terms={},
    )


# ---------------------------------------------------------------------------
# Explicit target titles
# ---------------------------------------------------------------------------


def test_extract_title_from_label_line(glossary: Glossary):
    spec = extract(TITLE_LABEL_JD, glossary)
    assert spec.titles == ["Senior Backend Engineer"]


def test_extract_title_from_trigger_phrase(glossary: Glossary):
    spec = extract(TITLE_TRIGGER_JD, glossary)
    assert spec.titles == ["Backend Engineer"]


# ---------------------------------------------------------------------------
# Seniority cues
# ---------------------------------------------------------------------------


def test_extract_seniority_cue(glossary: Glossary):
    spec = extract(SENIORITY_JD, glossary)
    assert spec.matched_signals["seniority"] == ["Senior"]


# ---------------------------------------------------------------------------
# Location terms
# ---------------------------------------------------------------------------


def test_extract_location_city_and_country(glossary: Glossary):
    spec = extract(LOCATION_JD, glossary)
    assert spec.locations == ["Munich", "Poland"]


# ---------------------------------------------------------------------------
# Language requirements — positive cases (rule 2) + multi-language
# ---------------------------------------------------------------------------


def test_extract_multiple_languages_from_fluency_cue(glossary: Glossary):
    spec = extract(LANGUAGE_FLUENT_MULTI_JD, glossary)
    assert set(spec.languages.important) == {"German", "English"}
    assert spec.languages.must == []
    assert spec.languages.nice_to_have == []


def test_extract_languages_from_cefr_codes(glossary: Glossary):
    spec = extract(LANGUAGE_CEFR_JD, glossary)
    assert set(spec.languages.important) == {"German", "English"}


def test_extract_language_from_speaking_form(glossary: Glossary):
    spec = extract(LANGUAGE_SPEAKING_JD, glossary)
    assert "German" in spec.languages.important
    assert "German-speaking" in spec.matched_signals["languages"]


def test_extract_language_with_important_priority_cue(glossary: Glossary):
    spec = extract(LANGUAGE_PREFERRED_JD, glossary)
    assert spec.languages.important == ["English"]
    assert "preferred" in spec.matched_signals["priority_important"]


def test_extract_language_with_must_priority_cue(glossary: Glossary):
    spec = extract(LANGUAGE_MUST_JD, glossary)
    assert spec.languages.must == ["German"]


def test_extract_language_with_nice_to_have_priority_cue(glossary: Glossary):
    spec = extract(LANGUAGE_NICE_JD, glossary)
    assert spec.languages.nice_to_have == ["French"]


def test_optional_language_cue_does_not_become_must(glossary: Glossary):
    spec = extract(LANGUAGE_OPTIONAL_NOT_MUST_JD, glossary)
    assert spec.languages.nice_to_have == ["German"]
    assert spec.languages.must == []


# ---------------------------------------------------------------------------
# Language requirements — false positives (rule 3)
# ---------------------------------------------------------------------------


def test_language_false_positive_company_is_not_extracted(glossary: Glossary):
    spec = extract(LANGUAGE_FALSE_POSITIVE_COMPANY_JD, glossary)
    assert spec.languages == PrioritizedTerms()


def test_language_false_positive_version_is_not_extracted(glossary: Glossary):
    spec = extract(LANGUAGE_FALSE_POSITIVE_VERSION_JD, glossary)
    assert spec.languages == PrioritizedTerms()


def test_language_false_positive_native_cloud_is_not_extracted(glossary: Glossary):
    spec = extract(LANGUAGE_FALSE_POSITIVE_NATIVE_CLOUD_JD, glossary)
    assert spec.languages == PrioritizedTerms()


def test_language_false_positive_speaking_conference_is_not_extracted(glossary: Glossary):
    spec = extract(LANGUAGE_FALSE_POSITIVE_SPEAKING_CONFERENCE_JD, glossary)
    assert spec.languages == PrioritizedTerms()


# ---------------------------------------------------------------------------
# Company-environment requirements — positive cases (rule 4)
# ---------------------------------------------------------------------------


def test_company_type_extracted_with_experience_context(glossary: Glossary):
    spec = extract(COMPANY_TYPE_POSITIVE_EXPERIENCE_JD, glossary)
    assert "Consultancy" in spec.company_types.nice_to_have


def test_company_type_extracted_with_background_context(glossary: Glossary):
    spec = extract(COMPANY_TYPE_POSITIVE_BACKGROUND_JD, glossary)
    assert "Consultancy" in spec.company_types.nice_to_have


def test_company_type_extracted_with_worked_for_context(glossary: Glossary):
    spec = extract(COMPANY_TYPE_POSITIVE_WORKED_EPC_JD, glossary)
    assert "EPC" in spec.company_types.nice_to_have


# ---------------------------------------------------------------------------
# Company-environment requirements — negative cases (rule 5)
# ---------------------------------------------------------------------------


def test_company_type_not_extracted_when_describing_employer_our(glossary: Glossary):
    spec = extract(COMPANY_TYPE_NEGATIVE_OUR_CONSULTANCY_JD, glossary)
    assert spec.company_types == PrioritizedTerms()


def test_company_type_not_extracted_when_describing_employer_we_are(glossary: Glossary):
    spec = extract(COMPANY_TYPE_NEGATIVE_WE_ARE_EPC_JD, glossary)
    assert spec.company_types == PrioritizedTerms()


# ---------------------------------------------------------------------------
# Explicit priority cues (MUST / IMPORTANT / NICE-TO-HAVE)
# ---------------------------------------------------------------------------


def test_priority_cues_are_recorded_independent_of_field(glossary: Glossary):
    spec = extract(PRIORITY_CUES_JD, glossary)
    assert spec.matched_signals["priority_must"] == ["required"]
    assert spec.matched_signals["priority_important"] == ["preferred"]
    assert spec.matched_signals["priority_nice_to_have"] == ["nice to have"]


# ---------------------------------------------------------------------------
# Profession-specific terms only from an activated knowledge pack
# ---------------------------------------------------------------------------


def test_pack_terms_not_extracted_without_activated_pack(glossary: Glossary):
    spec = extract(PACK_TERMS_JD, glossary, pack=None)
    assert spec.skills == PrioritizedTerms()
    assert spec.industries == []
    assert spec.job_family is None


def test_pack_titles_industries_and_skills_extracted_with_activated_pack(glossary: Glossary):
    spec = extract(PACK_TERMS_JD, glossary, pack=_software_engineer_pack())
    assert spec.job_family == "Software Engineer"
    assert "Backend Engineer" in spec.titles
    assert spec.industries == ["Fintech"]
    assert spec.skills.must == ["Python"]
    assert spec.skills.nice_to_have == ["Kubernetes"]


def test_pack_titles_are_deduplicated_against_structural_titles(glossary: Glossary):
    spec = extract(PACK_TERMS_JD, glossary, pack=_software_engineer_pack())
    assert spec.titles.count("Backend Engineer") == 1


# ---------------------------------------------------------------------------
# Does not assemble Boolean queries
# ---------------------------------------------------------------------------


def test_extract_result_has_no_boolean_query_output(glossary: Glossary):
    spec = extract(TITLE_TRIGGER_JD, glossary)
    assert not hasattr(spec, "strict")
    assert not hasattr(spec, "balanced")
    assert not hasattr(spec, "broad")
