# Electrical Engineering benchmark method

This document defines how "at least 90% functional equivalence with
approved Claude benchmark outputs" (CLAUDE.md section 1) is measured for
the Electrical Engineering job family, and how the deterministic
regression suite under `tests/` relates to that measurement.

It covers two distinct, complementary mechanisms:

1. **The deterministic property harness** — `tests/test_regression_electrical.py`,
   run over `tests/fixtures/electrical_jds.py`. A hard pass/fail pytest
   gate over structural properties (detected family, required/forbidden
   terms, source domain, warnings, query-variant relationships). It runs
   in CI on every change and never compares against Claude output — it
   only checks the engine against itself, deterministically.
2. **The weighted scoring method** (this document) — an offline
   comparison between the deterministic engine's output
   (`generate_xray_queries`) and the approved Claude-authored benchmark
   output for the same JD (produced by the `jd-to-xray` skill, reviewed
   with `audit-xray`). This is how "90% functional equivalence" is
   actually computed; it produces a percentage, not a boolean.

Do not conflate the two: the property harness enforces invariants that
must always hold (e.g. "Electrician must never be promoted to Lead
Electrical Engineer"); the weighted score measures *how close* a
passing engine output is to what Claude, working from the same JD,
would independently produce.

## Why not exact string equality

CLAUDE.md section 1 explicitly targets "at least 90% functional
equivalence," not identity — the deterministic engine is a rules and
knowledge engine, not a language understander, so its phrasing,
ordering, and expansion choices will legitimately differ from Claude's
in ways that don't change what the query actually finds. Scoring must
therefore reward *functional* agreement (same titles represented, same
MUST/IMPORTANT/NICE tiering, same locations, same domain evidence) over
*textual* agreement (identical Boolean string). See
`tests/test_regression_electrical.py`'s module docstring for the same
principle applied to the property harness.

## Scoring unit

One score is computed per **(JD, variant)** pair — Strict, Balanced,
Broad, and Hidden Titles are scored independently, since CLAUDE.md
section 6 gives each variant different semantics and a defect in one
(e.g. Hidden Titles still requiring the literal title) must not be
diluted by the other three scoring well. A JD's overall score is the
mean of its four variant scores unless otherwise noted.

## Category weights

Each variant comparison is scored across eight categories. Weights sum
to 100 and were chosen to mirror `audit-xray`'s ten audit criteria,
consolidated to the granularity a single query variant can be scored at
(Overall assessment and Recommended corrected queries are audit-only
outputs, not scoring inputs).

| # | Category | Weight | `audit-xray` criteria it mirrors |
|---|---|---|---|
| 1 | Title accuracy | 15 | 1 (Candidate Profile alignment), 7 (terminology expansion) |
| 2 | Core Function / Industry evidence | 15 | 1, 9 (precision risk) |
| 3 | MUST-skill coverage | 20 | 3 (MUST/IMPORTANT/NICE treatment), 8 (recall risk) |
| 4 | IMPORTANT/NICE-TO-HAVE skill coverage | 10 | 3, 4 (variant progression) |
| 5 | Location block correctness | 15 | 1, 6 (ccTLD strategy) |
| 6 | Language/company-type tier correctness | 5 | 1, 3 |
| 7 | Exclusion / false-positive avoidance | 10 | 2 (field-type mixing), 10 (over-filtering) |
| 8 | Variant structural correctness | 10 | 4, 5 (Hidden Titles), 6 (ccTLD), Boolean grouping rules |

MUST-skill coverage carries the highest weight deliberately: an
over- or under-inflated MUST list is the single most consequential
defect a query can have (`examples/common-errors.md` #3 — "too many
mandatory skills" collapses recall to near zero; a missing MUST term
does the opposite, flooding results).

## Per-category scoring formulas

Let `claude_X` be the set/value extracted from the approved Claude
output for category X, and `engine_X` the equivalent extracted from
`generate_xray_queries`'s `(SearchSpec, QueryVariants)` result.

**1. Title accuracy** — set comparison over the title OR group.
`score = |claude_titles ∩ engine_titles| / |claude_titles ∪ engine_titles|`
(Jaccard similarity). An engine title with no counterpart in Claude's
output (over-expansion) penalizes exactly as much as a missing one
(under-expansion), consistent with `audit-xray` criterion 7's "note any
lens that seems force-fit or invented."

**2. Core Function / Industry evidence** — boolean per dimension, then
averaged: 1.0 if `engine`'s Core Function clause and Industry clause
each represent the same real-world dimension Claude's Candidate Profile
states, 0.5 if only one of the two is represented, 0.0 if neither is
or if the engine asserts a dimension Claude's JD-grounded profile does
not support (a false positive is scored identically to a miss — CLAUDE.md
section 7 treats an invented classification as worse than an honest
gap). `SearchSpec.core_functions` is now populated by extraction (a
job-family pack's own `core_functions:` section, matched the same way
`industries` is — see `knowledge/job_families/electrical_engineering.yaml`),
so this category scores both dimensions independently; a pack that has
not yet curated its own `core_functions` vocabulary will still score 0.0
on that half, same as any other genuine coverage gap.

**3. MUST-skill coverage** — precision and recall over the MUST set,
combined as F1:
`precision = |claude_must ∩ engine_must| / |engine_must|`,
`recall = |claude_must ∩ engine_must| / |claude_must|`,
`score = 2 · precision · recall / (precision + recall)` (0 if both are
0). An engine MUST list padded beyond Claude's is penalized via
precision; a thinned-out list is penalized via recall — this
deliberately makes both `common-errors.md` #3 ("too many mandatory
skills") and a missing genuine MUST equally visible in the score.

**4. IMPORTANT/NICE-TO-HAVE skill coverage** — Jaccard similarity over
`important ∪ nice_to_have`, same formula as category 1. Lower weight
than MUST coverage because CLAUDE.md section 6 treats these as optional
OR expansion, where partial overlap still returns usable candidates.

**5. Location block correctness** — 0.6 × Jaccard similarity over the
location-term set, + 0.4 × a boolean check that the `site:` source
matches Claude's stated ccTLD strategy (same ccTLD, or both using the
global source) **and** the location OR group is still present alongside
any ccTLD (CLAUDE.md section 5 — a ccTLD used without the location block
scores 0 on this half regardless of term overlap, mirroring
`audit-xray` criterion 6's "critical error" framing).

**6. Language/company-type tier correctness** — for each requirement
Claude's benchmark states, 1.0 if the engine places it in the same tier
(must/important/nice_to_have or "not a query filter" for
important/nice_to_have per CLAUDE.md section 6), 0.5 if present but in
an adjacent tier, 0.0 if absent or invented; averaged across all
requirements Claude's output states. A requirement the engine invents
that Claude's output does not state also scores 0.0 (counted as an
extra "requirement" for averaging purposes) — this is the direct
scoring analogue of `tests/test_regression_electrical.py`'s
company-introduction and mandatory/optional-language fixtures.

**7. Exclusion / false-positive avoidance** — starts at 1.0; deduct 0.5
for each Claude-flagged false positive the engine output exhibits
(field-type mixing per `examples/common-errors.md` #1, a location or
skill term leaking from context that should have been rejected per the
company-type/language negative-context guards, or an excessive `NOT`
chain per #4), floored at 0.0.

**8. Variant structural correctness** — 0.25 each for: (a) the query
starts with a well-formed `site:` prefix and has balanced parentheses /
no dangling operator (`src/xray/validator.py`'s structural checks); (b)
Strict has at least as many required clauses as Broad (the one
narrowing relationship this engine version guarantees — see "Known
limitations"); (c) Hidden Titles omits the literal target title clause
(CLAUDE.md section 6); (d) no OR group mixes two semantic types
(`examples/common-errors.md` #1/#5).

## Per-JD and aggregate score

```
variant_score   = Σ (category_score × category_weight) / 100
jd_score        = mean(strict_score, balanced_score, broad_score, hidden_titles_score)
family_score    = mean(jd_score for every JD in the family's benchmark corpus)
overall_score   = mean(family_score for every supported job family)
```

`family_score` is what CLAUDE.md section 1's "at least 90% functional
equivalence... across supported job families" refers to concretely: the
Electrical Engineering family passes the bar when its `family_score`
(averaged over `tests/fixtures/electrical_jds.py`'s corpus, or a wider
corpus if one is later authorized) is **≥ 90%**.

**Floor rule:** in addition to the 90% family average, no individual
`jd_score` may fall below **70%** — a family can't average above the bar
by being excellent on easy JDs while badly failing a specific pattern
(e.g. one specialization). A JD below the floor is a required-fix item
even if the family average already clears 90%.

## Current benchmark corpus

`tests/fixtures/electrical_jds.py` defines 14 JDs; the table in that
module's docstring maps each to the dimensions it covers (short/long,
English/German, explicit/implicit seniority, all three specializations,
Germany/Germany+Poland/Poland-only locations, mandatory/optional
language, company-introduction false positive, two adjacent-but-incorrect
families, and — the 14th, real-world fixture —
`REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD`, a real
job posting with no bullet markers, a company-HQ location false
positive, and dense core-function/skill evidence). `tests/test_regression_electrical.py`
gates every fixture's structural properties deterministically; applying
this document's weighted rubric to the same 14 JDs (comparing engine
output against `jd-to-xray`-produced benchmark output for each) is how
the family's 90% figure is actually produced. Extending the corpus — for a new
specialization, a new locale, or a bug-report JD — should add to
`tests/fixtures/electrical_jds.py` first (with matching property
coverage in `tests/test_regression_electrical.py`) and only then be
scored under this rubric.

## Worked example

JD: `SHORT_EXPLICIT_SENIORITY_EN_JD` ("Senior Electrical Engineer needed
in Munich, Germany."). Assume the approved Claude benchmark output for
this JD states: titles `{"Senior Electrical Engineer", "Senior
Electrical Design Engineer"}`, no Core Function/Industry qualifier (the
JD is too short to state one), no MUST/IMPORTANT skills, locations
`{"Munich", "Germany"}`, global `site:linkedin.com/in/` source (Claude
did not commit to a ccTLD from a single short line), no language/company
requirement, no exclusions, Hidden Titles built from adjacent titles
only.

Scoring the engine's **Strict** variant
(`site:de.linkedin.com/in/ ("Electrical Engineer" OR "Senior Electrical
Engineer") AND (Munich OR Germany)`):

| Category | Engine value | Score | Weight | Contribution |
|---|---|---|---|---|
| 1. Title accuracy | `{"Electrical Engineer","Senior Electrical Engineer"}` vs. Claude's `{"Senior Electrical Engineer","Senior Electrical Design Engineer"}` → intersection 1, union 3 | 0.33 | 15 | 5.0 |
| 2. Core Function/Industry | neither side has one → vacuously aligned | 1.0 | 15 | 15.0 |
| 3. MUST-skill coverage | both empty → no MUST claims made or missed | 1.0 | 20 | 20.0 |
| 4. IMPORTANT/NICE coverage | both empty | 1.0 | 10 | 10.0 |
| 5. Location correctness | term overlap 1.0; ccTLD strategy differs (engine chose `de`, Claude chose global) → 0.6×1.0 + 0.4×0.0 | 0.6 | 15 | 9.0 |
| 6. Language/company-type | no requirements either side | 1.0 | 5 | 5.0 |
| 7. Exclusion/false-positive | none present | 1.0 | 10 | 10.0 |
| 8. Variant structural correctness | well-formed (0.25); Strict≥Broad clause count (0.25); n/a for Hidden Titles on this variant's own score (0.25 credited); no field-type mixing (0.25) | 1.0 | 10 | 10.0 |

`variant_score = (5.0+15.0+20.0+10.0+9.0+5.0+10.0+10.0)/100 = 0.84` →
84%. The gap is driven almost entirely by category 1 (the engine's pack
does not yet carry an "Electrical Design Engineer" seniority-tier title
term — a legitimate finding to route through `xray-code-maintenance` as
a category-3 knowledge-pack gap) and category 5's ccTLD strategy
disagreement (a defensible, not incorrect, choice per CLAUDE.md section
5, but scored as partial credit here since Claude's benchmark made a
different defensible choice). Repeating this for Balanced, Broad, and
Hidden Titles and averaging the four gives this JD's `jd_score`.

## Known limitations affecting scoring

State these plainly per CLAUDE.md section 7 — they are why certain
categories above are scored more leniently, not defects in this
methodology:

- **The pairwise Strict-narrower-than-Balanced and
  Balanced-narrower-than-Broad clause-count relationships are still not
  scored as a hard requirement in category 8.** `SearchSpec.core_functions`
  is now populated, but `SearchSpec.confidence` (used by `assembler.py`'s
  `_strongest_evidence_group` to pick Balanced's single evidence clause)
  is still never populated by extraction, so Balanced's evidence clause
  can still tie Strict's clause count depending on pack content. Only the
  universal Strict-≥-Broad relationship is asserted as a hard invariant
  (see `tests/test_regression_electrical.py`'s comment on this).
- **MUST/IMPORTANT/NICE-TO-HAVE classification is English-cue-only.**
  `LONG_INDUSTRIAL_POWER_DE_JD` demonstrates this concretely: German
  cue phrases ("zwingend erforderlich", "von Vorteil") are not
  recognized, so both terms default to "important" regardless of the
  JD's intent. Category 6 should credit a German-cue JD leniently
  (adjacent-tier, 0.5) rather than as a full miss, since this is a
  documented, not silent, gap.
- **Hidden Titles does not yet substitute adjacent/feeder titles** — it
  only omits the literal title clause (`JobFamilyPack.hidden_title_signals`
  is schema-only, not yet consumed). Category 8's Hidden Titles check is
  scored on title *omission* only, not on feeder-title substitution
  quality, until that mechanism exists.
- **Only one production job-family pack exists** (Electrical
  Engineering). `overall_score` currently equals Electrical
  Engineering's `family_score` alone; the mean-of-families formula
  above is written for when additional packs are added.

## How to run the deterministic gate

```
pytest tests/test_regression_electrical.py -v
```

This is the CI-facing, zero-tolerance half of this benchmark. The
weighted scoring method in this document is an offline exercise (via
the `jd-to-xray` and `audit-xray` skills) run when the family's
functional-equivalence percentage needs to be re-measured — e.g. after
a knowledge-pack change, or periodically to confirm the 90% bar still
holds as `knowledge/job_families/electrical_engineering.yaml` evolves.
