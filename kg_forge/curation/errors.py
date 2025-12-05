"""Custom exceptions for document curation."""


class CurationError(Exception):
    """Base exception for document curation errors."""
    
    def __init__(self, message: str, doc_path: str = None, original_error: Exception = None):
        """
        Initialize curation error.
        
        Args:
            message: Error message
            doc_path: Path to the document that failed (optional)
            original_error: Original exception that caused this error (optional)
        """
        self.message = message
        self.doc_path = doc_path
        self.original_error = original_error
        
        error_msg = message
        if doc_path:
            error_msg = f"{message} (document: {doc_path})"
        if original_error:
            error_msg = f"{error_msg} - Caused by: {str(original_error)}"
        
        super().__init__(error_msg)


class UnsupportedFormatError(CurationError):
    """Exception raised when document format is not supported."""
    pass


class CurationBackendError(CurationError):
    """Exception raised when curation backend fails."""
    pass


class FormatDetectionError(CurationError):
    """Exception raised when format cannot be detected."""
    pass
