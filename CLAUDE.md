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
| `src/xray/`      | Deterministic runtime engine — extraction, scoring, query assembly. |
| `knowledge/`     | Curated generic and profession-specific knowledge (glossaries, YAML job-family packs). |
| `tests/`         | Regression protection for engine and knowledge behavior. |

Do not blur these lines: engine code should not embed knowledge, and
knowledge packs should not embed engine logic.

## 4. Three implementation categories

Before writing any change, classify it into exactly one of these:

1. **Generic deterministic logic** — applies across all job families
   (parsing, scoring, query assembly, dedup, formatting). May be
   implemented in Python under `src/xray/`.
2. **Dictionary-driven knowledge** — profession-specific terms,
   synonyms, title variants, seniority cues. Must be stored in a
   glossary or YAML knowledge pack under `knowledge/`, not in Python.
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

Every generated X-ray must be produced in four variants:

- **Strict** — narrowest match, all MUST criteria required, minimal
  synonym expansion.
- **Balanced** — MUST + IMPORTANT criteria, moderate synonym
  expansion. Default recommended variant.
- **Broad** — MUST criteria plus wide synonym/title expansion, NICE
  criteria included as optional (OR) terms.
- **Hidden Titles** — targets candidates whose current title doesn't
  match the target role, using adjacent/feeder titles and skill-based
  terms instead of the literal target title.

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
