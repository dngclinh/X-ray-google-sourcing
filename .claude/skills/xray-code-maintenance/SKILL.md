---
name: xray-code-maintenance
description: Use when an audited X-ray sourcing issue (from audit-xray, a bug report, or a failed benchmark comparison) needs to be turned into an actual repository change — deciding whether it belongs in src/xray/, knowledge/, tests/, app.py, or must stay skill-only, and then implementing it safely with the required tests and verification. Use this before editing any runtime file to fix a sourcing defect.
---

# X-ray code maintenance

## Scope and boundary

This skill governs how an already-diagnosed sourcing issue (typically the
output of `audit-xray`, but also a manually reported bug or a benchmark
mismatch against `jd-to-xray` output) becomes a safe, tested repository
change. It sits downstream of diagnosis: it does not re-audit a query
from scratch — it takes a known root cause and routes it correctly per
CLAUDE.md §3–§4, then implements it.

This is a Claude-side workflow for editing the repository. It is not
runtime logic itself, and none of the categories below authorize adding
an LLM/NLP call to the runtime app (CLAUDE.md §2).

## Workflow

### 1. Classify the issue

Every issue must be placed in exactly one of these eight categories
before any file is touched. If a category doesn't fit cleanly, re-read
the issue rather than forcing it — see step 1's last rule.

1. **Generic engine bug** — the deterministic logic itself is wrong in a
   way that applies across all job families: broken extraction, wrong
   Boolean grouping, incorrect variant assembly, dedup/formatting bugs,
   `SearchSpec` construction/consumption errors. → `src/xray/`.
2. **Generic glossary gap** — a cross-family term is missing or wrong:
   generic seniority modifiers, generic company-type terms, generic
   exclusion boilerplate, structural title-suffix patterns that apply
   regardless of profession. → the shared/generic glossary under
   `knowledge/`.
3. **Job-family knowledge gap** — a whole job family's titles, skills, or
   synonyms are missing or wrong (e.g. no pack yet for "Data Engineer",
   or an existing pack is missing an obvious equivalent title). →
   `knowledge/job_families/<family>.yaml`.
4. **Specialization knowledge gap** — within an existing job family, a
   narrower specialization/sub-role is missing its own terms (e.g. the
   "Software Engineer" family pack exists but has no entry for
   "Embedded Software Engineer"). → a specialization-scoped section or
   entry inside the relevant `knowledge/job_families/<family>.yaml`, not
   a new engine branch and not a generic-glossary entry (a specialization
   term is still profession-specific).
5. **Priority-cue gap** — the MUST/IMPORTANT/NICE cue-phrase dictionary
   (e.g. "required", "must have", "nice to have", "bonus") is missing a
   real, widely-used cue phrase. → the cue-phrase dictionary under
   `knowledge/` (dictionary-driven knowledge per CLAUDE.md §4 category 2,
   not engine code — the engine only applies the cue list it's given).
6. **Validation gap** — the behavior is actually correct (or was just
   fixed), but there is no regression test guarding it, or an existing
   knowledge relationship lacks its required positive/negative pair. →
   `tests/`.
7. **UI issue** — the defect is in how `app.py` displays, labels, or
   passes through already-correct `SearchSpec`/query data (formatting,
   layout, missing variant tab, mislabeled section) with no change to
   extraction or query-assembly logic. → `app.py`.
8. **Semantic limitation that must remain skill-only** — the issue
   requires judgment about intent or ambiguous context (CLAUDE.md §4
   category 3) that cannot be reduced to a deterministic rule or a
   dictionary lookup without inventing a relationship the JD doesn't
   support. → no repository change; document it as a known limitation
   (CLAUDE.md §7) and/or a skill-level note for `jd-to-xray`/
   `audit-xray`, not code.

If the issue doesn't clearly fit categories 1–7, do not force it into
one — treat it as category 8 (CLAUDE.md §4: "If a change doesn't clearly
fit category 1 or 2, do not encode it as Python or YAML — flag it as a
skill-level concern instead").

### 2. Select the correct implementation layer

Map the classification directly to its owning location per CLAUDE.md §3:

| Category | Layer |
|---|---|
| 1. Generic engine bug | `src/xray/` |
| 2. Generic glossary gap | `knowledge/` (shared glossary) |
| 3. Job-family knowledge gap | `knowledge/job_families/<family>.yaml` |
| 4. Specialization knowledge gap | scoped entry inside the relevant `knowledge/job_families/<family>.yaml` |
| 5. Priority-cue gap | cue-phrase dictionary under `knowledge/` |
| 6. Validation gap | `tests/` |
| 7. UI issue | `app.py` |
| 8. Semantic limitation | no code — skill-level documentation only |

Do not split a single concern across two layers (e.g. half a fix in
`src/xray/` and half in YAML) — pick the one location that owns it and
implement the whole fix there. If a fix genuinely needs both an engine
change and a knowledge addition (e.g. the engine has no mechanism yet to
consult a new dictionary), treat that as two explicitly separate changes,
each with its own tests, not one blended edit.

### 3. Prohibited actions

Regardless of category, never:

- **Hardcode profession-specific terms in core engine modules** — any
  job title, skill name, or industry term appearing as a Python literal
  inside `src/xray/` is a violation, even if it "just fixes one case."
  It belongs in a `knowledge/` pack (CLAUDE.md §5).
- **Write a broad regex patch that only fixes one JD** — a regex change
  justified by "this makes the failing example pass" without checking it
  against the general structural pattern it claims to match is not
  acceptable. Regex is for structural/syntactic patterns (e.g. stripping
  a job-ID suffix), not a substitute for curated knowledge (CLAUDE.md
  §5). If the "fix" only works because it was shaped around one example,
  it is a glossary/job-family entry, not an engine regex.
- **Silently convert semantic inference into deterministic code** —
  if making the fix requires guessing intent, resolving ambiguity, or
  inventing a relationship the JD/knowledge base doesn't already support,
  that is category 8 and stays skill-only. Do not encode a one-off
  judgment call as if it were a general rule.
- **Change behavior without regression tests** — no edit to `src/xray/`,
  `knowledge/`, or `app.py` service logic ships without a test that would
  fail before the fix and pass after it (CLAUDE.md §5, §8).

### 4. Required fields for every knowledge addition

Every new entry added to any `knowledge/` file (generic glossary,
job-family pack, specialization entry, or priority-cue dictionary) must
include all five of the following — an entry missing any of these is
incomplete:

1. **Category** — which of the classification types above it belongs to
   (glossary / job-family / specialization / priority-cue), so future
   maintainers know why it lives where it does.
2. **Activation signal** — the literal term(s)/phrase(s) that trigger
   this entry (e.g. the synonym, abbreviation, or cue phrase itself).
3. **Optional weight** — a scoring/priority weight if the engine's
   scoring model uses one for this entry type; omit only if the
   knowledge schema genuinely has no weighting concept yet, not by
   default.
4. **Positive test** — a test proving the entry fires correctly on
   representative input (CLAUDE.md §5).
5. **Negative test** — a test proving the entry does not over-fire on
   clearly unrelated input (CLAUDE.md §5).

### 5. Implement the minimal change

Once classified and routed, implement only the fix required — no
speculative abstractions, no unrelated refactors bundled into the same
change (CLAUDE.md §8). Keep `SearchSpec` as the boundary between
extraction and query assembly intact; do not let a fix reach across that
boundary (CLAUDE.md §5).

### 6. Final verification

Before considering any change done, run all of the following that apply:

- **Targeted tests** — the specific new/updated test(s) for this change,
  confirmed failing before the fix (where practical) and passing after.
- **Full pytest suite** — `pytest` across `tests/`, to catch regressions
  elsewhere.
- **`python -m compileall .`** — confirm no syntax errors were
  introduced anywhere in the repository.
- **Streamlit smoke test** — required whenever the change touches `app.py`
  or any service/engine code the UI depends on (i.e. categories 1, 2, 3,
  4, 5, 7): start the app (e.g. `streamlit run app.py --server.headless
  true`) and confirm it serves without error. Not required for a
  test-only change (category 6) or a skill-only/no-code outcome
  (category 8).

Do not report a change as done if any applicable verification step was
skipped or failed.

### 7. Required final report

Every change produced by this skill ends with a concise report
containing exactly these five items:

1. **Root cause** — the actual underlying defect or gap, in one or two
   sentences.
2. **Implementation layer** — which category (1–8) and which location
   from the table in step 2 the fix went into (or "none — skill-only"
   for category 8).
3. **Files changed** — the specific file path(s) touched.
4. **Tests** — which tests were added/updated, and the verification
   commands actually run (per step 6).
5. **Known remaining limitation** — anything the fix does not cover,
   any heuristic still in play, or any related issue deliberately left
   for a separate change (CLAUDE.md §7 transparency requirement).
