# CLAUDE.md

## Project

Deterministic LinkedIn X-ray sourcing application. Given structured job
criteria, it builds X-ray search strings (e.g. for Google) to find LinkedIn
profiles — without calling any LLM or external NLP API at runtime.

## Architecture rules

- Deterministic only: no LLM calls, no external NLP APIs at runtime.
- Business logic lives under `src/xray/`.
- Reference data (job families, keyword sets, etc.) lives under
  `knowledge/job_families/` as YAML, loaded via PyYAML.
- UI is a thin Streamlit layer in `app.py` — no logic in the UI layer.
- Tests live under `tests/` and use pytest.

## Constraints

- Python 3.11+
- Keep dependencies minimal: streamlit, PyYAML, pytest only, unless a new
  capability genuinely requires more.
- Do not add features or abstractions ahead of actual requirements.
