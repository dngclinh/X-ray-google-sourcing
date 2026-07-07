"""Tests for src/xray/source_resolver.py.

Covers LinkedIn `site:` source resolution against the real, checked-in
generic location glossary (`Glossary.load`). Every example listed in
the task's "may resolve to Germany" / "must use the global source"
lists is represented here as a `SearchSpec.locations`-shaped list of
already-extracted location tokens.
"""

from __future__ import annotations

import pytest

from src.xray.glossary import DEFAULT_KNOWLEDGE_DIR, Glossary
from src.xray.models import SearchSpec
from src.xray.source_resolver import DEFAULT_SOURCE, resolve_source, resolve_source_for_spec


@pytest.fixture(scope="module")
def glossary() -> Glossary:
    return Glossary.load(DEFAULT_KNOWLEDGE_DIR)


# ---------------------------------------------------------------------------
# May resolve to Germany (site:de.linkedin.com/in/)
# ---------------------------------------------------------------------------


def test_resolves_germany_by_canonical_name(glossary: Glossary):
    assert resolve_source(["Germany"], glossary) == "site:de.linkedin.com/in/"


def test_resolves_germany_by_local_name_deutschland(glossary: Glossary):
    assert resolve_source(["Deutschland"], glossary) == "site:de.linkedin.com/in/"


def test_resolves_germany_from_city_and_country_token_pair(glossary: Glossary):
    # "Frankfurt, Germany": two raw tokens, one normalized country.
    assert resolve_source(["Frankfurt", "Germany"], glossary) == "site:de.linkedin.com/in/"


def test_resolves_germany_from_two_cities_same_country(glossary: Glossary):
    # "Berlin and Munich": two raw tokens, both cities of Germany.
    assert resolve_source(["Berlin", "Munich"], glossary) == "site:de.linkedin.com/in/"


def test_resolves_germany_from_local_city_name_munchen(glossary: Glossary):
    assert resolve_source(["München"], glossary) == "site:de.linkedin.com/in/"


# ---------------------------------------------------------------------------
# Must use the global source (site:linkedin.com/in/)
# ---------------------------------------------------------------------------


def test_global_source_for_two_distinct_countries_by_name(glossary: Glossary):
    # "Germany and Poland"
    assert resolve_source(["Germany", "Poland"], glossary) == DEFAULT_SOURCE


def test_global_source_for_two_distinct_countries_slash_separated(glossary: Glossary):
    # "Austria / Germany"
    assert resolve_source(["Austria", "Germany"], glossary) == DEFAULT_SOURCE


def test_global_source_for_unknown_country(glossary: Glossary):
    assert resolve_source(["Narnia"], glossary) == DEFAULT_SOURCE


def test_global_source_for_ambiguous_city_mapping_to_different_countries(glossary: Glossary):
    # Two cities that each resolve unambiguously, but to two different
    # countries ("Vienna" -> Austria, "Munich" -> Germany) — the overall
    # location set is still ambiguous at the country level.
    assert resolve_source(["Vienna", "Munich"], glossary) == DEFAULT_SOURCE


def test_global_source_for_empty_locations(glossary: Glossary):
    assert resolve_source([], glossary) == DEFAULT_SOURCE


def test_global_source_for_single_country_without_verified_cctld(glossary: Glossary):
    # United States is a known country in the glossary but has no
    # configured ccTLD — a single, unambiguous, but unverified country
    # must still fall back to the global source.
    assert resolve_source(["United States"], glossary) == DEFAULT_SOURCE


# ---------------------------------------------------------------------------
# Country count is normalized, not raw-token count
# ---------------------------------------------------------------------------


def test_country_count_uses_normalized_countries_not_raw_token_count(glossary: Glossary):
    # Four raw tokens, but they all normalize to the single country
    # Germany, so this must still resolve to the German ccTLD.
    locations = ["Frankfurt", "Germany", "Munich", "Berlin"]
    assert resolve_source(locations, glossary) == "site:de.linkedin.com/in/"


def test_unresolvable_token_does_not_block_a_single_known_country(glossary: Glossary):
    # An unrecognized token contributes nothing to the normalized
    # country count, so the one real, identified country still wins.
    assert resolve_source(["Germany", "Narnia"], glossary) == "site:de.linkedin.com/in/"


# ---------------------------------------------------------------------------
# The location block is never removed from SearchSpec
# ---------------------------------------------------------------------------


def test_resolve_source_for_spec_does_not_mutate_locations(glossary: Glossary):
    spec = SearchSpec(locations=["Frankfurt", "Germany"])
    original_locations = list(spec.locations)

    source = resolve_source_for_spec(spec, glossary)

    assert source == "site:de.linkedin.com/in/"
    assert spec.locations == original_locations


def test_resolve_source_for_spec_does_not_mutate_locations_for_global_source(glossary: Glossary):
    spec = SearchSpec(locations=["Germany", "Poland"])
    original_locations = list(spec.locations)

    source = resolve_source_for_spec(spec, glossary)

    assert source == DEFAULT_SOURCE
    assert spec.locations == original_locations


def test_resolve_source_for_spec_does_not_mutate_empty_locations(glossary: Glossary):
    spec = SearchSpec()

    source = resolve_source_for_spec(spec, glossary)

    assert source == DEFAULT_SOURCE
    assert spec.locations == []
