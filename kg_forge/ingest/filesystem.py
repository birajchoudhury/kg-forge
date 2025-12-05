"""
Filesystem utilities for file discovery and path handling.
"""

import os
from pathlib import Path
from typing import Generator, List, Set


# Supported document formats for curation
SUPPORTED_FORMATS = {'.html', '.htm', '.pdf', '.docx', '.pptx'}


def derive_doc_id(file_path: Path, source_root: Path) -> str:
    """
    Convert file path to doc_id by creating a normalized identifier WITH extension.
    
    This follows the Option B strategy from the curation spec where doc_id includes
    the file extension to allow the same document in multiple formats.
    
    Args:
        file_path: Full path to the document file
        source_root: Root directory being processed
        
    Returns:
        Normalized doc_id WITH extension (e.g., "team_project.html", "report.pdf")
        
    Example:
        derive_doc_id(Path("/data/docs/team/project.html"), Path("/data/docs"))
        -> "team_project.html"
        
        derive_doc_id(Path("/data/docs/report.pdf"), Path("/data/docs"))
        -> "report.pdf"
    """
    try:
        relative_path = file_path.relative_to(source_root)
    except ValueError:
        # File is not under source_root, use filename with extension
        return file_path.name.lower()
    
    # Replace separators with underscores, keep extension, normalize to lowercase
    doc_id = str(relative_path).replace(os.sep, '_').lower()
    
    # Handle edge cases
    if not doc_id or doc_id == '.':
        doc_id = file_path.name.lower()
        
    return doc_id


class FileDiscovery:
    """Utilities for discovering and processing multi-format document files in a directory tree."""
    
    def __init__(self, source_path: Path, supported_formats: Set[str] = None):
        """
        Initialize file discovery for a source directory.
        
        Args:
            source_path: Root directory to search for document files
            supported_formats: Set of file extensions to discover (default: SUPPORTED_FORMATS)
            
        Raises:
            FileNotFoundError: If source_path doesn't exist
            NotADirectoryError: If source_path is not a directory
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
            
        if not source_path.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_path}")
            
        self.source_path = source_path.resolve()
        self.supported_formats = supported_formats or SUPPORTED_FORMATS
    
    def discover_documents(self) -> Generator[Path, None, None]:
        """
        Discover all supported document files in the source directory recursively.
        
        Yields:
            Path objects for document files, sorted alphabetically for reproducible order
            
        Notes:
            - Searches recursively through subdirectories
            - Filters for supported formats (HTML, PDF, DOCX, PPTX, etc.) case-insensitive
            - Returns files in sorted order for deterministic processing
        """
        document_files = []
        
        for root, dirs, files in os.walk(self.source_path):
            root_path = Path(root)
            
            for file in files:
                file_path = root_path / file
                
                # Check for supported extensions (case-insensitive)
                if file_path.suffix.lower() in self.supported_formats:
                    document_files.append(file_path)
        
        # Sort for reproducible processing order
        document_files.sort()
        
        for file_path in document_files:
            yield file_path
    
    def discover_html_files(self) -> Generator[Path, None, None]:
        """
        Discover all HTML files in the source directory recursively.
        
        Yields:
            Path objects for HTML files, sorted alphabetically for reproducible order
            
        Notes:
            - Searches recursively through subdirectories
            - Filters for .html and .htm files (case-insensitive)
            - Returns files in sorted order for deterministic processing
            - DEPRECATED: Use discover_documents() for multi-format support
        """
        html_files = []
        
        for root, dirs, files in os.walk(self.source_path):
            root_path = Path(root)
            
            for file in files:
                file_path = root_path / file
                
                # Check for HTML extensions (case-insensitive)
                if file_path.suffix.lower() in ['.html', '.htm']:
                    html_files.append(file_path)
        
        # Sort for reproducible processing order
        html_files.sort()
        
        for file_path in html_files:
            yield file_path
    
    def get_document_count(self) -> int:
        """
        Get total count of supported document files without processing them.
        
        Returns:
            Number of document files found in source directory
        """
        return sum(1 for _ in self.discover_documents())
    
    def get_html_file_count(self) -> int:
        """
        Get total count of HTML files without processing them.
        
        Returns:
            Number of HTML files found in source directory
            
        Note:
            DEPRECATED: Use get_document_count() for multi-format support
        """
        return sum(1 for _ in self.discover_html_files())
    
    def get_doc_id(self, file_path: Path) -> str:
        """
        Get document ID for a specific file.
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            Document ID derived from file path
        """
        return derive_doc_id(file_path, self.source_path)
    
    def list_html_files(self) -> List[Path]:
        """
        Get list of all HTML files (convenience method).
        
        Returns:
            List of Path objects for all HTML files
        """
        return list(self.discover_html_files())