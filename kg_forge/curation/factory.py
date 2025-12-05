"""Factory function for creating curation backends."""

import logging
from typing import Optional

from kg_forge.curation.base import CurationBackend
from kg_forge.curation.docling_backend import DoclingCurationBackend
from kg_forge.curation.hyland_backend import HylandKECurationBackend
from kg_forge.curation.errors import CurationBackendError

logger = logging.getLogger(__name__)


def create_curation_backend(
    backend_name: str = "docling",
    hyland_client_id: Optional[str] = None,
    hyland_client_secret: Optional[str] = None,
    hyland_api_url: Optional[str] = None,
    hyland_oauth_url: Optional[str] = None,
    hyland_curation_options: Optional[dict] = None
) -> CurationBackend:
    """
    Factory function to create a curation backend.
    
    Args:
        backend_name: Backend to use ('docling' or 'hylandKE')
        hyland_client_id: Hyland OAuth client ID (only for hylandKE backend)
        hyland_client_secret: Hyland OAuth client secret (only for hylandKE backend)
        hyland_api_url: Hyland Data Curation API URL (optional, uses default)
        hyland_oauth_url: Hyland OAuth URL (optional, uses default)
        hyland_curation_options: Hyland curation options dict (optional)
    
    Returns:
        CurationBackend instance
    
    Raises:
        CurationBackendError: If backend name is invalid or initialization fails
    
    Examples:
        >>> backend = create_curation_backend("docling")
        >>> backend = create_curation_backend(
        ...     "hylandKE",
        ...     hyland_client_id="my-client-id",
        ...     hyland_client_secret="my-secret"
        ... )
    """
    backend_name = backend_name.lower()
    
    if backend_name == "docling":
        try:
            return DoclingCurationBackend()
        except Exception as e:
            raise CurationBackendError(
                f"Failed to initialize Docling backend",
                original_error=e
            )
    
    elif backend_name == "hylandke":
        try:
            return HylandKECurationBackend(
                client_id=hyland_client_id,
                client_secret=hyland_client_secret,
                api_url=hyland_api_url,
                oauth_url=hyland_oauth_url,
                curation_options=hyland_curation_options
            )
        except Exception as e:
            raise CurationBackendError(
                f"Failed to initialize Hyland KE backend",
                original_error=e
            )
    
    else:
        raise CurationBackendError(
            f"Unknown curation backend: '{backend_name}'. "
            f"Supported backends: 'docling', 'hylandKE'"
        )
