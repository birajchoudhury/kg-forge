"""
Extraction backend interfaces and protocols.

Defines the common interface for all extraction backends (LLM, spaCy, hybrid, fake, etc.).
"""

from kg_forge.extraction.interface import ExtractionBackend, BaseExtractionBackend
from kg_forge.extraction.llm_backend import LLMExtractionBackend
from kg_forge.extraction.spacy_backend import SpacyLexicalBackend
from kg_forge.extraction.hybrid_backend import HybridExtractionBackend
from kg_forge.extraction.fake_backend import FakeExtractionBackend
from kg_forge.extraction.exceptions import (
    ExtractionError,
    BackendNotAvailableError,
    ModelLoadingError,
    ConsecutiveFailureError,
    ExtractionTimeoutError
)

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