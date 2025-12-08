"""Hyland Knowledge Extraction API-based curation backend."""

import base64
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from kg_forge.curation.base import CurationBackend
from kg_forge.curation.errors import CurationBackendError, CurationError
from kg_forge.models.curation import CurationResult, DocumentChunk, DocumentMetadata

logger = logging.getLogger(__name__)


class HylandKECurationBackend:
    """
    Document curation backend using Hyland Knowledge Enrichment Data Curation API.
    
    This backend uses Hyland's cloud-based curation service which provides:
    - Multi-format document processing (HTML, PDF, DOCX, PPTX, etc.)
    - Markdown conversion with structure preservation
    - Optional text chunking, embeddings, and PII detection
    - OAuth 2.0 authentication with client credentials flow
    
    Reference: https://hyland.github.io/ContentIntelligence-Docs/KnowledgeEnrichment/Reference/DataCurationAPI/
    """

    SUPPORTED_FORMATS = {'.html', '.htm', '.pdf', '.docx', '.pptx', '.txt', '.xml'}
    
    # Default API endpoints
    DEFAULT_API_URL = "https://knowledge-enrichment.ai.experience.hyland.com/latest/api/data-curation"
    DEFAULT_OAUTH_URL = "https://auth.iam.experience.hyland.com/idp"
    
    # Polling configuration
    DEFAULT_POLL_INTERVAL_SECONDS = 2
    DEFAULT_MAX_POLL_ATTEMPTS = 60  # 2 minutes max wait
    
    def __init__(
        self, 
        client_id: str = None,
        client_secret: str = None,
        api_url: str = None,
        oauth_url: str = None,
        curation_options: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Hyland KE backend.
        
        Args:
            client_id: OAuth client ID (required)
            client_secret: OAuth client secret (required)
            api_url: Data Curation API base URL (optional, uses default if not provided)
            oauth_url: OAuth token endpoint base URL (optional, uses default if not provided)
            curation_options: Curation options dict (normalization, chunking, etc.)
                Default: {"normalization": {"quotations": True, "dashes": True}, "chunking": False}
        
        Raises:
            CurationBackendError: If client credentials are missing
        """
        self._backend_name = "hyland_ke"
        
        # Validate credentials
        if not client_id or not client_secret:
            raise CurationBackendError(
                "Hyland KE backend requires OAuth client credentials. "
                "Set client_id and client_secret parameters."
            )
        
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_url = api_url or self.DEFAULT_API_URL
        self._oauth_url = oauth_url or self.DEFAULT_OAUTH_URL
        
        # Default curation options (no chunking, basic normalization)
        self._curation_options = curation_options or {
            "normalization": {
                "quotations": True,  # Normalize quotation marks
                "dashes": True       # Normalize dashes
            },
            "chunking": False,       # Disable chunking (we want full document)
            "embedding": False,      # Disable embeddings
            "json_schema": False,    # Disable JSON schema output
            "pii": False            # Disable PII detection
        }
        
        # Access token cache
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

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
    
    # OAuth 2.0 Authentication Methods
    
    def _get_access_token(self) -> str:
        """
        Get OAuth access token using client credentials flow.
        Uses cached token if valid, otherwise requests new token.
        
        Returns:
            Valid access token
            
        Raises:
            CurationBackendError: If token request fails
        """
        # Check if cached token is still valid (30 second buffer)
        if self._access_token and self._token_expiry:
            time_until_expiry = self._token_expiry - datetime.now().timestamp()
            if time_until_expiry > 30:
                logger.debug(f"Using cached access token (expires in {time_until_expiry:.0f}s)")
                return self._access_token
        
        # Request new access token
        logger.info("Requesting new OAuth access token from Hyland")
        
        token_url = f"{self._oauth_url}/connect/token"
        
        # Basic auth header: base64(client_id:client_secret)
        credentials = f"{self._client_id}:{self._client_secret}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        body = {
            "grant_type": "client_credentials",
            "scope": "environment_authorization"
        }
        
        form_data = urlencode(body).encode()
        
        try:
            request = Request(url=token_url, data=form_data, headers=headers, method="POST")
            response = urlopen(request)
            response_body = json.loads(response.read().decode())
            response.close()
            
            access_token = response_body.get("access_token")
            expires_in = response_body.get("expires_in", 3600)  # Default 1 hour
            
            if not access_token:
                raise CurationBackendError("No access_token in OAuth response")
            
            # Cache token with expiry
            self._access_token = access_token
            self._token_expiry = datetime.now().timestamp() + expires_in
            
            logger.info(f"Obtained new access token (expires in {expires_in}s)")
            return access_token
            
        except HTTPError as e:
            error_body = e.read().decode()
            raise CurationBackendError(
                f"OAuth token request failed: {e.code} - {error_body}",
                original_error=e
            )
        except Exception as e:
            raise CurationBackendError(
                "Failed to obtain OAuth access token",
                original_error=e
            )
    
    # API Request Methods
    
    def _get_presign_url(self, access_token: str, curation_options: Dict[str, Any]) -> Dict[str, str]:
        """
        Request presigned URLs for file upload and result download.
        
        Args:
            access_token: Valid OAuth access token
            curation_options: Curation options including optional chunking config
            
        Returns:
            Dict with job_id, put_url, get_url
            
        Raises:
            CurationBackendError: If presign request fails
        """
        presign_url = f"{self._api_url}/presign"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-type": "application/json"
        }
        
        # Send curation options in presign request
        request_data = json.dumps(curation_options).encode()
        
        try:
            request = Request(url=presign_url, data=request_data, headers=headers, method="POST")
            response = urlopen(request)
            response_body = json.loads(response.read().decode())
            response.close()
            
            job_id = response_body.get("job_id")
            put_url = response_body.get("put_url")
            get_url = response_body.get("get_url")
            
            if not all([job_id, put_url, get_url]):
                raise CurationBackendError(
                    f"Incomplete presign response: {response_body}"
                )
            
            logger.debug(f"Obtained presign URLs for job: {job_id}")
            return {
                "job_id": job_id,
                "put_url": put_url,
                "get_url": get_url
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            raise CurationBackendError(
                f"Presign request failed: {e.code} - {error_body}",
                original_error=e
            )
        except Exception as e:
            raise CurationBackendError(
                "Failed to get presign URL",
                original_error=e
            )
    
    def _upload_file(self, put_url: str, file_path: Path) -> None:
        """
        Upload file to presigned URL.
        
        Args:
            put_url: Presigned PUT URL
            file_path: Path to file to upload
            
        Raises:
            CurationBackendError: If upload fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            headers = {
                'Content-type': 'application/octet-stream',
                'Content-length': str(len(file_bytes))
            }
            
            request = Request(url=put_url, data=file_bytes, headers=headers, method="PUT")
            response = urlopen(request)
            response.close()
            
            logger.debug(f"Uploaded file: {file_path.name} ({len(file_bytes)} bytes)")
            
        except Exception as e:
            raise CurationBackendError(
                f"File upload failed for {file_path.name}",
                doc_path=str(file_path),
                original_error=e
            )
    
    def _poll_job_status(
        self, 
        job_id: str, 
        access_token: str,
        max_attempts: int = None,
        poll_interval: float = None
    ) -> str:
        """
        Poll job status until completion or failure.
        
        Args:
            job_id: Curation job ID
            access_token: Valid OAuth access token
            max_attempts: Maximum polling attempts (default: 60)
            poll_interval: Seconds between polls (default: 2)
            
        Returns:
            Final job status ("Completed", "Failed", etc.)
            
        Raises:
            CurationBackendError: If polling fails or job fails
        """
        max_attempts = max_attempts or self.DEFAULT_MAX_POLL_ATTEMPTS
        poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL_SECONDS
        
        status_url = f"{self._api_url}/status/{job_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        for attempt in range(max_attempts):
            try:
                request = Request(url=status_url, headers=headers, method="GET")
                response = urlopen(request)
                response_body = json.loads(response.read().decode())
                response.close()
                
                status = response_body.get("status")
                
                logger.debug(f"Job {job_id} status: {status} (attempt {attempt + 1}/{max_attempts})")
                
                if status in ["Completed", "Done"]:
                    return status
                elif status == "Failed":
                    error_msg = response_body.get("error", "Unknown error")
                    raise CurationBackendError(
                        f"Hyland curation job failed: {error_msg}",
                        original_error=Exception(error_msg)
                    )
                elif status in ["Pending", "Processing", "InProgress", "Wait For Upload"]:
                    # Still processing, wait and retry
                    time.sleep(poll_interval)
                    continue
                else:
                    # Unknown status
                    logger.warning(f"Unknown job status: {status}")
                    time.sleep(poll_interval)
                    continue
                    
            except HTTPError as e:
                if e.code == 404:
                    # Job not found yet, wait and retry
                    time.sleep(poll_interval)
                    continue
                else:
                    error_body = e.read().decode()
                    raise CurationBackendError(
                        f"Status check failed: {e.code} - {error_body}",
                        original_error=e
                    )
            except Exception as e:
                raise CurationBackendError(
                    f"Failed to poll job status for {job_id}",
                    original_error=e
                )
        
        # Timeout
        raise CurationBackendError(
            f"Job {job_id} did not complete within {max_attempts * poll_interval} seconds"
        )
    
    def _download_results(self, get_url: str) -> Dict[str, Any]:
        """
        Download curation results from presigned GET URL.
        
        Args:
            get_url: Presigned GET URL
            
        Returns:
            Curation result dict with markdown and optional JSON
            
        Raises:
            CurationBackendError: If download fails
        """
        try:
            request = Request(url=get_url, method="GET")
            response = urlopen(request)
            response_body = json.loads(response.read().decode())
            response.close()
            
            logger.debug("Downloaded curation results")
            return response_body
            
        except Exception as e:
            raise CurationBackendError(
                "Failed to download curation results",
                original_error=e
            )
    
    # Main Curation Method

    # Main Curation Method

    def curate(
        self,
        source_path: Path,
        namespace: str,
        markdown_base_dir: Path,
        chunking_enabled: bool = False
    ) -> CurationResult:
        """
        Curate document using Hyland KE Data Curation API.
        
        Workflow:
        1. Get OAuth access token
        2. Request presigned URLs (with chunking options if enabled)
        3. Upload file to presigned PUT URL
        4. Poll job status until complete
        5. Download results from presigned GET URL
        6. Extract markdown and metadata
        7. If chunking enabled: Extract and save chunks
        8. Save markdown to file
        9. Return CurationResult
        
        Args:
            source_path: Path to source document
            namespace: Namespace for organizing output
            markdown_base_dir: Base directory for markdown output
            chunking_enabled: Whether to request document chunks from API
        
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
            raise CurationBackendError(
                f"Format '{file_ext}' not supported by Hyland KE. Supported: {self.SUPPORTED_FORMATS}",
                doc_path=str(source_path)
            )

        # Generate doc_id with extension
        doc_id = source_path.name
        
        warnings = []
        
        try:
            logger.info(f"Starting Hyland KE curation for: {source_path.name}")
            
            # Step 1: Get access token
            access_token = self._get_access_token()
            
            # Step 2: Prepare curation options with optional chunking
            curation_options = self._curation_options.copy()
            if chunking_enabled:
                # Simple boolean format (as per original API docs)
                curation_options["chunking"] = True
                # NOTE: Hyland API chunk_size is a "desired" size - actual chunks may be longer
                # to prevent breaking sentences/paragraphs. For GLiREL compatibility (512 token limit),
                # we request smaller chunks, but some may still exceed the limit and get truncated.
                # Recommended: 800 chars (~200 tokens average), but some chunks may reach 2000+ chars.
                curation_options["chunk_size"] = 800  # characters (desired, not guaranteed)
                logger.info("Chunking enabled with chunk_size=800 chars (desired, may be longer to preserve sentences)")
            
            # Step 3: Get presigned URLs
            presign_response = self._get_presign_url(access_token, curation_options)
            job_id = presign_response["job_id"]
            put_url = presign_response["put_url"]
            get_url = presign_response["get_url"]
            
            logger.info(f"Hyland job created: {job_id}")
            
            # Step 4: Upload file
            self._upload_file(put_url, source_path)
            
            # Step 5: Poll for completion
            logger.info(f"Waiting for Hyland job {job_id} to complete...")
            status = self._poll_job_status(job_id, access_token)
            logger.info(f"Hyland job {job_id} completed with status: {status}")
            
            # Step 6: Download results
            results = self._download_results(get_url)
            
            # Step 7: Extract markdown and metadata
            markdown_data = results.get("markdown", {})
            markdown_content = markdown_data.get("output", "")
            
            if not markdown_content or not markdown_content.strip():
                warnings.append("Hyland KE produced empty markdown content")
                markdown_content = f"# {source_path.name}\n\n*No content extracted*"
            
            # Extract metadata from results (Hyland doesn't provide as much metadata as Docling)
            metadata = self._extract_metadata(results, source_path, file_ext)
            
            # Step 8: Save markdown file
            markdown_path = self._save_markdown(
                markdown_content,
                doc_id,
                namespace,
                markdown_base_dir
            )
            
            # Step 9: Extract and save chunks if enabled
            chunks = None
            chunks_path = None
            if chunking_enabled:
                try:
                    chunks, chunks_path = self._extract_chunks(
                        results, 
                        doc_id, 
                        namespace, 
                        markdown_base_dir,
                        markdown_content
                    )
                    logger.info(f"Extracted {len(chunks)} chunks from Hyland KE results")
                except Exception as e:
                    logger.warning(f"Failed to extract chunks from Hyland KE results: {e}")
                    warnings.append(f"Chunk extraction failed: {str(e)}")
            
            # Step 10: Create curation result
            curation_result = CurationResult(
                doc_id=doc_id,
                curated_text=markdown_content,
                markdown_path=markdown_path,
                metadata=metadata,
                curation_backend=self.name,
                curated_at=datetime.now(),
                warnings=warnings,
                chunks=chunks,
                chunks_path=chunks_path
            )
            
            logger.info(f"Successfully curated document with Hyland KE: {doc_id}")
            return curation_result
            
        except Exception as e:
            if isinstance(e, (CurationBackendError, CurationError)):
                raise
            raise CurationBackendError(
                f"Hyland KE curation failed for {source_path.name}",
                doc_path=str(source_path),
                original_error=e
            )
    
    def _extract_metadata(
        self,
        hyland_results: Dict[str, Any],
        source_path: Path,
        file_ext: str
    ) -> DocumentMetadata:
        """
        Extract metadata from Hyland KE results.
        
        Note: Hyland KE API returns minimal metadata compared to Docling.
        We extract what's available and use defaults for the rest.
        
        Args:
            hyland_results: Hyland API response dict
            source_path: Original source file path
            file_ext: File extension
        
        Returns:
            DocumentMetadata instance
        """
        # Default title to filename without extension
        title = source_path.stem
        
        # Get file size
        file_size_bytes = source_path.stat().st_size if source_path.exists() else None
        
        # Hyland provides chunks/locations if chunking was enabled
        # For now, we don't extract page count from Hyland results
        page_count = None
        
        # Check if JSON schema was included
        extra = {}
        if hyland_results.get("json"):
            extra["has_json_schema"] = True
        
        markdown_data = hyland_results.get("markdown", {})
        if markdown_data.get("chunks"):
            extra["chunk_count"] = len(markdown_data["chunks"])
        
        return DocumentMetadata(
            title=title,
            author=None,  # Hyland doesn't extract author
            creation_date=None,  # Hyland doesn't extract dates
            modification_date=None,
            page_count=page_count,
            source_format=file_ext.lstrip('.'),
            file_size_bytes=file_size_bytes,
            language=None,  # Hyland doesn't detect language
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

    def _extract_chunks(
        self,
        hyland_results: Dict[str, Any],
        doc_id: str,
        namespace: str,
        markdown_base_dir: Path,
        markdown_content: str
    ) -> tuple[list[DocumentChunk], Path]:
        """
        Extract chunks from Hyland KE API results.
        
        Hyland KE API returns chunks when chunking is enabled in curation options.
        The chunks array is found at results["markdown"]["chunks"].
        
        Each chunk contains:
        - text: Chunk text content
        - metadata: Dict with page, section, paragraph_index, heading_level, etc.
        - location: Optional dict with start/end offsets
        
        Args:
            hyland_results: Hyland API response dict
            doc_id: Document ID with extension
            namespace: Namespace for organization
            markdown_base_dir: Base directory for markdown files
            markdown_content: Full markdown content (for offset calculation)
        
        Returns:
            Tuple of (chunks list, chunks_path)
        
        Raises:
            ValueError: If chunks not found in results or invalid format
        """
        markdown_data = hyland_results.get("markdown", {})
        api_chunks = markdown_data.get("chunks")
        
        logger.info(f"Chunk extraction: markdown_data keys={markdown_data.keys() if isinstance(markdown_data, dict) else type(markdown_data)}")
        logger.info(f"Chunk extraction: api_chunks type={type(api_chunks)}, count={len(api_chunks) if isinstance(api_chunks, list) else 'N/A'}")
        
        if not api_chunks:
            raise ValueError("No chunks found in Hyland KE results - chunking may not be enabled")
        
        if not isinstance(api_chunks, list):
            raise ValueError(f"Expected chunks to be a list, got {type(api_chunks)}")
        
        chunks = []
        current_offset = 0  # Track cumulative offset for string chunks
        
        for idx, api_chunk in enumerate(api_chunks):
            # Handle both string chunks and dict chunks
            if isinstance(api_chunk, str):
                chunk_text = api_chunk
                chunk_metadata = {}
            elif isinstance(api_chunk, dict):
                # Extract chunk text
                chunk_text = api_chunk.get("text", "")
                chunk_metadata = api_chunk.get("metadata", {})
            else:
                logger.warning(f"Skipping chunk at index {idx} - unexpected type {type(api_chunk)}")
                continue
            
            if not chunk_text or not chunk_text.strip():
                logger.warning(f"Skipping empty chunk at index {idx}")
                continue
            
            # Extract metadata (if dict chunk)
            page = chunk_metadata.get("page") if chunk_metadata else None
            section = chunk_metadata.get("section") if chunk_metadata else None
            heading_level = chunk_metadata.get("heading_level") if chunk_metadata else None
            paragraph_index = chunk_metadata.get("paragraph_index") if chunk_metadata else None
            
            # Extract or calculate offsets (only for dict chunks)
            start_offset = None
            end_offset = None
            
            if isinstance(api_chunk, dict):
                location = api_chunk.get("location", {})
                start_offset = location.get("start")
                end_offset = location.get("end")
            
            # If offsets not provided, try to find text in markdown
            if start_offset is None and chunk_text in markdown_content:
                start_offset = markdown_content.find(chunk_text)
                end_offset = start_offset + len(chunk_text) if start_offset != -1 else None
            
            # If still no offsets, use sequential offsets based on chunk order
            if start_offset is None:
                start_offset = current_offset
                end_offset = current_offset + len(chunk_text)
                current_offset = end_offset
            
            # Generate chunk_id: <doc_id>_chunk_<zero-padded-index>
            # e.g., "platform-overview.pdf_chunk_001"
            chunk_id = f"{doc_id}_chunk_{idx+1:03d}"
            
            # Build metadata dict (preserve all Hyland-specific metadata)
            metadata_dict = {
                "source": "hyland_ke",
                "chunk_index": idx
            }
            if heading_level is not None:
                metadata_dict["heading_level"] = heading_level
            if paragraph_index is not None:
                metadata_dict["paragraph_index"] = paragraph_index
            # Include any extra metadata from Hyland
            for key, value in chunk_metadata.items():
                if key not in ["page", "section", "heading_level", "paragraph_index"]:
                    metadata_dict[key] = value
            
            # Create DocumentChunk object
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                page=page,
                section=section,
                start_offset=start_offset,
                end_offset=end_offset,
                text=chunk_text,
                metadata=metadata_dict
            )
            chunks.append(chunk)
        
        logger.info(f"Extracted {len(chunks)} chunks from Hyland KE results")
        
        # Save chunks to JSON file
        namespace_dir = markdown_base_dir / namespace
        namespace_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = namespace_dir / f"{doc_id}.chunks.json"
        
        # Serialize chunks to JSON
        chunks_data = [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "page": c.page,
                "section": c.section,
                "start_offset": c.start_offset,
                "end_offset": c.end_offset,
                "text": c.text,
                "metadata": c.metadata
            }
            for c in chunks
        ]
        
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved {len(chunks)} chunks to: {chunks_path}")
        
        return chunks, chunks_path


