"""Tests for curation exceptions."""

import pytest

from kg_forge.curation.errors import (
    CurationError,
    UnsupportedFormatError,
    CurationBackendError,
    FormatDetectionError
)


class TestCurationExceptions:
    """Tests for curation exception classes."""

    def test_basic_curation_error(self):
        """Test basic CurationError."""
        error = CurationError("Something went wrong")
        
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.doc_path is None
        assert error.original_error is None

    def test_curation_error_with_doc_path(self):
        """Test CurationError with document path."""
        error = CurationError("Failed to process", doc_path="/path/to/doc.pdf")
        
        assert "Failed to process" in str(error)
        assert "/path/to/doc.pdf" in str(error)
        assert error.doc_path == "/path/to/doc.pdf"

    def test_curation_error_with_original_error(self):
        """Test CurationError with original exception."""
        original = ValueError("Original problem")
        error = CurationError("Wrapper error", original_error=original)
        
        assert "Wrapper error" in str(error)
        assert "Original problem" in str(error)
        assert error.original_error == original

    def test_curation_error_all_params(self):
        """Test CurationError with all parameters."""
        original = IOError("File not found")
        error = CurationError(
            "Failed to read document",
            doc_path="/docs/test.pdf",
            original_error=original
        )
        
        error_str = str(error)
        assert "Failed to read document" in error_str
        assert "/docs/test.pdf" in error_str
        assert "File not found" in error_str

    def test_unsupported_format_error(self):
        """Test UnsupportedFormatError inherits from CurationError."""
        error = UnsupportedFormatError(
            "Format .xyz not supported",
            doc_path="file.xyz"
        )
        
        assert isinstance(error, CurationError)
        assert "Format .xyz not supported" in str(error)
        assert "file.xyz" in str(error)

    def test_curation_backend_error(self):
        """Test CurationBackendError inherits from CurationError."""
        error = CurationBackendError(
            "Backend initialization failed",
            original_error=ImportError("Module not found")
        )
        
        assert isinstance(error, CurationError)
        assert "Backend initialization failed" in str(error)
        assert "Module not found" in str(error)

    def test_format_detection_error(self):
        """Test FormatDetectionError inherits from CurationError."""
        error = FormatDetectionError(
            "Could not detect format",
            doc_path="/path/unknown"
        )
        
        assert isinstance(error, CurationError)
        assert "Could not detect format" in str(error)

    def test_exception_can_be_raised_and_caught(self):
        """Test exceptions can be raised and caught properly."""
        with pytest.raises(CurationError):
            raise CurationError("Test error")

        with pytest.raises(UnsupportedFormatError):
            raise UnsupportedFormatError("Bad format")

        with pytest.raises(CurationBackendError):
            raise CurationBackendError("Backend failed")

    def test_catch_specific_exception(self):
        """Test catching specific exception type."""
        try:
            raise UnsupportedFormatError("Bad format", doc_path="test.xyz")
        except UnsupportedFormatError as e:
            assert e.doc_path == "test.xyz"
        except CurationError:
            pytest.fail("Should have caught UnsupportedFormatError specifically")
