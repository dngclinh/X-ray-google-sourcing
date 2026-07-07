"""Public interface of the X-ray deterministic sourcing engine.

The only supported entry point for callers outside `src/xray/` is
`generate_xray_queries` — every other module under `src/xray/`
(`normalizer`, `glossary`, `knowledge_loader`, `family_detector`,
`extractor`, `source_resolver`, `assembler`, `validator`) is an
internal implementation detail of the pipeline it wires together and
may change without notice.

Example:
    from src.xray import generate_xray_queries

    spec, variants = generate_xray_queries(jd_text)
    print(variants.balanced)
    print(spec.warnings)
"""

from __future__ import annotations

from src.xray.models import PrioritizedTerms, QueryVariants, SearchSpec
from src.xray.service import InvalidJobDescriptionError, generate_xray_queries

__all__ = [
    "generate_xray_queries",
    "InvalidJobDescriptionError",
    "SearchSpec",
    "QueryVariants",
    "PrioritizedTerms",
]
