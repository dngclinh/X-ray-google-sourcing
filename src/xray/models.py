"""Structured data models for the X-ray engine.

These are pure data containers — the structured intermediate
representation (`SearchSpec`) that sits between extraction and query
assembly, per CLAUDE.md section 5 ("Use a structured intermediate
representation, `SearchSpec`, between extraction and query assembly").

This module intentionally contains:
- no extraction logic (turning a Job Description into these models);
- no query-construction logic (turning these models into Boolean
  strings).

Both of those are separate concerns and belong in other modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Inclusive range that every confidence score must fall within.
_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0


def _validate_confidence(confidence: dict[str, float]) -> None:
    """Raise ValueError if any confidence score is not a number in [0, 1]."""
    for category, value in confidence.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"confidence value for {category!r} must be a number, "
                f"got {value!r}"
            )
        if not _MIN_CONFIDENCE <= value <= _MAX_CONFIDENCE:
            raise ValueError(
                f"confidence value for {category!r} must be between "
                f"{_MIN_CONFIDENCE} and {_MAX_CONFIDENCE}, got {value!r}"
            )


@dataclass
class PrioritizedTerms:
    """Terms for one concept, split by CLAUDE.md section 6 priority.

    - `must`: required for the Strict variant.
    - `important`: added on top of `must` for the Balanced variant.
    - `nice_to_have`: added as optional (OR) terms for the Broad variant.
    """

    must: list[str] = field(default_factory=list)
    important: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)


@dataclass
class SearchSpec:
    """Structured intermediate representation produced by extraction and
    consumed by query assembly (CLAUDE.md section 5). Neither extraction
    nor query assembly should skip this representation.
    """

    source: str = ""
    titles: list[str] = field(default_factory=list)
    core_functions: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    skills: PrioritizedTerms = field(default_factory=PrioritizedTerms)
    locations: list[str] = field(default_factory=list)
    languages: PrioritizedTerms = field(default_factory=PrioritizedTerms)
    company_types: PrioritizedTerms = field(default_factory=PrioritizedTerms)
    exclusions: list[str] = field(default_factory=list)
    job_family: str | None = None
    specialization: str | None = None
    #: Confidence score (0.0-1.0) per classification category, e.g.
    #: {"core_functions": 0.6, "industries": 0.4} — see CLAUDE.md
    #: section 7 on heuristic Core Function/Industry classification.
    confidence: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    #: Which literal JD signal(s) triggered each category's
    #: classification, e.g. {"core_functions": ["backend", "API"]} —
    #: kept for traceability/QA, not for query assembly.
    matched_signals: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass
class QueryVariants:
    """The four required X-ray query variants (CLAUDE.md section 6).

    Holds only the assembled Boolean query strings for each variant —
    assembling them is query-construction logic that lives elsewhere.
    """

    strict: str = ""
    balanced: str = ""
    broad: str = ""
    hidden_titles: str = ""
