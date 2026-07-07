# CLAUDE.md

This file is the repository-wide source of truth for development. It
overrides ad hoc judgment calls — when in doubt, follow this document.

## 1. Project objective

- Build a deterministic Streamlit application that generates LinkedIn
  Boolean X-ray queries from Job Descriptions.
- Target at least 90% functional equivalence with approved Claude
  benchmark outputs across supported job families.
- Do not claim universal semantic understanding. The system is a rules
  and knowledge engine, not a general-purpose language understander.

## 2. Runtime boundary

- The running Streamlit app must never call Claude, OpenAI, or any
  LLM/NLP API. This applies at runtime, without exception.
- Runtime logic may only use: Python, regex, dictionaries, YAML
  knowledge packs, scoring/weighting, and deterministic rules.
- LLMs (e.g. Claude via a skill) may be used *offline*, outside the
  running app, to help author or update knowledge packs — never as part
  of a request/response cycle inside the app.

## 3. Responsibility boundaries

| Location       | Owns |
|-----------------|------|
| `CLAUDE.md`      | Repository-wide rules and constraints. |
| Skills (`.claude/skills/`) | Claude's professional workflows — how a human/Claude author knowledge packs, review outputs, or extend job families. Not executed at runtime. |
| `src/xray/`      | Deterministic runtime engine — extraction, scoring, query assembly. See module pipeline below. |
| `knowledge/`     | Curated generic and profession-specific knowledge (glossaries, YAML job-family packs). |
| `tests/`         | Regression protection for engine and knowledge behavior. |
| `app.py`         | Streamlit presentation layer only. Must call only the public interface (`src.xray.generate_xray_queries`) — no extraction, classification, or query-assembly logic of its own. |

Do not blur these lines: engine code should not embed knowledge, and
knowledge packs should not embed engine logic.

### `src/xray/` module pipeline

`generate_xray_queries` (`service.py`, re-exported from
`src/xray/__init__.py`) is the only supported public entry point;
every other module below is an internal implementation detail and may
change without notice.

| Module | Responsibility |
|---|---|
| `models.py` | `SearchSpec`, `PrioritizedTerms`, `QueryVariants` — the shared data contracts between every stage below. |
| `normalizer.py` | Generic text normalization (whitespace, casefold, phrase-boundary matching, dedup, Boolean-term quoting). No knowledge. |
| `glossary.py` | Loads/validates the generic knowledge files under `knowledge/` (locations, languages, company types, seniority, priority cues). |
| `knowledge_loader.py` | Loads/validates one job-family pack from `knowledge/job_families/<family>.yaml`. |
| `family_detector.py` | Weighted, deterministic job-family/specialization detection over an activated set of packs. Never guesses a family. |
| `extractor.py` | Turns raw JD text into a `SearchSpec` (titles, seniority, locations, languages, company type, priority cues, and — only if a pack is activated — profession-specific terms). |
| `source_resolver.py` | Resolves the LinkedIn `site:` prefix (global vs. verified-ccTLD) from `SearchSpec.locations`. |
| `assembler.py` | Turns a `SearchSpec` into the four `QueryVariants` strings. |
| `validator.py` | Non-fatal structural/evidence checks over a `(SearchSpec, QueryVariants)` pair. |
| `service.py` | Orchestrates all of the above into `generate_xray_queries`. |

## 4. Three implementation categories

Before writing any change, classify it into exactly one of these:

1. **Generic deterministic logic** — applies across all job families
   (parsing, scoring, query assembly, dedup, formatting). May be
   implemented in Python under `src/xray/`.
2. **Dictionary-driven knowledge** — profession-specific terms,
   synonyms, title variants, seniority cues, and MUST/IMPORTANT/
   NICE-TO-HAVE priority-cue phrases. Must be stored in a glossary or
   YAML knowledge pack under `knowledge/`, not in Python.
3. **Semantic/contextual reasoning** — judgment calls that require
   understanding intent or ambiguous context. Remains skill-only
   (human- or Claude-assisted, offline) unless explicitly converted
   into approved structured rules and reviewed as such.

If a change doesn't clearly fit category 1 or 2, do not encode it as
Python or YAML — flag it as a skill-level concern instead.

## 5. Non-negotiable coding rules

- Do not hardcode profession-specific terms (job titles, skills,
  industry jargon) in core engine modules under `src/xray/`.
- Profession-specific terms belong in job-family packs under
  `knowledge/job_families/`.
- Do not convert every skill instruction into regex. Regex is for
  structural/syntactic patterns, not a substitute for curated
  knowledge or semantic judgment.
- Keep extraction separate from query assembly: parsing a Job
  Description into structured data is a distinct step from turning
  that data into a Boolean string.
- Use a structured intermediate representation, `SearchSpec`, between
  extraction and query assembly. Extraction produces a `SearchSpec`;
  query assembly consumes one. Neither step should skip it.
- Preserve location blocks in the query even when using a LinkedIn
  country ccTLD (e.g. `site:xx.linkedin.com/in`) — the ccTLD narrows
  by domain, but explicit location terms still add precision and must
  not be dropped.
- Every behavioral change requires tests.
- Every new knowledge relationship (synonym, title mapping, industry
  link, etc.) requires both a positive test (it fires correctly) and
  a negative test (it doesn't over-fire on unrelated input).
- Keep public interfaces backward-compatible unless a change is
  explicitly approved as a breaking change.

## 6. Four query variants

Every generated X-ray must be produced in four variants (implemented in
`assembler.py`):

- **Strict** — narrowest match: titles, core-function evidence AND
  industry evidence (both required, as separate clauses), every MUST
  skill, and any explicit MUST-tier language/company-type requirement,
  each as its own required clause, plus location.
- **Balanced** — titles, only the single strongest core-function/
  industry evidence group (not both), every MUST skill, IMPORTANT
  skills merged into one additional optional-OR clause, plus location.
  Default recommended variant.
- **Broad** — titles plus core-function and industry evidence merged
  into one OR clause (matches either dimension); intentionally
  skill-agnostic — no MUST/IMPORTANT/NICE-TO-HAVE skill filtering —
  plus location.
- **Hidden Titles** — omits the title clause entirely and substitutes
  a merged MUST+IMPORTANT+NICE-TO-HAVE skill-evidence clause, alongside
  the same merged core-function/industry evidence and location, so
  candidates are found by domain + skill signal regardless of title.
  Does not yet substitute adjacent/feeder titles (see section 7).

## 7. Known limitations

State these plainly to users; do not paper over them:

- Core Function and Industry classification may be heuristic at
  runtime and can be wrong for ambiguous or hybrid roles.
- MUST / IMPORTANT / NICE classification is reliable only when the
  Job Description contains explicit cues (e.g. "required", "must
  have", "nice to have"). Absent cues, classification is a best-effort
  default, not a guarantee.
- Local-language expansion (non-English synonyms/titles) is limited
  to what exists in knowledge packs — the engine does not translate
  or infer local-language terms on the fly.
- Unsupported job families must produce an explicit warning to the
  user rather than inventing semantic relationships or falling back
  to guessed keywords.
- Hidden Titles achieves title-independence by omitting the title
  clause, not by substituting adjacent/feeder titles —
  `JobFamilyPack.hidden_title_signals` exists in the pack schema but
  is not yet consumed by extraction or assembly.
- No production job-family pack exists yet under
  `knowledge/job_families/` (only the illustrative, non-production
  `_schema_example.yaml`) — every result currently reports "no job
  family matched" until a real pack is added.
- In the Streamlit UI, editing the structured-analysis fields is for
  the user's own review/copy convenience only; it does not feed back
  into query reassembly (`app.py` calls the service layer once per
  Generate click, per its responsibility boundary in section 3).

## 8. Required workflow before modifying code

Follow these steps in order for every change:

1. **Classify the issue** — is it generic logic, dictionary-driven
   knowledge, or semantic/contextual reasoning (see section 4)?
2. **Choose the right location** — engine (`src/xray/`), glossary,
   knowledge pack (`knowledge/`), validation/tests, or skill. Do not
   split one concern across the wrong locations.
3. **Implement the minimal change** — no speculative abstractions, no
   unrelated refactors bundled in.
4. **Add tests** — behavioral tests for engine/logic changes;
   positive + negative tests for new knowledge relationships.
5. **Run the suite** — all tests must pass before the change is
   considered done.

## Constraints

- Python 3.11+
- Keep dependencies minimal: streamlit, PyYAML, pytest only, unless a
  new capability genuinely requires more.
- Do not add features or abstractions ahead of actual requirements.

## Maintaining CLAUDE.md

CLAUDE.md is a durable architectural source of truth, not a task log or
changelog.

Update CLAUDE.md in the same task only when an approved change affects:

- repository architecture;
- module or file responsibilities;
- runtime boundaries;
- knowledge placement;
- public interfaces;
- query-variant semantics;
- required verification;
- known limitations.

Do not update CLAUDE.md for ordinary bug fixes, new data entries, added
tests, passing test counts, or internal implementation details.

If the current task file scope excludes CLAUDE.md but the change requires
an architectural documentation update, stop and ask for a narrow scope
amendment.