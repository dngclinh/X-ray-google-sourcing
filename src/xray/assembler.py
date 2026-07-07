"""Deterministic Boolean query assembly.

Turns a `SearchSpec` (CLAUDE.md section 5) into the four required
`QueryVariants` (CLAUDE.md section 6): strict, balanced, broad, and
hidden_titles. This is the query-construction step that sits *after*
extraction (`extractor.py`) and family/specialization detection
(`family_detector.py`) — it never re-derives evidence, never adds a
term that isn't already present in the `SearchSpec` it's given
("only activated evidence may be used" / "do not insert every pack
term automatically"), and never mutates the `SearchSpec` it reads.

Important naming note: `SearchSpec.source` holds a JD identifier for
traceability (set by `extractor.py`) and, per the jd-to-xray rules,
never appears in the Boolean string itself. The `site:` prefix that
*does* open every assembled query ("source remains first") is instead
resolved fresh here via `source_resolver.resolve_source_for_spec`,
which reads `SearchSpec.locations` — never `SearchSpec.source`.

Variant design (reconciling CLAUDE.md section 6's general framework
with this module's concrete per-variant requirements):

- Strict ANDs every available signal as its own clause: titles,
  core-function evidence, industry evidence (as two separate clauses,
  requiring both dimensions), each MUST skill individually, each
  explicit MUST-tier language/company-type requirement individually,
  and location. This is the maximum number of required AND'd clauses,
  making it the narrowest variant.
- Balanced keeps titles, each MUST skill, and location, but only ANDs
  a single "strongest" evidence clause (core-function or industry,
  picked via `SearchSpec.confidence` when available) instead of both,
  adds IMPORTANT-tier skills as one additional OR'd clause (CLAUDE.md
  section 6: "MUST + IMPORTANT criteria"), and drops the
  language/company-type MUST clauses entirely ("reduced optional
  filtering" relative to Strict).
- Broad keeps titles and location, but merges core-function and
  industry evidence into a single OR'd clause (matching on *either*
  dimension, the widest of the three evidence strategies) and drops
  skill filtering entirely — the intentionally skill-agnostic, title-
  and-domain-driven variant.
- Hidden Titles is Broad's mirror image: it drops the title clause
  entirely ("reduce or omit conventional title dependence") and
  substitutes a skill-evidence clause (MUST + IMPORTANT + NICE-TO-HAVE
  skills merged into one OR'd clause) alongside the same merged
  core-function/industry evidence clause and location — finding
  candidates via domain + skill signal regardless of their title.

Exclusions are applied identically across all four variants: CLAUDE.md
section 6 says variants scale skill/synonym breadth, and
`SearchSpec.exclusions` carries no severity tier to further subset by
without inventing one — narrowing it per-variant would be a
speculative rule the data doesn't support.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.xray.glossary import Glossary
from src.xray.models import QueryVariants, SearchSpec
from src.xray.normalizer import dedupe_preserve_order, quote_boolean_term
from src.xray.source_resolver import resolve_source_for_spec

_DEFAULT_GLOSSARY: Glossary | None = None


def _default_glossary() -> Glossary:
    global _DEFAULT_GLOSSARY
    if _DEFAULT_GLOSSARY is None:
        _DEFAULT_GLOSSARY = Glossary.load()
    return _DEFAULT_GLOSSARY


# ---------------------------------------------------------------------------
# Group-building primitives (General rules: OR within a group, quoting,
# no empty parentheses, stable dedup)
# ---------------------------------------------------------------------------


def _dedupe_and_quote(terms: Iterable[str]) -> list[str]:
    return [quote_boolean_term(term) for term in dedupe_preserve_order(terms)]


def _or_group(terms: Iterable[str]) -> str:
    """One parenthesized OR group of synonymous/equivalent terms.

    Returns `""` (never `"()"`) when `terms` has nothing in it, so
    callers can filter it out and never emit an empty group.
    """
    quoted = _dedupe_and_quote(terms)
    if not quoted:
        return ""
    return "(" + " OR ".join(quoted) + ")"


def _and_single_term_clauses(terms: Iterable[str]) -> list[str]:
    """Each distinct term becomes its own required, independent clause.

    Used for MUST-tier skills/language/company-type requirements: these
    are distinct concepts extracted independently (not synonyms of one
    another), so per the jd-to-xray rules ("each distinct skill/concept
    gets its own OR group... combined with AND between groups") they
    must be ANDed as separate clauses rather than OR'd together.
    """
    return [f"({term})" for term in _dedupe_and_quote(terms)]


def _exclusion_clauses(terms: Iterable[str]) -> list[str]:
    return [f"NOT {term}" for term in _dedupe_and_quote(terms)]


def _join_variant(source: str, positive_clauses: list[str], exclusion_clauses: list[str]) -> str:
    clauses = [clause for clause in positive_clauses if clause] + exclusion_clauses
    if not clauses:
        return source
    return source + " " + " AND ".join(clauses)


# ---------------------------------------------------------------------------
# Evidence (core function / industry) group strategies
# ---------------------------------------------------------------------------


def _strongest_evidence_group(spec: SearchSpec) -> str:
    """The single "strongest" of core-function vs. industry evidence.

    Preferred by `SearchSpec.confidence` when available; defaults to
    core-function evidence on a tie or when neither has a recorded
    confidence, since Core Function is the more fundamental
    classification (CLAUDE.md section 7).
    """
    core_score = spec.confidence.get("core_functions", 0.0) if spec.core_functions else None
    industry_score = spec.confidence.get("industries", 0.0) if spec.industries else None

    if core_score is None and industry_score is None:
        return ""
    if industry_score is not None and (core_score is None or industry_score > core_score):
        return _or_group(spec.industries)
    return _or_group(spec.core_functions)


def _merged_evidence_group(spec: SearchSpec) -> str:
    """Core-function and industry evidence merged into one OR group."""
    return _or_group([*spec.core_functions, *spec.industries])


# ---------------------------------------------------------------------------
# Skill group strategies
# ---------------------------------------------------------------------------


def _must_skill_clauses(spec: SearchSpec) -> list[str]:
    return _and_single_term_clauses(spec.skills.must)


def _important_skill_group(spec: SearchSpec) -> str:
    return _or_group(spec.skills.important)


def _all_skill_evidence_group(spec: SearchSpec) -> str:
    return _or_group([*spec.skills.must, *spec.skills.important, *spec.skills.nice_to_have])


# ---------------------------------------------------------------------------
# Mandatory language / company-type clauses (Strict only)
# ---------------------------------------------------------------------------


def _mandatory_requirement_clauses(spec: SearchSpec) -> list[str]:
    return [
        *_and_single_term_clauses(spec.languages.must),
        *_and_single_term_clauses(spec.company_types.must),
    ]


# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------


def assemble(spec: SearchSpec, glossary: Glossary | None = None) -> QueryVariants:
    """Assemble the four required Boolean query variants from a `SearchSpec`.

    Reads only fields already populated on `spec` — it never expands
    beyond them (no automatic pack-term insertion) and never mutates
    `spec` (in particular, `spec.locations` is preserved regardless of
    whether a country-specific `site:` ccTLD is used).
    """
    glossary = glossary if glossary is not None else _default_glossary()
    source = resolve_source_for_spec(spec, glossary)

    title_group = _or_group(spec.titles)
    location_group = _or_group(spec.locations)
    exclusion_clauses = _exclusion_clauses(spec.exclusions)

    strict = _join_variant(
        source,
        [
            title_group,
            _or_group(spec.core_functions),
            _or_group(spec.industries),
            *_must_skill_clauses(spec),
            *_mandatory_requirement_clauses(spec),
            location_group,
        ],
        exclusion_clauses,
    )

    balanced = _join_variant(
        source,
        [
            title_group,
            _strongest_evidence_group(spec),
            *_must_skill_clauses(spec),
            _important_skill_group(spec),
            location_group,
        ],
        exclusion_clauses,
    )

    broad = _join_variant(
        source,
        [
            title_group,
            _merged_evidence_group(spec),
            location_group,
        ],
        exclusion_clauses,
    )

    hidden_titles = _join_variant(
        source,
        [
            _merged_evidence_group(spec),
            _all_skill_evidence_group(spec),
            location_group,
        ],
        exclusion_clauses,
    )

    return QueryVariants(strict=strict, balanced=balanced, broad=broad, hidden_titles=hidden_titles)
