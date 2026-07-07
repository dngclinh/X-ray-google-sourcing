"""Streamlit UI for the X-ray deterministic sourcing engine.

This file is a thin presentation layer: it collects input, calls
`src.xray.generate_xray_queries` (the one supported service-layer
entry point), and renders the result. It contains no extraction,
classification, or query-assembly logic of its own — every piece of
structured data shown here already exists on the `SearchSpec` /
`QueryVariants` objects the service layer returned; this module only
formats them for display and editing.
"""

from __future__ import annotations

import urllib.parse

import streamlit as st

from src.xray import (
    InvalidJobDescriptionError,
    PrioritizedTerms,
    QueryVariants,
    SearchSpec,
    generate_xray_queries,
)

_VARIANT_FIELD_KEYS = {
    "Strict": "field_query_strict",
    "Balanced": "field_query_balanced",
    "Broad": "field_query_broad",
    "Hidden Titles": "field_query_hidden_titles",
}


# ---------------------------------------------------------------------------
# Display formatting helpers (formatting only — no extraction logic)
# ---------------------------------------------------------------------------


def _join(values: list[str]) -> str:
    return ", ".join(values)


def _format_prioritized(terms: PrioritizedTerms) -> str:
    lines = []
    if terms.must:
        lines.append("MUST: " + _join(terms.must))
    if terms.important:
        lines.append("IMPORTANT: " + _join(terms.important))
    if terms.nice_to_have:
        lines.append("NICE-TO-HAVE: " + _join(terms.nice_to_have))
    return "\n".join(lines)


def _format_confidence(confidence: dict[str, float]) -> str:
    return "\n".join(f"{category}: {score:.2f}" for category, score in confidence.items())


def _format_matched_signals(matched_signals: dict[str, list[str]]) -> str:
    return "\n".join(
        f"{category}: {_join(terms)}" for category, terms in matched_signals.items()
    )


def _seed_editable_fields(spec: SearchSpec, variants: QueryVariants) -> None:
    """Populate every editable widget's session-state slot from a fresh result.

    Must run before the corresponding widgets are instantiated further
    down the script — this is Streamlit's documented pattern for
    setting a widget's value programmatically (see module docstring
    note in the results-rendering section below).
    """
    st.session_state["field_job_family"] = spec.job_family or ""
    st.session_state["field_specialization"] = spec.specialization or ""
    st.session_state["field_titles"] = _join(spec.titles)
    st.session_state["field_core_functions"] = _join(spec.core_functions)
    st.session_state["field_industries"] = _join(spec.industries)
    st.session_state["field_skills_must"] = _join(spec.skills.must)
    st.session_state["field_skills_important"] = _join(spec.skills.important)
    st.session_state["field_skills_nice_to_have"] = _join(spec.skills.nice_to_have)
    st.session_state["field_locations"] = _join(spec.locations)
    st.session_state["field_languages"] = _format_prioritized(spec.languages)
    st.session_state["field_company_types"] = _format_prioritized(spec.company_types)
    st.session_state["field_confidence"] = _format_confidence(spec.confidence)
    st.session_state["field_matched_signals"] = _format_matched_signals(spec.matched_signals)

    st.session_state["field_query_strict"] = variants.strict
    st.session_state["field_query_balanced"] = variants.balanced
    st.session_state["field_query_broad"] = variants.broad
    st.session_state["field_query_hidden_titles"] = variants.hidden_titles


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_warnings(spec: SearchSpec) -> None:
    if not spec.warnings:
        return
    st.subheader("Warnings")
    for warning in spec.warnings:
        st.warning(warning)


def _render_structured_analysis() -> None:
    st.subheader("2. Structured analysis (editable)")
    st.caption(
        "Deterministic extraction results, shown for review — edit these for "
        "your own reference; edit the Boolean query below to change the search."
    )

    left, right = st.columns(2)
    with left:
        st.text_input("Detected job family", key="field_job_family")
        st.text_input("Specialization", key="field_specialization")
        st.text_area("Titles", key="field_titles", height=80)
        st.text_area("Core functions", key="field_core_functions", height=80)
        st.text_area("Industries", key="field_industries", height=80)
        st.text_area("Locations", key="field_locations", height=80)
    with right:
        st.text_area("MUST skills", key="field_skills_must", height=80)
        st.text_area("Important skills", key="field_skills_important", height=80)
        st.text_area("Nice-to-have skills", key="field_skills_nice_to_have", height=80)
        st.text_area("Languages", key="field_languages", height=100)
        st.text_area("Company types", key="field_company_types", height=100)

    with st.expander("Confidence"):
        st.text_area(
            "Confidence scores", key="field_confidence", height=100, label_visibility="collapsed"
        )
    with st.expander("Matched signals"):
        st.text_area(
            "Matched signals",
            key="field_matched_signals",
            height=150,
            label_visibility="collapsed",
        )


def _render_query_section() -> None:
    st.subheader("3. Search type")
    selected_label = st.radio(
        "Choose a query variant",
        list(_VARIANT_FIELD_KEYS.keys()),
        horizontal=True,
        key="selected_variant_label",
    )
    selected_key = _VARIANT_FIELD_KEYS[selected_label]

    st.subheader("4. Final Boolean query (editable)")
    final_query = st.text_area(
        "Edit the query before copying or searching",
        key=selected_key,
        height=120,
    )

    st.caption("Copy-friendly view (hover for the copy icon):")
    st.code(final_query, language=None)

    google_url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(final_query)
    st.link_button("🔎 Open in Google Search", google_url, disabled=not final_query.strip())


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.set_page_config(page_title="X-ray LinkedIn Sourcing Tool", page_icon="🔎", layout="wide")
st.title("X-ray LinkedIn Sourcing Tool")
st.caption(
    "Deterministic, rule-based LinkedIn X-ray query generation — no LLM or "
    "external NLP is used at runtime (CLAUDE.md section 2)."
)

st.subheader("1. Job Description")
jd_text = st.text_area(
    "Paste the Job Description text",
    height=280,
    key="jd_text_input",
    placeholder="Paste the full job description here...",
)
location_override = st.text_input(
    "Location override (optional)",
    key="location_override_input",
    help="Adds an extra location on top of anything already found in the JD.",
)

if st.button("Generate X-ray Queries", type="primary"):
    try:
        spec, variants = generate_xray_queries(jd_text, location_override)
    except InvalidJobDescriptionError as exc:
        st.session_state["xray_error"] = str(exc)
        st.session_state["xray_spec"] = None
        st.session_state["xray_variants"] = None
    else:
        st.session_state["xray_error"] = None
        st.session_state["xray_spec"] = spec
        st.session_state["xray_variants"] = variants
        _seed_editable_fields(spec, variants)

if st.session_state.get("xray_error"):
    st.error(st.session_state["xray_error"])

result_spec: SearchSpec | None = st.session_state.get("xray_spec")
result_variants: QueryVariants | None = st.session_state.get("xray_variants")

if result_spec is not None and result_variants is not None:
    _render_warnings(result_spec)
    _render_structured_analysis()
    _render_query_section()
