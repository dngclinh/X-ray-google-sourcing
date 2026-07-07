---
name: audit-xray
description: Use when asked to audit, review, QA, or critique an existing LinkedIn X-ray Boolean query — whether it was hand-written, produced by Claude via the jd-to-xray skill, or produced by the Streamlit runtime engine (src/xray/). This is a Claude-side, offline review workflow — it is not runtime Python logic and is never called by the running app.
---

# Audit X-ray

## Scope and boundary

This skill audits an X-ray query (or a set of Strict/Balanced/Broad/
Hidden Titles variants) against its source Job Description, regardless
of where the query came from:

- a manually written X-ray query;
- Claude-generated output (e.g. from the `jd-to-xray` skill);
- Streamlit-generated output (the deterministic `src/xray/` engine).

It is a skill-only, offline review workflow (CLAUDE.md §2–§3). It never
runs inside the Streamlit request/response cycle, and it does not modify
runtime code — it only produces findings and recommendations. Whether a
given finding should ever become runtime code is itself part of the
required output (see "Changes suitable for runtime code" /
"Changes that must remain skill-only" below), decided against the three
categories in CLAUDE.md §4.

This skill assumes familiarity with `jd-to-xray`'s workflow and
references (`references/rules.md`, `references/jd-patterns.md`,
`examples/common-errors.md`) — reuse those definitions rather than
re-deriving field rules here.

## Inputs required

Before auditing, confirm you have:

- the original Job Description (or a reliable summary of it);
- the query/queries under review — ideally all four variants, but a
  single query may be audited alone if that's all that's provided (note
  this limitation in the Overall assessment);
- the source of the query (manual / Claude / Streamlit), since Known
  Limitations (CLAUDE.md §7) apply differently: Streamlit output may be
  heuristic by construction, while manual/Claude output should be held
  to the full `jd-to-xray` standard.

If the JD is not provided, audit only internal consistency (grouping,
Boolean correctness, variant progression) and say plainly that
JD-alignment criteria (below) could not be checked.

## Audit criteria

Work through all ten criteria, in order, for every query under review.
Do not skip a criterion because the query "looks fine" — state the
check was performed even when it passes.

### 1. Candidate Profile alignment

Does the query's content trace back to a Candidate Profile that
actually matches the JD? Check title(s), core function, industry,
seniority, location(s), language, and company type each against what
the JD states — flag anything in the query that isn't grounded in the
JD, and anything in the JD that's missing from the query without
explanation.

### 2. Correct distinction between field types

Verify each OR group represents exactly one of the following semantic
types, per `references/rules.md`, and that no group blends two:

- titles;
- core function;
- industry;
- skills;
- location;
- language;
- company environment;
- exclusions.

A group mixing any two of these is a critical error (see
`examples/common-errors.md` #1 and #5, and the canonical bad example
`("electrical" OR "Poland" OR "Germany")`).

### 3. MUST / IMPORTANT / NICE-TO-HAVE treatment

Check that:

- MUST terms are the small, genuinely non-negotiable set (not inflated —
  see `examples/common-errors.md` #3);
- IMPORTANT/NICE terms appear as optional OR expansion in Balanced/Broad,
  not silently AND-ed as if MUST;
- nothing was promoted or demoted between buckets without a stated
  reason;
- where the JD lacks explicit cues, the query's classification is
  flagged as best-effort, not asserted as certain (CLAUDE.md §7).

### 4. Correct Strict / Balanced / Broad / Hidden Titles progression

Verify the four variants actually form a progression, per CLAUDE.md §6:

- Strict ⊆ Balanced in constraint relaxation direction (Strict is
  narrowest: MUST only, minimal expansion);
- Balanced adds IMPORTANT criteria and moderate expansion over Strict;
- Broad adds wide synonym/title expansion and includes NICE as optional
  OR terms, without dropping MUST criteria;
- Hidden Titles is structurally different (see criterion 5), not simply
  a copy of Broad.

Flag any variant that doesn't meaningfully differ from its neighbor
(e.g. Balanced identical to Strict), or where Broad is narrower than
Balanced.

### 5. Hidden Titles must reduce dependence on conventional titles

Specifically confirm the Hidden Titles variant:

- does not simply reuse the literal target title group from
  Strict/Balanced/Broad;
- substitutes adjacent/feeder titles and/or skill-based terms in place
  of (not in addition to, as a MUST) the conventional title;
- still respects field-type separation (criterion 2) and MUST/IMPORTANT/
  NICE treatment (criterion 3) — "hidden titles" changes what stands in
  for the title group, not the discipline of building the query.

If Hidden Titles still ANDs the conventional title as a MUST term, this
is a critical error — the variant fails its purpose.

### 6. Correct ccTLD strategy without removing the location block

Per `references/rules.md` ("ccTLD strategy") and CLAUDE.md §5: if a
`site:xx.linkedin.com/in` ccTLD is used, confirm the location OR group
(city/region/country terms from the JD) is still present in the query.
A ccTLD alone, with the location block dropped, is a critical error —
it silently narrows by domain without preserving location precision.

### 7. Consideration of six terminology expansion directions

Check that the query's keyword expansion considered, where genuinely
applicable, all six lenses from `jd-to-xray` step 4:

- official title;
- equivalent/adjacent title;
- abbreviation;
- full form;
- English term;
- local-market terminology.

Do not require all six to be present for every group — flag only where
a lens was clearly applicable and skipped (e.g. a well-known abbreviation
omitted), not where a lens is unnatural for that term (e.g. forcing a
local-market synonym that doesn't exist). Note any lens that seems
force-fit or invented as a separate finding (over-expansion risk).

### 8. Recall risks

Identify anything that could cause the query to miss qualified
candidates: too many MUST terms stacked together (see
`examples/common-errors.md` #3), missing synonym/title expansion,
missing feeder titles in Hidden Titles, an overly narrow location group,
or an unstated language requirement acting as a de facto filter.

### 9. Precision risks

Identify anything that could cause the query to return excess irrelevant
results: overly generic title/skill terms standing in for specific ones
(`examples/common-errors.md` #2), missing location/industry qualifiers
where the JD specifies them, or Broad/Hidden Titles expansion so wide it
loses connection to the Candidate Profile.

### 10. Over-filtering and false-positive risks

Distinguish this from precision/recall above: check specifically for
compounding effects — e.g. multiple independently reasonable AND groups
that, combined, statistically exclude nearly all real profiles; or
exclusion (`NOT`) chains (`examples/common-errors.md` #4) that remove
valid candidates for reasons unrelated to the JD. Also flag any single
term broad enough to produce false positives even though it's correctly
grouped (e.g. a common company name reused as a person's employer term
without qualification).

## Required output

Always return exactly these six sections, in this order:

1. **Overall assessment** — pass / pass-with-issues / fail, one or two
   sentences, naming the query source (manual / Claude / Streamlit) and
   whether the JD was available for alignment checks.
2. **Critical errors** — field-type mixing, Hidden Titles still
   requiring the conventional title, ccTLD used without a location
   block, or any other criterion-1/2/5/6 violation that breaks the
   query's core semantics. Empty list if none.
3. **Group-level findings** — a per-OR-group walkthrough (titles, core
   function, industry, skills, location, language, company environment,
   exclusions) noting what's correct and what's wrong, tied to the
   specific criterion number(s) above.
4. **Recommended corrected queries** — the corrected Strict / Balanced /
   Broad / Hidden Titles strings (or just the corrected form of whatever
   subset was reviewed), applying `references/rules.md` Boolean grouping
   rules.
5. **Changes suitable for runtime code** — findings that are generic,
   deterministic, and reproducible (CLAUDE.md §4 category 1, e.g. a
   grouping/parsing bug) or a missing dictionary entry (category 2, e.g.
   a missing synonym/title mapping) that could become a `src/xray/`
   change or a `knowledge/job_families/` entry, each with its target
   location and required tests (CLAUDE.md §5, §8) named.
6. **Changes that must remain skill-only** — findings that are semantic/
   contextual judgment calls (CLAUDE.md §4 category 3: ambiguous Core
   Function calls, JD interpretation, hybrid-role classification, or
   anything not reducible to a structured rule without more approved
   examples) and therefore stay in skill-level review rather than being
   encoded in Python or YAML.

If a finding's category is unclear, say so explicitly in section 5/6
rather than defaulting it into either bucket (CLAUDE.md §4: "If a change
doesn't clearly fit category 1 or 2, do not encode it as Python or
YAML — flag it as a skill-level concern instead").
