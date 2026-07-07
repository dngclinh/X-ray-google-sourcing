"""Deterministic job-family and specialization detection.

Takes a normalized Job Description and a set of loaded
`knowledge_loader.JobFamilyPack` instances and decides — using only
weighted matching against each pack's own explicit signals — which
family (and, optionally, specialization) the JD belongs to.

Per CLAUDE.md section 7, Core Function/family classification is
heuristic and must be flagged as such when evidence is thin. This
module never guesses a family when no pack has adequate support
("do not infer missing professions"): it always prefers returning no
match, or an ambiguity warning, over inventing a relationship the JD
doesn't support.

This module intentionally contains no profession-specific knowledge —
every term it matches against comes from the packs it's given — and no
extraction or query-assembly logic. It also does not decide which
packs to load; callers pass in whichever packs are relevant.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.xray.knowledge_loader import JobFamilyPack, Specialization
from src.xray.normalizer import contains_phrase, dedupe_preserve_order

#: Weight of a single matched `family_signals` phrase. Family signals are
#: a pack's own explicit, unambiguous declaration of "this JD is this
#: family" — the strongest evidence category, so a single match already
#: qualifies a pack as a candidate.
FAMILY_SIGNAL_WEIGHT = 1.0

#: Weight applied to a matched title term when its `TitleGroup` doesn't
#: set an explicit weight. Titles are specific evidence (like family
#: signals), so — like family signals — a single match qualifies.
DEFAULT_TITLE_WEIGHT = 0.6

#: Weight applied to a matched skill term when its `SkillGroup` doesn't
#: set an explicit weight. Skills are generic/ambiguous evidence: they
#: are commonly shared across families, so on their own they never
#: qualify a pack (see `MIN_GENERIC_SIGNALS`).
DEFAULT_SKILL_WEIGHT = 0.3

#: Weight applied to a matched industry term when its `Industry` entry
#: doesn't set an explicit weight. Industry keywords are generic
#: evidence for the same reason as skills — a single industry keyword
#: must never outrank real family evidence.
DEFAULT_INDUSTRY_WEIGHT = 0.25

#: Weight applied to a matched specialization term when the
#: `Specialization` entry doesn't set an explicit weight.
DEFAULT_SPECIALIZATION_WEIGHT = 0.6

#: Weight of a single matched `specialization_signals` phrase.
SPECIALIZATION_SIGNAL_WEIGHT = 0.5

#: Minimum number of distinct generic (skill/industry) signal terms
#: required for a pack to qualify as a candidate when it has no
#: specific (family-signal or title) evidence at all. This is what
#: prevents a single generic/ambiguous term — e.g. one shared industry
#: keyword — from classifying a family on its own.
MIN_GENERIC_SIGNALS = 2

#: Confidence is reported on a 0.0-1.0 scale even though raw weighted
#: scores can exceed 1.0 when several signals match.
CONFIDENCE_CAP = 1.0

#: Number of decimal places scores are rounded to before comparing them
#: for ties, to avoid spurious float-precision mismatches.
_TIE_ROUNDING = 6


@dataclass(frozen=True)
class FamilyDetectionResult:
    """Result of `detect_family`.

    - `family` / `specialization` are `None` whenever there isn't a
      single confident, unambiguous winner (CLAUDE.md section 7: do not
      present a guess as certain).
    - `confidence` is 0.0 when there is no match.
    - `matched_signals` maps a pack schema category (e.g.
      `"family_signals"`, `"titles"`) to the literal pack-defined terms
      that matched, for traceability/QA — mirrors the shape of
      `SearchSpec.matched_signals`.
    - `warnings` explains no-match and ambiguous-match outcomes in
      plain language.
    """

    family: str | None
    specialization: str | None
    confidence: float
    matched_signals: dict[str, tuple[str, ...]]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Match:
    category: str
    term: str
    weight: float


def _weight_or_default(weight: float | None, default: float) -> float:
    return weight if weight is not None else default


def _score_pack(jd: str, pack: JobFamilyPack) -> tuple[float, list[_Match], bool]:
    """Score one pack against the JD.

    Returns `(score, matches, qualifies)`. `qualifies` is False whenever
    the only evidence found is fewer than `MIN_GENERIC_SIGNALS` distinct
    generic (skill/industry) terms with no specific (family-signal or
    title) evidence at all — in that case `score` is 0.0 and the pack
    must be excluded from consideration entirely, per the requirement
    that a single generic term never classifies a family on its own.
    """
    matches: list[_Match] = []
    has_specific_evidence = False

    for signal in pack.family_signals:
        if contains_phrase(jd, signal):
            matches.append(_Match("family_signals", signal, FAMILY_SIGNAL_WEIGHT))
            has_specific_evidence = True

    for title in pack.titles:
        weight = _weight_or_default(title.weight, DEFAULT_TITLE_WEIGHT)
        for term in title.terms:
            if contains_phrase(jd, term):
                matches.append(_Match("titles", term, weight))
                has_specific_evidence = True

    generic_terms_seen: set[str] = set()

    for skill in pack.skill_groups:
        weight = _weight_or_default(skill.weight, DEFAULT_SKILL_WEIGHT)
        for term in skill.terms:
            if contains_phrase(jd, term):
                matches.append(_Match("skill_groups", term, weight))
                generic_terms_seen.add(term)

    for industry in pack.industries:
        weight = _weight_or_default(industry.weight, DEFAULT_INDUSTRY_WEIGHT)
        for term in industry.terms:
            if contains_phrase(jd, term):
                matches.append(_Match("industries", term, weight))
                generic_terms_seen.add(term)

    qualifies = has_specific_evidence or len(generic_terms_seen) >= MIN_GENERIC_SIGNALS
    if not qualifies:
        return 0.0, [], False

    score = sum(match.weight for match in matches)
    return score, matches, True


def _score_specialization(jd: str, pack: JobFamilyPack, spec: Specialization) -> tuple[float, list[_Match]]:
    weight = _weight_or_default(spec.weight, DEFAULT_SPECIALIZATION_WEIGHT)
    matches: list[_Match] = []

    for term in spec.terms:
        if contains_phrase(jd, term):
            matches.append(_Match("specialization_terms", term, weight))

    for signal in pack.specialization_signals.get(spec.id, ()):
        if contains_phrase(jd, signal):
            matches.append(_Match("specialization_signals", signal, SPECIALIZATION_SIGNAL_WEIGHT))

    return sum(match.weight for match in matches), matches


def _group_matches(matches: Iterable[_Match]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for match in matches:
        grouped.setdefault(match.category, []).append(match.term)
    return {category: tuple(dedupe_preserve_order(terms)) for category, terms in grouped.items()}


def _detect_specialization(
    jd: str, pack: JobFamilyPack
) -> tuple[str | None, dict[str, tuple[str, ...]], str | None]:
    """Pick the winning specialization within an already-selected pack.

    Returns `(specialization_name, matched_signals, warning)`.
    Specialization terms/signals are curated, specific cues (like
    family signals), so — unlike family detection — a single matched
    signal is sufficient; there is no generic-evidence category at the
    specialization level to guard against.
    """
    if not pack.specializations:
        return None, {}, None

    scored = [
        (spec, *_score_specialization(jd, pack, spec))
        for spec in pack.specializations
    ]
    scored = [(spec, score, matches) for spec, score, matches in scored if matches]
    if not scored:
        return None, {}, None

    top_score = round(max(score for _, score, _ in scored), _TIE_ROUNDING)
    winners = [
        (spec, score, matches)
        for spec, score, matches in scored
        if round(score, _TIE_ROUNDING) == top_score
    ]

    if len(winners) > 1:
        tied_names = sorted({spec.name for spec, _, _ in winners})
        warning = (
            f"Ambiguous specialization match between {', '.join(tied_names)} "
            f"within {pack.family!r}; no specialization was selected."
        )
        return None, {}, warning

    winner_spec, _, winner_matches = winners[0]
    return winner_spec.name, _group_matches(winner_matches), None


def detect_family(
    normalized_jd: str, packs: Iterable[JobFamilyPack]
) -> FamilyDetectionResult:
    """Detect the job family (and, optionally, specialization) for a JD.

    `normalized_jd` should already have had generic whitespace
    normalization applied (see `normalizer.normalize_whitespace`); this
    function performs its own Unicode-safe, phrase-boundary matching on
    top of that (see `normalizer.contains_phrase`).

    `packs` is every job-family pack the caller wants considered — this
    function does not decide which packs are relevant, and never
    fabricates a family for a JD that matches none of them.
    """
    candidates: list[tuple[JobFamilyPack, float, list[_Match]]] = []
    for pack in packs:
        score, matches, qualifies = _score_pack(normalized_jd, pack)
        if qualifies:
            candidates.append((pack, score, matches))

    if not candidates:
        return FamilyDetectionResult(
            family=None,
            specialization=None,
            confidence=0.0,
            matched_signals={},
            warnings=("No job family matched the job description.",),
        )

    top_score = round(max(score for _, score, _ in candidates), _TIE_ROUNDING)
    winners = [
        (pack, score, matches)
        for pack, score, matches in candidates
        if round(score, _TIE_ROUNDING) == top_score
    ]

    if len(winners) > 1:
        tied_names = sorted({pack.family for pack, _, _ in winners})
        return FamilyDetectionResult(
            family=None,
            specialization=None,
            confidence=min(top_score, CONFIDENCE_CAP),
            matched_signals={},
            warnings=(
                f"Ambiguous job family match between {', '.join(tied_names)}; "
                "no family was selected.",
            ),
        )

    winner_pack, winner_score, winner_matches = winners[0]
    matched_signals = _group_matches(winner_matches)

    specialization, specialization_signals, specialization_warning = _detect_specialization(
        normalized_jd, winner_pack
    )
    for category, terms in specialization_signals.items():
        matched_signals[category] = tuple(
            dedupe_preserve_order((*matched_signals.get(category, ()), *terms))
        )

    warnings = (specialization_warning,) if specialization_warning else ()

    return FamilyDetectionResult(
        family=winner_pack.family,
        specialization=specialization,
        confidence=min(winner_score, CONFIDENCE_CAP),
        matched_signals=matched_signals,
        warnings=warnings,
    )
