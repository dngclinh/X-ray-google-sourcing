# Handoff — Real "Lead Electrical Engineer" JD gap-closing session

**Date:** 2026-07-08
**Branch:** main (no commit made — changes are in the working tree, uncommitted)
**Status:** Complete. 288/288 tests passing, `compileall` clean, Streamlit smoke test OK.

## Goal

The user ran a real "Lead Electrical Engineer" job posting (data-center
due-diligence role at gbc engineers, Germany/Poland) through the running
Streamlit app and compared the deterministic engine's output against a
Claude-authored benchmark for the same JD. The gap was large: Core
functions empty, "Berlin" wrongly included as a job location, German/
English wrongly shown as NICE-TO-HAVE, and most MUST/IMPORTANT skill
terms missing. This session diagnosed and closed that gap.

## Root causes found (all fixed except one deliberately-accepted trade-off)

Investigated via 2 parallel Explore agents + manual tracing against the
literal JD text, then designed via 1 Plan agent. Full plan is preserved
at `C:\Users\linh.duongn\.claude\plans\t-jd-lead-electrical-flickering-treehouse.md`.

1. **Segmentation bug (generic engine).** The JD's Responsibilities/
   Profile/Offer sections have no bullet markers (`-`, `•`) — common
   when copy-pasted from a rendered HTML `<li>` list. `_split_into_blocks`
   in `src/xray/extractor.py` only started a new block on a blank line
   or bullet marker, so ~10 requirement lines merged into one giant
   block. `_classify_priority()` then found the nice-to-have cue "a
   plus" from an *unrelated* clause ("broader European experience a
   plus") inside that merged block and force-labeled the whole block —
   including "Fluent German and professional English" — as
   `nice_to_have`. This was the actual cause of the German/English
   mislabeling, not a language-extraction bug.
2. **No context guard on location extraction (generic engine).**
   `_extract_locations` did an unconditional whole-document scan, unlike
   `_extract_company_types` (which already guards against "our"/"we
   are" employer self-reference). "Berlin" appeared once, in
   "headquartered in Berlin, Germany" — pure company-HQ mention — and
   was swept in.
3. **`SearchSpec.core_functions` was a dead field.** Declared in
   `models.py`, read by `assembler.py`/`validator.py`, but never
   assigned by `extractor.py` — always `[]`, for every JD, every job
   family, in the entire engine's history until this session. The pack
   schema also had no section for core-function vocabulary.
4. **Missing Electrical Engineering vocabulary (pack-only).** hyperscale,
   colocation, Tier III/IV, grid connection, BIM/Revit MEP, busbar,
   standby generation, greenfield/brownfield, HOAI, feasibility studies,
   Uptime Institute Tier standards, and core-function-shaped evidence
   (technical due diligence, electrical planning, multidisciplinary
   teams, stakeholder communication) were all absent from
   `electrical_engineering.yaml`.
5. **Closed-set language-cue gap.** The JD says "Fluent German" (no
   "in"); `_LANGUAGE_PROFICIENCY_CUES` only recognized "fluent in".
   Confirmed with user: added bare "fluent".

**Explicitly out of scope** (confirmed with user, not touched):
- Inventing adjacent/equivalent titles not literally in the JD (Claude's
  benchmark suggested "Senior Electrical Engineer", "Electrical Design
  Lead" as "equivalent" — these are Claude's own semantic expansion, not
  literal JD text; CLAUDE.md forbids the engine inventing title
  relationships the JD doesn't literally support). Guarded by a
  `forbidden_titles` regression assertion.
- Expanding `knowledge/company_types.yaml` with data-center-specific
  company types — that file is schema-enforced generic/cross-family
  knowledge (`REQUIRED_COMPANY_TYPES` in `glossary.py`); no pack-scoped
  company-type concept exists, adding one is a separate architectural
  decision.

## What changed (12 files, +679/-56 lines)

| File | What |
|---|---|
| `src/xray/extractor.py` | `_ends_with_continuation_cue` + `_CONTINUATION_TRAILING_WORDS` (segmentation fix); `_LOCATION_NEGATIVE_CONTEXT_RE` + rewritten `_extract_locations` (now segment-aware, per-match rejection); `_extract_pack_terms` returns a 5-tuple including `core_functions`; bare `"fluent"` added to `_LANGUAGE_PROFICIENCY_CUES`. |
| `src/xray/knowledge_loader.py` | New `CoreFunction` dataclass + `_parse_core_function`; `"core_functions"` added to allowed top-level fields and to the shared duplicate-id namespace check. |
| `knowledge/job_families/electrical_engineering.yaml` | New `core_functions:` section (4 entries); 3 new `industries` (Digital Infrastructure, Engineering Consulting, Industrial Practice); 2 new `skill_groups` (`facility_scale_class`, `grid_utility_infrastructure`) + 2 more (`site_development_process`, `bim_coordination`); hyperscale/colocation/Tier III/IV added to `specialization_signals.data_center_mission_critical` and `industries.data_center_industry`; `standby generation` added to `backup_emergency_power`; `busbar` added to `switchgear_substations`. |
| `knowledge/job_families/_schema_example.yaml` | Illustrative `core_functions:` section added for documentation parity. |
| `tests/fixtures/electrical_jds.py` | New fixture `REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD` — the real JD, verbatim, no bullets added. Corpus is now 14 fixtures. |
| `tests/fixtures/sample_jds.py` | New fixtures: `BULLETLESS_LOOSE_LIST_JD`, `LOCATION_NEGATIVE_HEADQUARTERED_JD`, `LOCATION_NEGATIVE_GLOBAL_DESIGN_CENTER_JD`, `LOCATION_POSITIVE_DESPITE_UNRELATED_HQ_MENTION_JD`, `LANGUAGE_FLUENT_BARE_JD`, `PACK_CORE_FUNCTION_JD`. |
| `tests/test_extractor.py` | Unit tests for segmentation, location guard (3 cases), bare-fluent cue, `core_functions` extraction (positive + "no pack -> empty" negative). `_software_engineer_pack()` extended with a `core_functions` entry. |
| `tests/test_family_detector.py` | `core_functions=()` added to every synthetic `JobFamilyPack(...)` construction (required field, no default — mechanical fix for the schema change). |
| `tests/test_knowledge_loader.py` | `core_functions` added to `_valid_pack_dict()`, the optional-section-deletion test, the schema-example assertion, and a new duplicate-id-across-sections test. |
| `tests/test_job_family_electrical_engineering.py` | 6 new positive/negative pairs: hyperscale-alone activates specialization / bare skill terms alone don't; Digital Infrastructure industry positive / Engineering Consulting near-miss negative; technical-due-diligence core function positive/negative. |
| `tests/test_regression_electrical.py` | New `ExpectedProperties` fields (`forbidden_locations`, `required_core_functions`, `forbidden_core_functions`); new benchmark case for the real JD; `_ALL_INDUSTRY_NAMES` extended to 6; `COMPANY_INTRODUCTION_FALSE_POSITIVE_EN_JD` case updated (now correctly picks up "Engineering Consulting"); stale comment about the never-populated `core_functions` field rewritten to reflect the new `spec.confidence` framing; new standalone test `test_real_lead_electrical_engineer_jd_has_no_must_tier_skills`. |
| `docs/benchmark-method.md` | Category 2 scoring description updated (Core Function evidence is scored again, not skipped); corpus count 13→14; known-limitations bullet rewritten. |

## Accepted trade-off (not fixed, documented instead)

Adding the skill term **"Revit MEP"** (needed — appears verbatim in the
real JD) causes the pack's pre-existing bare **"MEP"** industry/
specialization-signal term to also match (since "MEP" is a whole word
inside "Revit MEP"), so `spec.industries` for the real-JD fixture
includes `"Building Services / MEP"` even though the JD isn't about
building services. **Not fixed** because removing bare "MEP" would
break the already-passing `AMBIGUOUS_SPECIALIZATION_EN_JD` fixture,
which relies on "MEP" as one of exactly two tied specialization signals.
Documented with an inline comment in `test_regression_electrical.py` at
the `real_lead_electrical_engineer_...` case. If this ever needs
revisiting, the fix would be replacing bare `"MEP"` with more specific
phrases (`"MEP engineering"`, `"MEP design"`, `"MEP coordination"`)
across `specialization_signals.building_services_mep` and
`industries.building_services_industry` — but that requires also
updating `AMBIGUOUS_SPECIALIZATION_EN_JD`'s JD text to use one of the
new specific phrases instead of bare "MEP".

## Verified end state (real JD, run through `generate_xray_queries`)

```
family: Electrical Engineering
specialization: Data Center / Mission Critical
titles: ['Lead Electrical Engineer', 'Electrical Engineer']
industries: ['Data Center / Mission Critical', 'Building Services / MEP',
             'Digital Infrastructure', 'Engineering Consulting', 'Industrial Practice']
core_functions: ['Technical Due Diligence', 'Electrical Planning',
                 'Multidisciplinary Coordination', 'Stakeholder Communication']
locations: ['Germany', 'Poland']                      # Berlin correctly excluded
languages important: ['German', 'English'] | nice: ['Polish']
skills.must: []                                        # correct — no MUST-cue phrase anywhere in this JD
skills.important: [hyperscale, colocation, BIM, HV, MV, grid connection,
                    greenfield, brownfield, utility availability,
                    constraints on power delivery, low voltage distribution,
                    switchgear, busbar, UPS, standby generation, Tier III,
                    Tier IV, HOAI, HOAI phase, feasibility studies,
                    planning and permitting]
skills.nice_to_have: [BIM coordination, Revit MEP, Uptime Institute Tier standards]
strict source: site:linkedin.com/in/                   # correct — 2 distinct countries
BER13 / FRA31 / HAM01 project codes: absent from both locations and skills
```

## How to resume / verify

```bash
pytest tests/ -q                                  # 288 passed
python -m compileall .                            # clean
pytest tests/test_regression_electrical.py -k real_lead -v   # the two dedicated cases
```

Nothing is committed — `git status` shows 12 modified files, no new
untracked files outside `docs/handoffs/`. Review the diff and commit
when ready.
