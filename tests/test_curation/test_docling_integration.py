"""Integration tests for Docling curation backend.

These tests require Docling to be installed.
They will be skipped if Docling is not available.
"""

import pytest
from pathlib import Path

# Try to import Docling - skip tests if not available
docling_available = True
try:
    import docling
except ImportError:
    docling_available = False

from kg_forge.curation import DoclingCurationBackend, CurationBackendError, UnsupportedFormatError
from kg_forge.models.curation import CurationResult


@pytest.fixture
def test_html_file():
    """Path to test HTML file."""
    return Path(__file__).parent / "test_data" / "simple_test.html"


@pytest.fixture
def markdown_output_dir(tmp_path):
    """Temporary directory for markdown output."""
    return tmp_path / "markdowns"


@pytest.mark.skipif(not docling_available, reason="Docling not installed")
class TestDoclingIntegration:
    """Integration tests for Docling backend."""

    def test_curate_html_file(self, test_html_file, markdown_output_dir):
        """Test curating an HTML file."""
        backend = DoclingCurationBackend()
        
        result = backend.curate(
            source_path=test_html_file,
            namespace="test-namespace",
            markdown_base_dir=markdown_output_dir
        )
        
        # Verify result structure
        assert isinstance(result, CurationResult)
        assert result.doc_id == "simple_test.html"
        assert result.curation_backend == "docling"
        assert len(result.curated_text) > 0
        
        # Verify markdown was saved
        assert result.markdown_path.exists()
        assert result.markdown_path.parent.name == "test-namespace"
        
        # Verify markdown content
        markdown_content = result.markdown_path.read_text(encoding='utf-8')
        assert len(markdown_content) > 0
        assert markdown_content == result.curated_text
        
        # Verify metadata
        assert result.metadata.source_format == "html"
        assert result.metadata.file_size_bytes > 0

    def test_curate_nonexistent_file(self, markdown_output_dir):
        """Test curating a file that doesn't exist."""
        backend = DoclingCurationBackend()
        
        with pytest.raises(CurationBackendError) as exc_info:
            backend.curate(
                source_path=Path("nonexistent.html"),
                namespace="test",
                markdown_base_dir=markdown_output_dir
            )
        
        assert "does not exist" in str(exc_info.value)

    def test_curate_unsupported_format(self, tmp_path, markdown_output_dir):
        """Test curating an unsupported file format."""
        # Create a .txt file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Some text content")
        
        backend = DoclingCurationBackend()
        
        with pytest.raises(UnsupportedFormatError) as exc_info:
            backend.curate(
                source_path=txt_file,
                namespace="test",
                markdown_base_dir=markdown_output_dir
            )
        
        assert "not supported" in str(exc_info.value)
        assert ".txt" in str(exc_info.value)

    def test_markdown_organization_by_namespace(self, test_html_file, markdown_output_dir):
        """Test that markdown files are organized by namespace."""
        backend = DoclingCurationBackend()
        
        # Curate with namespace "project-a"
        result1 = backend.curate(
            source_path=test_html_file,
            namespace="project-a",
            markdown_base_dir=markdown_output_dir
        )
        
        # Verify namespace directory structure
        expected_path = markdown_output_dir / "project-a" / "simple_test.html.md"
        assert result1.markdown_path == expected_path
        assert result1.markdown_path.exists()

    def test_doc_id_includes_extension(self, test_html_file, markdown_output_dir):
        """Test that doc_id includes file extension."""
        backend = DoclingCurationBackend()
        
        result = backend.curate(
            source_path=test_html_file,
            namespace="test",
            markdown_base_dir=markdown_output_dir
        )
        
        # doc_id should be filename WITH extension
        assert result.doc_id == "simple_test.html"
        assert result.doc_id.endswith(".html")


@pytest.mark.skipif(docling_available, reason="Test for missing Docling")
class TestDoclingMissingDependency:
    """Tests for when Docling is not installed."""

    def test_backend_initialization_fails_without_docling(self):
        """Test that backend initialization fails gracefully without Docling."""
        with pytest.raises(CurationBackendError) as exc_info:
            DoclingCurationBackend()
        
        assert "not installed" in str(exc_info.value).lower()
        assert "docling" in str(exc_info.value).lower()
