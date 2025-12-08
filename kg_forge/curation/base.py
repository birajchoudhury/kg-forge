"""Base protocol and interfaces for document curation backends."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from kg_forge.models.curation import CurationResult


@runtime_checkable
class CurationBackend(Protocol):
    """
    Protocol defining the interface for document curation backends.
    
    Implementations must:
    1. Detect document format from file extension
    2. Convert document to curated text
    3. Generate markdown file
    4. Extract metadata
    5. Return CurationResult with both outputs
    """

    def curate(
        self,
        source_path: Path,
        namespace: str,
        markdown_base_dir: Path,
        chunking_enabled: bool = False
    ) -> CurationResult:
        """
        Curate a document to extract text and metadata.
        
        Args:
            source_path: Path to source document (HTML, PDF, DOCX, PPTX, etc.)
            namespace: Namespace for organizing output
            markdown_base_dir: Base directory for markdown output (e.g., output/markdowns)
            chunking_enabled: Whether to produce document chunks
        
        Returns:
            CurationResult containing:
                - curated_text: Clean text for extraction
                - markdown_path: Path to saved markdown file
                - chunks: List of DocumentChunk (if chunking_enabled=True)
                - chunks_path: Path to chunks.json file (if chunking_enabled=True)
                - metadata: Document metadata
        
        Raises:
            CurationError: If curation fails
            UnsupportedFormatError: If document format is not supported
        """
        ...

    def supports_format(self, file_extension: str) -> bool:
        """
        Check if this backend supports the given file format.
        
        Args:
            file_extension: File extension (e.g., '.pdf', '.html')
        
        Returns:
            True if format is supported, False otherwise
        """
        ...

    @property
    def name(self) -> str:
        """
        Get the backend name.
        
        Returns:
            Backend identifier (e.g., 'docling', 'hyland_ke')
        """
        ...
