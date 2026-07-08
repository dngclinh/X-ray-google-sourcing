"""Tests for src/xray/family_detector.py.

Covers deterministic family/specialization detection against synthetic,
in-test job-family packs — no production pack under
`knowledge/job_families/` is loaded or required here. JD text fixtures
live in `tests/fixtures/sample_jds.py`.
"""

from __future__ import annotations

from pathlib import Path

from src.xray.family_detector import (
    CONFIDENCE_CAP,
    FamilyDetectionResult,
    detect_family,
)
from src.xray.knowledge_loader import (
    Industry,
    JobFamilyPack,
    SkillGroup,
    Specialization,
    TitleGroup,
)
from src.xray.normalizer import normalize_whitespace
from tests.fixtures.sample_jds import (
    AMBIGUOUS_MATCH_JD,
    CONFIDENT_FAMILY_MATCH_JD,
    CONFIDENT_SPECIALIZATION_MATCH_JD,
    CROSS_FAMILY_FALSE_POSITIVE_JD,
    GENERIC_KEYWORD_BELOW_THRESHOLD_JD,
    NO_MATCH_JD,
    TWO_GENERIC_SIGNALS_JD,
)

_SYNTHETIC_SOURCE = Path("tests/synthetic-pack")


def _software_engineer_pack() -> JobFamilyPack:
    return JobFamilyPack(
        source_path=_SYNTHETIC_SOURCE,
        family="Software Engineer",
        family_signals=("software engineer",),
        titles=(
            TitleGroup(
                id="core",
                group_type="role_type",
                terms=("Software Engineer", "Backend Software Engineer"),
                weight=0.6,
            ),
        ),
        specializations=(
            Specialization(
                id="distributed_systems",
                name="Distributed Systems",
                terms=("Distributed Systems Engineer",),
                weight=0.6,
            ),
        ),
        specialization_signals={
            "distributed_systems": ("distributed systems", "cloud infrastructure"),
        },
        industries=(
            Industry(id="tech_sector", name="Technology", terms=("technology sector",), weight=0.2),
        ),
        skill_groups=(
            SkillGroup(id="languages", name="Languages", terms=("Python", "Java"), weight=0.3),
        ),
        core_functions=(),
        hidden_title_signals=(),
        exclusions=(),
        local_market_terms={},
    )


def _electrical_engineer_pack() -> JobFamilyPack:
    return JobFamilyPack(
        source_path=_SYNTHETIC_SOURCE,
        family="Electrical Engineer",
        family_signals=("electrical engineer",),
        titles=(
            TitleGroup(
                id="core",
                group_type="role_type",
                terms=("Electrical Engineer", "Power Systems Engineer"),
                weight=0.6,
            ),
        ),
        specializations=(),
        specialization_signals={},
        industries=(
            Industry(
                id="data_center_infra",
                name="Data Center Infrastructure",
                terms=("data center",),
                weight=0.25,
            ),
        ),
        skill_groups=(
            SkillGroup(
                id="power_systems",
                name="Power Systems",
                terms=("power distribution", "electrical circuits"),
                weight=0.3,
            ),
        ),
        core_functions=(),
        hidden_title_signals=(),
        exclusions=(),
        local_market_terms={},
    )


def _nova_engineer_pack() -> JobFamilyPack:
    return JobFamilyPack(
        source_path=_SYNTHETIC_SOURCE,
        family="Nova Engineer",
        family_signals=("nova engineer",),
        titles=(TitleGroup(id="core", group_type="role_type", terms=("Nova Engineer",), weight=0.5),),
        specializations=(),
        specialization_signals={},
        industries=(),
        skill_groups=(),
        core_functions=(),
        hidden_title_signals=(),
        exclusions=(),
        local_market_terms={},
    )


def _terra_engineer_pack() -> JobFamilyPack:
    return JobFamilyPack(
        source_path=_SYNTHETIC_SOURCE,
        family="Terra Engineer",
        family_signals=("terra engineer",),
        titles=(TitleGroup(id="core", group_type="role_type", terms=("Terra Engineer",), weight=0.5),),
        specializations=(),
        specialization_signals={},
        industries=(),
        skill_groups=(),
        core_functions=(),
        hidden_title_signals=(),
        exclusions=(),
        local_market_terms={},
    )


def _detect(jd_text: str, packs) -> FamilyDetectionResult:
    return detect_family(normalize_whitespace(jd_text), packs)


# ---------------------------------------------------------------------------
# Confident family match
# ---------------------------------------------------------------------------


def test_confident_family_match():
    result = _detect(
        CONFIDENT_FAMILY_MATCH_JD,
        [_software_engineer_pack(), _electrical_engineer_pack()],
    )

    assert result.family == "Software Engineer"
    assert result.specialization is None
    assert result.confidence == CONFIDENCE_CAP
    assert result.matched_signals["family_signals"] == ("software engineer",)
    assert result.matched_signals["titles"] == ("Software Engineer",)
    assert result.warnings == ()


def test_confident_family_match_score_below_cap_is_not_rounded_up():
    # A pack with only a low-weight title match (no family signal) should
    # report a confidence proportional to the evidence, not the cap.
    weak_pack = JobFamilyPack(
        source_path=_SYNTHETIC_SOURCE,
        family="Weak Evidence Family",
        family_signals=("weak evidence family",),
        titles=(TitleGroup(id="core", group_type="role_type", terms=("Weak Title",), weight=0.4),),
        specializations=(),
        specialization_signals={},
        industries=(),
        skill_groups=(),
        core_functions=(),
        hidden_title_signals=(),
        exclusions=(),
        local_market_terms={},
    )
    result = _detect("We need a Weak Title to help out.", [weak_pack])
    assert result.family == "Weak Evidence Family"
    assert result.confidence == 0.4


# ---------------------------------------------------------------------------
# Confident specialization match
# ---------------------------------------------------------------------------


def test_confident_specialization_match():
    result = _detect(
        CONFIDENT_SPECIALIZATION_MATCH_JD,
        [_software_engineer_pack(), _electrical_engineer_pack()],
    )

    assert result.family == "Software Engineer"
    assert result.specialization == "Distributed Systems"
    assert set(result.matched_signals["specialization_signals"]) == {
        "distributed systems",
        "cloud infrastructure",
    }
    assert result.warnings == ()


def test_specialization_is_none_when_no_specialization_evidence_present():
    result = _detect(CONFIDENT_FAMILY_MATCH_JD, [_software_engineer_pack()])
    assert result.family == "Software Engineer"
    assert result.specialization is None
    assert "specialization_signals" not in result.matched_signals
    assert "specialization_terms" not in result.matched_signals


# ---------------------------------------------------------------------------
# No match
# ---------------------------------------------------------------------------


def test_no_match_returns_none_family_and_warning():
    result = _detect(
        NO_MATCH_JD,
        [_software_engineer_pack(), _electrical_engineer_pack()],
    )

    assert result.family is None
    assert result.specialization is None
    assert result.confidence == 0.0
    assert result.matched_signals == {}
    assert len(result.warnings) == 1
    assert "no job family matched" in result.warnings[0].lower()


def test_no_match_with_empty_pack_list():
    result = _detect(CONFIDENT_FAMILY_MATCH_JD, [])
    assert result.family is None
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Ambiguous match
# ---------------------------------------------------------------------------


def test_ambiguous_match_returns_none_family_with_warning():
    result = _detect(
        AMBIGUOUS_MATCH_JD,
        [_nova_engineer_pack(), _terra_engineer_pack()],
    )

    assert result.family is None
    assert result.specialization is None
    assert result.matched_signals == {}
    assert len(result.warnings) == 1
    warning = result.warnings[0].lower()
    assert "ambiguous" in warning
    assert "nova engineer" in warning
    assert "terra engineer" in warning


def test_ambiguous_match_confidence_reflects_tied_score_capped():
    result = _detect(
        AMBIGUOUS_MATCH_JD,
        [_nova_engineer_pack(), _terra_engineer_pack()],
    )
    # Each pack scores family_signal (1.0) + title (0.5) = 1.5, capped to 1.0.
    assert result.confidence == CONFIDENCE_CAP


# ---------------------------------------------------------------------------
# Cross-family false positive
# ---------------------------------------------------------------------------


def test_cross_family_false_positive_data_center_does_not_win_electrical():
    result = _detect(
        CROSS_FAMILY_FALSE_POSITIVE_JD,
        [_software_engineer_pack(), _electrical_engineer_pack()],
    )

    assert result.family == "Software Engineer"
    assert result.warnings == ()
    assert "industries" not in result.matched_signals
    assert all("data center" not in terms for terms in result.matched_signals.values())


def test_two_generic_signals_qualify_pack_without_competing_family():
    result = _detect(TWO_GENERIC_SIGNALS_JD, [_electrical_engineer_pack()])

    assert result.family == "Electrical Engineer"
    assert set(result.matched_signals["industries"]) == {"data center"}
    assert set(result.matched_signals["skill_groups"]) == {"power distribution"}


# ---------------------------------------------------------------------------
# Generic keyword below threshold
# ---------------------------------------------------------------------------


def test_generic_keyword_alone_stays_below_threshold():
    result = _detect(GENERIC_KEYWORD_BELOW_THRESHOLD_JD, [_electrical_engineer_pack()])

    assert result.family is None
    assert result.confidence == 0.0
    assert result.matched_signals == {}
    assert len(result.warnings) == 1
    assert "no job family matched" in result.warnings[0].lower()


def test_generic_keyword_below_threshold_even_with_competing_family_present():
    result = _detect(
        GENERIC_KEYWORD_BELOW_THRESHOLD_JD,
        [_software_engineer_pack(), _electrical_engineer_pack()],
    )
    assert result.family is None
