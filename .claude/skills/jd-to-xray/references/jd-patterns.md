# JD shape patterns

Guidance for handling different Job Description shapes during Candidate
Profile extraction (SKILL.md step 1) and keyword grouping (step 3).
These are input-shape patterns, not new workflow steps — the six-step
workflow in `SKILL.md` still applies unchanged.

## Long JD

- Long JDs mix boilerplate (company blurb, benefits, EEO statements,
  application instructions) with substantive requirements. Extract only
  the substantive parts into the Candidate Profile; do not let
  boilerplate leak into MUST/IMPORTANT/NICE classification.
- Responsibilities sections often restate requirements in narrative form
  — cross-check them against the explicit "Requirements"/"Qualifications"
  section rather than double-counting the same skill from two sections
  as two separate MUST items.
- If a long JD still yields few explicit MUST cues, say so in Adjustment
  Logic rather than inventing structure that isn't there.

## Short JD

- Short JDs (a title plus a few bullet points) often lack explicit
  MUST/IMPORTANT/NICE cues. Apply the best-effort default from
  CLAUDE.md §7 and state plainly in Adjustment Logic that classification
  is a best-effort default, not a guarantee.
- Do not compensate for a short JD by inventing additional requirements
  not present in the text — expand terminology (step 4), not scope.
- Keyword groups may be thinner than usual; this is expected and should
  be reflected honestly in the Strict variant (fewer MUST groups) rather
  than padded out.

## Multiple responsibilities

- A JD listing many distinct responsibilities does not mean each becomes
  a MUST skill. Separate "what the role does" (responsibilities) from
  "what the candidate must already have" (requirements) — only the
  latter feeds Requirement Priority.
- Where a responsibility clearly implies an unstated but necessary skill
  (e.g. "will manage the CI/CD pipeline" implying CI/CD experience),
  note it as an inferred IMPORTANT/NICE item and flag the inference in
  Adjustment Logic rather than presenting it as an explicit MUST.

## Many skills

- When a JD lists many skills, resist collapsing them all into MUST.
  Keep the MUST list to the small set of skills that are genuinely
  non-negotiable; route the rest to IMPORTANT/NICE per
  `references/rules.md` ("MUST-HAVE SKILLS", "SECONDARY SKILLS").
- Group related skills into one concept where they are genuinely
  synonyms/expansions of the same thing (e.g. "React" / "React.js" /
  "ReactJS"), but keep genuinely distinct skills (e.g. "React" vs.
  "Node.js") as separate groups — do not merge distinct concepts to
  shrink the group count.

## Multiple locations

- List every location the JD names in the Candidate Profile's Location
  field; do not pick just one.
- All locations for a single role form one OR group in the location
  block (per `references/rules.md`, "LOCATION" and "Boolean grouping
  rules") — they do not get split into separate AND-ed constraints, and
  they never merge into the title or skill groups.
- If locations span multiple countries and a ccTLD is used, prefer the
  broadest ccTLD that covers the set, or omit the ccTLD narrowing and
  rely on the location OR group alone — but never drop the location
  terms themselves (CLAUDE.md §5).

## Multiple titles

- When a JD gives multiple acceptable titles (e.g. "Data Analyst / BI
  Analyst"), treat each literal title as a variant to expand under step 4
  (equivalent title), not as separate roles requiring separate output
  sets.
- If a JD genuinely describes two distinct roles bundled together (rare,
  but possible in poorly written postings), flag this explicitly in
  Adjustment Logic and pick the dominant role for Core Function rather
  than silently merging two unrelated functions into one query.
