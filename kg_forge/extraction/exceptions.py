"""
Extraction-specific exceptions.

Defines error types that can be raised during entity and relation extraction.
"""


class ExtractionError(Exception):
    """Base exception for all extraction-related errors."""
    pass


class BackendNotAvailableError(ExtractionError):
    """Raised when an extraction backend is not available or not configured."""
    pass


class ModelLoadingError(ExtractionError):
    """Raised when extraction models fail to load."""
    pass


class ExtractionTimeoutError(ExtractionError):
    """Raised when extraction takes too long."""
    pass


class ParseError(ExtractionError):
    """Raised when extraction output cannot be parsed."""
    pass


class ValidationError(ExtractionError):
    """Raised when extraction output fails validation."""
    pass


class ConsecutiveFailureError(ExtractionError):
    """Raised when too many consecutive extraction failures occur."""
    
    def __init__(self, failure_count: int, threshold: int, message: str = None):
        self.failure_count = failure_count
        self.threshold = threshold
        if message is None:
            message = f"Consecutive failure threshold exceeded: {failure_count} >= {threshold}"
        super().__init__(message)


class ConfigurationError(ExtractionError):
    """Raised when extraction backend configuration is invalid."""
    pass


class CredentialsError(ExtractionError):
    """Raised when authentication/authorization fails."""
    pass