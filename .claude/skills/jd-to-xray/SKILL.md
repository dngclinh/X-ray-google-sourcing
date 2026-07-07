---
name: jd-to-xray
description: Use when Claude is asked to directly analyze a Job Description and produce the professional benchmark LinkedIn X-ray result (Strict/Balanced/Broad/Hidden Titles Boolean searches). This is a Claude-side, offline authoring/analysis workflow — it is not the runtime Python engine under src/xray/, and its output is not called by the running Streamlit app.
---

# JD to X-ray

## Scope and boundary

This skill produces the **approved benchmark output** that the
deterministic runtime engine (`src/xray/`) is measured against (see
CLAUDE.md §1, §2, §4). It is used by Claude directly, outside the running
app, to:

- author or validate benchmark results for a job family;
- review/QA outputs the deterministic engine produces;
- extend or sanity-check `knowledge/job_families/` packs.

It must never be invoked as part of a runtime request/response cycle
inside the Streamlit app. If a step below requires judgment that cannot
be reduced to a deterministic rule, it stays skill-only (category 3 in
CLAUDE.md §4) — do not silently convert it into engine code.

See `references/rules.md` for the detailed field-by-field rules and
Boolean grammar, `references/jd-patterns.md` for handling JD shapes
(long/short, multi-location, multi-title, etc.), and
`examples/common-errors.md` for mistakes to avoid before finalizing
output.

## Workflow

Work through these steps in order for every JD. Do not skip a step or
merge two steps together — each one produces an input the next step
depends on.

### 1. Build Candidate Profile

Read the full JD and extract, as plain structured facts (no Boolean
syntax yet):

- **Source** — literal source JD text/company, for traceability.
- **Target Titles** — the literal title(s) used in the JD.
- **Core Function** — the primary discipline/function (e.g. Software
  Engineering, Electrical Design, Finance Ops). Flag as heuristic if the
  JD is ambiguous or hybrid (CLAUDE.md §7).
- **Industry/Domain** — sector context if stated or strongly implied.
- **Seniority** — level cues (years of experience, title modifiers such
  as Senior/Lead/Principal).
- **Location(s)** — every location mentioned, including remote/hybrid
  notes.
- **Language** requirements, if any.
- **Company type**, if stated (startup, enterprise, agency, etc.).

### 2. Classify requirements as MUST / IMPORTANT / NICE-TO-HAVE

Classify every requirement (skills, certifications, experience) into
exactly one bucket, using explicit JD cues where present ("required",
"must have", "preferred", "nice to have", "bonus"). Where cues are
absent, apply best-effort judgment and say so explicitly — do not present
a guess as a certainty (CLAUDE.md §7).

### 3. Build independent keyword groups

Group requirements so each group represents one semantic concept (one
skill, one title family, one location set, etc.). Never mix semantic
types (e.g. skills and locations) inside the same OR group — see
`examples/common-errors.md`.

### 4. Expand terminology

For each keyword group, expand using all of the following lenses, only
where genuinely applicable:

- official title;
- equivalent/adjacent title;
- abbreviation;
- full form;
- English term;
- local-market terminology (only where it is a real, known equivalent —
  do not invent local-language terms, per CLAUDE.md §7).

### 5. Generate the four query variants

Produce all four, per CLAUDE.md §6:

- **Strict** — MUST criteria only, minimal expansion.
- **Balanced** — MUST + IMPORTANT, moderate expansion. Default
  recommended variant.
- **Broad** — MUST + wide synonym/title expansion + NICE criteria as
  optional OR terms.
- **Hidden Titles** — drop the literal target title; use adjacent/feeder
  titles and skill-based terms instead, to surface candidates whose
  current title doesn't match the target role.

Apply Boolean grouping and ccTLD/location rules from
`references/rules.md` to every variant.

### 6. Audit group integrity and recall risk

Before finalizing, check each variant against `examples/common-errors.md`
and confirm:

- no OR group mixes semantic types;
- no group is so generic it will flood results (e.g. a bare function
  name with no qualifier);
- MUST criteria count is small enough that real candidates can plausibly
  satisfy all of them simultaneously;
- exclusions (`NOT`) are minimal and justified, not a substitute for
  precise inclusion terms;
- location terms appear only in the location block, never merged into a
  title or skill OR group;
- job-posting boilerplate suffixes are stripped from titles (see
  `references/rules.md`).

Note any recall/precision trade-off you made explicitly in the output's
Adjustment Logic section.

## Required output

Always return exactly these eight sections, in this order:

1. **Candidate Profile**
2. **Requirement Priority** (MUST / IMPORTANT / NICE-TO-HAVE)
3. **Keyword Map** (groups and their expansions)
4. **Strict Search**
5. **Balanced Search**
6. **Broad Search**
7. **Hidden Titles Search**
8. **Adjustment Logic** (what trade-offs were made and why, including any
   heuristic calls per CLAUDE.md §7)

If the job family is not one this skill/knowledge base supports, say so
explicitly in the output instead of inventing keyword relationships
(CLAUDE.md §7).
