"""Test data models for curation."""

import pytest
from datetime import datetime
from pathlib import Path

from kg_forge.models.curation import CurationResult, DocumentMetadata


class TestDocumentMetadata:
    """Tests for DocumentMetadata model."""

    def test_basic_metadata(self):
        """Test creating basic metadata."""
        metadata = DocumentMetadata(
            title="Test Document",
            source_format="pdf",
            page_count=5
        )
        
        assert metadata.title == "Test Document"
        assert metadata.source_format == "pdf"
        assert metadata.page_count == 5
        assert metadata.author is None

    def test_full_metadata(self):
        """Test creating metadata with all fields."""
        now = datetime.now()
        metadata = DocumentMetadata(
            title="Complete Document",
            author="John Doe",
            creation_date=now,
            modification_date=now,
            page_count=10,
            source_format="docx",
            file_size_bytes=1024,
            language="en",
            extra={"custom_field": "value"}
        )
        
        assert metadata.title == "Complete Document"
        assert metadata.author == "John Doe"
        assert metadata.page_count == 10
        assert metadata.source_format == "docx"
        assert metadata.extra["custom_field"] == "value"

    def test_metadata_serialization(self):
        """Test metadata can be serialized."""
        metadata = DocumentMetadata(
            title="Test",
            source_format="html",
            page_count=1
        )
        
        data = metadata.model_dump()
        assert data["title"] == "Test"
        assert data["source_format"] == "html"


class TestCurationResult:
    """Tests for CurationResult model."""

    def test_basic_curation_result(self):
        """Test creating basic curation result."""
        metadata = DocumentMetadata(
            title="Test Doc",
            source_format="pdf"
        )
        
        result = CurationResult(
            doc_id="test.pdf",
            curated_text="# Test\n\nContent here",
            markdown_path=Path("output/markdowns/ns/test.pdf.md"),
            metadata=metadata,
            curation_backend="docling"
        )
        
        assert result.doc_id == "test.pdf"
        assert "# Test" in result.curated_text
        assert result.markdown_path.name == "test.pdf.md"
        assert result.metadata.source_format == "pdf"
        assert result.curation_backend == "docling"
        assert len(result.warnings) == 0

    def test_curation_result_with_warnings(self):
        """Test curation result with warnings."""
        metadata = DocumentMetadata(title="Test", source_format="html")
        
        result = CurationResult(
            doc_id="test.html",
            curated_text="# Test",
            markdown_path=Path("output/test.html.md"),
            metadata=metadata,
            curation_backend="docling",
            warnings=["Warning 1", "Warning 2"]
        )
        
        assert len(result.warnings) == 2
        assert "Warning 1" in result.warnings

    def test_to_dict(self):
        """Test converting curation result to dictionary."""
        metadata = DocumentMetadata(title="Test", source_format="pdf")
        
        result = CurationResult(
            doc_id="test.pdf",
            curated_text="Content",
            markdown_path=Path("output/test.pdf.md"),
            metadata=metadata,
            curation_backend="docling"
        )
        
        data = result.to_dict()
        
        assert data["doc_id"] == "test.pdf"
        assert data["curated_text"] == "Content"
        assert data["curation_backend"] == "docling"
        assert isinstance(data["markdown_path"], str)
        assert isinstance(data["metadata"], dict)
        assert isinstance(data["curated_at"], str)  # ISO format
