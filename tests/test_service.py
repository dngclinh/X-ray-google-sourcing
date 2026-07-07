"""Tests for src/xray/service.py (and the src/xray/__init__.py re-exports).

Exercises the full `generate_xray_queries` pipeline end to end. Uses
the real, checked-in generic knowledge (`knowledge/*.yaml`) since that
is already extensively tested elsewhere, but always points
`job_families_dir` at a temporary directory of synthetic packs — the
real `knowledge/job_families/` intentionally has no production packs
yet, and this suite must not depend on that ever changing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.xray import (
    InvalidJobDescriptionError,
    QueryVariants,
    SearchSpec,
    generate_xray_queries,
)


def _write_pack(path: Path, data: dict) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True)
    return path


def _nova_engineer_pack_data() -> dict:
    return {
        "family": "Nova Engineer",
        "family_signals": ["nova engineer"],
        "titles": [
            {"id": "core", "group_type": "role_type", "terms": ["Nova Engineer"]},
        ],
        "specializations": [
            {"id": "cloud_nova", "name": "Cloud Nova", "terms": ["Cloud Nova Engineer"]},
        ],
        "specialization_signals": {"cloud_nova": ["cloud nova platform"]},
        "industries": [
            {"id": "space_tech", "name": "Space Technology", "terms": ["space technology"]},
        ],
        "skill_groups": [
            {"id": "core_skill", "name": "Core Skill", "terms": ["Astrodynamics"]},
        ],
    }


def _terra_engineer_pack_data() -> dict:
    return {
        "family": "Terra Engineer",
        "family_signals": ["terra engineer"],
        "titles": [
            {"id": "core", "group_type": "role_type", "terms": ["Terra Engineer"]},
        ],
    }


NOVA_JD = (
    "We are hiring a Nova Engineer to work in space technology on our "
    "cloud nova platform. Astrodynamics experience is required. This "
    "role is based in Germany."
)


@pytest.fixture()
def nova_packs_dir(tmp_path: Path) -> Path:
    packs_dir = tmp_path / "job_families"
    packs_dir.mkdir()
    _write_pack(packs_dir / "nova_engineer.yaml", _nova_engineer_pack_data())
    return packs_dir


@pytest.fixture()
def empty_packs_dir(tmp_path: Path) -> Path:
    packs_dir = tmp_path / "job_families_empty"
    packs_dir.mkdir()
    return packs_dir


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


def test_returns_search_spec_and_query_variants(empty_packs_dir: Path):
    spec, variants = generate_xray_queries(
        "We are hiring a Backend Engineer based in Germany.",
        job_families_dir=empty_packs_dir,
    )
    assert isinstance(spec, SearchSpec)
    assert isinstance(variants, QueryVariants)


def test_result_is_importable_from_package_root():
    # generate_xray_queries, SearchSpec, QueryVariants were all imported
    # from `src.xray` (not `src.xray.service`/`src.xray.models`) above —
    # this test simply documents that this is the supported import path.
    assert callable(generate_xray_queries)


# ---------------------------------------------------------------------------
# Clear exceptions for invalid input
# ---------------------------------------------------------------------------


def test_empty_jd_text_raises_cleanly():
    with pytest.raises(InvalidJobDescriptionError):
        generate_xray_queries("")


def test_whitespace_only_jd_text_raises_cleanly():
    with pytest.raises(InvalidJobDescriptionError):
        generate_xray_queries("   \n\t  ")


def test_invalid_job_description_error_is_a_value_error():
    assert issubclass(InvalidJobDescriptionError, ValueError)


def test_non_string_jd_text_raises_type_error():
    with pytest.raises(TypeError):
        generate_xray_queries(None)  # type: ignore[arg-type]


def test_non_string_location_override_raises_type_error():
    with pytest.raises(TypeError):
        generate_xray_queries("Backend Engineer", location_override=123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Pipeline wiring: job family + specialization detection feeding extraction
# ---------------------------------------------------------------------------


def test_detects_job_family_and_specialization_from_synthetic_pack(nova_packs_dir: Path):
    spec, variants = generate_xray_queries(NOVA_JD, job_families_dir=nova_packs_dir)

    assert spec.job_family == "Nova Engineer"
    assert spec.specialization == "Cloud Nova"
    assert "Nova Engineer" in spec.titles
    assert spec.industries == ["Space Technology"]
    assert "Astrodynamics" in spec.skills.must
    assert '"Nova Engineer"' in variants.strict or "Nova Engineer" in variants.strict


def test_unsupported_job_family_warns_through_search_spec(empty_packs_dir: Path):
    spec, _ = generate_xray_queries(
        "We are hiring a Backend Engineer based in Germany.",
        job_families_dir=empty_packs_dir,
    )
    assert spec.job_family is None
    assert any("no job family matched" in w.lower() for w in spec.warnings)


def test_ambiguous_job_family_warns_through_search_spec(tmp_path: Path):
    packs_dir = tmp_path / "ambiguous_packs"
    packs_dir.mkdir()
    _write_pack(packs_dir / "nova_engineer.yaml", _nova_engineer_pack_data())
    _write_pack(packs_dir / "terra_engineer.yaml", _terra_engineer_pack_data())

    jd = "We are hiring a Nova Engineer who is also a Terra Engineer."
    spec, _ = generate_xray_queries(jd, job_families_dir=packs_dir)

    assert spec.job_family is None
    assert any("ambiguous" in w.lower() for w in spec.warnings)


def test_underscore_prefixed_pack_files_are_never_loaded(tmp_path: Path):
    packs_dir = tmp_path / "packs_with_schema_example"
    packs_dir.mkdir()
    _write_pack(packs_dir / "_schema_example.yaml", _nova_engineer_pack_data())

    spec, _ = generate_xray_queries(NOVA_JD, job_families_dir=packs_dir)

    # The only pack present is underscore-prefixed, so it must be
    # ignored — this JD should behave exactly like the no-packs case.
    assert spec.job_family is None
    assert any("no job family matched" in w.lower() for w in spec.warnings)


def test_missing_job_families_directory_behaves_like_no_packs(tmp_path: Path):
    missing_dir = tmp_path / "does_not_exist"
    spec, _ = generate_xray_queries(
        "We are hiring a Backend Engineer based in Germany.",
        job_families_dir=missing_dir,
    )
    assert spec.job_family is None
    assert any("no job family matched" in w.lower() for w in spec.warnings)


# ---------------------------------------------------------------------------
# Location override merging + LinkedIn source resolution
# ---------------------------------------------------------------------------


def test_location_override_is_merged_additively(empty_packs_dir: Path):
    spec, variants = generate_xray_queries(
        "We are hiring a Backend Engineer.",
        location_override="Germany",
        job_families_dir=empty_packs_dir,
    )
    assert "Germany" in spec.locations
    assert variants.strict.startswith("site:de.linkedin.com/in/")
    assert "Germany" in variants.strict


def test_location_override_does_not_replace_extracted_locations(empty_packs_dir: Path):
    spec, _ = generate_xray_queries(
        "We are hiring a Backend Engineer based in Munich.",
        location_override="Berlin",
        job_families_dir=empty_packs_dir,
    )
    assert "Berlin" in spec.locations
    assert "Munich" in spec.locations


def test_conflicting_location_override_safely_falls_back_to_global_source(
    empty_packs_dir: Path,
):
    spec, variants = generate_xray_queries(
        "We are hiring a Backend Engineer based in Germany.",
        location_override="Poland",
        job_families_dir=empty_packs_dir,
    )
    assert "Germany" in spec.locations
    assert "Poland" in spec.locations
    for variant in (variants.strict, variants.balanced, variants.broad, variants.hidden_titles):
        assert variant.startswith("site:linkedin.com/in/")
        assert not variant.startswith("site:de.linkedin.com")


def test_blank_location_override_is_a_no_op(empty_packs_dir: Path):
    spec, _ = generate_xray_queries(
        "We are hiring a Backend Engineer based in Germany.",
        location_override="   ",
        job_families_dir=empty_packs_dir,
    )
    assert spec.locations == ["Germany"]


# ---------------------------------------------------------------------------
# Determinism and statelessness across calls
# ---------------------------------------------------------------------------


def test_same_input_produces_equal_output(nova_packs_dir: Path):
    spec_a, variants_a = generate_xray_queries(NOVA_JD, job_families_dir=nova_packs_dir)
    spec_b, variants_b = generate_xray_queries(NOVA_JD, job_families_dir=nova_packs_dir)

    assert spec_a == spec_b
    assert variants_a == variants_b


def test_calls_do_not_leak_state_into_each_other(nova_packs_dir: Path, empty_packs_dir: Path):
    spec_nova, _ = generate_xray_queries(NOVA_JD, job_families_dir=nova_packs_dir)
    spec_plain, _ = generate_xray_queries(
        "We are hiring a Backend Engineer based in Germany.",
        job_families_dir=empty_packs_dir,
    )

    assert spec_nova.job_family == "Nova Engineer"
    assert spec_plain.job_family is None
    assert "Nova Engineer" not in spec_plain.titles
    assert not any("no job family matched" in w.lower() for w in spec_nova.warnings)


# ---------------------------------------------------------------------------
# Warnings surfaced through SearchSpec (validator findings included)
# ---------------------------------------------------------------------------


def test_missing_title_evidence_warning_reaches_search_spec(empty_packs_dir: Path):
    spec, _ = generate_xray_queries(
        "Experience with cloud platforms is required.",
        job_families_dir=empty_packs_dir,
    )
    assert spec.titles == []
    assert any("title" in w.lower() for w in spec.warnings)


def test_source_field_holds_original_jd_text_not_the_linkedin_source(empty_packs_dir: Path):
    jd = "We are hiring a Backend Engineer based in Germany."
    spec, _ = generate_xray_queries(jd, job_families_dir=empty_packs_dir)
    assert spec.source == jd
    assert not spec.source.startswith("site:")
