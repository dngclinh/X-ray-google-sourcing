"""Deterministic Job Description extraction.

Turns raw JD text into a `SearchSpec` (CLAUDE.md section 5) using only
generic, structural parsing plus lookups against the generic glossary
(`glossary.py`) and, optionally, one already-activated job-family pack
(`knowledge_loader.JobFamilyPack`).

Scope, per CLAUDE.md section 4:

- Sentence/bullet segmentation, label-line detection, CEFR-level-code
  detection, and priority-cue-driven MUST/IMPORTANT/NICE-TO-HAVE
  bucketing are category 1 generic deterministic logic — structural
  parsing, not profession knowledge.
- Location, language, company-type, seniority, and priority-cue
  *terms* all come from `Glossary` (dictionary-driven knowledge already
  under `knowledge/`). Title/skill/industry terms come only from the
  single `JobFamilyPack` the caller passes in as already "activated" —
  this module never decides which family applies (that is
  `family_detector.py`'s job) and never invents a profession-specific
  term of its own; with no pack given, zero profession-specific terms
  are extracted.
- A small, fixed set of English language-proficiency phrases (e.g.
  "fluent in") and title-introducing phrases (e.g. "we are hiring a")
  is treated as generic sentence-structure vocabulary — closed,
  grammatical patterns, not a growing curated dictionary — and is
  defined locally rather than in `knowledge/`.

This module does not assemble Boolean query strings (CLAUDE.md section
2/5) and does not decide which job-family pack is active.

Input contract: `extract()` takes the JD text as originally written,
with line breaks and bullet markers intact — sentence/bullet
segmentation (rule: "match requirements at sentence or bullet level
where practical") depends on that structure, so callers must not
pre-flatten whitespace across the whole document before calling this
function (unlike `family_detector.detect_family`, which does expect
pre-flattened text).
"""

from __future__ import annotations

import re

from src.xray.glossary import Glossary
from src.xray.knowledge_loader import JobFamilyPack
from src.xray.models import PrioritizedTerms, SearchSpec
from src.xray.normalizer import contains_phrase, dedupe_preserve_order, normalize_whitespace

# ---------------------------------------------------------------------------
# Generic structural patterns (CLAUDE.md category 1: small, fixed,
# purely grammatical/structural sets — not profession knowledge and not
# a growing curated dictionary).
# ---------------------------------------------------------------------------

_BULLET_PREFIX_RE = re.compile(r"^[ \t]*(?:[-*•‣▪]|\d+[.)])[ \t]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")

_TITLE_LABEL_RE = re.compile(r"(?i)^(?:job\s+title|position|role|title)\s*[:\-]\s*(?P<title>.+)$")
#: The trigger phrase and article are matched case-insensitively via a
#: *scoped* inline flag `(?i:...)` — the capturing group itself must stay
#: case-sensitive, since it relies on `[A-Z]` to identify title-case
#: words (a bare `(?i)` on the whole pattern would make `[A-Z]` match
#: lowercase words too, over-capturing trailing lowercase text).
_TITLE_TRIGGER_RE = re.compile(
    r"\b(?:(?i:hiring|looking for|seeking|searching for))\s+(?:(?i:an?|our))\s+"
    r"(?P<title>[A-Z][\w&/'-]*(?:\s+[A-Z][\w&/'-]*){0,4})"
)

_LANGUAGE_LABEL_RE = re.compile(r"(?i)^(?:languages?|language\s+(?:requirements?|skills?))\s*[:\-]")
_CEFR_LEVEL_RE = re.compile(r"(?i)\b[ABC][12]\b")
#: Fixed set of English phrases that structurally assert language
#: proficiency, regardless of which language follows them.
_LANGUAGE_PROFICIENCY_CUES = (
    "fluent in",
    "fluency in",
    "proficient in",
    "proficiency in",
    "native speaker of",
    "working knowledge of",
    "excellent command of",
    "written and spoken",
)

#: Phrases indicating the company-type mention describes the employer
#: itself ("our consultancy", "we are an EPC contractor") rather than a
#: candidate-background requirement.
_COMPANY_TYPE_NEGATIVE_CONTEXT_RE = re.compile(r"(?i)\b(?:our|we\s*'?re|we\s+are|us\s+as)\b")
#: Phrases confirming a company-type mention describes candidate
#: background ("experience in", "consultancy background", "worked
#: for an EPC contractor").
_COMPANY_TYPE_POSITIVE_CONTEXT_RE = re.compile(
    r"(?i)\b(?:experience|background|worked|work\s+history|track\s+record|"
    r"previously\s+worked|coming\s+from)\b"
)
#: How many characters immediately before a matched company-type term
#: are inspected for employer-self-reference context.
_COMPANY_TYPE_NEGATIVE_CONTEXT_WINDOW = 40

#: Merge precedence when the same term is matched more than once with
#: different priority buckets (e.g. in two different sentences).
_PRIORITY_RANK = {"must": 3, "important": 2, "nice_to_have": 1}


def _find_phrase(text: str, phrase: str) -> re.Match[str] | None:
    """Locate `phrase` in `text` on phrase boundaries, case-insensitively.

    Local to this module (rather than reusing
    `normalizer.contains_phrase`) because company-type context detection
    needs the match *position* to inspect nearby text, which the boolean
    `contains_phrase` deliberately doesn't expose.
    """
    escaped = re.escape(normalize_whitespace(phrase)).replace(r"\ ", r"\s+")
    pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    return pattern.search(text)


def _merge_priority(current: str | None, new: str) -> str:
    if current is None:
        return new
    return current if _PRIORITY_RANK[current] >= _PRIORITY_RANK[new] else new


def _to_prioritized_terms(bucket_by_term: dict[str, str]) -> PrioritizedTerms:
    result = PrioritizedTerms()
    for term, bucket in bucket_by_term.items():
        getattr(result, bucket).append(term)
    return result


def _split_into_blocks(jd_text: str) -> list[str]:
    """Group raw lines into paragraph/bullet-item blocks.

    A blank line or a new bullet marker starts a new block; any other
    line is a soft wrap continuing the current block (common when JD
    text is copy-pasted with fixed line widths) and is joined onto it
    with a space rather than treated as its own unit — otherwise a
    single sentence wrapped across two lines would be incorrectly cut
    in half before sentence-level matching ever runs.
    """
    blocks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            blocks.append(" ".join(current))
            current.clear()

    for raw_line in jd_text.splitlines():
        if not raw_line.strip():
            flush()
            continue
        if _BULLET_PREFIX_RE.match(raw_line):
            flush()
            current.append(_BULLET_PREFIX_RE.sub("", raw_line).strip())
        else:
            current.append(raw_line.strip())
    flush()
    return blocks


def _segment_jd(jd_text: str) -> list[str]:
    """Split JD text into sentence/bullet-level units.

    Implements the rule "match requirements at sentence or bullet level
    where practical": each output segment is either one bullet-list
    item or one sentence, so that context checks (fluency cues, company
    -type background context, priority cues) apply to a small enough
    unit of text to stay precise.
    """
    segments: list[str] = []
    for block in _split_into_blocks(jd_text):
        block = normalize_whitespace(block)
        if not block:
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(block):
            sentence = normalize_whitespace(sentence)
            if sentence:
                segments.append(sentence)
    return segments


def _classify_priority(segment: str, glossary: Glossary) -> tuple[str | None, str | None]:
    """Classify a segment's explicit priority cue, if any.

    Checks nice_to_have first, then important, then must — a segment
    that (however unusually) contains more than one cue type is never
    allowed to resolve to "must" ahead of a nice-to-have cue that is
    also present (rule: "optional cues must not become MUST").
    """
    for bucket, phrases in (
        ("nice_to_have", glossary.priority_cues.nice_to_have),
        ("important", glossary.priority_cues.important),
        ("must", glossary.priority_cues.must),
    ):
        for phrase in phrases:
            if contains_phrase(segment, phrase):
                return bucket, phrase
    return None, None


def _collect_priority_signals(segments: list[str], glossary: Glossary) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {
        "priority_must": [],
        "priority_important": [],
        "priority_nice_to_have": [],
    }
    for segment in segments:
        for category, phrases in (
            ("priority_must", glossary.priority_cues.must),
            ("priority_important", glossary.priority_cues.important),
            ("priority_nice_to_have", glossary.priority_cues.nice_to_have),
        ):
            for phrase in phrases:
                if contains_phrase(segment, phrase):
                    found[category].append(phrase)
    return {category: dedupe_preserve_order(phrases) for category, phrases in found.items() if phrases}


# ---------------------------------------------------------------------------
# Explicit target titles
# ---------------------------------------------------------------------------


def _extract_titles(segments: list[str]) -> list[str]:
    titles: list[str] = []
    for segment in segments:
        label_match = _TITLE_LABEL_RE.match(segment)
        if label_match:
            titles.append(label_match.group("title").strip(" .,;"))
            continue
        trigger_match = _TITLE_TRIGGER_RE.search(segment)
        if trigger_match:
            titles.append(trigger_match.group("title").strip(" .,;"))
    return dedupe_preserve_order(titles)


# ---------------------------------------------------------------------------
# Seniority cues
# ---------------------------------------------------------------------------


def _extract_seniority(full_text: str, glossary: Glossary) -> tuple[list[str], list[str]]:
    canonical_matches: list[str] = []
    literal_matches: list[str] = []
    for level in glossary.seniority_levels:
        for alias in level.aliases:
            if contains_phrase(full_text, alias):
                canonical_matches.append(level.canonical)
                literal_matches.append(alias)
    return dedupe_preserve_order(canonical_matches), dedupe_preserve_order(literal_matches)


# ---------------------------------------------------------------------------
# Location terms
# ---------------------------------------------------------------------------


def _extract_locations(full_text: str, glossary: Glossary) -> tuple[list[str], list[str]]:
    canonical_matches: list[str] = []
    literal_matches: list[str] = []
    for location in glossary.locations:
        for city in location.cities:
            for alias in city.aliases:
                if contains_phrase(full_text, alias):
                    canonical_matches.append(city.canonical)
                    literal_matches.append(alias)
        for name in location.names:
            if contains_phrase(full_text, name):
                canonical_matches.append(location.canonical)
                literal_matches.append(name)
    return dedupe_preserve_order(canonical_matches), dedupe_preserve_order(literal_matches)


# ---------------------------------------------------------------------------
# Language requirements
# ---------------------------------------------------------------------------


def _extract_languages(
    segments: list[str], glossary: Glossary
) -> tuple[PrioritizedTerms, list[str]]:
    """Extract language requirements, avoiding bare-name false positives.

    A language's own "-speaking" form (e.g. "German-speaking") is
    unambiguous on its own. A bare canonical/local name match (e.g.
    "German") is only accepted when the same segment also has
    confirming context — a CEFR level code, an explicit proficiency
    phrase, an explicit priority cue, or a "Languages:"-style label —
    which is what keeps "German company" / "English version" from being
    misread as language requirements.
    """
    bucket_by_term: dict[str, str] = {}
    literal_matches: list[str] = []

    for segment in segments:
        has_label = bool(_LANGUAGE_LABEL_RE.match(segment))
        has_cefr = bool(_CEFR_LEVEL_RE.search(segment))
        has_proficiency_cue = any(
            contains_phrase(segment, cue) for cue in _LANGUAGE_PROFICIENCY_CUES
        )
        bucket, cue_phrase = _classify_priority(segment, glossary)
        segment_confirmed = has_label or has_cefr or has_proficiency_cue or cue_phrase is not None
        effective_bucket = bucket or "important"

        for language in glossary.languages:
            for form in language.speaking_forms:
                if contains_phrase(segment, form):
                    bucket_by_term[language.canonical] = _merge_priority(
                        bucket_by_term.get(language.canonical), effective_bucket
                    )
                    literal_matches.append(form)

            if not segment_confirmed:
                continue
            for name in language.names:
                if contains_phrase(segment, name):
                    bucket_by_term[language.canonical] = _merge_priority(
                        bucket_by_term.get(language.canonical), effective_bucket
                    )
                    literal_matches.append(name)

    return _to_prioritized_terms(bucket_by_term), dedupe_preserve_order(literal_matches)


# ---------------------------------------------------------------------------
# Company-environment (company-type) requirements
# ---------------------------------------------------------------------------


def _extract_company_types(
    segments: list[str], glossary: Glossary
) -> tuple[PrioritizedTerms, list[str]]:
    """Extract company-type requirements, requiring candidate-background context.

    A matched company-type term (e.g. "consultancy", "EPC contractor")
    is only accepted when the segment confirms it describes the
    *candidate's* background ("experience in", "background",
    "worked for") and is rejected outright when the text immediately
    before it instead describes the employer itself ("our
    consultancy", "we are an EPC contractor").
    """
    bucket_by_term: dict[str, str] = {}
    literal_matches: list[str] = []

    for segment in segments:
        bucket, _ = _classify_priority(segment, glossary)
        effective_bucket = bucket or "nice_to_have"

        for company_type in glossary.company_types:
            for alias in company_type.aliases:
                match = _find_phrase(segment, alias)
                if not match:
                    continue
                window_start = max(0, match.start() - _COMPANY_TYPE_NEGATIVE_CONTEXT_WINDOW)
                window = segment[window_start : match.start()]
                if _COMPANY_TYPE_NEGATIVE_CONTEXT_RE.search(window):
                    continue
                if not _COMPANY_TYPE_POSITIVE_CONTEXT_RE.search(segment):
                    continue
                bucket_by_term[company_type.canonical] = _merge_priority(
                    bucket_by_term.get(company_type.canonical), effective_bucket
                )
                literal_matches.append(alias)

    return _to_prioritized_terms(bucket_by_term), dedupe_preserve_order(literal_matches)


# ---------------------------------------------------------------------------
# Profession-specific terms from an activated job-family pack
# ---------------------------------------------------------------------------


def _extract_pack_terms(
    segments: list[str], full_text: str, pack: JobFamilyPack, glossary: Glossary
) -> tuple[list[str], PrioritizedTerms, list[str], dict[str, list[str]]]:
    titles: list[str] = []
    for title_group in pack.titles:
        for term in title_group.terms:
            if contains_phrase(full_text, term):
                titles.append(term)

    industries: list[str] = []
    industry_literal: list[str] = []
    for industry in pack.industries:
        for term in industry.terms:
            if contains_phrase(full_text, term):
                industries.append(industry.name)
                industry_literal.append(term)

    skill_bucket_by_term: dict[str, str] = {}
    skill_literal: list[str] = []
    for segment in segments:
        bucket, _ = _classify_priority(segment, glossary)
        effective_bucket = bucket or "important"
        for skill_group in pack.skill_groups:
            for term in skill_group.terms:
                if contains_phrase(segment, term):
                    skill_bucket_by_term[term] = _merge_priority(
                        skill_bucket_by_term.get(term), effective_bucket
                    )
                    skill_literal.append(term)

    matched_signals: dict[str, list[str]] = {}
    if titles:
        matched_signals["pack_titles"] = dedupe_preserve_order(titles)
    if industry_literal:
        matched_signals["industries"] = dedupe_preserve_order(industry_literal)
    if skill_literal:
        matched_signals["skills"] = dedupe_preserve_order(skill_literal)

    return (
        dedupe_preserve_order(titles),
        _to_prioritized_terms(skill_bucket_by_term),
        dedupe_preserve_order(industries),
        matched_signals,
    )


# ---------------------------------------------------------------------------
# Top-level extraction
# ---------------------------------------------------------------------------


def extract(jd_text: str, glossary: Glossary, pack: JobFamilyPack | None = None) -> SearchSpec:
    """Extract deterministic evidence from a Job Description into a `SearchSpec`.

    `pack` is an already-activated `JobFamilyPack` (see
    `family_detector.detect_family`) — this function never selects one
    itself, and extracts no profession-specific term (title, skill,
    industry) unless a pack is given (rule: "profession-specific terms
    only from an activated knowledge pack"). This function never
    assembles a Boolean query.
    """
    segments = _segment_jd(jd_text)
    full_text = normalize_whitespace(jd_text)

    spec = SearchSpec(source=jd_text)
    spec.titles = _extract_titles(segments)

    seniority_canonical, seniority_literal = _extract_seniority(full_text, glossary)
    if seniority_canonical:
        spec.matched_signals["seniority"] = seniority_canonical
    if seniority_literal:
        spec.matched_signals["seniority_literal"] = seniority_literal

    locations_canonical, locations_literal = _extract_locations(full_text, glossary)
    spec.locations = locations_canonical
    if locations_literal:
        spec.matched_signals["locations"] = locations_literal

    spec.languages, language_literal = _extract_languages(segments, glossary)
    if language_literal:
        spec.matched_signals["languages"] = language_literal

    spec.company_types, company_type_literal = _extract_company_types(segments, glossary)
    if company_type_literal:
        spec.matched_signals["company_types"] = company_type_literal

    spec.matched_signals.update(_collect_priority_signals(segments, glossary))

    if pack is not None:
        spec.job_family = pack.family
        pack_titles, pack_skills, pack_industries, pack_matched_signals = _extract_pack_terms(
            segments, full_text, pack, glossary
        )
        spec.titles = dedupe_preserve_order([*spec.titles, *pack_titles])
        spec.skills = pack_skills
        spec.industries = pack_industries
        spec.matched_signals.update(pack_matched_signals)

    return spec
