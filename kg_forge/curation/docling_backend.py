"""Docling-based curation backend for multi-format document processing."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from kg_forge.curation.base import CurationBackend
from kg_forge.curation.errors import CurationBackendError, UnsupportedFormatError
from kg_forge.models.curation import CurationResult, DocumentChunk, DocumentMetadata

logger = logging.getLogger(__name__)


class DoclingCurationBackend:
    """
    Document curation backend using Docling library.
    
    Supports: HTML, PDF, DOCX, PPTX formats.
    Provides both markdown output and curated text.
    """

    SUPPORTED_FORMATS = {'.html', '.htm', '.pdf', '.docx', '.pptx'}

    def __init__(self, chunk_config: Optional[dict] = None):
        """
        Initialize Docling backend.
        
        Args:
            chunk_config: Optional chunking configuration
                - tokenizer: Tokenizer name (default: "Xenova/llama2-tokenizer")
                - max_tokens: Max tokens per chunk (default: 400, GLiREL compatible)
                - merge_peers: Merge small adjacent sections (default: True)
        """
        self._backend_name = "docling"
        self._chunk_config = chunk_config or {
            "tokenizer": "Xenova/llama2-tokenizer",
            "max_tokens": 400,  # GLiREL max is 512, use 400 for safety
            "merge_peers": True
        }
        
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
        markdown_base_dir: Path,
        chunking_enabled: bool = False
    ) -> CurationResult:
        """
        Curate document using Docling.
        
        Args:
            source_path: Path to source document
            namespace: Namespace for organizing output
            markdown_base_dir: Base directory for markdown output
            chunking_enabled: Whether to produce document chunks
        
        Returns:
            CurationResult with curated text, markdown path, metadata, and optional chunks
        
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

            # Step 7: Generate chunks if requested
            chunks = None
            chunks_path = None
            
            if chunking_enabled:
                try:
                    chunks, chunks_path = self._create_chunks(
                        result.document,
                        doc_id,
                        markdown_content,
                        namespace,
                        markdown_base_dir
                    )
                    logger.info(f"Created {len(chunks)} chunks for document: {doc_id}")
                except Exception as e:
                    logger.warning(f"Chunking failed for {doc_id}: {e}")
                    warnings.append(f"Chunking failed: {str(e)}")

            # Create curation result
            curation_result = CurationResult(
                doc_id=doc_id,
                curated_text=markdown_content,
                markdown_path=markdown_path,
                chunks=chunks,
                chunks_path=chunks_path,
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

    def _create_chunks(
        self,
        docling_doc,
        doc_id: str,
        markdown_content: str,
        namespace: str,
        markdown_base_dir: Path
    ) -> tuple[list[DocumentChunk], Path]:
        """
        Create document chunks using Docling's HybridChunker.
        
        Args:
            docling_doc: Docling Document object
            doc_id: Document ID
            markdown_content: Full markdown content
            namespace: Namespace for organization
            markdown_base_dir: Base directory for markdown files
        
        Returns:
            Tuple of (chunks list, chunks_path)
        """
        try:
            from docling_core.transforms.chunker import HybridChunker
        except ImportError as e:
            raise CurationBackendError(
                "docling-core not installed. Install with: pip install docling-core",
                original_error=e
            )

        # Create chunker
        chunker = HybridChunker(
            tokenizer=self._chunk_config.get("tokenizer", "Xenova/llama2-tokenizer"),
            max_tokens=self._chunk_config.get("max_tokens", 400),  # GLiREL compatible
            merge_peers=self._chunk_config.get("merge_peers", True)
        )

        # Generate chunks
        chunks = []
        current_offset = 0
        
        for idx, chunk in enumerate(chunker.chunk(docling_doc)):
            # chunk is a DocChunk object from docling_core
            # Extract text content from the chunk
            if hasattr(chunk, 'text'):
                chunk_text = chunk.text
            elif hasattr(chunk, 'content'):
                chunk_text = chunk.content
            else:
                # Fallback: try to convert to string
                chunk_text = str(chunk)
            
            # Calculate offsets in the full markdown
            start_offset = current_offset
            end_offset = current_offset + len(chunk_text)
            current_offset = end_offset
            
            # Extract metadata from chunk
            page = None
            section = None
            chunk_metadata = {}
            
            # Try to extract metadata from chunk attributes
            if hasattr(chunk, 'meta'):
                if hasattr(chunk.meta, 'page'):
                    page = chunk.meta.page
                if hasattr(chunk.meta, 'doc_items'):
                    # Try to extract section from doc items
                    for item in chunk.meta.doc_items:
                        if hasattr(item, 'label') and 'section' in item.label.lower():
                            section = str(item.text) if hasattr(item, 'text') else None
                            break
            
            # Create DocumentChunk
            doc_chunk = DocumentChunk(
                chunk_id=f"{doc_id}_chunk_{idx+1:03d}",
                doc_id=doc_id,
                page=page,
                section=section,
                start_offset=start_offset,
                end_offset=end_offset,
                text=chunk_text,
                metadata=chunk_metadata
            )
            chunks.append(doc_chunk)
        
        # Save chunks to JSON file
        namespace_dir = markdown_base_dir / namespace
        namespace_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = namespace_dir / f"{doc_id}.chunks.json"
        
        # Serialize chunks to JSON
        chunks_data = [chunk.model_dump() for chunk in chunks]
        chunks_path.write_text(
            json.dumps(chunks_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        logger.debug(f"Saved {len(chunks)} chunks to: {chunks_path}")
        
        return chunks, chunks_path
