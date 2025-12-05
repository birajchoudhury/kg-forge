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
    hyland_endpoint: Optional[str] = None,
    hyland_api_key: Optional[str] = None
) -> CurationBackend:
    """
    Factory function to create a curation backend.
    
    Args:
        backend_name: Backend to use ('docling' or 'hyland_ke'/'hylandKE')
        hyland_endpoint: Hyland KE API endpoint (only for hyland_ke backend)
        hyland_api_key: Hyland KE API key (only for hyland_ke backend)
    
    Returns:
        CurationBackend instance
    
    Raises:
        CurationBackendError: If backend name is invalid or initialization fails
    
    Examples:
        >>> backend = create_curation_backend("docling")
        >>> backend = create_curation_backend("hyland_ke", 
        ...     hyland_endpoint="https://api.hyland.com/ke",
        ...     hyland_api_key="secret-key")
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
                api_endpoint=hyland_endpoint,
                api_key=hyland_api_key
            )
        except Exception as e:
            raise CurationBackendError(
                f"Failed to initialize Hyland KE backend",
                original_error=e
            )
    
    else:
        raise CurationBackendError(
            f"Unknown curation backend: '{backend_name}'. "
            f"Supported backends: 'docling', 'hyland_ke'"
        )
