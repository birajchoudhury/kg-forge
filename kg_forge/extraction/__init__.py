"""
Extraction backend interfaces and protocols.

Defines the common interface for all extraction backends (LLM, spaCy, hybrid, fake, etc.).
"""

from kg_forge.extraction.interface import ExtractionBackend, BaseExtractionBackend
from kg_forge.extraction.llm_backend import LLMExtractionBackend
from kg_forge.extraction.fake_backend import FakeExtractionBackend
from kg_forge.extraction.exceptions import (
    ExtractionError,
    BackendNotAvailableError,
    ModelLoadingError,
    ConsecutiveFailureError,
    ExtractionTimeoutError
)

# Lazy imports for backends that require Python 3.10+
# These will be imported on-demand in create_extraction_backend()
SpacyLexicalBackend = None
HybridExtractionBackend = None

__all__ = [
    "ExtractionBackend",
    "BaseExtractionBackend",
    "LLMExtractionBackend",
    "SpacyLexicalBackend",
    "HybridExtractionBackend",
    "FakeExtractionBackend",
    "ExtractionError",
    "BackendNotAvailableError",
    "ModelLoadingError",
    "ConsecutiveFailureError",
    "ExtractionTimeoutError"
]