"""Tests for DocumentLoader."""

from pathlib import Path

import pytest

from kg_forge.parsers.document_loader import DocumentLoader
from kg_forge.parsers.html_parser import ConfluenceHTMLParser
from kg_forge.models.document import ParsedDocument


@pytest.fixture
def loader():
    """Create loader instance."""
    return DocumentLoader()


@pytest.fixture
def test_data_dir():
    """Get test data directory path."""
    return Path(__file__).parent.parent.parent / "test_docs"


def test_loader_initialization():
    """Test loader initialization."""
    loader = DocumentLoader()
    assert isinstance(loader.parser, ConfluenceHTMLParser)

    # Test with custom parser
    custom_parser =ConfluenceHTMLParser()
    loader = DocumentLoader(parser=custom_parser)
    assert loader.parser is custom_parser


def test_load_from_directory_not_found(loader):
    """Test loading from non-existent directory raises error."""
    with pytest.raises(FileNotFoundError):
        loader.load_from_directory(Path("/nonexistent/directory"))


def test_load_from_directory_not_a_directory(loader, tmp_path):
    """Test loading from file (not directory) raises error."""
    # Create a temporary file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    with pytest.raises(ValueError):
        loader.load_from_directory(test_file)


def test_load_from_directory_no_html_files(loader, tmp_path):
    """Test loading from directory with no HTML files raises error."""
    with pytest.raises(ValueError, match="No files matching"):
        loader.load_from_directory(tmp_path)


def test_load_from_test_directory(loader, test_data_dir):
    """Test loading from test_data directory."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory not found")

    documents = loader.load_from_directory(test_data_dir)

    # Should have loaded all test files
    assert len(documents) > 0
    assert all(isinstance(doc, ParsedDocument) for doc in documents)

    # Verify each document has required fields
    for doc in documents:
        assert len(doc.doc_id) > 0
        assert len(doc.title) > 0
        assert len(doc.source_file) > 0
        assert len(doc.content_hash) == 64  # SHA-256 hash


def test_load_specific_files(loader, test_data_dir):
    """Test loading specific files."""
    if not test_data_dir.exists():
        pytest.skip("Test data directory not found")

    # Get list of HTML files
    html_files = list(test_data_dir.glob("*.html"))

    if not html_files:
        pytest.skip("No HTML files in test data")

    # Load just the first file
    documents = loader.load_files([html_files[0]])

    assert len(documents) == 1
    assert isinstance(documents[0], ParsedDocument)
    assert documents[0].source_file == html_files[0].name


def test_load_handles_errors_gracefully(loader, tmp_path):
    """Test that loader continues on parse errors."""
    # Create a valid HTML file
    valid_html = tmp_path / "valid_123.html"
    valid_html.write_text("""
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
    <h1 id="title-heading"><span id="title-text">Test Title</span></h1>
    <div id="main-content"><p>Test content</p></div>
    </body>
    </html>
    """)

    # Create an invalid HTML file (empty)
    invalid_html = tmp_path / "invalid_456.html"
    invalid_html.write_text("")

    # Load should succeed for valid file, skip invalid
    documents = loader.load_from_directory(tmp_path)

    # Should have loaded at least the valid file
    assert len(documents) >= 1
    assert any(doc.doc_id == "123" for doc in documents)
