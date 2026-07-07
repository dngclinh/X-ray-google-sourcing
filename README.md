# LinkedIn X-ray Sourcing

A deterministic sourcing tool that turns structured job criteria into
LinkedIn X-ray search strings. No LLM or external NLP API is used at
runtime — all logic is rule-based, driven by YAML knowledge files under
`knowledge/job_families/`.

## Architecture

- `app.py` — Streamlit UI (thin layer, no business logic).
- `src/xray/` — core deterministic logic (not yet implemented).
- `knowledge/job_families/` — YAML reference data used to build searches.
- `tests/` — pytest test suite.

## Setup

Create and activate a virtual environment (Python 3.11+):

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

## Run the app

```bash
python -m streamlit run app.py
```

This opens the "X-ray LinkedIn Sourcing Tool" UI: paste a Job
Description, optionally add a location override, click **Generate
X-ray Queries**, then review the editable structured analysis and pick
a search type (Strict / Balanced / Broad / Hidden Titles) before
copying the Boolean query or opening it directly in Google Search.

No production job-family packs exist yet (see CLAUDE.md), so every
generated result currently includes an "unsupported job family"
warning — this is expected until real packs are added under
`knowledge/job_families/`.

## Run tests

```bash
python -m pytest
```

To run only the UI smoke tests:

```bash
python -m pytest tests/test_app_smoke.py
```

## Check for syntax errors across the whole repo

```bash
python -m compileall .
```
