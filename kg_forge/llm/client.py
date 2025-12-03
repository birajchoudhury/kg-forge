"""
Core LLM client interfaces and data models.
"""

import logging
from typing import Protocol
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class ExtractedEntity:
    """Represents a single entity extracted by the LLM."""
    type: str
    name: str
    confidence: float = 1.0

@dataclass 
class ExtractionResult:
    """Container for LLM extraction results."""
    entities: list[ExtractedEntity]

class LLMExtractor(Protocol):
    """Protocol for LLM-based entity extraction."""
    
    def extract_entities(self, prompt: str) -> ExtractionResult:
        """Extract entities from prompt, return structured result."""
        ...

class BaseLLMExtractor(ABC):
    """Base class for LLM extractors with common functionality."""
    
    def __init__(self):
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10
    
    @abstractmethod
    def _call_llm(self, prompt: str) -> str:
        """Make the actual LLM call. Must be implemented by subclasses."""
        ...
    
    def extract_entities(self, prompt: str) -> ExtractionResult:
        """Extract entities with error handling and retry logic."""
        from .parser import ResponseParser
        from .exceptions import ExtractionAbortError
        
        parser = ResponseParser()
        
        for attempt in range(2):  # Retry once on failure
            try:
                response = self._call_llm(prompt)
                result = parser.parse_extraction_result(response)
                
                # Success - reset failure counter
                self.consecutive_failures = 0
                return result
                
            except Exception as e:
                self.consecutive_failures += 1
                
                if self.consecutive_failures > self.max_consecutive_failures:
                    raise ExtractionAbortError(
                        f"Exceeded maximum consecutive failures ({self.max_consecutive_failures})"
                    ) from e
                
                # Log warning and continue to retry (if not last attempt)
                if attempt == 0:
                    logger.warning(f"LLM extraction failed (attempt {attempt + 1}), retrying: {e}")
                else:
                    # Last attempt failed, re-raise
                    raise e
        
        # Should not reach here, but just in case
        raise RuntimeError("Unexpected error in extraction logic")