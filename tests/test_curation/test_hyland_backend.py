"""Tests for Hyland Knowledge Enrichment curation backend."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from urllib.error import HTTPError

from kg_forge.curation.hyland_backend import HylandKECurationBackend
from kg_forge.curation.errors import CurationBackendError
from kg_forge.models.curation import CurationResult, DocumentMetadata


class TestHylandKEBackendInitialization:
    """Test backend initialization."""
    
    def test_initialization_with_credentials(self):
        """Test successful initialization with credentials."""
        backend = HylandKECurationBackend(
            client_id="test-client-id",
            client_secret="test-secret"
        )
        
        assert backend.name == "hyland_ke"
        assert backend._client_id == "test-client-id"
        assert backend._client_secret == "test-secret"
        assert backend._api_url == HylandKECurationBackend.DEFAULT_API_URL
        assert backend._oauth_url == HylandKECurationBackend.DEFAULT_OAUTH_URL
    
    def test_initialization_without_credentials_raises_error(self):
        """Test initialization without credentials raises error."""
        with pytest.raises(CurationBackendError, match="requires OAuth client credentials"):
            HylandKECurationBackend()
        
        with pytest.raises(CurationBackendError, match="requires OAuth client credentials"):
            HylandKECurationBackend(client_id="id-only")
    
    def test_initialization_with_custom_urls(self):
        """Test initialization with custom API URLs."""
        backend = HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret",
            api_url="https://custom.api.url",
            oauth_url="https://custom.oauth.url"
        )
        
        assert backend._api_url == "https://custom.api.url"
        assert backend._oauth_url == "https://custom.oauth.url"
    
    def test_initialization_with_custom_curation_options(self):
        """Test initialization with custom curation options."""
        custom_options = {
            "chunking": True,
            "chunk_size": 2000,
            "embedding": True
        }
        
        backend = HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret",
            curation_options=custom_options
        )
        
        assert backend._curation_options == custom_options


class TestHylandKEFormatSupport:
    """Test format detection and support."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    def test_supports_html_formats(self, backend):
        """Test HTML format support."""
        assert backend.supports_format('.html')
        assert backend.supports_format('.htm')
        assert backend.supports_format('.HTML')  # Case insensitive
    
    def test_supports_document_formats(self, backend):
        """Test document format support."""
        assert backend.supports_format('.pdf')
        assert backend.supports_format('.docx')
        assert backend.supports_format('.pptx')
        assert backend.supports_format('.txt')
        assert backend.supports_format('.xml')
    
    def test_unsupported_formats(self, backend):
        """Test unsupported formats."""
        assert not backend.supports_format('.jpg')
        assert not backend.supports_format('.png')
        assert not backend.supports_format('.mp4')
        assert not backend.supports_format('.unknown')


class TestHylandKEOAuthAuthentication:
    """Test OAuth 2.0 authentication."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-client-id",
            client_secret="test-secret"
        )
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_get_access_token_success(self, mock_urlopen, backend):
        """Test successful access token retrieval."""
        # Mock successful OAuth response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "mock-access-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }).encode()
        mock_urlopen.return_value = mock_response
        
        token = backend._get_access_token()
        
        assert token == "mock-access-token"
        assert backend._access_token == "mock-access-token"
        assert backend._token_expiry is not None
        
        # Verify OAuth request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert "connect/token" in request.full_url
        assert request.headers.get('Authorization').startswith('Basic ')
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_get_access_token_uses_cache(self, mock_urlopen, backend):
        """Test that cached token is reused."""
        # Set up cached token
        backend._access_token = "cached-token"
        backend._token_expiry = datetime.now().timestamp() + 3600  # Valid for 1 hour
        
        token = backend._get_access_token()
        
        # Should return cached token without API call
        assert token == "cached-token"
        mock_urlopen.assert_not_called()
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_get_access_token_refreshes_expired(self, mock_urlopen, backend):
        """Test that expired token is refreshed."""
        # Set up expired token
        backend._access_token = "expired-token"
        backend._token_expiry = datetime.now().timestamp() - 100  # Expired
        
        # Mock new token response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "new-token",
            "expires_in": 3600
        }).encode()
        mock_urlopen.return_value = mock_response
        
        token = backend._get_access_token()
        
        # Should get new token
        assert token == "new-token"
        assert backend._access_token == "new-token"
        mock_urlopen.assert_called_once()
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_get_access_token_http_error(self, mock_urlopen, backend):
        """Test OAuth failure handling."""
        # Mock HTTP error
        mock_urlopen.side_effect = HTTPError(
            "url", 401, "Unauthorized", {}, None
        )
        mock_urlopen.side_effect.read = lambda: b"Invalid credentials"
        
        with pytest.raises(CurationBackendError, match="OAuth token request failed"):
            backend._get_access_token()


class TestHylandKEPresignURL:
    """Test presigned URL request."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_get_presign_url_success(self, mock_urlopen, backend):
        """Test successful presign URL request."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "job_id": "test-job-123",
            "put_url": "https://s3.amazonaws.com/upload-url",
            "get_url": "https://s3.amazonaws.com/download-url"
        }).encode()
        mock_urlopen.return_value = mock_response
        
        # Pass default curation options
        curation_options = {"output_formats": ["markdown"]}
        result = backend._get_presign_url("test-token", curation_options)
        
        assert result["job_id"] == "test-job-123"
        assert result["put_url"] == "https://s3.amazonaws.com/upload-url"
        assert result["get_url"] == "https://s3.amazonaws.com/download-url"
        
        # Verify request headers
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.headers.get('Authorization') == "Bearer test-token"
        assert request.headers.get('Content-type') == "application/json"
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_get_presign_url_incomplete_response(self, mock_urlopen, backend):
        """Test handling of incomplete presign response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "job_id": "test-job-123"
            # Missing put_url and get_url
        }).encode()
        mock_urlopen.return_value = mock_response
        
        # Pass default curation options
        curation_options = {"output_formats": ["markdown"]}
        with pytest.raises(CurationBackendError, match="Incomplete presign response"):
            backend._get_presign_url("test-token", curation_options)


class TestHylandKEFileUpload:
    """Test file upload functionality."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    @pytest.fixture
    def test_file(self, tmp_path):
        """Create a test file."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content here")
        return test_file
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_upload_file_success(self, mock_urlopen, backend, test_file):
        """Test successful file upload."""
        mock_response = MagicMock()
        mock_urlopen.return_value = mock_response
        
        backend._upload_file("https://s3.amazonaws.com/upload", test_file)
        
        # Verify upload request
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.method == "PUT"
        assert request.headers.get('Content-type') == 'application/octet-stream'
        assert 'Content-length' in request.headers
        assert int(request.headers.get('Content-length')) == len(b"PDF content here")
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_upload_file_nonexistent(self, mock_urlopen, backend):
        """Test upload of nonexistent file."""
        with pytest.raises(CurationBackendError, match="File upload failed"):
            backend._upload_file("https://url", Path("/nonexistent/file.pdf"))


class TestHylandKEJobStatusPolling:
    """Test job status polling."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    @patch('kg_forge.curation.hyland_backend.time.sleep')
    def test_poll_job_status_immediate_completion(self, mock_sleep, mock_urlopen, backend):
        """Test job that completes immediately."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "jobId": "test-job",
            "status": "Completed"
        }).encode()
        mock_urlopen.return_value = mock_response
        
        status = backend._poll_job_status("test-job", "test-token")
        
        assert status == "Completed"
        mock_sleep.assert_not_called()
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    @patch('kg_forge.curation.hyland_backend.time.sleep')
    def test_poll_job_status_with_waiting(self, mock_sleep, mock_urlopen, backend):
        """Test job that requires polling."""
        # First two calls: Pending/Processing, third call: Completed
        responses = [
            json.dumps({"jobId": "test-job", "status": "Pending"}).encode(),
            json.dumps({"jobId": "test-job", "status": "Processing"}).encode(),
            json.dumps({"jobId": "test-job", "status": "Completed"}).encode()
        ]
        
        mock_response = MagicMock()
        mock_response.read.side_effect = responses
        mock_urlopen.return_value = mock_response
        
        status = backend._poll_job_status("test-job", "test-token")
        
        assert status == "Completed"
        assert mock_sleep.call_count == 2  # Slept twice while waiting
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_poll_job_status_failed(self, mock_urlopen, backend):
        """Test job that fails."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "jobId": "test-job",
            "status": "Failed",
            "error": "Processing error"
        }).encode()
        mock_urlopen.return_value = mock_response
        
        with pytest.raises(CurationBackendError, match="curation job failed"):
            backend._poll_job_status("test-job", "test-token")
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    @patch('kg_forge.curation.hyland_backend.time.sleep')
    def test_poll_job_status_timeout(self, mock_sleep, mock_urlopen, backend):
        """Test polling timeout."""
        # Always return Pending status
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "jobId": "test-job",
            "status": "Pending"
        }).encode()
        mock_urlopen.return_value = mock_response
        
        with pytest.raises(CurationBackendError, match="did not complete within"):
            backend._poll_job_status("test-job", "test-token", max_attempts=3)


class TestHylandKEResultsDownload:
    """Test results download."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_download_results_success(self, mock_urlopen, backend):
        """Test successful results download."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "markdown": {
                "output": "# Test Document\n\nContent here",
                "locations": ["location1"]
            }
        }).encode()
        mock_urlopen.return_value = mock_response
        
        results = backend._download_results("https://s3.amazonaws.com/results")
        
        assert "markdown" in results
        assert results["markdown"]["output"] == "# Test Document\n\nContent here"


class TestHylandKEMetadataExtraction:
    """Test metadata extraction."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    def test_extract_metadata_basic(self, backend, tmp_path):
        """Test basic metadata extraction."""
        test_file = tmp_path / "test_document.pdf"
        test_file.write_bytes(b"PDF content")
        
        hyland_results = {
            "markdown": {
                "output": "# Content"
            }
        }
        
        metadata = backend._extract_metadata(hyland_results, test_file, ".pdf")
        
        assert metadata.title == "test_document"
        assert metadata.source_format == "pdf"
        assert metadata.file_size_bytes == len(b"PDF content")
        assert metadata.author is None  # Hyland doesn't provide
        assert metadata.page_count is None
    
    def test_extract_metadata_with_chunks(self, backend, tmp_path):
        """Test metadata extraction with chunks."""
        test_file = tmp_path / "test.html"
        test_file.write_text("HTML content")
        
        hyland_results = {
            "markdown": {
                "output": "# Content",
                "chunks": ["chunk1", "chunk2", "chunk3"]
            }
        }
        
        metadata = backend._extract_metadata(hyland_results, test_file, ".html")
        
        assert metadata.extra.get("chunk_count") == 3


class TestHylandKEEndToEnd:
    """Test end-to-end curation workflow."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    @pytest.fixture
    def test_file(self, tmp_path):
        """Create a test file."""
        test_file = tmp_path / "document.pdf"
        test_file.write_bytes(b"PDF content for testing")
        return test_file
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    @patch('kg_forge.curation.hyland_backend.time.sleep')
    def test_curate_success(self, mock_sleep, mock_urlopen, backend, test_file, tmp_path):
        """Test successful end-to-end curation."""
        # Create separate mock response objects for each API call
        oauth_response = MagicMock()
        oauth_response.read.return_value = json.dumps({
            "access_token": "test-token",
            "expires_in": 3600
        }).encode()
        
        presign_response = MagicMock()
        presign_response.read.return_value = json.dumps({
            "job_id": "job-123",
            "put_url": "https://s3.amazonaws.com/upload",
            "get_url": "https://s3.amazonaws.com/download"
        }).encode()
        
        upload_response = MagicMock()
        
        status_response = MagicMock()
        status_response.read.return_value = json.dumps({
            "jobId": "job-123",
            "status": "Completed"
        }).encode()
        
        results_response = MagicMock()
        results_response.read.return_value = json.dumps({
            "markdown": {
                "output": "# Test Document\n\nThis is curated content.",
                "locations": ["loc1"]
            }
        }).encode()
        
        # Set side_effect to return different responses for each call
        mock_urlopen.side_effect = [
            oauth_response,
            presign_response,
            upload_response,
            status_response,
            results_response
        ]
        
        markdown_dir = tmp_path / "markdowns"
        result = backend.curate(
            source_path=test_file,
            namespace="test",
            markdown_base_dir=markdown_dir
        )
        
        # Verify result
        assert isinstance(result, CurationResult)
        assert result.doc_id == "document.pdf"
        assert result.curated_text == "# Test Document\n\nThis is curated content."
        assert result.curation_backend == "hyland_ke"
        assert result.metadata.source_format == "pdf"
        
        # Verify markdown file was saved
        expected_path = markdown_dir / "test" / "document.pdf.md"
        assert result.markdown_path == expected_path
        assert expected_path.exists()
        assert expected_path.read_text() == "# Test Document\n\nThis is curated content."
    
    def test_curate_nonexistent_file(self, backend, tmp_path):
        """Test curating nonexistent file."""
        with pytest.raises(CurationBackendError, match="does not exist"):
            backend.curate(
                source_path=Path("/nonexistent/file.pdf"),
                namespace="test",
                markdown_base_dir=tmp_path
            )
    
    def test_curate_unsupported_format(self, backend, tmp_path):
        """Test curating unsupported file format."""
        test_file = tmp_path / "image.jpg"
        test_file.write_bytes(b"JPEG data")
        
        with pytest.raises(CurationBackendError, match="not supported"):
            backend.curate(
                source_path=test_file,
                namespace="test",
                markdown_base_dir=tmp_path
            )
    
    @patch('kg_forge.curation.hyland_backend.urlopen')
    def test_curate_empty_markdown(self, mock_urlopen, backend, test_file, tmp_path):
        """Test handling of empty markdown response."""
        # Create separate mock response objects
        oauth_response = MagicMock()
        oauth_response.read.return_value = json.dumps({
            "access_token": "token",
            "expires_in": 3600
        }).encode()
        
        presign_response = MagicMock()
        presign_response.read.return_value = json.dumps({
            "job_id": "job-123",
            "put_url": "https://upload",
            "get_url": "https://download"
        }).encode()
        
        upload_response = MagicMock()
        
        status_response = MagicMock()
        status_response.read.return_value = json.dumps({
            "jobId": "job-123",
            "status": "Completed"
        }).encode()
        
        results_response = MagicMock()
        results_response.read.return_value = json.dumps({
            "markdown": {
                "output": "",
                "locations": []
            }
        }).encode()
        
        mock_urlopen.side_effect = [
            oauth_response,
            presign_response,
            upload_response,
            status_response,
            results_response
        ]
        
        result = backend.curate(
            source_path=test_file,
            namespace="test",
            markdown_base_dir=tmp_path
        )
        
        # Should have warning about empty content
        assert len(result.warnings) > 0
        assert "empty markdown" in result.warnings[0].lower()
        # Should create fallback content
        assert "No content extracted" in result.curated_text


class TestHylandKESaveMarkdown:
    """Test markdown saving functionality."""
    
    @pytest.fixture
    def backend(self):
        """Create backend for testing."""
        return HylandKECurationBackend(
            client_id="test-id",
            client_secret="test-secret"
        )
    
    def test_save_markdown_creates_namespace_directory(self, backend, tmp_path):
        """Test that namespace directory is created."""
        markdown_path = backend._save_markdown(
            markdown_content="# Test",
            doc_id="test.pdf",
            namespace="my_namespace",
            markdown_base_dir=tmp_path
        )
        
        expected_dir = tmp_path / "my_namespace"
        assert expected_dir.exists()
        assert expected_dir.is_dir()
        assert markdown_path == expected_dir / "test.pdf.md"
    
    def test_save_markdown_content(self, backend, tmp_path):
        """Test that markdown content is saved correctly."""
        content = "# Test Document\n\nThis is test content."
        
        markdown_path = backend._save_markdown(
            markdown_content=content,
            doc_id="doc.html",
            namespace="test",
            markdown_base_dir=tmp_path
        )
        
        assert markdown_path.exists()
        assert markdown_path.read_text(encoding='utf-8') == content
    
    def test_save_markdown_with_nested_namespace(self, backend, tmp_path):
        """Test saving with nested namespace path."""
        markdown_path = backend._save_markdown(
            markdown_content="# Test",
            doc_id="file.docx",
            namespace="project/subproject",
            markdown_base_dir=tmp_path
        )
        
        expected_path = tmp_path / "project/subproject" / "file.docx.md"
        assert markdown_path == expected_path
        assert markdown_path.exists()
