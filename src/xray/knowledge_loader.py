"""Job-family knowledge-pack loader for the X-ray engine.

Loads and validates a single job-family knowledge pack YAML file
(`knowledge/job_families/<family>.yaml`) into typed Python objects.

Per CLAUDE.md section 4 (category 2, dictionary-driven knowledge), a
job-family pack is where every profession-specific term (titles,
specializations, industries, skills, core functions, hidden-title
signals, exclusions, local-market terms) belongs. This module only
parses and validates that structure. It deliberately does not:

- decide *which* pack applies to a given Job Description — job-family
  detection is a separate, not-yet-implemented concern;
- perform any extraction or query-assembly logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.xray.normalizer import casefold_key

#: Top-level keys a job-family pack YAML file is allowed to define. Any
#: other top-level key is rejected rather than silently ignored.
_ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {
        "family",
        "family_signals",
        "titles",
        "specializations",
        "specialization_signals",
        "industries",
        "skill_groups",
        "core_functions",
        "hidden_title_signals",
        "exclusions",
        "local_market_terms",
    }
)

#: Fields that must be present in every job-family pack.
_REQUIRED_TOP_LEVEL_FIELDS = frozenset({"family", "family_signals", "titles"})

#: A title group must be grouped by seniority or by role type.
_VALID_TITLE_GROUP_TYPES = frozenset({"seniority", "role_type"})

#: Inclusive range every optional weight must fall within.
_MIN_WEIGHT = 0.0
_MAX_WEIGHT = 1.0

_TITLE_GROUP_FIELDS = frozenset({"id", "group_type", "terms", "weight"})
_SPECIALIZATION_FIELDS = frozenset({"id", "name", "terms", "weight"})
_INDUSTRY_FIELDS = frozenset({"id", "name", "terms", "weight"})
_SKILL_GROUP_FIELDS = frozenset({"id", "name", "terms", "weight"})
_CORE_FUNCTION_FIELDS = frozenset({"id", "name", "terms", "weight"})


class KnowledgePackSchemaError(ValueError):
    """Raised when a job-family knowledge pack YAML file fails schema validation."""


@dataclass(frozen=True)
class TitleGroup:
    """One group of title synonyms, grouped by seniority or role type."""

    id: str
    group_type: str  # "seniority" | "role_type"
    terms: tuple[str, ...]
    weight: float | None = None


@dataclass(frozen=True)
class Specialization:
    id: str
    name: str
    terms: tuple[str, ...]
    weight: float | None = None


@dataclass(frozen=True)
class Industry:
    id: str
    name: str
    terms: tuple[str, ...]
    weight: float | None = None


@dataclass(frozen=True)
class SkillGroup:
    id: str
    name: str
    terms: tuple[str, ...]
    weight: float | None = None


@dataclass(frozen=True)
class CoreFunction:
    """One core-function/activity evidence group (CLAUDE.md section 6:
    Core Function evidence, distinct from Industry evidence)."""

    id: str
    name: str
    terms: tuple[str, ...]
    weight: float | None = None


@dataclass(frozen=True)
class JobFamilyPack:
    """Typed, validated contents of one job-family knowledge pack file."""

    source_path: Path
    family: str
    family_signals: tuple[str, ...]
    titles: tuple[TitleGroup, ...]
    specializations: tuple[Specialization, ...]
    specialization_signals: dict[str, tuple[str, ...]]
    industries: tuple[Industry, ...]
    skill_groups: tuple[SkillGroup, ...]
    core_functions: tuple[CoreFunction, ...]
    hidden_title_signals: tuple[str, ...]
    exclusions: tuple[str, ...]
    local_market_terms: dict[str, tuple[str, ...]]


# ---------------------------------------------------------------------------
# Generic validation helpers
# ---------------------------------------------------------------------------


def _require_str(value: Any, field: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgePackSchemaError(
            f"{context}: {field!r} must be a non-empty string, got {value!r}"
        )
    return value


def _require_str_list(value: Any, field: str, context: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise KnowledgePackSchemaError(
            f"{context}: {field!r} must be a non-empty list of strings, got {value!r}"
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise KnowledgePackSchemaError(
                f"{context}: {field!r} entries must be non-empty strings, got {item!r}"
            )
    return value


def _require_mapping(value: Any, field: str, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KnowledgePackSchemaError(f"{context}: {field!r} must be a mapping, got {value!r}")
    return value


def _reject_unknown_keys(raw: dict[str, Any], allowed: frozenset[str], context: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise KnowledgePackSchemaError(
            f"{context}: unknown field(s) {sorted(unknown)}; allowed: {sorted(allowed)}"
        )


def _parse_weight(raw: dict[str, Any], context: str) -> float | None:
    if "weight" not in raw:
        return None
    value = raw["weight"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KnowledgePackSchemaError(f"{context}: 'weight' must be a number, got {value!r}")
    if not _MIN_WEIGHT <= value <= _MAX_WEIGHT:
        raise KnowledgePackSchemaError(
            f"{context}: 'weight' must be between {_MIN_WEIGHT} and {_MAX_WEIGHT}, got {value!r}"
        )
    return float(value)


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_title_group(raw: Any, index: int) -> TitleGroup:
    context = f"titles[{index}]"
    if not isinstance(raw, dict):
        raise KnowledgePackSchemaError(f"{context}: must be a mapping, got {raw!r}")
    _reject_unknown_keys(raw, _TITLE_GROUP_FIELDS, context)
    entry_id = _require_str(raw.get("id"), "id", context)
    context = f"titles[{index}] (id={entry_id!r})"
    group_type = _require_str(raw.get("group_type"), "group_type", context)
    if group_type not in _VALID_TITLE_GROUP_TYPES:
        raise KnowledgePackSchemaError(
            f"{context}: 'group_type' must be one of {sorted(_VALID_TITLE_GROUP_TYPES)}, "
            f"got {group_type!r}"
        )
    terms = _require_str_list(raw.get("terms"), "terms", context)
    weight = _parse_weight(raw, context)
    return TitleGroup(id=entry_id, group_type=group_type, terms=tuple(terms), weight=weight)


def _parse_specialization(raw: Any, index: int) -> Specialization:
    context = f"specializations[{index}]"
    if not isinstance(raw, dict):
        raise KnowledgePackSchemaError(f"{context}: must be a mapping, got {raw!r}")
    _reject_unknown_keys(raw, _SPECIALIZATION_FIELDS, context)
    entry_id = _require_str(raw.get("id"), "id", context)
    context = f"specializations[{index}] (id={entry_id!r})"
    name = _require_str(raw.get("name"), "name", context)
    terms = _require_str_list(raw.get("terms"), "terms", context)
    weight = _parse_weight(raw, context)
    return Specialization(id=entry_id, name=name, terms=tuple(terms), weight=weight)


def _parse_industry(raw: Any, index: int) -> Industry:
    context = f"industries[{index}]"
    if not isinstance(raw, dict):
        raise KnowledgePackSchemaError(f"{context}: must be a mapping, got {raw!r}")
    _reject_unknown_keys(raw, _INDUSTRY_FIELDS, context)
    entry_id = _require_str(raw.get("id"), "id", context)
    context = f"industries[{index}] (id={entry_id!r})"
    name = _require_str(raw.get("name"), "name", context)
    terms = _require_str_list(raw.get("terms"), "terms", context)
    weight = _parse_weight(raw, context)
    return Industry(id=entry_id, name=name, terms=tuple(terms), weight=weight)


def _parse_skill_group(raw: Any, index: int) -> SkillGroup:
    context = f"skill_groups[{index}]"
    if not isinstance(raw, dict):
        raise KnowledgePackSchemaError(f"{context}: must be a mapping, got {raw!r}")
    _reject_unknown_keys(raw, _SKILL_GROUP_FIELDS, context)
    entry_id = _require_str(raw.get("id"), "id", context)
    context = f"skill_groups[{index}] (id={entry_id!r})"
    name = _require_str(raw.get("name"), "name", context)
    terms = _require_str_list(raw.get("terms"), "terms", context)
    weight = _parse_weight(raw, context)
    return SkillGroup(id=entry_id, name=name, terms=tuple(terms), weight=weight)


def _parse_core_function(raw: Any, index: int) -> CoreFunction:
    context = f"core_functions[{index}]"
    if not isinstance(raw, dict):
        raise KnowledgePackSchemaError(f"{context}: must be a mapping, got {raw!r}")
    _reject_unknown_keys(raw, _CORE_FUNCTION_FIELDS, context)
    entry_id = _require_str(raw.get("id"), "id", context)
    context = f"core_functions[{index}] (id={entry_id!r})"
    name = _require_str(raw.get("name"), "name", context)
    terms = _require_str_list(raw.get("terms"), "terms", context)
    weight = _parse_weight(raw, context)
    return CoreFunction(id=entry_id, name=name, terms=tuple(terms), weight=weight)


def _parse_specialization_signals(
    raw: Any, valid_ids: set[str], context: str
) -> dict[str, tuple[str, ...]]:
    mapping = _require_mapping(raw, "specialization_signals", context)
    result: dict[str, tuple[str, ...]] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise KnowledgePackSchemaError(
                f"{context}: specialization_signals keys must be non-empty strings, got {key!r}"
            )
        if key not in valid_ids:
            raise KnowledgePackSchemaError(
                f"{context}: specialization_signals key {key!r} does not match any "
                f"specialization id {sorted(valid_ids)}"
            )
        terms = _require_str_list(value, f"specialization_signals[{key!r}]", context)
        result[key] = tuple(terms)
    return result


def _parse_local_market_terms(raw: Any, context: str) -> dict[str, tuple[str, ...]]:
    mapping = _require_mapping(raw, "local_market_terms", context)
    result: dict[str, tuple[str, ...]] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise KnowledgePackSchemaError(
                f"{context}: local_market_terms keys must be non-empty locale strings, "
                f"got {key!r}"
            )
        terms = _require_str_list(value, f"local_market_terms[{key!r}]", context)
        result[key] = tuple(terms)
    return result


def _check_no_duplicate_ids(
    titles: tuple[TitleGroup, ...],
    specializations: tuple[Specialization, ...],
    industries: tuple[Industry, ...],
    skill_groups: tuple[SkillGroup, ...],
    core_functions: tuple[CoreFunction, ...],
    context: str,
) -> None:
    """Reject duplicate canonical ids across all id-bearing sections.

    Ids share a single namespace across titles/specializations/
    industries/skill_groups/core_functions (case-insensitive,
    Unicode-safe) so that a later cross-reference (e.g.
    specialization_signals) can never silently resolve to the wrong
    entry.
    """
    seen: dict[str, tuple[str, str]] = {}
    for label, entries in (
        ("titles", titles),
        ("specializations", specializations),
        ("industries", industries),
        ("skill_groups", skill_groups),
        ("core_functions", core_functions),
    ):
        for entry in entries:
            key = casefold_key(entry.id)
            if key in seen:
                other_label, other_id = seen[key]
                raise KnowledgePackSchemaError(
                    f"{context}: duplicate canonical id {entry.id!r} in {label!r} "
                    f"(already used as {other_id!r} in {other_label!r})"
                )
            seen[key] = (label, entry.id)


# ---------------------------------------------------------------------------
# Top-level parse + cache
# ---------------------------------------------------------------------------


def _parse_pack(path: Path) -> JobFamilyPack:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    context = str(path)
    if not isinstance(raw, dict):
        raise KnowledgePackSchemaError(f"{context}: file must contain a YAML mapping")

    _reject_unknown_keys(raw, _ALLOWED_TOP_LEVEL_FIELDS, context)
    missing = _REQUIRED_TOP_LEVEL_FIELDS - set(raw)
    if missing:
        raise KnowledgePackSchemaError(f"{context}: missing required field(s) {sorted(missing)}")

    family = _require_str(raw.get("family"), "family", context)
    context = f"{path} (family={family!r})"
    family_signals = _require_str_list(raw.get("family_signals"), "family_signals", context)

    titles_raw = raw.get("titles")
    if not isinstance(titles_raw, list) or not titles_raw:
        raise KnowledgePackSchemaError(f"{context}: 'titles' must be a non-empty list")
    titles = tuple(_parse_title_group(entry, i) for i, entry in enumerate(titles_raw))

    specializations_raw = raw.get("specializations", [])
    if not isinstance(specializations_raw, list):
        raise KnowledgePackSchemaError(f"{context}: 'specializations' must be a list")
    specializations = tuple(
        _parse_specialization(entry, i) for i, entry in enumerate(specializations_raw)
    )

    industries_raw = raw.get("industries", [])
    if not isinstance(industries_raw, list):
        raise KnowledgePackSchemaError(f"{context}: 'industries' must be a list")
    industries = tuple(_parse_industry(entry, i) for i, entry in enumerate(industries_raw))

    skill_groups_raw = raw.get("skill_groups", [])
    if not isinstance(skill_groups_raw, list):
        raise KnowledgePackSchemaError(f"{context}: 'skill_groups' must be a list")
    skill_groups = tuple(_parse_skill_group(entry, i) for i, entry in enumerate(skill_groups_raw))

    core_functions_raw = raw.get("core_functions", [])
    if not isinstance(core_functions_raw, list):
        raise KnowledgePackSchemaError(f"{context}: 'core_functions' must be a list")
    core_functions = tuple(
        _parse_core_function(entry, i) for i, entry in enumerate(core_functions_raw)
    )

    _check_no_duplicate_ids(titles, specializations, industries, skill_groups, core_functions, context)

    specialization_ids = {s.id for s in specializations}
    specialization_signals = (
        _parse_specialization_signals(raw["specialization_signals"], specialization_ids, context)
        if "specialization_signals" in raw
        else {}
    )

    hidden_title_signals = tuple(
        _require_str_list(raw["hidden_title_signals"], "hidden_title_signals", context)
        if "hidden_title_signals" in raw
        else []
    )
    exclusions = tuple(
        _require_str_list(raw["exclusions"], "exclusions", context) if "exclusions" in raw else []
    )
    local_market_terms = (
        _parse_local_market_terms(raw["local_market_terms"], context)
        if "local_market_terms" in raw
        else {}
    )

    return JobFamilyPack(
        source_path=path,
        family=family,
        family_signals=tuple(family_signals),
        titles=titles,
        specializations=specializations,
        specialization_signals=specialization_signals,
        industries=industries,
        skill_groups=skill_groups,
        core_functions=core_functions,
        hidden_title_signals=hidden_title_signals,
        exclusions=exclusions,
        local_market_terms=local_market_terms,
    )


#: Successfully loaded packs, keyed by resolved absolute path.
_CACHE: dict[str, JobFamilyPack] = {}


def load_job_family_pack(path: str | Path) -> JobFamilyPack:
    """Load, validate, and cache a job-family knowledge pack YAML file.

    Repeated calls with the same path return the same cached
    `JobFamilyPack` instance without re-reading or re-validating the
    file. Only successful loads are cached — a schema error is raised
    fresh on every call until the underlying file is fixed.
    """
    resolved = str(Path(path).resolve())
    cached = _CACHE.get(resolved)
    if cached is not None:
        return cached
    pack = _parse_pack(Path(path))
    _CACHE[resolved] = pack
    return pack


def clear_cache() -> None:
    """Clear the job-family pack cache (primarily for test isolation)."""
    _CACHE.clear()
