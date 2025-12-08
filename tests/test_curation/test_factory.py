"""Tests for curation backend factory."""

import pytest

# Check if Docling is available
docling_available = True
try:
    import docling
except ImportError:
    docling_available = False

from kg_forge.curation import (
    create_curation_backend,
    DoclingCurationBackend,
    HylandKECurationBackend,
    CurationBackendError
)


class TestCurationFactory:
    """Tests for curation backend factory."""

    @pytest.mark.skipif(not docling_available, reason="Docling not installed")
    def test_create_docling_backend(self):
        """Test creating Docling backend."""
        backend = create_curation_backend("docling")
        
        assert isinstance(backend, DoclingCurationBackend)
        assert backend.name == "docling"

    @pytest.mark.skipif(not docling_available, reason="Docling not installed")
    def test_create_docling_backend_case_insensitive(self):
        """Test backend name is case-insensitive."""
        backend = create_curation_backend("DOCLING")
        
        assert isinstance(backend, DoclingCurationBackend)

    def test_create_hyland_backend(self):
        """Test creating Hyland KE backend."""
        backend = create_curation_backend(
            "hyland_ke",
            hyland_client_id="test-client-id",
            hyland_client_secret="test-secret"
        )
        
        assert isinstance(backend, HylandKECurationBackend)
        assert backend.name == "hyland_ke"
    
    def test_create_hyland_backend_with_custom_urls(self):
        """Test creating Hyland KE backend with custom URLs."""
        backend = create_curation_backend(
            "hyland_ke",
            hyland_client_id="test-id",
            hyland_client_secret="test-secret",
            hyland_api_url="https://custom.api.url",
            hyland_oauth_url="https://custom.oauth.url"
        )
        
        assert isinstance(backend, HylandKECurationBackend)
        assert backend._api_url == "https://custom.api.url"
        assert backend._oauth_url == "https://custom.oauth.url"
    
    def test_create_hyland_backend_missing_credentials(self):
        """Test creating Hyland KE backend without credentials raises error."""
        with pytest.raises(CurationBackendError, match="requires OAuth client credentials"):
            create_curation_backend("hyland_ke")

    def test_invalid_backend_name(self):
        """Test invalid backend name raises error."""
        with pytest.raises(CurationBackendError) as exc_info:
            create_curation_backend("invalid_backend")
        
        assert "Unknown curation backend" in str(exc_info.value)
        assert "invalid_backend" in str(exc_info.value)

    @pytest.mark.skipif(not docling_available, reason="Docling not installed")
    def test_default_backend(self):
        """Test default backend is docling."""
        backend = create_curation_backend()
        
        assert isinstance(backend, DoclingCurationBackend)


@pytest.mark.skipif(not docling_available, reason="Docling not installed")
class TestDoclingBackend:
    """Tests for Docling backend."""

    def test_backend_name(self):
        """Test backend name property."""
        backend = DoclingCurationBackend()
        assert backend.name == "docling"

    def test_supports_html(self):
        """Test HTML format support."""
        backend = DoclingCurationBackend()
        
        assert backend.supports_format(".html")
        assert backend.supports_format(".htm")
        assert backend.supports_format(".HTML")  # Case insensitive

    def test_supports_pdf(self):
        """Test PDF format support."""
        backend = DoclingCurationBackend()
        
        assert backend.supports_format(".pdf")
        assert backend.supports_format(".PDF")

    def test_supports_office_formats(self):
        """Test Office format support."""
        backend = DoclingCurationBackend()
        
        assert backend.supports_format(".docx")
        assert backend.supports_format(".pptx")

    def test_unsupported_format(self):
        """Test unsupported format detection."""
        backend = DoclingCurationBackend()
        
        assert not backend.supports_format(".txt")
        assert not backend.supports_format(".json")
        assert not backend.supports_format(".unknown")


class TestHylandBackend:
    """Tests for Hyland KE backend."""

    def test_backend_name(self):
        """Test backend name property."""
        backend = HylandKECurationBackend(
            client_id="test-client-id",
            client_secret="test-client-secret"
        )
        assert backend.name == "hyland_ke"

    def test_supports_formats(self):
        """Test format support."""
        backend = HylandKECurationBackend(
            client_id="test-client-id",
            client_secret="test-client-secret"
        )
        
        assert backend.supports_format(".html")
        assert backend.supports_format(".pdf")
        assert backend.supports_format(".docx")
        assert backend.supports_format(".txt")

    def test_requires_credentials(self):
        """Test that backend requires OAuth credentials."""
        from kg_forge.curation.errors import CurationBackendError
        
        # Should raise error without credentials
        with pytest.raises(CurationBackendError) as exc_info:
            HylandKECurationBackend()
        
        assert "OAuth client credentials" in str(exc_info.value)

