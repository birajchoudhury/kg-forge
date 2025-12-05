"""Hyland Knowledge Extraction API-based curation backend (stub for future implementation)."""

import logging
from pathlib import Path

from kg_forge.curation.base import CurationBackend
from kg_forge.curation.errors import CurationBackendError
from kg_forge.models.curation import CurationResult

logger = logging.getLogger(__name__)


class HylandKECurationBackend:
    """
    Document curation backend using Hyland Knowledge Extraction API.
    
    This is a stub implementation for future integration.
    When implemented, this will use Hyland's curated content API
    instead of local processing.
    """

    SUPPORTED_FORMATS = {'.html', '.htm', '.pdf', '.docx', '.pptx', '.txt', '.xml'}

    def __init__(self, api_endpoint: str = None, api_key: str = None):
        """
        Initialize Hyland KE backend.
        
        Args:
            api_endpoint: Hyland KE API endpoint URL
            api_key: API authentication key
        """
        self._backend_name = "hylandKE"
        self._api_endpoint = api_endpoint
        self._api_key = api_key
        
        if not api_endpoint or not api_key:
            logger.warning(
                "HylandKECurationBackend initialized without API credentials. "
                "Set HYLAND_KE_ENDPOINT and HYLAND_KE_API_KEY in environment or config."
            )

    @property
    def name(self) -> str:
        """Get backend name."""
        return self._backend_name

    def supports_format(self, file_extension: str) -> bool:
        """
        Check if format is supported.
        
        Args:
            file_extension: File extension (e.g., '.pdf', '.html')
        
        Returns:
            True if supported, False otherwise
        """
        return file_extension.lower() in self.SUPPORTED_FORMATS

    def curate(
        self,
        source_path: Path,
        namespace: str,
        markdown_base_dir: Path
    ) -> CurationResult:
        """
        Curate document using Hyland KE API.
        
        Args:
            source_path: Path to source document
            namespace: Namespace for organizing output
            markdown_base_dir: Base directory for markdown output
        
        Returns:
            CurationResult with curated text, markdown path, and metadata
        
        Raises:
            CurationBackendError: This is a stub implementation
        """
        raise CurationBackendError(
            "HylandKECurationBackend is not yet implemented. "
            "This is a stub for future integration with Hyland Knowledge Extraction API. "
            "Use 'docling' backend instead.",
            doc_path=str(source_path)
        )

    # Future implementation would include:
    # - Upload document to Hyland KE API
    # - Poll for processing completion
    # - Download curated content
    # - Extract metadata from API response
    # - Save markdown file
    # - Return CurationResult
