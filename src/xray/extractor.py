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
    "fluent",
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

#: A line ending in one of these words cannot grammatically stand as a
#: complete clause on its own (article / preposition / coordinating
#: conjunction / relative pronoun / copula-auxiliary / possessive) — a
#: closed, purely structural signal (same "generic sentence-structure
#: vocabulary" justification as `_LANGUAGE_PROFICIENCY_CUES` above) that
#: the line was cut mid-sentence by fixed-width line wrapping, not that
#: it is a complete, standalone "loose list" item lacking a bullet
#: marker (common when a JD is copy-pasted from a rendered HTML `<li>`
#: list with the bullet glyphs stripped out).
_CONTINUATION_TRAILING_WORDS = frozenset(
    {
        "a", "an", "the",
        "and", "or", "but", "nor",
        "to", "of", "in", "on", "at", "by", "for", "with", "from", "into", "onto", "as",
        "is", "are", "was", "were", "be", "being", "been",
        "that", "which", "who", "whom", "whose",
        "our", "your", "their", "its", "his", "her",
    }
)
_TRAILING_WORD_RE = re.compile(r"([A-Za-z]+)[.,;:!?)/\-]*$")


def _ends_with_continuation_cue(line: str) -> bool:
    """True if `line` grammatically reads as cut off mid-clause.

    Used only to decide whether the *next* line is a wrapped
    continuation of `line` (keep merging) or a new, bullet-less "loose
    list" item (start a new block) — see `_split_into_blocks`.
    """
    match = _TRAILING_WORD_RE.search(line.strip())
    return bool(match) and match.group(1).casefold() in _CONTINUATION_TRAILING_WORDS


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

    A blank line or a new bullet marker always starts a new block. A
    plain (non-bulleted) line starts a new block too, UNLESS the
    previous line in the current block ends with a continuation cue
    (`_ends_with_continuation_cue`) — i.e. it grammatically reads as cut
    off mid-clause, meaning it's a genuine soft wrap from a fixed-width
    paste, not a complete "loose list" item that merely lacks a bullet
    marker (common when a JD is copy-pasted from a rendered HTML `<li>`
    list with the bullet glyphs stripped). Without this check, a whole
    section of one-requirement-per-line text with no bullets would
    collapse into a single giant block, letting an unrelated priority
    cue in one requirement (e.g. "...a plus") bleed its classification
    onto every other requirement merged into the same block.
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
            continue
        if current and not _ends_with_continuation_cue(current[-1]):
            flush()
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

#: Phrases indicating a location mention describes the EMPLOYER's own
#: office network/HQ ("headquartered in Berlin", "with offices in
#: Germany"), not a job location — generic, structural JD boilerplate
#: (not electrical- or any other profession-specific), mirroring
#: `_COMPANY_TYPE_NEGATIVE_CONTEXT_RE`'s employer-self-reference guard.
#: Deliberately restricted to the PLURAL "offices" only — a singular
#: "based in our office in <city>" is a common, genuine job-location
#: phrasing and must not be rejected.
_LOCATION_NEGATIVE_CONTEXT_RE = re.compile(
    r"(?i)\b(?:headquartered\s+in|"
    r"(?:our|with)\s+offices\s+in|"
    r"company\s+based\s+in|"
    r"global\s+design\s+cent(?:er|re)\s+in)\b"
)
#: How many characters immediately before a matched location term are
#: inspected for employer-self-reference context.
_LOCATION_NEGATIVE_CONTEXT_WINDOW = 40


def _extract_locations(segments: list[str], glossary: Glossary) -> tuple[list[str], list[str]]:
    """Extract location terms, rejecting employer-HQ mentions.

    A matched location term (e.g. "Berlin") is rejected at the specific
    occurrence where the text immediately before it describes the
    employer's own office network/HQ ("headquartered in Berlin",
    "with offices in Germany") rather than a job location. Unlike
    `_extract_company_types`, no positive-context confirmation is
    required — a bare location line (e.g. "Remote / Hybrid – Germany or
    Poland") has no candidate-background-style cue to require, so
    demanding one would cause false rejections. Rejection is per-match:
    a term with any other, clean occurrence elsewhere in the JD is still
    kept (mirrors `_extract_company_types`'s per-match design).
    """
    canonical_matches: list[str] = []
    literal_matches: list[str] = []
    for segment in segments:
        for location in glossary.locations:
            for city in location.cities:
                for alias in city.aliases:
                    match = _find_phrase(segment, alias)
                    if not match:
                        continue
                    window_start = max(0, match.start() - _LOCATION_NEGATIVE_CONTEXT_WINDOW)
                    window = segment[window_start : match.start()]
                    if _LOCATION_NEGATIVE_CONTEXT_RE.search(window):
                        continue
                    canonical_matches.append(city.canonical)
                    literal_matches.append(alias)
            for name in location.names:
                match = _find_phrase(segment, name)
                if not match:
                    continue
                window_start = max(0, match.start() - _LOCATION_NEGATIVE_CONTEXT_WINDOW)
                window = segment[window_start : match.start()]
                if _LOCATION_NEGATIVE_CONTEXT_RE.search(window):
                    continue
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
) -> tuple[list[str], PrioritizedTerms, list[str], list[str], dict[str, list[str]]]:
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

    core_functions: list[str] = []
    core_function_literal: list[str] = []
    for core_function in pack.core_functions:
        for term in core_function.terms:
            if contains_phrase(full_text, term):
                core_functions.append(core_function.name)
                core_function_literal.append(term)

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
    if core_function_literal:
        matched_signals["core_functions"] = dedupe_preserve_order(core_function_literal)
    if skill_literal:
        matched_signals["skills"] = dedupe_preserve_order(skill_literal)

    return (
        dedupe_preserve_order(titles),
        _to_prioritized_terms(skill_bucket_by_term),
        dedupe_preserve_order(industries),
        dedupe_preserve_order(core_functions),
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

    locations_canonical, locations_literal = _extract_locations(segments, glossary)
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
        pack_titles, pack_skills, pack_industries, pack_core_functions, pack_matched_signals = (
            _extract_pack_terms(segments, full_text, pack, glossary)
        )
        spec.titles = dedupe_preserve_order([*spec.titles, *pack_titles])
        spec.skills = pack_skills
        spec.industries = pack_industries
        spec.core_functions = pack_core_functions
        spec.matched_signals.update(pack_matched_signals)

    return spec
