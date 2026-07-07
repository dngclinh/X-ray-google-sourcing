"""Tests for src/xray/glossary.py.

Covers loading/validating the five generic knowledge files
(locations, languages, company types, seniority levels, priority
cues) and the typed lookup helpers over them. Does not test
job-family packs (not loaded by this module) or any query-assembly
behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.xray.glossary import (
    DEFAULT_KNOWLEDGE_DIR,
    Glossary,
    GlossarySchemaError,
)

# ---------------------------------------------------------------------------
# Loading the real, checked-in knowledge files
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return Glossary.load(DEFAULT_KNOWLEDGE_DIR)


def test_load_default_knowledge_dir_succeeds(glossary: Glossary):
    assert glossary.locations
    assert glossary.languages
    assert glossary.company_types
    assert glossary.seniority_levels
    assert glossary.priority_cues.must
    assert glossary.priority_cues.important
    assert glossary.priority_cues.nice_to_have


# ---------------------------------------------------------------------------
# Locations: canonical / English / local names, unicode, case-insensitivity
# ---------------------------------------------------------------------------


def test_find_location_by_canonical_name(glossary: Glossary):
    result = glossary.find_location("Germany")
    assert result is not None
    assert result.canonical == "Germany"


def test_find_location_by_local_name_deutschland(glossary: Glossary):
    result = glossary.find_location("Deutschland")
    assert result is not None
    assert result.canonical == "Germany"


def test_find_location_is_case_insensitive(glossary: Glossary):
    assert glossary.find_location("GERMANY").canonical == "Germany"
    assert glossary.find_location("germany").canonical == "Germany"
    assert glossary.find_location("deutschland").canonical == "Germany"


def test_find_location_verified_cctld_present(glossary: Glossary):
    germany = glossary.find_location("Germany")
    assert germany.cctld == "de"


def test_find_location_unknown_country_returns_none(glossary: Glossary):
    assert glossary.find_location("Narnia") is None


# ---------------------------------------------------------------------------
# Cities: Munich / München
# ---------------------------------------------------------------------------


def test_find_city_munich_english(glossary: Glossary):
    match = glossary.find_city("Munich")
    assert match is not None
    assert match.city.canonical == "Munich"
    assert match.country.canonical == "Germany"


def test_find_city_munich_local_form(glossary: Glossary):
    match = glossary.find_city("München")
    assert match is not None
    assert match.city.canonical == "Munich"
    assert match.country.canonical == "Germany"


def test_find_city_is_case_insensitive_and_unicode_safe(glossary: Glossary):
    assert glossary.find_city("MÜNCHEN").city.canonical == "Munich"
    assert glossary.find_city("münchen").city.canonical == "Munich"


def test_find_city_unknown_city_returns_none(glossary: Glossary):
    assert glossary.find_city("Atlantis") is None


# ---------------------------------------------------------------------------
# Languages: German / Deutsch, speaking forms
# ---------------------------------------------------------------------------


def test_find_language_by_canonical_name(glossary: Glossary):
    result = glossary.find_language("German")
    assert result is not None
    assert result.canonical == "German"


def test_find_language_by_local_name_deutsch(glossary: Glossary):
    result = glossary.find_language("Deutsch")
    assert result is not None
    assert result.canonical == "German"


def test_find_language_by_speaking_form(glossary: Glossary):
    result = glossary.find_language("German-speaking")
    assert result is not None
    assert result.canonical == "German"


def test_find_language_is_case_insensitive(glossary: Glossary):
    assert glossary.find_language("DEUTSCH").canonical == "German"
    assert glossary.find_language("german").canonical == "German"


def test_find_language_unknown_language_returns_none(glossary: Glossary):
    assert glossary.find_language("Klingon") is None


# ---------------------------------------------------------------------------
# Company types: all ten required categories resolve
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "term",
    [
        "Consultancy",
        "Contractor",
        "Client-side",
        "Startup",
        "Enterprise",
        "Agency",
        "Manufacturer",
        "EPC",
        "General Contractor",
        "Design Office",
    ],
)
def test_find_company_type_resolves_each_required_category(glossary: Glossary, term: str):
    result = glossary.find_company_type(term)
    assert result is not None
    assert result.canonical == term


def test_find_company_type_by_alias(glossary: Glossary):
    result = glossary.find_company_type("Start-up")
    assert result is not None
    assert result.canonical == "Startup"


def test_find_company_type_is_case_insensitive(glossary: Glossary):
    assert glossary.find_company_type("consultancy").canonical == "Consultancy"
    assert glossary.find_company_type("CONSULTANCY").canonical == "Consultancy"


def test_find_company_type_unknown_returns_none(glossary: Glossary):
    assert glossary.find_company_type("Nonprofit") is None


# ---------------------------------------------------------------------------
# Seniority levels
# ---------------------------------------------------------------------------


def test_find_seniority_by_canonical_name(glossary: Glossary):
    result = glossary.find_seniority("Senior")
    assert result is not None
    assert result.canonical == "Senior"


def test_find_seniority_by_alias(glossary: Glossary):
    result = glossary.find_seniority("Entry-Level")
    assert result is not None
    assert result.canonical == "Junior"


def test_find_seniority_is_case_insensitive(glossary: Glossary):
    assert glossary.find_seniority("senior").canonical == "Senior"
    assert glossary.find_seniority("SENIOR").canonical == "Senior"


def test_find_seniority_unknown_returns_none(glossary: Glossary):
    assert glossary.find_seniority("Apprentice") is None


# ---------------------------------------------------------------------------
# Priority cues
# ---------------------------------------------------------------------------


def test_priority_cues_must_contains_required(glossary: Glossary):
    assert "required" in glossary.priority_cues.must


def test_priority_cues_important_contains_preferred(glossary: Glossary):
    assert "preferred" in glossary.priority_cues.important


def test_priority_cues_nice_to_have_contains_nice_to_have_phrase(glossary: Glossary):
    assert "nice to have" in glossary.priority_cues.nice_to_have


# ---------------------------------------------------------------------------
# Schema validation: malformed knowledge files are rejected
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True)


_VALID_COMPANY_TYPE_NAMES = [
    "Consultancy",
    "Contractor",
    "Client-side",
    "Startup",
    "Enterprise",
    "Agency",
    "Manufacturer",
    "EPC",
    "General Contractor",
    "Design Office",
]


def _valid_company_types_data() -> dict:
    return {
        "company_types": [
            {"canonical": name, "aliases": [name]} for name in _VALID_COMPANY_TYPE_NAMES
        ]
    }


def _valid_seniority_data() -> dict:
    return {"seniority_levels": [{"canonical": "Senior", "aliases": ["Senior"]}]}


def _valid_priority_cues_data() -> dict:
    return {
        "priority_cues": {
            "must": ["required"],
            "important": ["preferred"],
            "nice_to_have": ["nice to have"],
        }
    }


def _write_all_valid_knowledge_files(
    tmp_path: Path,
    *,
    locations: object | None = None,
    languages: object | None = None,
    company_types: object | None = None,
    seniority: object | None = None,
    priority_cues: object | None = None,
) -> None:
    """Write all five generic knowledge files as valid data, except for
    whichever one(s) the caller overrides — isolating a negative test to
    exactly the field under test."""
    _write_yaml(
        tmp_path / "locations.yaml",
        locations
        if locations is not None
        else {"countries": [{"canonical": "Germany", "names": ["Germany"]}]},
    )
    _write_yaml(
        tmp_path / "languages.yaml",
        languages
        if languages is not None
        else {"languages": [{"canonical": "German", "names": ["German"]}]},
    )
    _write_yaml(
        tmp_path / "company_types.yaml",
        company_types if company_types is not None else _valid_company_types_data(),
    )
    _write_yaml(
        tmp_path / "seniority.yaml",
        seniority if seniority is not None else _valid_seniority_data(),
    )
    _write_yaml(
        tmp_path / "priority_cues.yaml",
        priority_cues if priority_cues is not None else _valid_priority_cues_data(),
    )


def test_load_rejects_location_missing_canonical_in_names(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        locations={"countries": [{"canonical": "Germany", "names": ["Deutschland"]}]},
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_language_missing_required_field(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        languages={"languages": [{"canonical": "German"}]},
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_company_types_missing_a_required_category(tmp_path: Path):
    # Missing "EPC" from the required set.
    incomplete_names = [name for name in _VALID_COMPANY_TYPE_NAMES if name != "EPC"]
    _write_all_valid_knowledge_files(
        tmp_path,
        company_types={
            "company_types": [
                {"canonical": name, "aliases": [name]} for name in incomplete_names
            ]
        },
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_non_mapping_yaml_file(tmp_path: Path):
    _write_all_valid_knowledge_files(tmp_path, locations=["not", "a", "mapping"])
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


# ---------------------------------------------------------------------------
# Schema validation: seniority.yaml
# ---------------------------------------------------------------------------


def test_load_rejects_seniority_missing_canonical_in_aliases(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        seniority={"seniority_levels": [{"canonical": "Senior", "aliases": ["Lead"]}]},
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_seniority_empty_list(tmp_path: Path):
    _write_all_valid_knowledge_files(tmp_path, seniority={"seniority_levels": []})
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_seniority_unknown_top_level_field(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        seniority={
            "seniority_levels": [{"canonical": "Senior", "aliases": ["Senior"]}],
            "not_a_real_field": True,
        },
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


# ---------------------------------------------------------------------------
# Schema validation: priority_cues.yaml
# ---------------------------------------------------------------------------


def test_load_rejects_priority_cues_missing_category(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        priority_cues={"priority_cues": {"must": ["required"], "important": ["preferred"]}},
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_priority_cues_unknown_category(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        priority_cues={
            "priority_cues": {
                "must": ["required"],
                "important": ["preferred"],
                "nice_to_have": ["nice to have"],
                "urgent": ["asap"],
            }
        },
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_priority_cues_duplicate_phrase_across_categories(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        priority_cues={
            "priority_cues": {
                "must": ["required"],
                "important": ["required"],
                "nice_to_have": ["nice to have"],
            }
        },
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)


def test_load_rejects_priority_cues_empty_category(tmp_path: Path):
    _write_all_valid_knowledge_files(
        tmp_path,
        priority_cues={
            "priority_cues": {"must": [], "important": ["preferred"], "nice_to_have": ["bonus"]}
        },
    )
    with pytest.raises(GlossarySchemaError):
        Glossary.load(tmp_path)
