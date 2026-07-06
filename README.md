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
streamlit run app.py
```

## Run tests

```bash
pytest
```
