"""Smoke tests for app.py using Streamlit's AppTest framework.

These drive the actual Streamlit script (no mocking of `st.*`), so they
exercise the real UI wiring: input widgets, the Generate button, error
handling for an empty JD, and the structured-analysis/query rendering
for a real JD. They do not re-test extraction/assembly/validation
logic itself (that belongs to `src/xray/`'s own test suite) — only
that app.py calls the service layer correctly and renders without
raising.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

_SAMPLE_JD = "We are hiring a Backend Engineer based in Germany."


def _run_app() -> AppTest:
    at = AppTest.from_file("app.py")
    at.run(timeout=20)
    return at


def test_app_loads_without_exception():
    at = _run_app()
    assert not at.exception


def test_page_title_is_rendered():
    at = _run_app()
    assert at.title[0].value == "X-ray LinkedIn Sourcing Tool"


def test_inputs_and_generate_button_are_present():
    at = _run_app()
    assert at.text_area(key="jd_text_input") is not None
    assert at.text_input(key="location_override_input") is not None
    assert any(button.label == "Generate X-ray Queries" for button in at.button)


def test_empty_jd_shows_a_clean_error_not_an_exception():
    at = _run_app()
    at.button[0].click().run(timeout=20)

    assert not at.exception
    assert len(at.error) == 1
    assert "empty" in at.error[0].value.lower()


def test_generate_with_valid_jd_renders_results_without_exception():
    at = _run_app()
    at.text_area(key="jd_text_input").set_value(_SAMPLE_JD)
    at.button[0].click().run(timeout=20)

    assert not at.exception
    assert len(at.error) == 0
    # At least one warning is expected (no production job-family packs
    # exist yet, per this task's "do not create job-family knowledge
    # yet" constraint), and it must render via st.warning.
    assert len(at.warning) > 0


def test_structured_analysis_fields_are_populated_and_editable():
    at = _run_app()
    at.text_area(key="jd_text_input").set_value(_SAMPLE_JD)
    at.button[0].click().run(timeout=20)

    titles_field = at.text_area(key="field_titles")
    assert titles_field.value == "Backend Engineer"

    locations_field = at.text_area(key="field_locations")
    assert locations_field.value == "Germany"

    # Editable: changing the value and rerunning must not raise, and
    # the new value must stick.
    titles_field.set_value("Senior Backend Engineer").run(timeout=20)
    assert at.text_area(key="field_titles").value == "Senior Backend Engineer"
    assert not at.exception


def test_location_override_is_reflected_in_generated_locations():
    at = _run_app()
    at.text_area(key="jd_text_input").set_value(_SAMPLE_JD)
    at.text_input(key="location_override_input").set_value("Poland")
    at.button[0].click().run(timeout=20)

    assert not at.exception
    locations_field = at.text_area(key="field_locations")
    assert "Poland" in locations_field.value
    assert "Germany" in locations_field.value


def test_search_type_selector_has_all_four_variants():
    at = _run_app()
    at.text_area(key="jd_text_input").set_value(_SAMPLE_JD)
    at.button[0].click().run(timeout=20)

    radios = at.radio(key="selected_variant_label")
    assert radios.options == ["Strict", "Balanced", "Broad", "Hidden Titles"]


def test_final_boolean_query_starts_with_source_and_is_editable():
    at = _run_app()
    at.text_area(key="jd_text_input").set_value(_SAMPLE_JD)
    at.button[0].click().run(timeout=20)

    strict_query_field = at.text_area(key="field_query_strict")
    assert strict_query_field.value.startswith("site:")

    strict_query_field.set_value("site:linkedin.com/in/ (\"Custom Edit\")").run(timeout=20)
    assert at.text_area(key="field_query_strict").value == 'site:linkedin.com/in/ ("Custom Edit")'
    assert not at.exception


def test_google_search_link_button_uses_current_query():
    at = _run_app()
    at.text_area(key="jd_text_input").set_value(_SAMPLE_JD)
    at.button[0].click().run(timeout=20)

    link_buttons = at.get("link_button")
    assert len(link_buttons) == 1
    assert link_buttons[0].url.startswith("https://www.google.com/search?q=")
    assert not link_buttons[0].disabled
