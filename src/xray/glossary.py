"""Generic glossary loader for the X-ray engine.

Loads and validates the five generic, profession-agnostic knowledge
files under `knowledge/` — locations, languages, company types,
seniority levels, and priority cues — and exposes typed, case-
insensitive lookup helpers over them.

Per CLAUDE.md section 4, this module only ever deals with generic,
cross-family knowledge. Job-family packs under `knowledge/job_families/`
are a distinct concern (dictionary-driven, profession-specific
knowledge) and are intentionally not loaded here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.xray.normalizer import casefold_key

#: Directory containing the generic knowledge YAML files.
DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

#: Canonical company-type entries (casefolded) that
#: `knowledge/company_types.yaml` must define.
REQUIRED_COMPANY_TYPES = frozenset(
    {
        "consultancy",
        "contractor",
        "client-side",
        "startup",
        "enterprise",
        "agency",
        "manufacturer",
        "epc",
        "general contractor",
        "design office",
    }
)

#: The three priority categories `knowledge/priority_cues.yaml` must
#: define, in CLAUDE.md section 6 order.
REQUIRED_PRIORITY_CATEGORIES = ("must", "important", "nice_to_have")


class GlossarySchemaError(ValueError):
    """Raised when a generic knowledge YAML file fails schema validation."""


@dataclass(frozen=True)
class CityEntry:
    canonical: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class LocationEntry:
    canonical: str
    names: tuple[str, ...]
    cities: tuple[CityEntry, ...]
    cctld: str | None = None


@dataclass(frozen=True)
class CityMatch:
    """A city alias match, together with the country it belongs to."""

    country: LocationEntry
    city: CityEntry


@dataclass(frozen=True)
class LanguageEntry:
    canonical: str
    names: tuple[str, ...]
    speaking_forms: tuple[str, ...]


@dataclass(frozen=True)
class CompanyTypeEntry:
    canonical: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SeniorityEntry:
    canonical: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class PriorityCues:
    """The MUST / IMPORTANT / NICE-TO-HAVE cue-phrase dictionary (CLAUDE.md section 6)."""

    must: tuple[str, ...]
    important: tuple[str, ...]
    nice_to_have: tuple[str, ...]


# ---------------------------------------------------------------------------
# YAML loading + schema validation
# ---------------------------------------------------------------------------


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise GlossarySchemaError(f"{path}: file must contain a YAML mapping")
    return data


def _require_str(value: Any, field: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GlossarySchemaError(
            f"{context}: {field!r} must be a non-empty string, got {value!r}"
        )
    return value


def _require_str_list(
    value: Any, field: str, context: str, *, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise GlossarySchemaError(
            f"{context}: {field!r} must be a non-empty list of strings, got {value!r}"
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise GlossarySchemaError(
                f"{context}: {field!r} entries must be non-empty strings, got {item!r}"
            )
    return value


def _parse_city(raw: Any, context: str) -> CityEntry:
    if not isinstance(raw, dict):
        raise GlossarySchemaError(f"{context}: each city must be a mapping, got {raw!r}")
    canonical = _require_str(raw.get("canonical"), "canonical", context)
    city_context = f"{context} {canonical!r}"
    aliases = _require_str_list(raw.get("aliases"), "aliases", city_context)
    if canonical not in aliases:
        raise GlossarySchemaError(
            f"{city_context}: 'aliases' must include the canonical name {canonical!r}"
        )
    return CityEntry(canonical=canonical, aliases=tuple(aliases))


def _parse_location(raw: Any) -> LocationEntry:
    if not isinstance(raw, dict):
        raise GlossarySchemaError(f"locations.yaml: each country must be a mapping, got {raw!r}")
    canonical = _require_str(raw.get("canonical"), "canonical", "locations.yaml country")
    context = f"locations.yaml country {canonical!r}"
    names = _require_str_list(raw.get("names"), "names", context)
    if canonical not in names:
        raise GlossarySchemaError(
            f"{context}: 'names' must include the canonical name {canonical!r}"
        )
    cctld: str | None = raw.get("cctld")
    if cctld is not None:
        cctld = _require_str(cctld, "cctld", context)
    cities_raw = raw.get("cities", [])
    if not isinstance(cities_raw, list):
        raise GlossarySchemaError(f"{context}: 'cities' must be a list")
    cities = tuple(_parse_city(city, f"{context} city") for city in cities_raw)
    return LocationEntry(canonical=canonical, names=tuple(names), cities=cities, cctld=cctld)


def _parse_language(raw: Any) -> LanguageEntry:
    if not isinstance(raw, dict):
        raise GlossarySchemaError(f"languages.yaml: each language must be a mapping, got {raw!r}")
    canonical = _require_str(raw.get("canonical"), "canonical", "languages.yaml language")
    context = f"languages.yaml language {canonical!r}"
    names = _require_str_list(raw.get("names"), "names", context)
    if canonical not in names:
        raise GlossarySchemaError(
            f"{context}: 'names' must include the canonical name {canonical!r}"
        )
    speaking_forms_raw = raw.get("speaking_forms", [])
    if not isinstance(speaking_forms_raw, list):
        raise GlossarySchemaError(f"{context}: 'speaking_forms' must be a list")
    speaking_forms = (
        _require_str_list(speaking_forms_raw, "speaking_forms", context, allow_empty=True)
        if speaking_forms_raw
        else []
    )
    return LanguageEntry(canonical=canonical, names=tuple(names), speaking_forms=tuple(speaking_forms))


def _parse_company_type(raw: Any) -> CompanyTypeEntry:
    if not isinstance(raw, dict):
        raise GlossarySchemaError(
            f"company_types.yaml: each entry must be a mapping, got {raw!r}"
        )
    canonical = _require_str(raw.get("canonical"), "canonical", "company_types.yaml entry")
    context = f"company_types.yaml entry {canonical!r}"
    aliases = _require_str_list(raw.get("aliases"), "aliases", context)
    if canonical not in aliases:
        raise GlossarySchemaError(
            f"{context}: 'aliases' must include the canonical name {canonical!r}"
        )
    return CompanyTypeEntry(canonical=canonical, aliases=tuple(aliases))


def _parse_seniority_level(raw: Any) -> SeniorityEntry:
    if not isinstance(raw, dict):
        raise GlossarySchemaError(f"seniority.yaml: each entry must be a mapping, got {raw!r}")
    canonical = _require_str(raw.get("canonical"), "canonical", "seniority.yaml entry")
    context = f"seniority.yaml entry {canonical!r}"
    aliases = _require_str_list(raw.get("aliases"), "aliases", context)
    if canonical not in aliases:
        raise GlossarySchemaError(
            f"{context}: 'aliases' must include the canonical name {canonical!r}"
        )
    return SeniorityEntry(canonical=canonical, aliases=tuple(aliases))


def _load_locations(path: Path) -> tuple[LocationEntry, ...]:
    data = _load_yaml_mapping(path)
    countries = data.get("countries")
    if not isinstance(countries, list) or not countries:
        raise GlossarySchemaError(f"{path}: 'countries' must be a non-empty list")
    return tuple(_parse_location(entry) for entry in countries)


def _load_languages(path: Path) -> tuple[LanguageEntry, ...]:
    data = _load_yaml_mapping(path)
    languages = data.get("languages")
    if not isinstance(languages, list) or not languages:
        raise GlossarySchemaError(f"{path}: 'languages' must be a non-empty list")
    return tuple(_parse_language(entry) for entry in languages)


def _load_company_types(path: Path) -> tuple[CompanyTypeEntry, ...]:
    data = _load_yaml_mapping(path)
    entries = data.get("company_types")
    if not isinstance(entries, list) or not entries:
        raise GlossarySchemaError(f"{path}: 'company_types' must be a non-empty list")
    parsed = tuple(_parse_company_type(entry) for entry in entries)
    present = {casefold_key(entry.canonical) for entry in parsed}
    missing = REQUIRED_COMPANY_TYPES - present
    if missing:
        raise GlossarySchemaError(
            f"{path}: missing required company type(s): {sorted(missing)}"
        )
    return parsed


def _load_seniority_levels(path: Path) -> tuple[SeniorityEntry, ...]:
    data = _load_yaml_mapping(path)
    unknown_top = set(data) - {"seniority_levels"}
    if unknown_top:
        raise GlossarySchemaError(f"{path}: unknown field(s) {sorted(unknown_top)}")
    entries = data.get("seniority_levels")
    if not isinstance(entries, list) or not entries:
        raise GlossarySchemaError(f"{path}: 'seniority_levels' must be a non-empty list")
    return tuple(_parse_seniority_level(entry) for entry in entries)


def _load_priority_cues(path: Path) -> PriorityCues:
    data = _load_yaml_mapping(path)
    unknown_top = set(data) - {"priority_cues"}
    if unknown_top:
        raise GlossarySchemaError(f"{path}: unknown field(s) {sorted(unknown_top)}")

    cues = data.get("priority_cues")
    if not isinstance(cues, dict):
        raise GlossarySchemaError(f"{path}: 'priority_cues' must be a mapping")

    unknown_categories = set(cues) - set(REQUIRED_PRIORITY_CATEGORIES)
    if unknown_categories:
        raise GlossarySchemaError(
            f"{path}: unknown priority_cues categor(y/ies) {sorted(unknown_categories)}; "
            f"allowed: {list(REQUIRED_PRIORITY_CATEGORIES)}"
        )
    missing_categories = set(REQUIRED_PRIORITY_CATEGORIES) - set(cues)
    if missing_categories:
        raise GlossarySchemaError(
            f"{path}: missing priority_cues categor(y/ies) {sorted(missing_categories)}"
        )

    parsed: dict[str, tuple[str, ...]] = {}
    seen_phrases: dict[str, str] = {}
    for category in REQUIRED_PRIORITY_CATEGORIES:
        phrases = _require_str_list(cues[category], category, f"{path} priority_cues")
        for phrase in phrases:
            key = casefold_key(phrase)
            if key in seen_phrases:
                raise GlossarySchemaError(
                    f"{path}: cue phrase {phrase!r} appears in both "
                    f"{seen_phrases[key]!r} and {category!r}; each phrase must belong "
                    "to exactly one priority category"
                )
            seen_phrases[key] = category
        parsed[category] = tuple(phrases)

    return PriorityCues(
        must=parsed["must"], important=parsed["important"], nice_to_have=parsed["nice_to_have"]
    )


# ---------------------------------------------------------------------------
# Typed lookup
# ---------------------------------------------------------------------------


class Glossary:
    """Typed, case-insensitive lookup over the generic knowledge packs.

    Only the five generic files (locations, languages, company types,
    seniority levels, priority cues) are loaded here. Job-family packs
    are a separate, dictionary-driven concern loaded elsewhere.
    """

    def __init__(
        self,
        locations: tuple[LocationEntry, ...],
        languages: tuple[LanguageEntry, ...],
        company_types: tuple[CompanyTypeEntry, ...],
        seniority_levels: tuple[SeniorityEntry, ...],
        priority_cues: PriorityCues,
    ) -> None:
        self.locations = locations
        self.languages = languages
        self.company_types = company_types
        self.seniority_levels = seniority_levels
        self.priority_cues = priority_cues

        self._location_index: dict[str, LocationEntry] = {}
        for location in locations:
            for name in location.names:
                self._location_index[casefold_key(name)] = location

        self._city_index: dict[str, CityMatch] = {}
        for location in locations:
            for city in location.cities:
                for alias in city.aliases:
                    self._city_index[casefold_key(alias)] = CityMatch(
                        country=location, city=city
                    )

        self._language_index: dict[str, LanguageEntry] = {}
        for language in languages:
            for name in (*language.names, *language.speaking_forms):
                self._language_index[casefold_key(name)] = language

        self._company_type_index: dict[str, CompanyTypeEntry] = {}
        for company_type in company_types:
            for alias in company_type.aliases:
                self._company_type_index[casefold_key(alias)] = company_type

        self._seniority_index: dict[str, SeniorityEntry] = {}
        for seniority in seniority_levels:
            for alias in seniority.aliases:
                self._seniority_index[casefold_key(alias)] = seniority

    @classmethod
    def load(cls, knowledge_dir: str | Path = DEFAULT_KNOWLEDGE_DIR) -> "Glossary":
        """Load and validate the five generic knowledge YAML files."""
        base = Path(knowledge_dir)
        locations = _load_locations(base / "locations.yaml")
        languages = _load_languages(base / "languages.yaml")
        company_types = _load_company_types(base / "company_types.yaml")
        seniority_levels = _load_seniority_levels(base / "seniority.yaml")
        priority_cues = _load_priority_cues(base / "priority_cues.yaml")
        return cls(locations, languages, company_types, seniority_levels, priority_cues)

    def find_location(self, term: str) -> LocationEntry | None:
        """Look up a country by canonical name or any known local/English name."""
        return self._location_index.get(casefold_key(term))

    def find_city(self, term: str) -> CityMatch | None:
        """Look up a city by canonical name or any known alias."""
        return self._city_index.get(casefold_key(term))

    def find_language(self, term: str) -> LanguageEntry | None:
        """Look up a language by canonical name, local name, or "-speaking" form."""
        return self._language_index.get(casefold_key(term))

    def find_company_type(self, term: str) -> CompanyTypeEntry | None:
        """Look up a company type by canonical name or any known alias."""
        return self._company_type_index.get(casefold_key(term))

    def find_seniority(self, term: str) -> SeniorityEntry | None:
        """Look up a seniority level by canonical name or any known alias."""
        return self._seniority_index.get(casefold_key(term))
