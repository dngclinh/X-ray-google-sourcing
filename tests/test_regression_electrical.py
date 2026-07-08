"""Deterministic regression benchmark for the Electrical Engineering
production pack (`knowledge/job_families/electrical_engineering.yaml`).

This is a *property-based* benchmark, not a full-string-equality one:
per CLAUDE.md section 1, the engine only needs to reach functional
equivalence with the approved Claude (`jd-to-xray`) benchmark output, not
byte-for-byte identity, so each fixture below asserts the specific,
named properties that matter for that fixture (detected family/
specialization, required/forbidden title or skill terms, required
locations, source domain, warning expectations, query-variant ordering)
rather than pinning the full assembled Boolean string. See
`docs/benchmark-method.md` for how this deterministic property harness
relates to the weighted scoring method used to track full functional
equivalence against Claude-authored benchmark output over time.

Every fixture is run through the real, default `generate_xray_queries`
pipeline (the production `knowledge/job_families/` directory), the same
way `tests/test_job_family_electrical_engineering.py` does — this suite
is deliberately not isolated from production knowledge, since pinning
down real production behavior is the point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pytest

from src.xray import generate_xray_queries
from tests.fixtures.electrical_jds import (
    ADJACENT_FAMILY_ELECTRICIAN_EN_JD,
    ADJACENT_FAMILY_MECHANICAL_ENGINEER_EN_JD,
    AMBIGUOUS_SPECIALIZATION_EN_JD,
    COMPANY_INTRODUCTION_FALSE_POSITIVE_EN_JD,
    LONG_IMPLICIT_SENIORITY_DATA_CENTER_EN_JD,
    LONG_INDUSTRIAL_POWER_DE_JD,
    MANDATORY_LANGUAGE_EN_JD,
    MULTI_COUNTRY_GERMANY_POLAND_EN_JD,
    OPTIONAL_LANGUAGE_EN_JD,
    REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD,
    SHORT_EXPLICIT_SENIORITY_BUILDING_SERVICES_DE_JD,
    SHORT_EXPLICIT_SENIORITY_EN_JD,
    SINGLE_COUNTRY_POLAND_EN_JD,
    UNSUPPORTED_FAMILY_EN_JD,
)

#: The six industry names the pack defines, for concise "no industry
#: evidence at all" assertions (`forbidden_industries`).
_ALL_INDUSTRY_NAMES = (
    "Data Center / Mission Critical",
    "Building Services / MEP",
    "Industrial Power",
    "Digital Infrastructure",
    "Engineering Consulting",
    "Industrial Practice",
)

#: The pack's every seniority-tier + base title term, for concise
#: "no title evidence at all" assertions on adjacent/unsupported-family
#: fixtures (`forbidden_titles`).
_ALL_ENGINEER_TITLE_TERMS = (
    "Electrical Engineer",
    "Senior Electrical Engineer",
    "Lead Electrical Engineer",
    "Principal Electrical Engineer",
    "Electrical Design Lead",
    "Elektroingenieur",
)


def _word_present(term: str, text: str) -> bool:
    """Whole-word (not substring) case-insensitive presence check.

    Mirrors `src/xray/normalizer.contains_phrase`'s boundary rule, used
    here only for `ExpectedProperties.forbidden_query_terms` so that a
    forbidden bare word like "German" is never mistakenly reported as
    present merely because the unrelated word "Germany" appears in the
    assembled query.
    """
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None


@dataclass(frozen=True)
class ExpectedProperties:
    """The subset of a `(SearchSpec, QueryVariants)` result a benchmark
    fixture asserts. Every field is a *property* check (membership,
    prefix, substring, warning-text) rather than full-string equality —
    only add a full-string assertion outside this harness where exact
    stability genuinely matters (none of the fixtures here need one).
    """

    #: Required — every fixture must state its expected family and
    #: specialization explicitly (`None` is a legitimate, asserted value
    #: for "no match", not an unset default).
    family: str | None
    specialization: str | None

    required_titles: tuple[str, ...] = ()
    forbidden_titles: tuple[str, ...] = ()

    required_industries: tuple[str, ...] = ()
    forbidden_industries: tuple[str, ...] = ()

    #: tier -> terms, tier in {"must", "important", "nice_to_have"}.
    required_skills: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Forbidden across all three skill tiers combined.
    forbidden_skill_terms: tuple[str, ...] = ()

    required_locations: tuple[str, ...] = ()
    forbidden_locations: tuple[str, ...] = ()

    #: `SearchSpec.core_functions` is a flat list (not tiered).
    required_core_functions: tuple[str, ...] = ()
    forbidden_core_functions: tuple[str, ...] = ()

    #: tier -> terms, tier in {"must", "important", "nice_to_have"}.
    required_languages: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Forbidden across all three language tiers combined.
    forbidden_language_terms: tuple[str, ...] = ()

    #: Forbidden across all three company-type tiers combined.
    forbidden_company_types: tuple[str, ...] = ()

    #: Every assembled variant must start with this `site:` prefix.
    source_prefix: str | None = None

    #: Case-insensitive substring that must appear in at least one
    #: `SearchSpec.warnings` entry.
    warning_contains: tuple[str, ...] = ()
    #: Case-insensitive substring that must appear in no warning.
    warning_absent: tuple[str, ...] = ()

    #: variant name -> substrings required in that assembled query text.
    required_variant_substrings: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: variant name -> substrings forbidden in that assembled query text.
    forbidden_variant_substrings: dict[str, tuple[str, ...]] = field(default_factory=dict)

    #: Whole words forbidden anywhere across all four assembled variants.
    forbidden_query_terms: tuple[str, ...] = ()

    #: Assert none of `required_titles`, quoted, appear in Hidden Titles
    #: (CLAUDE.md section 6: Hidden Titles omits the title clause).
    check_hidden_titles_omits_titles: bool = False


BENCHMARK_CASES: list[tuple[str, str, ExpectedProperties]] = [
    (
        "short_explicit_seniority_en",
        SHORT_EXPLICIT_SENIORITY_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Senior Electrical Engineer",),
            forbidden_industries=_ALL_INDUSTRY_NAMES,
            required_locations=("Munich", "Germany"),
            source_prefix="site:de.linkedin.com/in/",
            required_variant_substrings={"strict": ('"Senior Electrical Engineer"',)},
            check_hidden_titles_omits_titles=True,
        ),
    ),
    (
        "long_implicit_seniority_data_center_en",
        LONG_IMPLICIT_SENIORITY_DATA_CENTER_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization="Data Center / Mission Critical",
            required_titles=("Electrical Engineer",),
            required_industries=("Data Center / Mission Critical",),
            forbidden_industries=("Building Services / MEP", "Industrial Power"),
            required_skills={
                "must": ("medium voltage", "switchgear"),
                "important": ("HV", "MV", "transformers"),
                "nice_to_have": ("UPS", "emergency power"),
            },
            required_locations=("Frankfurt", "Germany"),
            source_prefix="site:de.linkedin.com/in/",
            check_hidden_titles_omits_titles=True,
        ),
    ),
    (
        "short_explicit_seniority_building_services_de",
        SHORT_EXPLICIT_SENIORITY_BUILDING_SERVICES_DE_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization="Building Services / MEP",
            required_titles=("Leitender Elektroingenieur",),
            required_industries=("Building Services / MEP",),
            forbidden_industries=("Data Center / Mission Critical", "Industrial Power"),
            required_locations=("Berlin",),
            source_prefix="site:de.linkedin.com/in/",
            check_hidden_titles_omits_titles=True,
        ),
    ),
    (
        "long_industrial_power_de",
        LONG_INDUSTRIAL_POWER_DE_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization="Industrial Power",
            required_titles=("Principal Elektroingenieur",),
            required_industries=("Industrial Power",),
            forbidden_industries=("Data Center / Mission Critical", "Building Services / MEP"),
            # German priority cues ("zwingend erforderlich", "von
            # Vorteil") are not in the English-only priority_cues.yaml
            # dictionary, so both terms fall back to "important" rather
            # than the must/nice-to-have tiers a German reader would
            # expect — a deliberate demonstration of the CLAUDE.md
            # section 7 known limitation, not a bug in this fixture.
            required_skills={"important": ("Stromverteilung", "Frequenzumrichter")},
            required_locations=("Nuremberg",),
            source_prefix="site:de.linkedin.com/in/",
            check_hidden_titles_omits_titles=True,
        ),
    ),
    (
        "multi_country_germany_poland_en",
        MULTI_COUNTRY_GERMANY_POLAND_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Electrical Engineer",),
            forbidden_industries=_ALL_INDUSTRY_NAMES,
            required_locations=("Frankfurt", "Germany", "Warsaw", "Poland"),
            source_prefix="site:linkedin.com/in/",
        ),
    ),
    (
        "mandatory_language_en",
        MANDATORY_LANGUAGE_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Electrical Engineer",),
            required_locations=("Munich",),
            required_languages={"must": ("German",)},
            source_prefix="site:de.linkedin.com/in/",
            required_variant_substrings={"strict": ("(German)",)},
            forbidden_variant_substrings={"balanced": ("(German)",)},
        ),
    ),
    (
        "optional_language_en",
        OPTIONAL_LANGUAGE_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Electrical Engineer",),
            required_locations=("Munich",),
            required_languages={"nice_to_have": ("French",)},
            source_prefix="site:de.linkedin.com/in/",
            # Nice-to-have languages are extracted but never fed into
            # assembler.py (only SearchSpec.languages.must is) — so
            # "French" must not leak into any assembled query text.
            forbidden_query_terms=("French",),
        ),
    ),
    (
        "company_introduction_false_positive_en",
        COMPANY_INTRODUCTION_FALSE_POSITIVE_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Electrical Engineer",),
            # New (Phase 5): the JD's own "German engineering
            # consultancy" phrase legitimately contains "engineering
            # consultancy" — a real, correct Engineering Consulting
            # industry match, unrelated to the company-intro
            # language/company-type false positives this fixture exists
            # to test.
            required_industries=("Engineering Consulting",),
            required_locations=("Munich",),
            forbidden_language_terms=("German",),
            forbidden_company_types=("Consultancy",),
            forbidden_query_terms=("German", "Consultancy"),
            source_prefix="site:de.linkedin.com/in/",
        ),
    ),
    (
        "adjacent_family_electrician_en",
        ADJACENT_FAMILY_ELECTRICIAN_EN_JD,
        ExpectedProperties(
            family=None,
            specialization=None,
            forbidden_titles=_ALL_ENGINEER_TITLE_TERMS,
            forbidden_industries=_ALL_INDUSTRY_NAMES,
            warning_contains=("no job family matched",),
        ),
    ),
    (
        "adjacent_family_mechanical_engineer_en",
        ADJACENT_FAMILY_MECHANICAL_ENGINEER_EN_JD,
        ExpectedProperties(
            family=None,
            specialization=None,
            forbidden_titles=_ALL_ENGINEER_TITLE_TERMS,
            forbidden_industries=_ALL_INDUSTRY_NAMES,
            warning_contains=("no job family matched",),
        ),
    ),
    (
        "ambiguous_specialization_en",
        AMBIGUOUS_SPECIALIZATION_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Electrical Engineer",),
            required_industries=("Data Center / Mission Critical", "Building Services / MEP"),
            forbidden_industries=("Industrial Power",),
            required_locations=("Berlin",),
            warning_contains=("ambiguous",),
        ),
    ),
    (
        "unsupported_family_en",
        UNSUPPORTED_FAMILY_EN_JD,
        ExpectedProperties(
            family=None,
            specialization=None,
            forbidden_titles=_ALL_ENGINEER_TITLE_TERMS,
            forbidden_industries=_ALL_INDUSTRY_NAMES,
            warning_contains=("no job family matched",),
        ),
    ),
    (
        "single_country_poland_en",
        SINGLE_COUNTRY_POLAND_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization=None,
            required_titles=("Electrical Engineer",),
            forbidden_industries=_ALL_INDUSTRY_NAMES,
            required_locations=("Warsaw", "Poland"),
            source_prefix="site:pl.linkedin.com/in/",
        ),
    ),
    (
        "real_lead_electrical_engineer_data_center_due_diligence_en",
        REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD,
        ExpectedProperties(
            family="Electrical Engineering",
            specialization="Data Center / Mission Critical",
            required_titles=("Lead Electrical Engineer", "Electrical Engineer"),
            # Out-of-scope guard: Claude's benchmark infers these as
            # "equivalent" titles for this JD, but neither appears
            # literally in the JD text — the engine must never invent
            # title relationships the JD doesn't literally support.
            forbidden_titles=("Senior Electrical Engineer", "Electrical Design Lead"),
            required_industries=(
                "Data Center / Mission Critical",
                "Digital Infrastructure",
                "Engineering Consulting",
                "Industrial Practice",
            ),
            # "Building Services / MEP" is NOT forbidden here: the
            # required skill "Revit MEP" (a BIM software name) contains
            # "MEP" as a substring-safe whole word, which is also the
            # pack's existing Building Services specialization signal —
            # an accepted, minor precision trade-off (removing bare
            # "MEP" would break the already-approved
            # AMBIGUOUS_SPECIALIZATION_EN_JD fixture, which relies on it
            # as one of its two tied specialization signals).
            forbidden_industries=("Industrial Power",),
            required_locations=("Germany", "Poland"),
            forbidden_locations=("Berlin",),
            # Two distinct countries -> global fallback.
            source_prefix="site:linkedin.com/in/",
            # spec.core_functions holds the CoreFunction's name (like
            # spec.industries holds Industry.name), not the literal
            # matched term.
            required_core_functions=(
                "Technical Due Diligence",
                "Electrical Planning",
                "Multidisciplinary Coordination",
                "Stakeholder Communication",
            ),
            required_skills={
                "important": (
                    "HV", "MV", "grid connection",
                    "UPS", "standby generation", "busbar", "switchgear",
                    "hyperscale", "colocation", "Tier III", "Tier IV",
                    "greenfield", "brownfield",
                    "BIM", "feasibility studies",
                    "utility availability", "constraints on power delivery",
                    "planning and permitting",
                ),
                "nice_to_have": (
                    "BIM coordination", "Revit MEP", "Uptime Institute Tier standards",
                ),
            },
            required_languages={
                "important": ("German", "English"),
                "nice_to_have": ("Polish",),
            },
            # Correctly rejected today already (employer self-description,
            # no candidate-background context) — asserted as a baseline
            # sanity check, not a fix target of this benchmark case.
            forbidden_company_types=("Consultancy",),
        ),
    ),
]

assert len(BENCHMARK_CASES) >= 12, "benchmark corpus must cover at least 12 representative JDs"


def _all_variant_texts(variants) -> tuple[str, str, str, str]:
    return (variants.strict, variants.balanced, variants.broad, variants.hidden_titles)


def _variants_by_name(variants) -> dict[str, str]:
    return {
        "strict": variants.strict,
        "balanced": variants.balanced,
        "broad": variants.broad,
        "hidden_titles": variants.hidden_titles,
    }


_SOURCE_PREFIX_RE = re.compile(r"^site:\S+\s*")


def _clause_count(variant_text: str) -> int:
    """Count top-level `AND`-joined clauses, mirroring
    `src/xray/validator._extract_clauses` (kept local/duplicated rather
    than imported since it is a private module helper)."""
    body = _SOURCE_PREFIX_RE.sub("", variant_text, count=1)
    if not body:
        return 0
    return len([clause for clause in body.split(" AND ") if clause.strip()])


@pytest.mark.parametrize(
    "name, jd_text, expected",
    BENCHMARK_CASES,
    ids=[case[0] for case in BENCHMARK_CASES],
)
def test_electrical_engineering_benchmark(name: str, jd_text: str, expected: ExpectedProperties):
    spec, variants = generate_xray_queries(jd_text)

    assert spec.job_family == expected.family, f"{name}: job_family mismatch"
    assert spec.specialization == expected.specialization, f"{name}: specialization mismatch"

    for term in expected.required_titles:
        assert term in spec.titles, f"{name}: expected title {term!r} missing from {spec.titles!r}"
    for term in expected.forbidden_titles:
        assert term not in spec.titles, f"{name}: forbidden title {term!r} present in {spec.titles!r}"

    for term in expected.required_industries:
        assert term in spec.industries, f"{name}: expected industry {term!r} missing"
    for term in expected.forbidden_industries:
        assert term not in spec.industries, f"{name}: forbidden industry {term!r} present"

    for tier, terms in expected.required_skills.items():
        bucket = getattr(spec.skills, tier)
        for term in terms:
            assert term in bucket, f"{name}: expected skill {term!r} in tier {tier!r} missing"
    all_skills = [*spec.skills.must, *spec.skills.important, *spec.skills.nice_to_have]
    for term in expected.forbidden_skill_terms:
        assert term not in all_skills, f"{name}: forbidden skill term {term!r} present"

    for term in expected.required_locations:
        assert term in spec.locations, f"{name}: expected location {term!r} missing from {spec.locations!r}"
    for term in expected.forbidden_locations:
        assert term not in spec.locations, f"{name}: forbidden location {term!r} present in {spec.locations!r}"

    for term in expected.required_core_functions:
        assert term in spec.core_functions, (
            f"{name}: expected core function {term!r} missing from {spec.core_functions!r}"
        )
    for term in expected.forbidden_core_functions:
        assert term not in spec.core_functions, f"{name}: forbidden core function {term!r} present"

    for tier, terms in expected.required_languages.items():
        bucket = getattr(spec.languages, tier)
        for term in terms:
            assert term in bucket, f"{name}: expected language {term!r} in tier {tier!r} missing"
    all_languages = [*spec.languages.must, *spec.languages.important, *spec.languages.nice_to_have]
    for term in expected.forbidden_language_terms:
        assert term not in all_languages, f"{name}: forbidden language term {term!r} present"

    all_company_types = [
        *spec.company_types.must,
        *spec.company_types.important,
        *spec.company_types.nice_to_have,
    ]
    for term in expected.forbidden_company_types:
        assert term not in all_company_types, f"{name}: forbidden company type {term!r} present"

    if expected.source_prefix is not None:
        for text in _all_variant_texts(variants):
            assert text.startswith(expected.source_prefix), (
                f"{name}: expected source prefix {expected.source_prefix!r}, got {text!r}"
            )

    for keyword in expected.warning_contains:
        assert any(keyword.lower() in w.lower() for w in spec.warnings), (
            f"{name}: expected a warning containing {keyword!r}, got {spec.warnings!r}"
        )
    for keyword in expected.warning_absent:
        assert not any(keyword.lower() in w.lower() for w in spec.warnings), (
            f"{name}: forbidden warning substring {keyword!r} present in {spec.warnings!r}"
        )

    by_name = _variants_by_name(variants)
    for variant_name, substrings in expected.required_variant_substrings.items():
        for substring in substrings:
            assert substring in by_name[variant_name], (
                f"{name}: expected {substring!r} in {variant_name}, got {by_name[variant_name]!r}"
            )
    for variant_name, substrings in expected.forbidden_variant_substrings.items():
        for substring in substrings:
            assert substring not in by_name[variant_name], (
                f"{name}: forbidden {substring!r} in {variant_name}, got {by_name[variant_name]!r}"
            )

    for term in expected.forbidden_query_terms:
        for variant_name, text in by_name.items():
            assert not _word_present(term, text), (
                f"{name}: forbidden term {term!r} present in {variant_name}: {text!r}"
            )

    # Universal query-variant ordering property: Strict always carries at
    # least as many required AND clauses as Broad. This holds structurally
    # for every fixture regardless of content — assembler.py builds Broad
    # from a strict subset of Strict's clause-producing inputs (title,
    # one merged evidence clause, location) and never adds anything Strict
    # lacks, while Strict can only add more (MUST skills, MUST-tier
    # language/company-type). A pairwise Strict-strictly-narrower-than-
    # Balanced (or Balanced-than-Broad) clause-count check is deliberately
    # *not* asserted here: `SearchSpec.core_functions` IS now populated by
    # extraction, but `SearchSpec.confidence` (which
    # `assembler._strongest_evidence_group` uses to pick Balanced's single
    # evidence clause between core-function and industry evidence) is
    # still never populated by extraction — so Balanced's evidence clause
    # can still tie Strict's merged-evidence clause count depending on
    # pack content, making that specific pairwise check unreliable
    # regardless of pack content (see docs/benchmark-method.md's "Known
    # limitations").
    assert _clause_count(variants.strict) >= _clause_count(variants.broad), (
        f"{name}: Strict has fewer clauses than Broad ({variants.strict!r} vs {variants.broad!r})"
    )

    if expected.check_hidden_titles_omits_titles:
        for term in expected.required_titles:
            quoted = f'"{term}"' if " " in term else term
            assert quoted not in variants.hidden_titles, (
                f"{name}: Hidden Titles must omit {quoted!r}, got {variants.hidden_titles!r}"
            )


def test_real_lead_electrical_engineer_jd_has_no_must_tier_skills():
    """No MUST-tier priority-cue phrase (`required`/`mandatory`/`essential`/
    etc., per `knowledge/priority_cues.yaml`) appears anywhere in this real
    JD's text — every technical term therefore correctly defaults to
    `important`, and the one segment carrying the literal "a plus" cue
    correctly lands in `nice_to_have`. This is a genuine, honest limitation
    (CLAUDE.md section 7: MUST/IMPORTANT/NICE classification is reliable
    only when the JD contains an explicit cue) to assert as-is, not a
    defect to work around — a one-off property not worth a generic
    `ExpectedProperties` field.
    """
    spec, _ = generate_xray_queries(REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD)
    assert spec.skills.must == []
