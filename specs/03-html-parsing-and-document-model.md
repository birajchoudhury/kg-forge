# Specification: Document Curation and Multi-Format Processing

**Status**: In Progress  
**Created**: 2025-11-21  
**Updated**: 2025-12-05  
**Related to**: Step 3 - Data Curation

## Overview

This specification defines how to process multiple document formats (HTML, PDF, DOCX, etc.) into structured curated content using a configurable curation backend architecture. The curation process converts source documents to both markdown representations (for provenance) and clean curated text (for entity extraction), supporting the downstream extraction, deduplication, and knowledge graph ingestion pipeline.

## Requirements Summary

1. Implement **CurationBackend** interface for pluggable document processing
2. Implement **DoclingCurationBackend** for multi-format document processing (HTML, PDF, DOCX, etc.)
3. Automatic file format detection based on extension and content
4. Convert documents to markdown and save to `output/markdowns/<namespace>/<doc_id>.md`
5. Extract clean curated text suitable for entity extraction backends
6. Generate content hash for change detection (MD5 of curated text)
7. Include document metadata (format, page count, processing stats)
8. Error handling: log failures and skip problematic documents
9. Stub **HylandKECurationBackend** for future API integration
10. Support namespace-based markdown organization
11. CLI integration with `--curator` flag for backend selection

## Data Model

### CurationResult

The output of a `CurationBackend` for a single document.

```python
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path

class CurationResult(BaseModel):
    """Result of document curation process."""
    
    curated_text: str = Field(..., description="Clean text suitable for extraction backends")
    markdown_content: str = Field(..., description="Full markdown representation of document")
    markdown_path: str = Field(..., description="Absolute path where markdown was saved")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Curation metadata")
    
    # Common metadata fields:
    # - source_format: str (e.g., "html", "pdf", "docx")
    # - page_count: int (for paginated formats)
    # - curation_backend: str (e.g., "docling", "hylandKE")
    # - timestamp: str (ISO format)
    # - file_size: int (bytes)
    # - processing_time: float (seconds)

class DocumentMetadata(BaseModel):
    """Metadata extracted during curation."""
    
    doc_id: str = Field(..., description="Document ID including extension (e.g., 'intro.html', 'report.pdf')")
    source_path: str = Field(..., description="Relative path to source file")
    source_format: str = Field(..., description="Document format (html, pdf, docx, etc.)")
    content_hash: str = Field(..., description="MD5 hash of curated text")
    namespace: str = Field(..., description="Target namespace for organization")
    
    # Optional fields
    title: Optional[str] = Field(None, description="Document title if extractable")
    page_count: Optional[int] = Field(None, description="Number of pages (for paginated formats)")
    file_size: Optional[int] = Field(None, description="Source file size in bytes")
```

### CurationBackend Protocol

```python
from typing import Protocol
from pathlib import Path

class CurationBackend(Protocol):
    """Protocol for document curation backends."""
    
    def curate(self, file_path: Path, namespace: str) -> CurationResult:
        """Process a document file and return markdown + curated text.
        
        Args:
            file_path: Path to source document
            namespace: Current namespace for organizing outputs
            
        Returns:
            CurationResult with curated_text, markdown_content, markdown_path, and metadata
            
        Raises:
            CurationError: If document cannot be processed
        """
        ...
    
    def detect_format(self, file_path: Path) -> str:
        """Detect document format from file.
        
        Args:
            file_path: Path to document file
            
        Returns:
            Format string (e.g., "html", "pdf", "docx")
        """
        ...
```

## Document Format Detection

### Format Detection Strategy

Automatic detection based on file extension and content verification:

```python
def detect_format(file_path: Path) -> str:
    """Detect document format from file path and content.
    
    Priority:
    1. File extension (.html, .pdf, .docx, .pptx, etc.)
    2. Content magic bytes verification for validation
    
    Returns:
        Format string: "html", "pdf", "docx", "pptx", "txt", "unknown"
    """
    extension_map = {
        '.html': 'html',
        '.htm': 'html',
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.doc': 'doc',
        '.pptx': 'pptx',
        '.txt': 'txt',
        '.md': 'markdown'
    }
    
    suffix = file_path.suffix.lower()
    return extension_map.get(suffix, 'unknown')
```

## Document ID Generation

### ID Format

Document IDs include the file extension to allow multiple formats of the same document:

```python
def generate_doc_id(file_path: Path, source_root: Path) -> str:
    """Generate document ID from file path.
    
    Args:
        file_path: Full path to document file
        source_root: Root directory of source files
        
    Returns:
        Document ID with extension (e.g., "docs/platform/intro.html", "reports/q4.pdf")
        
    Examples:
        source_root: /data/confluence/
        file_path: /data/confluence/docs/platform/intro.html
        → doc_id: "docs/platform/intro.html"
        
        source_root: /data/pdfs/
        file_path: /data/pdfs/reports/Q4-2025.pdf
        → doc_id: "reports/q4-2025.pdf"
    """
    relative_path = file_path.relative_to(source_root)
    # Normalize: lowercase, convert spaces to hyphens
    doc_id = str(relative_path).lower().replace(' ', '-')
    return doc_id
```

**Rationale for including extension:**
- Allows same logical document in different formats to coexist (e.g., `intro.html` and `intro.pdf`)
- Clear provenance of source format
- Different formats may yield different extraction results
- Enables format-specific processing strategies
## Docling Curation Backend

### Overview

Docling is a multi-format document processing library that converts documents to markdown with structure preservation.

**Supported Formats:**
- HTML (including Confluence exports)
- PDF (with layout analysis)
- DOCX (Microsoft Word)
- PPTX (PowerPoint presentations)
- Images with OCR support

### Implementation

```python
from docling.document_converter import DocumentConverter
from pathlib import Path
import hashlib
from datetime import datetime

class DoclingCurationBackend:
    """Docling-based multi-format document curation."""
    
    def __init__(self, output_base_dir: Path = Path("output/markdowns")):
        """Initialize Docling backend.
        
        Args:
            output_base_dir: Base directory for markdown outputs
        """
        self.output_base_dir = output_base_dir
        self.converter = DocumentConverter()
        
    def curate(self, file_path: Path, namespace: str) -> CurationResult:
        """Process document using Docling.
        
        Args:
            file_path: Path to source document
            namespace: Namespace for organizing outputs
            
        Returns:
            CurationResult with markdown and curated text
            
        Raises:
            CurationError: If processing fails
        """
        try:
            start_time = time.time()
            
            # Detect format
            source_format = self.detect_format(file_path)
            
            # Convert document to markdown using Docling
            result = self.converter.convert(str(file_path))
            
            # Extract markdown content
            markdown_content = result.document.export_to_markdown()
            
            # Generate curated text (cleaned version for extraction)
            curated_text = self._clean_for_extraction(markdown_content)
            
            # Compute content hash
            content_hash = hashlib.md5(curated_text.encode('utf-8')).hexdigest()
            
            # Generate doc_id (will be provided by caller, but we can suggest)
            # Save markdown to namespace-organized directory
            markdown_path = self._save_markdown(
                markdown_content, 
                file_path, 
                namespace
            )
            
            processing_time = time.time() - start_time
            
            # Build metadata
            metadata = {
                "source_format": source_format,
                "curation_backend": "docling",
                "timestamp": datetime.now().isoformat(),
                "file_size": file_path.stat().st_size,
                "processing_time": processing_time
            }
            
            # Add page count for paginated formats
            if hasattr(result.document, 'num_pages'):
                metadata["page_count"] = result.document.num_pages
            
            return CurationResult(
                curated_text=curated_text,
                markdown_content=markdown_content,
                markdown_path=str(markdown_path),
                metadata=metadata
            )
            
        except Exception as e:
            raise CurationError(f"Docling processing failed for {file_path}: {e}")
    
    def detect_format(self, file_path: Path) -> str:
        """Detect document format."""
        extension_map = {
            '.html': 'html',
            '.htm': 'html',
            '.pdf': 'pdf',
            '.docx': 'docx',
            '.pptx': 'pptx',
            '.txt': 'txt'
        }
        return extension_map.get(file_path.suffix.lower(), 'unknown')
    
    def _clean_for_extraction(self, markdown: str) -> str:
        """Clean markdown for entity extraction.
        
        Removes:
        - Excessive whitespace
        - Navigation elements
        - Boilerplate text
        - Special characters that interfere with NLP
        
        Returns:
            Clean text suitable for extraction backends
        """
        # Remove multiple blank lines
        lines = [line for line in markdown.split('\n') if line.strip()]
        
        # Join and normalize whitespace
        text = '\n'.join(lines)
        text = ' '.join(text.split())
        
        return text
    
    def _save_markdown(
        self, 
        markdown: str, 
        source_path: Path, 
        namespace: str
    ) -> Path:
        """Save markdown to namespace-organized directory.
        
        Structure: output/markdowns/<namespace>/<doc_id>.md
        """
        # Create namespace directory
        namespace_dir = self.output_base_dir / namespace
        namespace_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate markdown filename from source
        # Preserve directory structure and extension
        md_filename = source_path.name.lower().replace(' ', '-')
        if not md_filename.endswith('.md'):
            md_filename = md_filename.rsplit('.', 1)[0] + '.md'
        
        markdown_path = namespace_dir / md_filename
        
        # Write markdown
        markdown_path.write_text(markdown, encoding='utf-8')
        
        return markdown_path


class CurationError(Exception):
    """Raised when document curation fails."""
    pass
```

### Error Handling

```python
def process_with_error_handling(
    backend: CurationBackend,
    file_path: Path,
    namespace: str
) -> Optional[CurationResult]:
    """Process document with comprehensive error handling.
    
    Returns:
        CurationResult if successful, None if failed
    """
    try:
        return backend.curate(file_path, namespace)
    except CurationError as e:
        logger.error(f"Curation failed for {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error curating {file_path}: {e}", exc_info=True)
        return None
```

## Hyland KE Curation Backend (Future)

### Overview

Stub implementation for future integration with Hyland curated content API.

```python
class HylandKECurationBackend:
    """Hyland Knowledge Enrichment API-based curation (future)."""
    
    def __init__(self, api_endpoint: str, api_key: str, output_base_dir: Path = Path("output/markdowns")):
        """Initialize Hyland KE backend.
        
        Args:
            api_endpoint: Hyland KE API endpoint
            api_key: Authentication key
            output_base_dir: Base directory for markdown outputs
        """
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.output_base_dir = output_base_dir
        
    def curate(self, file_path: Path, namespace: str) -> CurationResult:
        """Process document using Hyland KE API.
        
        Future implementation will:
        - Upload document to Hyland KE API
        - Receive curated content and metadata
        - Extract entities and relations (optional)
        - Return standardized CurationResult
        
        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError(
            "Hyland KE backend will be implemented in a future iteration"
        )
    
    def detect_format(self, file_path: Path) -> str:
        """Detect document format."""
        # Same implementation as Docling
        pass
```

## Module Structure

```
kg_forge/
├── kg_forge/
│   ├── curation/
│   │   ├── __init__.py
│   │   ├── base.py              # CurationBackend protocol and base classes
│   │   ├── docling_backend.py   # Docling implementation
│   │   ├── hyland_backend.py    # Hyland KE stub
│   │   └── errors.py            # CurationError and related exceptions
│   ├── models/
│   │   ├── __init__.py
│   │   └── curation.py          # CurationResult, DocumentMetadata models
```

## Dependencies

Add to `requirements.txt`:

```
# Document curation
docling>=1.0.0              # Multi-format document processing
docling-core>=1.0.0         # Core Docling functionality
```

## Backend Selection

```python
from typing import Literal

CuratorType = Literal["docling", "hylandKE"]

def create_curation_backend(
    curator_type: CuratorType,
    output_dir: Path = Path("output/markdowns"),
    **kwargs
) -> CurationBackend:
    """Factory for curation backends.
    
    Args:
        curator_type: Backend type ("docling" or "hylandKE")
        output_dir: Base directory for markdown outputs
        **kwargs: Backend-specific configuration
        
    Returns:
        Configured CurationBackend instance
        
    Raises:
        ValueError: If curator_type is unknown or not available
    """
    if curator_type == "docling":
        return DoclingCurationBackend(output_base_dir=output_dir)
    
    elif curator_type == "hylandKE":
        # Require API configuration
        api_endpoint = kwargs.get("api_endpoint")
        api_key = kwargs.get("api_key")
        
        if not api_endpoint or not api_key:
            raise ValueError("HylandKE backend requires api_endpoint and api_key")
        
        return HylandKECurationBackend(
            api_endpoint=api_endpoint,
            api_key=api_key,
            output_base_dir=output_dir
        )
    
    else:
        raise ValueError(f"Unknown curator type: {curator_type}")
```

## Testing Strategy

### Unit Tests

```python
# tests/test_curation/test_docling_backend.py

def test_detect_format():
    """Test format detection for various file types."""
    assert detect_format(Path("test.html")) == "html"
    assert detect_format(Path("test.pdf")) == "pdf"
    assert detect_format(Path("test.docx")) == "docx"
    assert detect_format(Path("unknown.xyz")) == "unknown"

def test_generate_doc_id():
    """Test document ID generation with extensions."""
    source_root = Path("/data/docs")
    
    # HTML file
    html_path = Path("/data/docs/platform/intro.html")
    assert generate_doc_id(html_path, source_root) == "platform/intro.html"
    
    # PDF file
    pdf_path = Path("/data/docs/reports/Q4 Summary.pdf")
    assert generate_doc_id(pdf_path, source_root) == "reports/q4-summary.pdf"

def test_docling_curate_html():
    """Test Docling curation of HTML document."""
    backend = DoclingCurationBackend()
    result = backend.curate(
        Path("tests/data/sample.html"),
        namespace="test"
    )
    
    assert result.curated_text
    assert result.markdown_content
    assert result.metadata["source_format"] == "html"
    assert result.metadata["curation_backend"] == "docling"
    assert Path(result.markdown_path).exists()

def test_docling_curate_pdf():
    """Test Docling curation of PDF document."""
    backend = DoclingCurationBackend()
    result = backend.curate(
        Path("tests/data/sample.pdf"),
        namespace="test"
    )
    
    assert result.curated_text
    assert result.markdown_content
    assert result.metadata["source_format"] == "pdf"
    assert "page_count" in result.metadata

def test_curation_error_handling():
    """Test error handling for corrupted files."""
    backend = DoclingCurationBackend()
    
    with pytest.raises(CurationError):
        backend.curate(Path("tests/data/corrupted.pdf"), namespace="test")

def test_markdown_organization_by_namespace():
    """Test markdown files are organized by namespace."""
    backend = DoclingCurationBackend(output_base_dir=Path("output/markdowns"))
    
    result1 = backend.curate(Path("tests/data/doc1.html"), namespace="experiment1")
    result2 = backend.curate(Path("tests/data/doc2.html"), namespace="experiment2")
    
    assert "experiment1" in result1.markdown_path
    assert "experiment2" in result2.markdown_path
    assert Path(result1.markdown_path).parent.name == "experiment1"
    assert Path(result2.markdown_path).parent.name == "experiment2"

def test_content_hash_consistency():
    """Test content hash is consistent for same content."""
    backend = DoclingCurationBackend()
    
    result1 = backend.curate(Path("tests/data/sample.html"), namespace="test")
    result2 = backend.curate(Path("tests/data/sample.html"), namespace="test")
    
    # Compute hashes from curated text
    hash1 = hashlib.md5(result1.curated_text.encode()).hexdigest()
    hash2 = hashlib.md5(result2.curated_text.encode()).hexdigest()
    
    assert hash1 == hash2

def test_clean_for_extraction():
    """Test text cleaning produces extraction-ready content."""
    backend = DoclingCurationBackend()
    
    markdown = """
    # Title
    
    
    Some content with    multiple   spaces.
    
    
    More content.
    """
    
    cleaned = backend._clean_for_extraction(markdown)
    
    # Should remove excessive whitespace
    assert "   " not in cleaned
    # Should preserve meaningful content
    assert "Title" in cleaned
    assert "Some content" in cleaned
```

### Integration Tests

```python
# tests/test_curation/test_backend_integration.py

def test_multi_format_processing():
    """Test processing multiple document formats."""
    backend = DoclingCurationBackend()
    
    formats = [
        ("sample.html", "html"),
        ("sample.pdf", "pdf"),
        ("sample.docx", "docx")
    ]
    
    for filename, expected_format in formats:
        result = backend.curate(
            Path(f"tests/data/{filename}"),
            namespace="integration"
        )
        
        assert result.metadata["source_format"] == expected_format
        assert result.curated_text
        assert result.markdown_content

def test_curation_backend_factory():
    """Test backend factory creation."""
    
    # Docling backend
    docling = create_curation_backend("docling")
    assert isinstance(docling, DoclingCurationBackend)
    
    # Invalid backend
    with pytest.raises(ValueError):
        create_curation_backend("invalid")

def test_batch_processing_with_failures():
    """Test batch processing handles failures gracefully."""
    backend = DoclingCurationBackend()
    
    files = [
        Path("tests/data/valid1.html"),
        Path("tests/data/corrupted.pdf"),  # Will fail
        Path("tests/data/valid2.html")
    ]
    
    results = []
    failures = []
    
    for file_path in files:
        result = process_with_error_handling(backend, file_path, "test")
        if result:
            results.append(result)
        else:
            failures.append(file_path)
    
    assert len(results) == 2  # Two valid files processed
    assert len(failures) == 1  # One failed
```

### Test Data

Generate test documents in `tests/data/`:

```
tests/data/
├── sample.html              # Simple HTML page
├── confluence_export.html   # Confluence-style HTML
├── sample.pdf              # Multi-page PDF
├── sample.docx             # Word document
├── corrupted.pdf           # Intentionally corrupted file
├── large_document.pdf      # Large file for performance testing
└── special_chars.html      # HTML with special characters
```

## CLI Integration

### Configuration

Add `--curator` flag to `ingest` command:

```python
@click.command(name="ingest")
@click.option("--source", required=True, type=click.Path(exists=True))
@click.option("--namespace", default="default", help="Namespace for organizing outputs")
@click.option("--curator", 
              type=click.Choice(["docling", "hylandKE"], case_sensitive=False),
              default="docling",
              help="Curation backend to use")
@click.option("--dry-run", is_flag=True, help="Process without writing to graph")
def ingest(source: str, namespace: str, curator: str, dry_run: bool, **kwargs):
    """Ingest documents using selected curation backend."""
    
    # Create curation backend
    backend = create_curation_backend(curator)
    
    # Process documents
    source_path = Path(source)
    for file_path in source_path.rglob("*"):
        if file_path.is_file():
            try:
                result = backend.curate(file_path, namespace)
                click.echo(f"✓ Curated {file_path.name} → {result.markdown_path}")
            except CurationError as e:
                click.echo(f"✗ Failed {file_path.name}: {e}", err=True)
```

### Example Usage

```bash
# Use Docling backend (default)
kg-forge ingest --source ./docs --namespace experiment1

# Explicitly specify Docling
kg-forge ingest --source ./docs --curator docling --namespace experiment1

# Use Hyland KE backend (future)
kg-forge ingest --source ./docs --curator hylandKE --namespace production

# Dry run with PDF documents
kg-forge ingest --source ./pdfs --curator docling --namespace test --dry-run
```

## Success Criteria

1. ✓ Implement CurationBackend protocol for pluggable backends
2. ✓ DoclingCurationBackend processes multiple formats (HTML, PDF, DOCX)
3. ✓ Automatic format detection works correctly
4. ✓ Markdown saved to namespace-organized directories (`output/markdowns/<namespace>/`)
5. ✓ Curated text is clean and suitable for extraction
6. ✓ Content hashing (MD5) is consistent
7. ✓ Document IDs include file extension (e.g., `intro.html`, `report.pdf`)
8. ✓ Error handling logs failures and continues processing
9. ✓ HylandKECurationBackend stub exists for future implementation
10. ✓ CLI `--curator` flag selects backend
11. ✓ All tests pass (unit + integration)
12. ✓ Documentation complete

## Implementation Checklist

- [ ] Create `kg_forge/curation/` module structure
- [ ] Implement `CurationBackend` protocol in `base.py`
- [ ] Implement `DoclingCurationBackend` in `docling_backend.py`
- [ ] Implement `HylandKECurationBackend` stub in `hyland_backend.py`
- [ ] Create `CurationResult` and `DocumentMetadata` models
- [ ] Implement format detection logic
- [ ] Implement doc_id generation (with extension)
- [ ] Implement markdown saving with namespace organization
- [ ] Implement text cleaning for extraction
- [ ] Add `CurationError` exception
- [ ] Add backend factory function
- [ ] Update CLI with `--curator` flag
- [ ] Add Docling dependencies to `requirements.txt`
- [ ] Create test data (HTML, PDF, DOCX files)
- [ ] Write unit tests for all components
- [ ] Write integration tests for multi-format processing
- [ ] Test error handling and recovery
- [ ] Update documentation

## Next Steps

After Step 3 is complete:

1. **Step 4**: Load Entity Definitions
   - Works with format-agnostic curated text from curation backends
   
2. **Step 5**: Neo4j Bootstrap
   - Update schema to include `source_format`, `markdown_path`, `page_count`
   - Update doc_id constraint to handle extension-inclusive IDs

3. **Step 6**: LLM Integration & Extraction
   - Receive curated text from any curation backend
   - Extract entities regardless of source format

4. **Step 7**: Ingest Pipeline
   - Orchestrate curation → extraction → dedup → linking → storage
   - Handle multiple document formats in same ingest run
   - Batch processing with curation error tracking
