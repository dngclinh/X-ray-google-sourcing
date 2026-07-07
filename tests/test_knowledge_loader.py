"""Tests for src/xray/knowledge_loader.py.

Covers schema validation (valid pack, missing required field, invalid
term list, invalid weight, unknown field, duplicate canonical ids) and
cache behavior. Does not test job-family detection (not implemented by
this module) or any extraction/query-assembly behavior.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from src.xray.knowledge_loader import (
    JobFamilyPack,
    KnowledgePackSchemaError,
    clear_cache,
    load_job_family_pack,
)

SCHEMA_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[1] / "knowledge" / "job_families" / "_schema_example.yaml"
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


def _write_yaml(path: Path, data: object) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True)
    return path


def _valid_pack_dict() -> dict:
    return {
        "family": "Test Family",
        "family_signals": ["test family signal"],
        "titles": [
            {
                "id": "junior",
                "group_type": "seniority",
                "terms": ["Junior Test Role"],
                "weight": 0.3,
            },
            {
                "id": "core",
                "group_type": "role_type",
                "terms": ["Test Role"],
            },
        ],
        "specializations": [
            {"id": "spec_a", "name": "Spec A", "terms": ["Spec A Role"]},
        ],
        "specialization_signals": {"spec_a": ["spec a signal"]},
        "industries": [
            {"id": "ind_a", "name": "Industry A", "terms": ["industry a"]},
        ],
        "skill_groups": [
            {"id": "skill_a", "name": "Skill A", "terms": ["Skill A"], "weight": 0.5},
        ],
        "hidden_title_signals": ["Adjacent Title"],
        "exclusions": ["Recruiter"],
        "local_market_terms": {"xx": ["Local Title"]},
    }


# ---------------------------------------------------------------------------
# Valid pack
# ---------------------------------------------------------------------------


def test_load_schema_example_is_valid():
    pack = load_job_family_pack(SCHEMA_EXAMPLE_PATH)
    assert isinstance(pack, JobFamilyPack)
    assert pack.family == "Example Role Family"
    assert [t.id for t in pack.titles] == ["junior", "senior", "core_role_type"]
    assert pack.titles[0].group_type == "seniority"
    assert pack.titles[0].weight == 0.3
    assert pack.titles[2].weight is None
    assert pack.specializations[0].id == "example_specialization_a"
    assert pack.specialization_signals["example_specialization_a"] == (
        "example specialization a systems",
        "example specialization a platform",
    )
    assert pack.industries[0].name == "Example Industry"
    assert pack.skill_groups[0].weight == 0.8
    assert pack.hidden_title_signals == ("Example Adjacent Title", "Example Feeder Title")
    assert pack.exclusions == ("Example Recruiter",)
    assert pack.local_market_terms["xx"] == ("Example Local-Language Title",)


def test_load_valid_minimal_pack(tmp_path: Path):
    path = _write_yaml(tmp_path / "family.yaml", _valid_pack_dict())
    pack = load_job_family_pack(path)
    assert pack.family == "Test Family"
    assert pack.titles[0].id == "junior"
    assert pack.titles[0].weight == 0.3
    assert pack.titles[1].weight is None
    assert pack.skill_groups[0].weight == 0.5


def test_load_pack_without_optional_sections(tmp_path: Path):
    data = _valid_pack_dict()
    for optional_field in (
        "specializations",
        "specialization_signals",
        "industries",
        "skill_groups",
        "hidden_title_signals",
        "exclusions",
        "local_market_terms",
    ):
        del data[optional_field]
    path = _write_yaml(tmp_path / "minimal.yaml", data)
    pack = load_job_family_pack(path)
    assert pack.family == "Test Family"
    assert pack.specializations == ()
    assert pack.specialization_signals == {}
    assert pack.industries == ()
    assert pack.skill_groups == ()
    assert pack.hidden_title_signals == ()
    assert pack.exclusions == ()
    assert pack.local_market_terms == {}


# ---------------------------------------------------------------------------
# Missing family (and other required fields)
# ---------------------------------------------------------------------------


def test_missing_family_raises(tmp_path: Path):
    data = _valid_pack_dict()
    del data["family"]
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="family"):
        load_job_family_pack(path)


def test_missing_family_signals_raises(tmp_path: Path):
    data = _valid_pack_dict()
    del data["family_signals"]
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="family_signals"):
        load_job_family_pack(path)


def test_missing_titles_raises(tmp_path: Path):
    data = _valid_pack_dict()
    del data["titles"]
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="titles"):
        load_job_family_pack(path)


def test_empty_family_string_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["family"] = "   "
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError):
        load_job_family_pack(path)


# ---------------------------------------------------------------------------
# Invalid term list
# ---------------------------------------------------------------------------


def test_invalid_term_list_not_a_list_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["terms"] = "Junior Test Role"
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="terms"):
        load_job_family_pack(path)


def test_invalid_term_list_empty_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["terms"] = []
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="terms"):
        load_job_family_pack(path)


def test_invalid_term_list_non_string_item_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["skill_groups"][0]["terms"] = ["Skill A", 123]
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="terms"):
        load_job_family_pack(path)


def test_invalid_group_type_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["group_type"] = "experience_level"
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="group_type"):
        load_job_family_pack(path)


# ---------------------------------------------------------------------------
# Invalid weight
# ---------------------------------------------------------------------------


def test_invalid_weight_out_of_range_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["weight"] = 1.5
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="weight"):
        load_job_family_pack(path)


def test_invalid_weight_negative_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["skill_groups"][0]["weight"] = -0.1
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="weight"):
        load_job_family_pack(path)


def test_invalid_weight_wrong_type_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["weight"] = "high"
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="weight"):
        load_job_family_pack(path)


def test_invalid_weight_bool_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["weight"] = True
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="weight"):
        load_job_family_pack(path)


def test_valid_weight_boundaries_are_accepted(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["weight"] = 0.0
    data["titles"][1]["weight"] = 1.0
    path = _write_yaml(tmp_path / "family.yaml", data)
    pack = load_job_family_pack(path)
    assert pack.titles[0].weight == 0.0
    assert pack.titles[1].weight == 1.0


# ---------------------------------------------------------------------------
# Unknown field
# ---------------------------------------------------------------------------


def test_unknown_top_level_field_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["not_a_real_field"] = "oops"
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="not_a_real_field"):
        load_job_family_pack(path)


def test_unknown_nested_title_field_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"][0]["synonyms"] = ["oops"]
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="synonyms"):
        load_job_family_pack(path)


def test_specialization_signals_unknown_id_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["specialization_signals"] = {"does_not_exist": ["signal"]}
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="does_not_exist"):
        load_job_family_pack(path)


# ---------------------------------------------------------------------------
# Duplicate canonical ids
# ---------------------------------------------------------------------------


def test_duplicate_id_within_same_section_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["titles"].append(
        {"id": "junior", "group_type": "seniority", "terms": ["Another Junior Title"]}
    )
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="duplicate canonical id"):
        load_job_family_pack(path)


def test_duplicate_id_across_sections_raises(tmp_path: Path):
    data = _valid_pack_dict()
    # "core" is already a title id; reuse it as a skill-group id too.
    data["skill_groups"].append({"id": "core", "name": "Core Skill", "terms": ["Core"]})
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="duplicate canonical id"):
        load_job_family_pack(path)


def test_duplicate_id_case_insensitive_raises(tmp_path: Path):
    data = _valid_pack_dict()
    data["industries"].append({"id": "Spec_A", "name": "Collides", "terms": ["collides"]})
    path = _write_yaml(tmp_path / "family.yaml", data)
    with pytest.raises(KnowledgePackSchemaError, match="duplicate canonical id"):
        load_job_family_pack(path)


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------


def test_load_job_family_pack_returns_cached_instance(tmp_path: Path):
    path = _write_yaml(tmp_path / "family.yaml", _valid_pack_dict())
    first = load_job_family_pack(path)
    second = load_job_family_pack(path)
    assert first is second


def test_cache_survives_file_mutation_until_cleared(tmp_path: Path):
    path = _write_yaml(tmp_path / "family.yaml", _valid_pack_dict())
    first = load_job_family_pack(path)

    mutated = copy.deepcopy(_valid_pack_dict())
    mutated["family"] = "Mutated Family"
    _write_yaml(path, mutated)

    second = load_job_family_pack(path)
    assert second is first
    assert second.family == "Test Family"


def test_clear_cache_forces_reload(tmp_path: Path):
    path = _write_yaml(tmp_path / "family.yaml", _valid_pack_dict())
    first = load_job_family_pack(path)

    mutated = copy.deepcopy(_valid_pack_dict())
    mutated["family"] = "Mutated Family"
    _write_yaml(path, mutated)
    clear_cache()

    second = load_job_family_pack(path)
    assert second is not first
    assert second.family == "Mutated Family"


def test_different_paths_are_cached_independently(tmp_path: Path):
    data_a = _valid_pack_dict()
    data_b = copy.deepcopy(_valid_pack_dict())
    data_b["family"] = "Other Family"

    path_a = _write_yaml(tmp_path / "a.yaml", data_a)
    path_b = _write_yaml(tmp_path / "b.yaml", data_b)

    pack_a = load_job_family_pack(path_a)
    pack_b = load_job_family_pack(path_b)

    assert pack_a is not pack_b
    assert pack_a.family == "Test Family"
    assert pack_b.family == "Other Family"


def test_failed_load_is_not_cached(tmp_path: Path):
    data = _valid_pack_dict()
    del data["family"]
    path = _write_yaml(tmp_path / "family.yaml", data)

    with pytest.raises(KnowledgePackSchemaError):
        load_job_family_pack(path)

    fixed = _valid_pack_dict()
    _write_yaml(path, fixed)
    pack = load_job_family_pack(path)
    assert pack.family == "Test Family"
