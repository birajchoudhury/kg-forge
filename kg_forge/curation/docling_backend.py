"""Docling-based curation backend for multi-format document processing."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from kg_forge.curation.base import CurationBackend
from kg_forge.curation.errors import CurationBackendError, UnsupportedFormatError
from kg_forge.models.curation import CurationResult, DocumentMetadata

logger = logging.getLogger(__name__)


class DoclingCurationBackend:
    """
    Document curation backend using Docling library.
    
    Supports: HTML, PDF, DOCX, PPTX formats.
    Provides both markdown output and curated text.
    """

    SUPPORTED_FORMATS = {'.html', '.htm', '.pdf', '.docx', '.pptx'}

    def __init__(self):
        """Initialize Docling backend."""
        self._backend_name = "docling"
        
        # Lazy import to allow installation check
        try:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
        except ImportError as e:
            raise CurationBackendError(
                "Docling library not installed. Install with: pip install docling>=1.0.0",
                original_error=e
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
        Curate document using Docling.
        
        Args:
            source_path: Path to source document
            namespace: Namespace for organizing output
            markdown_base_dir: Base directory for markdown output
        
        Returns:
            CurationResult with curated text, markdown path, and metadata
        
        Raises:
            UnsupportedFormatError: If format is not supported
            CurationBackendError: If curation fails
        """
        # Validate source file
        if not source_path.exists():
            raise CurationBackendError(
                f"Source file does not exist",
                doc_path=str(source_path)
            )

        # Check format support
        file_ext = source_path.suffix.lower()
        if not self.supports_format(file_ext):
            raise UnsupportedFormatError(
                f"Format '{file_ext}' not supported by Docling. Supported: {self.SUPPORTED_FORMATS}",
                doc_path=str(source_path)
            )

        # Generate doc_id with extension (relative path from some base + extension)
        # For now, use filename with extension as doc_id
        doc_id = source_path.name  # e.g., "intro.pdf"

        warnings = []

        try:
            # Convert document using Docling
            logger.info(f"Converting document with Docling: {source_path}")
            result = self._converter.convert(str(source_path))
            
            # Extract markdown content
            markdown_content = result.document.export_to_markdown()
            
            if not markdown_content or not markdown_content.strip():
                warnings.append("Docling produced empty markdown content")
                markdown_content = f"# {source_path.name}\n\n*No content extracted*"

            # Extract metadata
            metadata = self._extract_metadata(result, source_path, file_ext)

            # Step 6: Save markdown file
            markdown_path = self._save_markdown(
                markdown_content,
                doc_id,
                namespace,
                markdown_base_dir
            )

            # Create curation result
            curation_result = CurationResult(
                doc_id=doc_id,
                curated_text=markdown_content,
                markdown_path=markdown_path,
                metadata=metadata,
                curation_backend=self.name,
                curated_at=datetime.now(),
                warnings=warnings
            )

            logger.info(f"Successfully curated document: {doc_id}")
            return curation_result

        except Exception as e:
            if isinstance(e, (UnsupportedFormatError, CurationBackendError)):
                raise
            raise CurationBackendError(
                f"Docling conversion failed for {source_path.name}",
                doc_path=str(source_path),
                original_error=e
            )

    def _extract_metadata(
        self,
        docling_result,
        source_path: Path,
        file_ext: str
    ) -> DocumentMetadata:
        """
        Extract metadata from Docling result.
        
        Args:
            docling_result: Docling conversion result
            source_path: Original source file path
            file_ext: File extension
        
        Returns:
            DocumentMetadata instance
        """
        doc = docling_result.document
        
        # Extract title - try multiple sources
        title = None
        if hasattr(doc, 'name') and doc.name:
            title = doc.name
        elif hasattr(doc, 'metadata') and hasattr(doc.metadata, 'title'):
            title = doc.metadata.title
        
        # Default to filename without extension if no title found
        if not title:
            title = source_path.stem

        # Extract page count (for paginated formats)
        page_count = None
        if file_ext in {'.pdf', '.docx', '.pptx'}:
            if hasattr(doc, 'pages') and doc.pages:
                page_count = len(doc.pages)

        # Get file size
        file_size_bytes = source_path.stat().st_size if source_path.exists() else None

        # Extract other metadata if available
        author = None
        creation_date = None
        modification_date = None
        language = None
        extra = {}

        if hasattr(doc, 'metadata'):
            meta = doc.metadata
            if hasattr(meta, 'creator'):
                author = meta.creator
            if hasattr(meta, 'creation_date'):
                try:
                    creation_date = meta.creation_date
                    if isinstance(creation_date, str):
                        creation_date = datetime.fromisoformat(creation_date.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            if hasattr(meta, 'modification_date'):
                try:
                    modification_date = meta.modification_date
                    if isinstance(modification_date, str):
                        modification_date = datetime.fromisoformat(modification_date.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            if hasattr(meta, 'language'):
                language = meta.language

            # Capture any additional metadata
            if file_ext == '.pdf' and hasattr(meta, 'pdf_version'):
                extra['pdf_version'] = meta.pdf_version

        return DocumentMetadata(
            title=title,
            author=author,
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=page_count,
            source_format=file_ext.lstrip('.'),  # Remove leading dot
            file_size_bytes=file_size_bytes,
            language=language,
            extra=extra
        )

    def _save_markdown(
        self,
        markdown_content: str,
        doc_id: str,
        namespace: str,
        markdown_base_dir: Path
    ) -> Path:
        """
        Save markdown content to file.
        
        Args:
            markdown_content: Markdown text
            doc_id: Document ID with extension
            namespace: Namespace for organization
            markdown_base_dir: Base directory for markdown files
        
        Returns:
            Path to saved markdown file
        """
        # Organize by namespace: output/markdowns/<namespace>/<doc_id>.md
        namespace_dir = markdown_base_dir / namespace
        namespace_dir.mkdir(parents=True, exist_ok=True)

        # Save with .md extension added to doc_id
        markdown_path = namespace_dir / f"{doc_id}.md"
        
        markdown_path.write_text(markdown_content, encoding='utf-8')
        logger.debug(f"Saved markdown to: {markdown_path}")

        return markdown_path
