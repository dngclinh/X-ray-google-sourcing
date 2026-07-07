# Common errors to check before finalizing output

Use this checklist during the audit step (SKILL.md step 6) before
returning any of the four search variants. Each item below is a mistake
seen in prior benchmark work — check for it explicitly.

## 1. Mixed semantic types in one OR block

Never combine title, skill, and location terms in a single OR group.
Each OR group must represent exactly one semantic concept.

Incorrect:

```
("electrical" OR "Poland" OR "Germany")
```

This mixes a skill/discipline term ("electrical") with two location
terms ("Poland", "Germany") in one OR block. Any single term alone can
satisfy the group, so the query effectively matches "anything
electrical" OR "anyone in Poland" OR "anyone in Germany" — not
"electrical people in Poland or Germany".

Correct:

```
("electrical" OR "electrical engineering") AND ("Poland" OR "Germany")
```

## 2. Overly generic titles

Using a bare function/discipline word as if it were a title term (e.g.
"electrical", "engineer", "manager", "analyst" alone) floods results
with unrelated matches. Titles must be specific enough to identify the
role (e.g. "Electrical Engineer", "Electrical Design Engineer"), not just
the discipline name.

## 3. Too many mandatory skills

Stacking many skills into the MUST/AND list (e.g. AND-ing five or six
distinct tools/technologies) makes it statistically unlikely any real
profile satisfies all of them at once, collapsing recall to near zero.
Keep MUST to the small set of truly non-negotiable skills; route the
rest to IMPORTANT/NICE in the Balanced/Broad variants.

## 4. Excessive exclusions

Chaining many `NOT` terms to "clean up" a query is a sign the inclusion
terms aren't precise enough. Each additional exclusion risks removing
valid candidates for reasons unrelated to the JD. Use `NOT` only for
clearly disqualifying terms, not as a substitute for better inclusion
grouping.

## 5. Location mixed with title or skill

Location terms must live only in the dedicated location block. A common
error is appending a location word directly into a title group (e.g.
`("Backend Engineer Berlin")` as a single phrase) or into a skill group.
Keep location extraction (Candidate Profile step 1) and location
grouping (keyword groups step 3) strictly separate from title/skill
handling — see `references/rules.md` ("LOCATION", "Location terms only
in the location block").

## 6. The canonical incorrect example

Always check final output against this known-bad pattern; if any
variant resembles it, the grouping step (step 3) was skipped or done
incorrectly:

```
("electrical" OR "Poland" OR "Germany")
```

This single line embodies errors #1, #2, and #5 at once: a generic
discipline word standing in for a title, mixed with location terms, all
in one OR group.
