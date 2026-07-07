"""Application service layer for the X-ray deterministic sourcing engine.

`generate_xray_queries` is the single supported entry point that wires
together every other `src/xray/` module into one deterministic
pipeline, from raw Job Description text to the four assembled Boolean
query variants:

1. normalize/validate the input;
2. load the generic knowledge glossary (`glossary.py`);
3. load every production job-family pack under
   `knowledge/job_families/` (`knowledge_loader.py`) — a filename
   starting with `_` (e.g. `_schema_example.yaml`) is treated as
   illustrative documentation, never as production data;
4. detect the job family and specialization (`family_detector.py`);
5. extract structured evidence into a `SearchSpec`, activating the
   detected pack (if any) for profession-specific terms
   (`extractor.py`);
6. merge `location_override` into `SearchSpec.locations` safely
   (additively — it never replaces JD-extracted locations, so a
   conflicting override correctly falls back to the global LinkedIn
   source rather than silently picking the wrong ccTLD);
7. resolve the LinkedIn `site:` source (`source_resolver.py`);
8. assemble the four query variants (`assembler.py`);
9. validate the result (`validator.py`) and fold every warning — from
   family detection and from validation alike — into
   `SearchSpec.warnings`, so a caller only ever has to look in one
   place;
10. return `(SearchSpec, QueryVariants)`.

This module never imports Streamlit and has no UI concerns — it is
pure application logic, safe to call from a CLI, a test, or a future
UI layer alike. It holds no module-level mutable state: every call is
independent and, for the same inputs and the same on-disk knowledge
files, deterministic.
"""

from __future__ import annotations

from pathlib import Path

from src.xray.assembler import assemble
from src.xray.extractor import extract
from src.xray.family_detector import detect_family
from src.xray.glossary import Glossary
from src.xray.knowledge_loader import JobFamilyPack, load_job_family_pack
from src.xray.models import QueryVariants, SearchSpec
from src.xray.normalizer import dedupe_preserve_order, normalize_whitespace
from src.xray.source_resolver import resolve_source_for_spec
from src.xray.validator import validate

#: Real, on-disk directory of production job-family packs.
_DEFAULT_JOB_FAMILIES_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "job_families"


class InvalidJobDescriptionError(ValueError):
    """Raised when `jd_text` is empty or contains only whitespace."""


def _load_production_packs(job_families_dir: Path) -> tuple[JobFamilyPack, ...]:
    """Load every production job-family pack in `job_families_dir`.

    A filename starting with `_` (e.g. `_schema_example.yaml`) is
    skipped — that naming convention marks a file as illustrative
    schema documentation, never production data (see
    `knowledge_loader.py`). Missing directories yield no packs rather
    than raising, since "no production packs yet" is a valid, expected
    state (CLAUDE.md section 7: unsupported job families must produce
    an explicit warning, not an error).
    """
    if not job_families_dir.is_dir():
        return ()
    return tuple(
        load_job_family_pack(path)
        for path in sorted(job_families_dir.glob("*.yaml"))
        if not path.name.startswith("_")
    )


def generate_xray_queries(
    jd_text: str,
    location_override: str = "",
    *,
    knowledge_dir: str | Path | None = None,
    job_families_dir: str | Path | None = None,
) -> tuple[SearchSpec, QueryVariants]:
    """Generate the four LinkedIn X-ray query variants for a Job Description.

    Args:
        jd_text: The Job Description text, as originally formatted
            (line breaks and bullet markers intact — this function
            handles all internal normalization itself; callers must
            not pre-flatten it).
        location_override: An optional extra location term (e.g. a
            recruiter-supplied city or country) merged additively into
            the locations extracted from `jd_text`. Left as `""` (the
            default) to use only what was extracted.
        knowledge_dir: Overrides the directory `glossary.py` loads the
            generic knowledge files from. Intended for test isolation;
            production callers should omit it.
        job_families_dir: Overrides the directory production
            job-family packs are loaded from. Intended for test
            isolation with synthetic packs; production callers should
            omit it.

    Returns:
        A `(SearchSpec, QueryVariants)` tuple. `SearchSpec.warnings`
        carries every non-fatal issue surfaced anywhere in the
        pipeline — ambiguous/unsupported job family, missing evidence,
        validator findings, and so on — so a caller never has to query
        multiple objects to know what to review.

    Raises:
        TypeError: if `jd_text` or `location_override` is not a `str`.
        InvalidJobDescriptionError: if `jd_text` is empty or contains
            only whitespace.
        GlossarySchemaError: if a generic knowledge file under
            `knowledge/` fails schema validation.
        KnowledgePackSchemaError: if a job-family pack under
            `knowledge/job_families/` fails schema validation.

    This function is deterministic: given the same arguments and the
    same on-disk knowledge files, it always returns an equal result. It
    never imports or depends on Streamlit.
    """
    if not isinstance(jd_text, str):
        raise TypeError(f"jd_text must be a string, got {type(jd_text).__name__}")
    if not isinstance(location_override, str):
        raise TypeError(
            f"location_override must be a string, got {type(location_override).__name__}"
        )
    if not jd_text.strip():
        raise InvalidJobDescriptionError("jd_text must not be empty or whitespace-only")

    # 1. normalize input (a second, whitespace-flattened copy for family
    # detection — extraction needs the original line/bullet structure).
    normalized_for_detection = normalize_whitespace(jd_text)

    # 2. load generic knowledge.
    glossary = Glossary.load(knowledge_dir) if knowledge_dir is not None else Glossary.load()

    # 3. load production job-family packs.
    packs = _load_production_packs(
        Path(job_families_dir) if job_families_dir is not None else _DEFAULT_JOB_FAMILIES_DIR
    )

    # 4. detect job family and specialization.
    detection = detect_family(normalized_for_detection, packs)
    activated_pack = next((pack for pack in packs if pack.family == detection.family), None)

    # 5. extract structured evidence (extractor.py sets SearchSpec.job_family
    # from the activated pack, but has no notion of specialization, which
    # detect_family already determined — folded in immediately below).
    spec = extract(jd_text, glossary, pack=activated_pack)
    spec.specialization = detection.specialization
    spec.confidence["job_family"] = detection.confidence
    for category, terms in detection.matched_signals.items():
        existing = spec.matched_signals.get(category, [])
        spec.matched_signals[category] = dedupe_preserve_order([*existing, *terms])
    for warning in detection.warnings:
        if warning not in spec.warnings:
            spec.warnings.append(warning)

    # 6. merge location override safely (additive, never a replacement —
    # see module docstring for why that's the safe choice).
    override = normalize_whitespace(location_override)
    if override:
        spec.locations = dedupe_preserve_order([override, *spec.locations])

    # 7. resolve LinkedIn source. `assemble()` (step 8) resolves and uses
    # this itself from the now-final `spec.locations`; called explicitly
    # here too only to keep this pipeline step visible and independently
    # testable, not because assembly needs the value handed to it.
    resolve_source_for_spec(spec, glossary)

    # 8. assemble four variants.
    variants = assemble(spec, glossary)

    # 9. validate results; fold every finding into SearchSpec.warnings.
    result = validate(spec, variants)
    for issue in result.issues:
        if issue.message not in spec.warnings:
            spec.warnings.append(issue.message)

    # 10. return SearchSpec and QueryVariants.
    return spec, variants
