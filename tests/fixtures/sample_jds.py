"""Synthetic Job Description text fixtures for family-detector tests.

These are hand-written snippets built to exercise specific detection
scenarios (confident match, ambiguity, cross-family false positives,
etc.) — not real job postings, and not tied to any production
knowledge pack under `knowledge/job_families/`. The synthetic packs
these JDs are matched against live in `tests/test_family_detector.py`.

Raw text only; callers are expected to run
`normalizer.normalize_whitespace` before passing these to
`family_detector.detect_family`, per that function's documented input
contract.
"""

from __future__ import annotations

#: A single, unambiguous family signal + title match for a "Software
#: Engineer" pack, with no specialization or competing-family evidence.
CONFIDENT_FAMILY_MATCH_JD = """
We are hiring a Software Engineer to join our backend platform team.
You will design, build, and maintain backend services.
"""

#: Same family evidence as above, plus specialization-signal phrases
#: ("distributed systems", "cloud infrastructure") for the pack's
#: "Distributed Systems" specialization.
CONFIDENT_SPECIALIZATION_MATCH_JD = """
We are hiring a Software Engineer with deep experience in distributed
systems and cloud infrastructure to join our backend platform team.
"""

#: No overlap with any synthetic pack's family signals, titles, skills,
#: or industries.
NO_MATCH_JD = """
We are looking for a Marketing Coordinator to plan social media
campaigns and manage brand partnerships.
"""

#: Equally strong evidence for two distinct synthetic families ("Nova
#: Engineer" and "Terra Engineer"), producing a tied score.
AMBIGUOUS_MATCH_JD = """
We are hiring either a Nova Engineer or a Terra Engineer to join our
platform team; experience as a Nova Engineer or as a Terra Engineer is
equally welcome.
"""

#: A Software Engineer JD that happens to mention "data center" — the
#: single industry keyword the synthetic "Electrical Engineer" pack
#: defines. Family evidence (family signal + title) for Software
#: Engineer must win; the isolated industry keyword alone must not
#: reclassify this as Electrical Engineer.
CROSS_FAMILY_FALSE_POSITIVE_JD = """
We are hiring a Software Engineer to build backend services that run
inside our data center. This is a software role, not a facilities
role.
"""

#: Only the single generic industry keyword ("data center") appears,
#: with no family-signal, title, or second generic term for any pack —
#: below the minimum-signal threshold required to classify a family.
GENERIC_KEYWORD_BELOW_THRESHOLD_JD = """
Our office facility includes a data center on site for internal IT
operations.
"""

#: Two distinct generic (industry + skill) terms for the synthetic
#: "Electrical Engineer" pack, with no competing family's evidence
#: present — enough generic signals to qualify on their own.
TWO_GENERIC_SIGNALS_JD = """
Our facilities team manages a data center that relies on careful power
distribution planning.
"""

# ---------------------------------------------------------------------------
# Fixtures below are for tests/test_extractor.py (src/xray/extractor.py).
# ---------------------------------------------------------------------------

#: A "Job Title:" label line, for structural title extraction.
TITLE_LABEL_JD = """
Job Title: Senior Backend Engineer

We are looking for someone to join our platform team.
"""

#: A "we are hiring a <Title>" trigger phrase, for structural title
#: extraction without any label line.
TITLE_TRIGGER_JD = """
We are hiring a Backend Engineer to join our platform team.
"""

#: A seniority modifier ("Senior") alongside a title.
SENIORITY_JD = """
We are hiring a Senior Backend Engineer to join our platform team.
"""

#: A city (Munich) and, separately, a country name (Poland).
LOCATION_JD = """
This role is based in Munich, with occasional travel to our office in
Poland.
"""

#: Two languages introduced by a single fluency cue — no explicit
#: MUST/IMPORTANT/NICE-TO-HAVE priority word, so both should default to
#: the "important" bucket.
LANGUAGE_FLUENT_MULTI_JD = """
Fluent in German and English is expected for daily communication with
the team.
"""

#: A language introduced by the bare "fluent" cue (no "in") — a common
#: real-world phrasing ("Fluent German and professional English") this
#: engine must also recognize, not just the "fluent in" form.
LANGUAGE_FLUENT_BARE_JD = """
Fluent German is expected for this role.
"""

#: Two languages confirmed by adjacent CEFR level codes in one segment.
LANGUAGE_CEFR_JD = """
Language skills: German C1, English B2.
"""

#: The "-speaking" compound form, unambiguous on its own.
LANGUAGE_SPEAKING_JD = """
We are looking for German-speaking support engineers.
"""

#: A language paired with an IMPORTANT priority cue ("preferred").
LANGUAGE_PREFERRED_JD = """
English preferred for this customer-facing role.
"""

#: A language paired with an explicit MUST priority cue.
LANGUAGE_MUST_JD = """
German is required for this role.
"""

#: A language paired with an explicit NICE-TO-HAVE priority cue.
LANGUAGE_NICE_JD = """
French is a nice to have for this position.
"""

#: A NICE-TO-HAVE cue and a MUST-sounding word both appear in the same
#: segment; the optional cue must win (rule: "optional cues must not
#: become MUST").
LANGUAGE_OPTIONAL_NOT_MUST_JD = """
German is nice to have, not required, for this role.
"""

#: False positive: a bare language name describing the employer's
#: nationality, not a candidate language requirement.
LANGUAGE_FALSE_POSITIVE_COMPANY_JD = """
We are a German company based in Munich.
"""

#: False positive: a bare language name describing a document version,
#: not a candidate language requirement.
LANGUAGE_FALSE_POSITIVE_VERSION_JD = """
Please review the English version of the contract before signing.
"""

#: False positive: "native" appears with no language name at all
#: ("native cloud" is a technology term).
LANGUAGE_FALSE_POSITIVE_NATIVE_CLOUD_JD = """
Our platform is built on native cloud infrastructure for elastic
scaling.
"""

#: False positive: "speaking" appears with no language name at all
#: (the verb "to speak", not a "-speaking" form).
LANGUAGE_FALSE_POSITIVE_SPEAKING_CONFERENCE_JD = """
The successful candidate will be speaking at a conference next year.
"""

#: Company-type mention with candidate-background context ("experience in").
COMPANY_TYPE_POSITIVE_EXPERIENCE_JD = """
The ideal candidate has experience in a consultancy.
"""

#: Company-type mention with candidate-background context ("background").
COMPANY_TYPE_POSITIVE_BACKGROUND_JD = """
The ideal candidate has a consultancy background.
"""

#: Company-type mention with candidate-background context ("worked for").
COMPANY_TYPE_POSITIVE_WORKED_EPC_JD = """
She previously worked for an EPC contractor in the Middle East.
"""

#: False positive: the company-type term describes the employer itself.
COMPANY_TYPE_NEGATIVE_OUR_CONSULTANCY_JD = """
Our engineering consultancy is looking for talented developers.
"""

#: False positive: the company-type term describes the employer itself.
COMPANY_TYPE_NEGATIVE_WE_ARE_EPC_JD = """
We are an EPC contractor delivering large-scale infrastructure
projects.
"""

#: Three separate sentences, one per priority category, for testing
#: explicit priority-cue extraction independent of which term they modify.
PRIORITY_CUES_JD = """
Experience with cloud platforms is required. Docker knowledge is
preferred. Kubernetes is a nice to have.
"""

#: A JD carrying profession-specific terms (title, industry, skills)
#: that only a matching, activated job-family pack should surface.
PACK_TERMS_JD = """
We are hiring a Backend Engineer with fintech experience. Python is
required. Kubernetes is a nice to have.
"""

#: A JD carrying a core-function term ("code review") that only a
#: matching, activated job-family pack should surface.
PACK_CORE_FUNCTION_JD = """
We are hiring a Backend Engineer. Code review is part of the role.
"""

#: False positive: the location term describes the employer's own HQ,
#: not a job location, with no other location mentioned anywhere.
LOCATION_NEGATIVE_HEADQUARTERED_JD = """
Acme Corp is headquartered in Berlin. We build software products.
"""

#: False positive: the location term describes the employer's Global
#: Design Center, not a job location, with no other location mentioned.
LOCATION_NEGATIVE_GLOBAL_DESIGN_CENTER_JD = """
Our company has a Global Design Center in Austria.
"""

#: The same country mentioned twice: once in a negative-context (HQ)
#: sentence, once in a clean job-location sentence — the canonical term
#: must still be extracted via the clean occurrence, not permanently
#: rejected just because one occurrence was employer-HQ context.
LOCATION_POSITIVE_DESPITE_UNRELATED_HQ_MENTION_JD = """
Our company is headquartered in Munich. This role is based in Munich.
"""

#: Two requirement lines with NO bullet markers and no terminal
#: punctuation — the common real-world shape when a JD is copy-pasted
#: from a rendered HTML `<li>` list with the bullet glyphs stripped.
#: Regression fixture for `_split_into_blocks`'s continuation-cue
#: heuristic: without it, both lines merge into one giant block, and
#: the "a plus" cue on the second (unrelated) line would incorrectly
#: bleed its nice-to-have classification onto the first line's "Python"
#: term too.
BULLETLESS_LOOSE_LIST_JD = """
Python experience is required
Kubernetes experience is a plus
"""
