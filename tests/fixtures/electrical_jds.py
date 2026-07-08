"""Job Description fixtures for the Electrical Engineering regression
benchmark (`tests/test_regression_electrical.py`).

These are hand-written, representative JDs — not real job postings —
built to exercise specific, named dimensions of
`knowledge/job_families/electrical_engineering.yaml` end to end through
`generate_xray_queries`. Every phrase that is expected to match a pack
term (title, specialization signal, industry term, or skill term) has
been checked against `src/xray/normalizer.contains_phrase`'s
whitespace-boundary matching rules (case-insensitive, but never a
substring of a larger word, and never across an inflected/declined
word form) so that matches in `tests/test_regression_electrical.py` are
deterministic, not incidental.

One deliberate exception to "not real job postings":
`REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD` is a real
job posting, kept verbatim (including its lack of bullet markers), added
specifically to regression-lock a real, root-caused gap found by running
it through the app and comparing against a Claude-authored benchmark.

This module holds JD text only — no expectations, no assertions. Expected
properties live in `tests/test_regression_electrical.py`, per the same
fixtures/assertions separation `tests/fixtures/sample_jds.py` already
uses for the generic family-detector tests.

Dimension coverage (CLAUDE.md section 1's "at least 90% functional
equivalence... across supported job families" requires a JD corpus wide
enough to be representative; see docs/benchmark-method.md for how these
fixtures feed the weighted scoring method):

| Fixture                                      | Dimensions                                                             |
|-----------------------------------------------|-------------------------------------------------------------------------|
| SHORT_EXPLICIT_SENIORITY_EN_JD                 | short, English, explicit seniority, Germany                             |
| LONG_IMPLICIT_SENIORITY_DATA_CENTER_EN_JD      | long, English, implicit seniority, data center, Germany                 |
| SHORT_EXPLICIT_SENIORITY_BUILDING_SERVICES_DE_JD| short, German, explicit seniority, building services, Germany           |
| LONG_INDUSTRIAL_POWER_DE_JD                    | long, German, industrial power, Germany                                 |
| MULTI_COUNTRY_GERMANY_POLAND_EN_JD             | English, Germany and Poland                                             |
| MANDATORY_LANGUAGE_EN_JD                       | English, mandatory language, Germany                                    |
| OPTIONAL_LANGUAGE_EN_JD                        | English, optional language, Germany                                     |
| COMPANY_INTRODUCTION_FALSE_POSITIVE_EN_JD      | English, company-introduction false positive, Germany                   |
| ADJACENT_FAMILY_ELECTRICIAN_EN_JD              | English, adjacent-but-incorrect job family (trade/vocational)           |
| ADJACENT_FAMILY_MECHANICAL_ENGINEER_EN_JD      | English, adjacent-but-incorrect job family (different engineering disc.)|
| AMBIGUOUS_SPECIALIZATION_EN_JD                 | English, tied specialization evidence, Germany                          |
| UNSUPPORTED_FAMILY_EN_JD                       | English, wholly unrelated family                                        |
| SINGLE_COUNTRY_POLAND_EN_JD                    | English, Poland only                                                    |
| REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD | real JD, long, English, no bullets, company-HQ false positive, multi-country, mandatory language, core functions |
"""

from __future__ import annotations

#: Short, English, explicit seniority ("Senior"), single-country location
#: (Germany, via both a city and the country name), no specialization
#: evidence at all — the baseline "plain Electrical Engineer" case.
SHORT_EXPLICIT_SENIORITY_EN_JD = (
    "Senior Electrical Engineer needed in Munich, Germany."
)

#: Long, English, multi-paragraph JD (company blurb, role summary,
#: responsibilities, requirements) with no literal seniority-modifier
#: word anywhere (only "a minimum of eight years... experience" —
#: implicit seniority the engine does not parse, per CLAUDE.md section 7).
#: Exercises the Data Center / Mission Critical specialization, all four
#: of its technical skill groups (HV/MV, switchgear, transformers,
#: UPS/emergency power), and an explicit MUST vs. NICE-TO-HAVE split.
LONG_IMPLICIT_SENIORITY_DATA_CENTER_EN_JD = """
About Our Firm

We are a rapidly growing critical infrastructure engineering firm delivering power systems for some of Europe's largest data center campuses. Our Frankfurt office partners directly with hyperscale operators to design resilient, mission critical electrical infrastructure from concept through commissioning.

Role

We are looking for an Electrical Engineer to join our data center design team. You will work across the full project lifecycle, from early-stage concept design through detailed engineering and site commissioning, on some of the region's largest mission critical facilities.

Responsibilities

- Design HV and MV distribution systems for data center campuses.
- Specify switchgear and transformers for critical facilities.
- Coordinate with mechanical, structural, and controls disciplines throughout each project.
- Support commissioning and site acceptance testing for new data center builds.

Requirements

- A minimum of eight years of relevant electrical design experience is required.
- Hands-on experience with medium voltage switchgear is required.
- Familiarity with UPS and emergency power systems is a plus.
- Based in or willing to relocate to Frankfurt, Germany.
"""

#: Short, German, explicit seniority ("Leitender" — the "lead" title
#: tier), Building Services / MEP specialization via the standard German
#: abbreviation "TGA" and the term "Gebäudetechnik", single-country
#: location resolved purely through a city alias (Berlin), with no
#: literal country name in the text at all.
SHORT_EXPLICIT_SENIORITY_BUILDING_SERVICES_DE_JD = (
    "Leitender Elektroingenieur (TGA) – Berlin\n\n"
    "Für unser Team in Berlin suchen wir Verstärkung im Bereich Gebäudetechnik."
)

#: Long, German, multi-paragraph JD for the Industrial Power
#: specialization at "Principal" seniority. Deliberately uses only German
#: priority-cue phrases ("zwingend erforderlich", "von Vorteil") to
#: demonstrate a known limitation (CLAUDE.md section 7): the priority-cue
#: dictionary is English-only, so both technical terms below fall back to
#: the "important" bucket regardless of the JD's clear German intent.
LONG_INDUSTRIAL_POWER_DE_JD = """
Über uns

Wir sind ein international tätiges Ingenieurbüro mit Schwerpunkt auf elektrischen Anlagen für die Schwerindustrie. Von unserem Standort in Nürnberg aus betreuen wir Projekte für Produktionsanlagen in ganz Europa.

Ihre Rolle

Für unser Team suchen wir einen Principal Elektroingenieur mit langjähriger Erfahrung in der Auslegung elektrischer Anlagen für Industrieanlagen. Sie übernehmen die fachliche Verantwortung für anspruchsvolle Projekte im Bereich Industrieelektrik.

Aufgaben

- Planung und Auslegung der Stromverteilung für Produktionsanlagen.
- Auswahl und Spezifikation von Frequenzumrichtern für industrielle Antriebe.
- Fachliche Führung des Planungsteams über den gesamten Projektverlauf.

Anforderungen

- Mehrjährige Erfahrung in der industriellen Stromverteilung ist zwingend erforderlich.
- Kenntnisse im Bereich Frequenzumrichter sind von Vorteil.
- Standort: Nürnberg.
"""

#: English, two distinct countries named explicitly (Frankfurt/Germany and
#: Warsaw/Poland) — exercises the location OR group holding every JD
#: location term and the LinkedIn source resolver's documented fallback
#: to the global `site:linkedin.com/in/` prefix when more than one
#: distinct country is present (no single verified ccTLD applies).
MULTI_COUNTRY_GERMANY_POLAND_EN_JD = (
    "We are hiring an Electrical Engineer for our facilities team, "
    "covering both our Frankfurt, Germany and Warsaw, Poland offices."
)

#: English, a single explicit MUST-tier language requirement ("German is
#: required"). Exercises the Strict-only mandatory-language clause
#: (CLAUDE.md section 6 / assembler.py: Balanced drops the
#: language/company-type MUST clauses entirely).
MANDATORY_LANGUAGE_EN_JD = (
    "We are hiring an Electrical Engineer based in Munich. "
    "German is required for this role."
)

#: English, a single explicit NICE-TO-HAVE-tier language requirement
#: ("French is a nice to have"). Nice-to-have languages are extracted
#: into `SearchSpec.languages.nice_to_have` but — unlike MUST-tier
#: languages — never appear in any assembled query variant, since only
#: `SearchSpec.languages.must` feeds `assembler.py`.
OPTIONAL_LANGUAGE_EN_JD = (
    "We are hiring an Electrical Engineer based in Munich. "
    "French is a nice to have for this role."
)

#: English, a company-introduction false positive: the employer describes
#: itself as "a German engineering consultancy" (no candidate-background
#: context, no language-proficiency cue). Exercises two independent
#: extractor guards at once — the language false-positive guard (a bare
#: language name needs confirming context) and the company-type
#: negative-context guard ("we are a ... consultancy" describes the
#: employer, not a candidate-background requirement).
COMPANY_INTRODUCTION_FALSE_POSITIVE_EN_JD = (
    "We are a German engineering consultancy based in Munich. "
    "We are hiring an Electrical Engineer to join our team."
)

#: English, adjacent-but-incorrect job family: a vocational/trade
#: electrical role (Electrician / Electrical Technician), which the pack
#: deliberately excludes from its title and family-signal vocabulary —
#: neither term should qualify the Electrical Engineering pack as a
#: candidate at all, let alone be promoted to a seniority-tier title.
ADJACENT_FAMILY_ELECTRICIAN_EN_JD = (
    "This role is for an experienced Electrician. Electrical Technician "
    "certification is a plus. No degree is required, only trade certification."
)

#: English, a second adjacent-but-incorrect job family: a different
#: engineering discipline (Mechanical Engineer / HVAC) that shares no
#: family signal, title, industry, or skill term with the Electrical
#: Engineering pack.
ADJACENT_FAMILY_MECHANICAL_ENGINEER_EN_JD = (
    "We are hiring a Mechanical Engineer to design HVAC systems for "
    "commercial buildings. Experience with ductwork and chillers is required."
)

#: English, deliberately tied evidence for two specializations (exactly
#: two signal-phrase matches each for Data Center / Mission Critical and
#: for Building Services / MEP, both scored at the same fixed
#: `SPECIALIZATION_SIGNAL_WEIGHT`) — exercises `family_detector`'s
#: ambiguous-specialization tie-break, which returns no specialization
#: plus an "ambiguous" warning rather than guessing.
AMBIGUOUS_SPECIALIZATION_EN_JD = (
    "We are hiring an Electrical Engineer whose responsibilities span both "
    "our data center and MEP teams in Berlin. The role covers mission "
    "critical infrastructure as well as TGA coordination for our office campus."
)

#: English, a wholly unrelated job family (Marketing Coordinator) —
#: exercises the "no job family matched" warning path distinctly from the
#: adjacent-but-incorrect-family cases above (which are near-misses
#: within electrical trades; this one shares no vocabulary at all).
UNSUPPORTED_FAMILY_EN_JD = (
    "We are looking for a Marketing Coordinator to manage social media "
    "campaigns and plan brand partnerships."
)

#: English, single-country location that is not Germany (Poland) —
#: exercises the LinkedIn source resolver's verified-ccTLD path for a
#: second country, complementing every other fixture's German-only or
#: multi-country location coverage.
SINGLE_COUNTRY_POLAND_EN_JD = (
    "We are hiring an Electrical Engineer for our office in Warsaw, Poland."
)

#: A real "Lead Electrical Engineer" job posting (data-center due
#: diligence role, Germany/Poland), kept byte-for-byte as originally
#: pasted — deliberately NOT reformatted with bullet markers, since the
#: complete absence of bullets in the Responsibilities/Profile/Offer
#: sections is precisely what exposed the segmentation bug this fixture
#: regression-locks (see `src/xray/extractor.py`'s
#: `_ends_with_continuation_cue`/`_split_into_blocks`). Also exercises:
#: a company-HQ location false positive ("headquartered in Berlin,
#: Germany" — Berlin must be excluded, Germany/Poland must survive via
#: their other clean occurrences), a two-country location set (global
#: `site:` source fallback), an implicit MUST-tier-shaped language
#: requirement ("Fluent German and professional English"), a
#: NICE-TO-HAVE language cleanly isolated by a semicolon even before the
#: segmentation fix ("Polish a plus"), rich Data Center / Mission
#: Critical specialization and core-function evidence, and zero MUST-cue
#: phrases anywhere in the text (`spec.skills.must` is correctly empty —
#: an honest CLAUDE.md section 7 limitation, not a defect).
REAL_LEAD_ELECTRICAL_ENGINEER_DATA_CENTER_DUE_DILIGENCE_EN_JD = """
Lead Electrical Engineer (m/f/d)
Electrical Planning – Data Centre Due Diligence – Hyperscale & Colocation
Remote / Hybrid – Germany or Poland
Full-time – Permanent – Immediate start
◆ Compensation: €100,000–150,000 p.a., depending on experience and qualifications

gbc engineers is an international structural and civil engineering consultancy headquartered in Berlin, Germany, with offices in Germany and a Global Design Center in Southeast Asia, and a growing presence in Poland. We specialise in planning and design consulting services, covering structural design, BIM modelling and related engineering services. Over the past decade we have completed over 1,000 projects, including more than 20 data centres, and are actively growing our digital infrastructure, new energy and industrial practice. By combining German engineering precision with digital innovation and international collaboration, we deliver sustainable, high-quality solutions for the built environment.

As we expand our Polish operations, we are looking for a Lead Electrical Engineer to anchor our electrical planning capability and lead the ELT workstream on data centre site due diligence and design projects.

YOUR MISSION AT GBC ENGINEERS
As Lead Electrical Engineer, you own the electrical workstream on hyperscale and colocation data centre projects in Poland and wider Europe. You lead site due diligence on grid connection, HV and MV supply infrastructure and utility feasibility, and you take electrical planning from concept through detailed design. You build the technical core of our ELT practice — anchoring the discipline while civil, mechanical and structural specialists support adjacent scopes through our subcontract network.

YOUR RESPONSIBILITIES
Conduct electrical site assessments and due diligence for greenfield and brownfield data centre developments in Poland and wider Europe
Evaluate HV and MV supply infrastructure, grid connection capacity, utility availability and constraints on power delivery
Lead concept and detailed design of medium and low voltage distribution systems for hyperscale and colocation data centres
Specify UPS, standby generation, busbar and switchgear systems to Tier III and Tier IV requirements
Coordinate BIM-based electrical models with structural and mechanical disciplines
Produce technical due diligence reports for developer and investor audiences with clear, decision-ready recommendations
Serve as primary technical interface with clients, developers and general contractors
Manage delivery against HOAI phase milestones (LP 1–6), including approval and permitting coordination
Manage and quality-assure deliverables produced by subcontract specialists across civil, mechanical and structural disciplines
Build and develop the electrical planning capability as we scale the Polish practice
YOUR PROFILE
Degree in Electrical Engineering or equivalent (Dipl.-Ing. / M.Sc.)
7+ years in electrical planning for mission-critical, industrial or large-scale infrastructure facilities
Proven data centre project experience — at least one hyperscale or Tier III/IV facility delivered
Solid knowledge of German or European HV and MV standards and grid connection processes
Track record in technical due diligence, feasibility studies or early-stage site development
Familiarity with planning and permitting processes in Poland; broader European experience a plus
Experience coordinating multidisciplinary teams and managing external consultants
BIM coordination experience (Revit MEP) and familiarity with Uptime Institute Tier standards a plus
Strong stakeholder communication and coordination skills
Fluent German and professional English; Polish a plus
WHAT WE OFFER
Senior ownership of an emerging practice area in Poland and Central Europe
Direct collaboration with leadership on high-profile hyperscale data centre projects (BER13, FRA31, Penta HAM01)
Direct access to Engineering Leads and management — founder-led, no corporate hierarchy
Flexible working — remote or hybrid from Germany or Poland
Collaboration with international teams on projects in Germany, Southeast Asia and beyond
Yearly employee exchange programmes with Germany and Southeast Asia
Exposure to landmark projects including data centres, industrial facilities and infrastructure
OUR VISION AT GBC ENGINEERS
We are founder-led, with over 200 employees in Germany and Southeast Asia. Buildability first is our standard: pragmatic solutions that optimise budget and timeline without compromising quality. Those who take on responsibility here move forward quickly. Visibility is guaranteed - as is the opportunity to learn fast.

Sounds Like You?

Please send your CV and a short motivation letter to bewerbung@gbc-engineers.de with the subject line:

Application - Lead Electrical Engineer

Please include your university transcript (Grade Overview / Transcript of Records) with your application.
"""
