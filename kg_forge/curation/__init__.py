"""Document curation module for multi-format processing.

This module provides pluggable backends for converting various document formats
(HTML, PDF, DOCX, PPTX) into curated text and markdown.

Backends:
    - Docling: Local multi-format processor (default)
    - Hyland KE: API-based curated content service (future)

Usage:
    from kg_forge.curation import create_curation_backend
    
    backend = create_curation_backend("docling")
    result = backend.curate(
        source_path=Path("document.pdf"),
        namespace="my-project",
        markdown_base_dir=Path("output/markdowns")
    )
    print(result.curated_text)
    print(result.markdown_path)
"""

from kg_forge.curation.base import CurationBackend
from kg_forge.curation.docling_backend import DoclingCurationBackend
from kg_forge.curation.errors import (
    CurationBackendError,
    CurationError,
    FormatDetectionError,
    UnsupportedFormatError,
)
from kg_forge.curation.factory import create_curation_backend
from kg_forge.curation.hyland_backend import HylandKECurationBackend

__all__ = [
    # Protocol
    "CurationBackend",
    # Backends
    "DoclingCurationBackend",
    "HylandKECurationBackend",
    # Factory
    "create_curation_backend",
    # Exceptions
    "CurationError",
    "CurationBackendError",
    "UnsupportedFormatError",
    "FormatDetectionError",
]
