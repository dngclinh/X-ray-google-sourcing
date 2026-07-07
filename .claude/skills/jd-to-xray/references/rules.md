# X-ray field and Boolean rules

Detailed rules for building the Candidate Profile, keyword groups, and
Boolean strings referenced by `SKILL.md`. Read `SKILL.md` first for the
overall workflow; this file is the field-by-field reference.

## SOURCE

- Record which JD (company/title/date or identifier) each output was
  derived from. This is for traceability/QA only — it never appears in
  the Boolean string itself.

## TARGET TITLES

- Extract the literal title(s) from the JD first, then normalize:
  - remove job-posting suffixes (see below);
  - keep the core role name (e.g. "Senior Backend Engineer" → title
    family "Backend Engineer", seniority handled separately).
- Titles form their own OR group, never merged with skills or location.
- Correct: `("Backend Engineer" OR "Backend Developer" OR "Software Engineer, Backend")`
- Incorrect: `("Backend Engineer" OR "Python" OR "Poland")` — mixes
  title, skill, and location in one group.

## CORE FUNCTION

- One primary discipline per role. If the JD genuinely spans two
  functions (e.g. "Sales Engineer"), treat it as its own hybrid function
  rather than forcing it into one or the other.
- Flag Core Function as heuristic whenever the JD is ambiguous — do not
  present a guess as certain (CLAUDE.md §7).

## INDUSTRY/DOMAIN

- Only include an industry/domain qualifier when the JD states or
  strongly implies it (e.g. "fintech", "automotive", "healthcare").
- Do not add an industry term as a MUST filter unless the JD makes it a
  hard requirement — industry context is usually IMPORTANT or NICE, not
  MUST, unless stated otherwise.

## MUST-HAVE SKILLS

- Reserve MUST for skills the JD marks as required, or that are
  functionally impossible to do the job without.
- Keep the MUST list short. Every additional MUST skill multiplies away
  candidates who satisfy all the others — see
  `examples/common-errors.md` ("too many mandatory skills").
- Each distinct skill/concept gets its own OR group of synonyms; MUST
  groups are combined with AND between groups.

## SECONDARY SKILLS

- IMPORTANT and NICE-TO-HAVE skills live in the Balanced/Broad variants
  as optional OR terms, not as additional AND-ed MUST groups.
- Do not silently promote a NICE-TO-HAVE to MUST to "tighten" a query —
  that changes its meaning and breaks equivalence with the JD.

## SENIORITY

- Model seniority as its own optional signal (title modifiers like
  "Senior", "Lead", "Staff", "Principal", or years-of-experience
  language), not folded into the title OR group unless the JD's title
  itself includes it.
- Do not treat seniority words as skills or titles for grouping purposes.

## LOCATION

- Location terms form their own dedicated block/group — never combined
  into a title or skill OR group.
- Include city, region, and country-level terms as given in the JD; do
  not invent additional locations.
- Incorrect: `("electrical" OR "Poland" OR "Germany")` — mixes a skill
  term with location terms in one OR group. See
  `examples/common-errors.md`.

## LANGUAGE

- Only include language requirements the JD states explicitly (e.g.
  "fluent German required").
- Do not infer a language requirement from a location alone (e.g. do not
  assume German is required just because the location is Germany).

## COMPANY TYPE

- Include company-type qualifiers (startup, enterprise, agency, in-house
  team) only when the JD states them as relevant context; this is
  typically NICE-TO-HAVE signal, not a MUST filter.

## EXCLUSIONS

- Use `NOT` sparingly and only for terms the JD or clear domain
  knowledge marks as genuinely disqualifying (e.g. excluding recruiters
  from a search for the role being recruited).
- Do not use exclusions as a substitute for precise inclusion terms —
  excessive `NOT` chains quietly destroy recall. See
  `examples/common-errors.md` ("excessive exclusions").

## ccTLD strategy

- When a LinkedIn country ccTLD is used (e.g. `site:de.linkedin.com/in`,
  `site:xx.linkedin.com/in`), it narrows results by LinkedIn domain/
  locale — it does **not** replace the location block.
- Always preserve explicit location terms in the query in addition to
  the ccTLD (CLAUDE.md §5). The ccTLD and the location terms serve
  different purposes: domain narrowing vs. profile-content precision.

## Boolean grouping rules

- One semantic concept per parenthesized OR group: titles, skills,
  locations, company types, and languages each get their own group.
- Groups are combined with AND (implicit adjacency or explicit `AND`)
  between different concepts, and OR within a single concept's
  synonyms/expansions.
- Correct:
  `site:linkedin.com/in ("Backend Engineer" OR "Backend Developer") AND ("Python" OR "Django") AND ("Berlin" OR "Germany")`
- Incorrect:
  `site:linkedin.com/in ("Backend Engineer" OR "Python" OR "Berlin")` —
  a single OR group spanning title, skill, and location collapses
  precision to near zero (any one term alone can match).

## Correct and incorrect examples

Correct — one concept per group, MUST count kept small:

```
site:linkedin.com/in
("Data Engineer" OR "Data Platform Engineer")
AND ("SQL" OR "Structured Query Language")
AND ("Warsaw" OR "Kraków" OR "Poland")
```

Incorrect — mixed semantic types in one group (see
`examples/common-errors.md` for more like this):

```
site:linkedin.com/in ("electrical" OR "Poland" OR "Germany")
```

## Location terms only in the location block

Never let a location word leak into a title or skill OR group (and vice
versa). If a JD phrase blends concepts (e.g. "Electrical Engineer based
in Poland or Germany"), split it during Candidate Profile extraction
(step 1) before it ever reaches keyword grouping (step 3), so the skill
group and the location group are built independently from the start.

## Removal of job-posting suffixes from titles

Strip boilerplate posting suffixes/prefixes before using a title in a
Boolean group. Examples of suffixes to remove: "(m/f/d)", "(all
genders)", "- Remote", "- Hybrid", "#123456", "New", "Urgent Hiring",
req/job-ID codes, and location tags appended to the title itself (e.g.
"Backend Engineer - Berlin" → title "Backend Engineer"; the location
moves to the location block, not dropped).
