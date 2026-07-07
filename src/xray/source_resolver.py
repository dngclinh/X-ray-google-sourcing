"""LinkedIn `site:` source resolution.

Decides which LinkedIn X-ray source prefix to use — the global
`site:linkedin.com/in/` or a country-specific
`site:{cc}.linkedin.com/in/` — from already-extracted location terms
(`SearchSpec.locations`) plus the generic location glossary
(`glossary.py`).

Per CLAUDE.md section 5: "Preserve location blocks in the query even
when using a LinkedIn country ccTLD — the ccTLD narrows by domain, but
explicit location terms still add precision and must not be dropped."
This module only ever *reads* `SearchSpec.locations`; it never clears,
replaces, or otherwise mutates it, regardless of which source it
resolves to.

This module contains no profession-specific knowledge and does not
assemble a full Boolean query — it only produces the `site:` prefix.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.xray.glossary import Glossary
from src.xray.models import SearchSpec

#: The global fallback source, used whenever a single verified-ccTLD
#: country cannot be uniquely determined.
DEFAULT_SOURCE = "site:linkedin.com/in/"


def _resolve_country_cctld(token: str, glossary: Glossary) -> tuple[str, str | None] | None:
    """Normalize one location token to `(country_canonical, cctld)`, or `None`."""
    location = glossary.find_location(token)
    if location is not None:
        return location.canonical, location.cctld

    city_match = glossary.find_city(token)
    if city_match is not None:
        return city_match.country.canonical, city_match.country.cctld

    return None


def resolve_source(locations: Sequence[str], glossary: Glossary) -> str:
    """Resolve the LinkedIn `site:` prefix for a set of location terms.

    Each token in `locations` is normalized to a country (a country
    name resolves directly; a city resolves via its country) — country
    count is determined from these *normalized* countries, not from
    `len(locations)`, so e.g. `["Frankfurt", "Germany"]` (two raw
    tokens, one country) still counts as one.

    A token that doesn't normalize to any known country (or city)
    contributes nothing to the count — it's neither a country of its
    own nor grounds to force the global source by itself, since the
    count that matters is of *identified* countries.

    Returns `site:{cc}.linkedin.com/in/` only when exactly one unique
    normalized country was identified AND that country has a verified
    ccTLD configured (`LocationEntry.cctld` is not `None`); otherwise
    returns `DEFAULT_SOURCE`. Never mutates `locations`.
    """
    cctld_by_country: dict[str, str | None] = {}

    for token in locations:
        resolved = _resolve_country_cctld(token, glossary)
        if resolved is not None:
            canonical, cctld = resolved
            cctld_by_country[canonical] = cctld

    if len(cctld_by_country) != 1:
        return DEFAULT_SOURCE

    (cctld,) = cctld_by_country.values()
    if not cctld:
        return DEFAULT_SOURCE

    return f"site:{cctld}.linkedin.com/in/"


def resolve_source_for_spec(spec: SearchSpec, glossary: Glossary) -> str:
    """Resolve the LinkedIn `site:` prefix for a `SearchSpec`.

    Reads `spec.locations` only — never clears or otherwise mutates it,
    even when a country-specific source is resolved (CLAUDE.md section
    5: the location block must still appear in the assembled query
    alongside the ccTLD).
    """
    return resolve_source(spec.locations, glossary)
