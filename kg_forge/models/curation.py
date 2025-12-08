"""Data models for document curation."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentChunk(BaseModel):
    """Represents a chunk of a document when chunking is enabled."""

    chunk_id: str = Field(..., description="Unique identifier for this chunk (e.g., 'doc123_chunk_001')")
    doc_id: str = Field(..., description="Parent document ID")
    page: Optional[int] = Field(None, description="Page number if available from source document")
    section: Optional[str] = Field(None, description="Section/heading name if available")
    start_offset: int = Field(..., description="Character offset in full markdown where chunk starts")
    end_offset: int = Field(..., description="Character offset in full markdown where chunk ends")
    text: str = Field(..., description="The actual chunk text content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional chunk metadata (heading_level, contains_table, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_id": "platform/intro.pdf_chunk_001",
                "doc_id": "platform/intro.pdf",
                "page": 1,
                "section": "Introduction",
                "start_offset": 0,
                "end_offset": 512,
                "text": "# Introduction\n\nThis document provides an overview...",
                "metadata": {
                    "heading_level": 1,
                    "contains_table": False,
                    "paragraph_index": 0
                }
            }
        }
    )


class DocumentMetadata(BaseModel):
    """Metadata extracted from a curated document."""

    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    creation_date: Optional[datetime] = Field(None, description="Document creation date")
    modification_date: Optional[datetime] = Field(None, description="Last modification date")
    page_count: Optional[int] = Field(None, description="Number of pages (for paginated formats)")
    source_format: str = Field(..., description="Original document format (html, pdf, docx, pptx)")
    file_size_bytes: Optional[int] = Field(None, description="Original file size in bytes")
    language: Optional[str] = Field(None, description="Document language (ISO 639-1 code)")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Additional format-specific metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Content Lake Overview",
                "author": "John Doe",
                "creation_date": "2024-01-15T10:30:00Z",
                "modification_date": "2024-01-20T14:45:00Z",
                "page_count": 15,
                "source_format": "pdf",
                "file_size_bytes": 2048576,
                "language": "en",
                "extra": {"pdf_version": "1.7", "encrypted": False}
            }
        }
    )


class CurationResult(BaseModel):
    """Result of document curation process."""

    doc_id: str = Field(..., description="Document ID with extension (e.g., 'intro.html', 'report.pdf')")
    curated_text: str = Field(..., description="Cleaned, curated text content")
    markdown_path: Path = Field(..., description="Path to saved markdown file")
    chunks: Optional[list[DocumentChunk]] = Field(
        None, 
        description="Document chunks when chunking is enabled"
    )
    chunks_path: Optional[Path] = Field(
        None, 
        description="Path to chunks.json file when chunking is enabled"
    )
    metadata: DocumentMetadata = Field(..., description="Extracted document metadata")
    curation_backend: str = Field(..., description="Backend used for curation (docling, hyland_ke)")
    curated_at: datetime = Field(default_factory=datetime.now, description="Curation timestamp")
    warnings: list[str] = Field(default_factory=list, description="Any warnings during curation")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "doc_id": "platform/intro.pdf",
                "curated_text": "# Introduction\n\nThis document provides...",
                "markdown_path": "output/markdowns/my-namespace/platform/intro.pdf.md",
                "chunks": [
                    {
                        "chunk_id": "platform/intro.pdf_chunk_001",
                        "doc_id": "platform/intro.pdf",
                        "page": 1,
                        "section": "Introduction",
                        "start_offset": 0,
                        "end_offset": 512,
                        "text": "# Introduction\n\nThis document provides..."
                    }
                ],
                "chunks_path": "output/markdowns/my-namespace/platform/intro.pdf.chunks.json",
                "metadata": {
                    "title": "Platform Introduction",
                    "source_format": "pdf",
                    "page_count": 5
                },
                "curation_backend": "docling",
                "curated_at": "2024-01-20T15:30:00Z",
                "warnings": []
            }
        }
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format for storage/serialization.
        
        Returns:
            Dict representation with serializable types
        """
        result = {
            "doc_id": self.doc_id,
            "curated_text": self.curated_text,
            "markdown_path": str(self.markdown_path),
            "metadata": self.metadata.model_dump(),
            "curation_backend": self.curation_backend,
            "curated_at": self.curated_at.isoformat(),
            "warnings": self.warnings
        }
        
        if self.chunks is not None:
            result["chunks"] = [chunk.model_dump() for chunk in self.chunks]
            
        if self.chunks_path is not None:
            result["chunks_path"] = str(self.chunks_path)
            
        return result
