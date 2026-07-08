"""Regression tests for the production Electrical Engineering pack
(`knowledge/job_families/electrical_engineering.yaml`).

This is the first production job-family pack (CLAUDE.md section 7 no
longer applies: "no production job-family pack exists yet" is now
outdated for this family). These tests exercise it through the full
`generate_xray_queries` pipeline, using the *default* `job_families_dir`
(the real `knowledge/job_families/` directory) deliberately — unlike
`tests/test_service.py`, which always isolates itself from production
packs, these tests exist specifically to pin down this real pack's
behavior.

Per CLAUDE.md section 5 and the xray-code-maintenance skill (category 3/
4/5 knowledge additions require both a positive and a negative test),
every knowledge relationship exercised here has a positive case (it
fires) and a negative case (it does not over-fire).
"""

from __future__ import annotations

from pathlib import Path

from src.xray import generate_xray_queries
from src.xray.knowledge_loader import JobFamilyPack, load_job_family_pack

PACK_PATH = (
    Path(__file__).resolve().parents[1] / "knowledge" / "job_families" / "electrical_engineering.yaml"
)


# ---------------------------------------------------------------------------
# Schema sanity
# ---------------------------------------------------------------------------


def test_pack_loads_and_is_well_formed():
    pack = load_job_family_pack(PACK_PATH)
    assert isinstance(pack, JobFamilyPack)
    assert pack.family == "Electrical Engineering"
    seniority_ids = {t.id for t in pack.titles if t.group_type == "seniority"}
    assert seniority_ids == {"senior", "lead", "principal", "design_lead"}
    assert {s.name for s in pack.specializations} == {
        "Data Center / Mission Critical",
        "Building Services / MEP",
        "Industrial Power",
    }


# ---------------------------------------------------------------------------
# Positive: Lead Electrical Engineer, mission-critical data center, Frankfurt
# ---------------------------------------------------------------------------


def test_lead_electrical_engineer_data_center_frankfurt_is_detected():
    jd = (
        "We are hiring a Lead Electrical Engineer for our mission critical "
        "data center campus in Frankfurt."
    )
    spec, variants = generate_xray_queries(jd)

    assert spec.job_family == "Electrical Engineering"
    assert spec.specialization == "Data Center / Mission Critical"
    assert "Lead Electrical Engineer" in spec.titles
    assert "Data Center / Mission Critical" in spec.industries
    assert "Frankfurt" in spec.locations
    assert '"Lead Electrical Engineer"' in variants.strict


def test_electrical_engineer_photovoltaic_does_not_receive_data_center_terms():
    jd = "We are hiring an Electrical Engineer for our photovoltaic solar farm projects."
    spec, _ = generate_xray_queries(jd)

    assert spec.job_family == "Electrical Engineering"
    assert spec.specialization is None
    assert spec.industries == []
    assert not any(
        term in (spec.skills.must + spec.skills.important + spec.skills.nice_to_have)
        for term in ("HV", "MV", "switchgear", "UPS", "transformer")
    )


# ---------------------------------------------------------------------------
# Positive: Senior Elektroingenieur, Rechenzentren + Mittelspannung (German)
# ---------------------------------------------------------------------------


def test_senior_elektroingenieur_rechenzentren_mittelspannung_is_detected():
    jd = (
        "Für unser Team in München suchen wir einen Senior Elektroingenieur "
        "für Rechenzentren und Mittelspannung."
    )
    spec, _ = generate_xray_queries(jd)

    assert spec.job_family == "Electrical Engineering"
    assert spec.specialization == "Data Center / Mission Critical"
    assert "Senior Elektroingenieur" in spec.titles
    assert "Data Center / Mission Critical" in spec.industries
    assert "Mittelspannung" in spec.skills.must + spec.skills.important + spec.skills.nice_to_have


def test_software_engineer_data_center_monitoring_is_not_electrical_engineering():
    jd = (
        "We are hiring a Software Engineer to build monitoring dashboards "
        "for our data center infrastructure."
    )
    spec, _ = generate_xray_queries(jd)

    assert spec.job_family is None
    assert any("no job family matched" in w.lower() for w in spec.warnings)


# ---------------------------------------------------------------------------
# Positive: Electrical Design Lead, switchgear + UPS
# ---------------------------------------------------------------------------


def test_electrical_design_lead_switchgear_ups_is_detected():
    jd = (
        "We are hiring an Electrical Design Lead. Switchgear design experience "
        "is required. UPS system knowledge is a plus."
    )
    spec, variants = generate_xray_queries(jd)

    assert spec.job_family == "Electrical Engineering"
    assert "Electrical Design Lead" in spec.titles
    assert "switchgear" in spec.skills.must
    assert "UPS" in spec.skills.nice_to_have
    assert '"Electrical Design Lead"' not in variants.hidden_titles


def test_electrician_and_electrical_technician_are_not_promoted_to_lead_engineer():
    jd = "This role is for an Electrician. Electrical Technician certification is a plus."
    spec, _ = generate_xray_queries(jd)

    assert spec.job_family is None
    assert "Lead Electrical Engineer" not in spec.titles
    assert not any("Electrical Engineer" in title for title in spec.titles)


# ---------------------------------------------------------------------------
# Positive/negative: "hyperscale"/"colocation" are strong standalone
# data-center specialization signals; a bare technical skill term
# (UPS/switchgear) is not — only specialization_signals feed
# specialization detection, never skill_groups (family_detector.py's
# `_score_specialization` never reads pack.skill_groups).
# ---------------------------------------------------------------------------


def test_hyperscale_alone_activates_data_center_specialization():
    jd = "We are hiring an Electrical Engineer for our hyperscale campus expansion."
    spec, _ = generate_xray_queries(jd)

    assert spec.specialization == "Data Center / Mission Critical"
    all_skills = spec.skills.must + spec.skills.important + spec.skills.nice_to_have
    assert "UPS" not in all_skills
    assert "switchgear" not in all_skills


def test_bare_skill_terms_alone_do_not_activate_specialization():
    jd = "We are hiring an Electrical Engineer. UPS and switchgear design experience required."
    spec, _ = generate_xray_queries(jd)

    assert spec.specialization is None
    assert spec.industries == []


# ---------------------------------------------------------------------------
# Positive/negative: new Digital Infrastructure / Engineering Consulting /
# Industrial Practice industries (Phase 5 additions)
# ---------------------------------------------------------------------------


def test_digital_infrastructure_industry_is_detected():
    jd = "We are hiring an Electrical Engineer supporting our digital infrastructure team."
    spec, _ = generate_xray_queries(jd)

    assert "Digital Infrastructure" in spec.industries


def test_consulting_firm_does_not_activate_engineering_consulting_industry():
    jd = "We are hiring an Electrical Engineer to join our consulting firm."
    spec, _ = generate_xray_queries(jd)

    assert "Engineering Consulting" not in spec.industries


# ---------------------------------------------------------------------------
# Positive/negative: new core_functions capability (Phase 4/5)
# ---------------------------------------------------------------------------


def test_technical_due_diligence_core_function_is_detected():
    jd = "We are hiring an Electrical Engineer to lead technical due diligence for site assessments."
    spec, _ = generate_xray_queries(jd)

    assert "Technical Due Diligence" in spec.core_functions


def test_generic_due_diligence_does_not_activate_core_function():
    jd = "We are hiring an Electrical Engineer to support due diligence activities for our projects."
    spec, _ = generate_xray_queries(jd)

    assert "Technical Due Diligence" not in spec.core_functions
