# Step 6: LLM Integration & Dual Extraction Backends

## Overview

Step 6 introduces a dual extraction architecture with pluggable backends that can extract entities and relations using either LLM-based approaches or NLP/ML pipelines. This step implements both the LLM extraction backend (using AWS Bedrock) and the spaCy lexical graph pipeline (using spaCy + GLiNER + GLiREL) behind a common `ExtractionBackend` interface. The extraction backends produce structured `LexicalGraph` objects containing mentions and relations that will be processed by deduplication and entity linking in subsequent steps.

Step 6 explicitly does NOT write anything to Neo4j (no graph persistence yet), orchestrate the full ingest pipeline over folders (that's Step 7), perform deduplication/entity resolution (handled by separate DedupBackend), or handle visualization or rendering.

## Scope

### In Scope

- Implement **ExtractionBackend interface**:
  - Common protocol for both LLM and spaCy-based extraction
  - Input: curated document content + ontology pack
  - Output: structured `LexicalGraph` with mentions and relations
- Implement **LLM Extraction Backend**:
  - Prompt builder using entity definitions and templates
  - AWS Bedrock client using LlamaIndex integration
  - Parse LLM JSON responses into `LexicalMention` and `LexicalRelation` objects
  - Error handling, retry logic, and consecutive failure tracking
- Implement **spaCy Lexical Graph Backend**:
  - spaCy pipeline for tokenization, sentences, and document structure
  - GLiNER integration for named entity recognition with ontology-aligned labels
  - GLiREL integration for relation extraction between entities
  - Entity linking preparation and mention feature extraction
- Implement **core data models**:
  - `LexicalMention`: entity mentions with positions and features
  - `LexicalRelation`: typed relations between mentions
  - `LexicalGraph`: container for mentions, relations, and metadata
- Implement **CLI commands** to:
  - Test extraction backends independently with sample content
  - Compare LLM vs spaCy extraction results side-by-side
  - Support fake/mock backends for testing without external dependencies
- Unit tests for:
  - Both extraction backends with mocked dependencies
  - Data model validation and serialization
  - Error handling and resilience patterns
  - Backend comparison and feature extraction

### Out of Scope

- Writing to Neo4j or creating `:Doc` / `:Entity` nodes (covered in Step 7)
- Walking folder trees and orchestrating ingest over many files (that's Step 7)
- Entity deduplication, resolution, or canonicalization (handled by separate DedupBackend)
- Entity linking to existing KG entities (handled by EntityLinkerBackend)
- Full ingest pipeline orchestration or batch processing workflows
- Advanced NLP features beyond basic spaCy + GLiNER + GLiREL integration
- Model training or fine-tuning for GLiNER/GLiREL components

## Core Data Models

### LexicalMention

A single mention of an entity in curated text, produced by either extraction backend.

```python
@dataclass
class LexicalMention:
    id: str                    # Unique within document/batch
    doc_id: str               # Links back to :Doc node
    entity_type: str          # e.g., "Product", "Team", "Topic"
    surface: str              # Exact text span
    start_offset: int         # Character offset in curated text
    end_offset: int           # Character offset in curated text
    features: Dict[str, Any]  # Backend-specific features
    
    # Common features examples:
    # - normalized_surface: normalized text
    # - sentence_index: sentence position
    # - surrounding_context: sentence text
    # - confidence: extraction confidence (0.0-1.0)
    # - backend_source: "llm" or "spacy"
```

### LexicalRelation

A typed relation between two lexical mentions, produced by GLiREL or LLM inference.

```python
@dataclass
class LexicalRelation:
    id: str                 # Unique relation identifier
    type: str              # e.g., "WORKS_ON", "USES", "PART_OF"
    src_mention_id: str    # Source LexicalMention ID
    dst_mention_id: str    # Destination LexicalMention ID
    features: Dict[str, Any]  # Backend-specific metadata
    
    # Common features examples:
    # - confidence: relation confidence score
    # - pattern: extraction pattern or rule
    # - sentence_index: where relation was found
    # - backend_source: "llm" or "spacy"
```

### LexicalGraph

The complete output from an extraction backend containing all mentions and relations.

```python
@dataclass
class LexicalGraph:
    mentions: List[LexicalMention]
    relations: List[LexicalRelation]
    metadata: Dict[str, Any]
    
    # Metadata examples:
    # - backend_name: "llm" or "spacy"
    # - model_version: model/library versions used
    # - extraction_time: processing timestamp
    # - runtime_stats: performance metrics
```

### ExtractionBackend Interface

Common interface for both LLM and spaCy-based extraction:

```python
from typing import Protocol

class ExtractionBackend(Protocol):
    def extract(self, content: str, ontology: OntologyPack) -> LexicalGraph:
        """
        Extract mentions and relations from curated text.
        
        Args:
            content: Curated document text
            ontology: Entity definitions and templates
            
        Returns:
            LexicalGraph with extracted mentions and relations
        """
        ...
```

## Extraction Backend Implementations

### LLMExtractionBackend

Uses AWS Bedrock via LlamaIndex to extract entities and relations through prompted generation.

```python
class LLMExtractionBackend:
    def __init__(self, bedrock_client, model_name: str, max_tokens: int = 4000):
        self.bedrock_client = bedrock_client
        self.model_name = model_name
        self.max_tokens = max_tokens
        
    def extract(self, content: str, ontology: OntologyPack) -> LexicalGraph:
        """
        Build prompt, call Bedrock, parse JSON response into LexicalGraph.
        """
        prompt = self._build_prompt(content, ontology)
        raw_response = self._call_bedrock(prompt)
        return self._parse_response(raw_response, content)
        
    def _build_prompt(self, content: str, ontology: OntologyPack) -> str:
        """Combine entity definitions, templates, and document content."""
        
    def _parse_response(self, response: str, original_content: str) -> LexicalGraph:
        """Parse LLM JSON into LexicalMention and LexicalRelation objects."""
```

**LLM Response Format:**
```json
{
  "entities": [
    {
      "type": "Product",
      "name": "Knowledge Discovery",
      "start": 45,
      "end": 63,
      "confidence": 0.92
    }
  ],
  "relations": [
    {
      "type": "WORKS_ON",
      "source": "Platform Engineering",
      "target": "Knowledge Discovery",
      "confidence": 0.85
    }
  ]
}
```

### SpacyLexicalBackend

Uses spaCy + GLiNER + GLiREL for entity and relation extraction through NLP pipelines.

```python
class SpacyLexicalBackend:
    def __init__(self, spacy_model: str, gliner_model: str, glirel_model: str):
        self.nlp = spacy.load(spacy_model)
        self.gliner = GLiNER.from_pretrained(gliner_model)
        self.glirel = GLiREL.from_pretrained(glirel_model)
        
    def extract(self, content: str, ontology: OntologyPack) -> LexicalGraph:
        """
        Run spaCy pipeline, GLiNER NER, GLiREL relation extraction.
        """
        # Tokenize and sentence segment with spaCy
        doc = self.nlp(content)
        
        # Extract entities with GLiNER using ontology labels
        entity_types = [et.name for et in ontology.entity_types]
        entities = self.gliner.predict_entities(content, entity_types)
        
        # Extract relations with GLiREL
        relations = self.glirel.predict_relations(doc, entities)
        
        return self._build_lexical_graph(entities, relations, content)
        
    def _build_lexical_graph(self, entities, relations, content: str) -> LexicalGraph:
        """Convert spaCy/GLiNER/GLiREL outputs to LexicalGraph format."""
```

### FakeExtractionBackend

Deterministic backend for testing that returns configurable responses without external dependencies.

```python
class FakeExtractionBackend:
    def __init__(self, response_data: Dict[str, Any]):
        self.response_data = response_data
        
    def extract(self, content: str, ontology: OntologyPack) -> LexicalGraph:
        """Return pre-configured LexicalGraph for testing."""
        # Load from tests/data/extraction_responses/*.json
        # Support malformed data injection for negative testing
```

### Configuration Integration

Backends use configuration from Step 0's settings system:

```yaml
# Extraction backend settings
extraction:
  default_backend: llm  # llm|spacy
  
  llm:
    model_name: anthropic.claude-3-haiku-20240307-v1:0
    max_tokens: 4000
    temperature: 0.1
    
  spacy:
    model: en_core_web_sm
    gliner_model: urchade/gliner_multi
    glirel_model: jackboyla/glirel_beta
```

## Error Handling & Resilience

### Failure Classification

**LLM Backend Failures:**
- HTTP/network errors from Bedrock API
- Timeout exceptions  
- Invalid JSON responses that cannot be parsed
- Valid JSON that doesn't match expected schema
- Empty or null responses from LLM

**spaCy Backend Failures:**
- Model loading failures (spaCy, GLiNER, GLiREL)
- Memory/resource exhaustion during processing
- Invalid input text that breaks tokenization
- Entity type mismatches with ontology definitions
- Relation extraction failures between entities

**Common Failures:**
- Malformed input content
- Ontology pack loading errors
- Configuration/credential issues

### Retry Logic

- **LLM failures**: Retry API calls once with exponential backoff
- **spaCy failures**: Retry with fallback models or simplified processing
- **Configuration failures**: No retry, immediate failure with clear error message
- **Parse failures**: Log raw output for debugging, attempt retry once

### Consecutive Failure Handling

- Maintain separate failure counters for each backend type
- If more than 10 consecutive failures for any backend:
  - Log critical error with backend-specific failure details
  - Raise `ExtractionAbortError` with backend context
  - Calling process should exit with non-zero code
- Reset counter to 0 on any successful extraction from that backend

### Batch Processing Resilience

For batch scenarios (used by Step 7):
- Single document failure causes that document to be skipped
- Log document ID, backend type, and error details
- Continue processing remaining documents with same or different backend
- Return partial results with backend-specific failure summary

### Backend Failover

- If LLM backend fails consistently, optionally fallover to spaCy backend
- If spaCy backend fails consistently, optionally fallover to LLM backend  
- Configuration controls failover behavior (enabled/disabled, thresholds)

### Logging Strategy

- **INFO**: Successful extractions with mention/relation counts and backend type
- **WARNING**: Recoverable failures, retries, skipped documents, backend switches
- **ERROR**: Abort conditions, consecutive failure threshold reached
- **DEBUG**: Raw prompts/responses (LLM), model outputs (spaCy), parsing details

Include correlation context:
- Document ID or source identifier
- Backend type (llm/spacy)
- Extraction attempt number
- Attempt number for retries
- Failure count in current batch

## CLI Integration

### New Command: `extract-test`

Add a new CLI subcommand for testing extraction backends:

```bash
kg-forge extract-test [OPTIONS] INPUT
```

#### Arguments and Options

- `INPUT`: Path to text file containing curated document content
- `--backend [llm|spacy|both]`: Extraction backend to use (default: both)
- `--model TEXT`: Override Bedrock model name for LLM backend
- `--fake-backends`: Use fake/mock backends for testing
- `--output-format [json|text|comparison]`: Output format (default: comparison)
- `--namespace TEXT`: Namespace for entity definitions (default: "default")
- `--entities-dir PATH`: Override entity definitions directory
- `--template-file PATH`: Override prompt template file (LLM only)

#### Example Usage

```bash
# Compare both backends
kg-forge extract-test sample_doc.txt

# Test only LLM backend
kg-forge extract-test sample_doc.txt --backend llm

# Test only spaCy backend
kg-forge extract-test sample_doc.txt --backend spacy

# Use mock backends for testing
kg-forge extract-test sample_doc.txt --fake-backends

# JSON output for programmatic use
kg-forge extract-test sample_doc.txt --backend llm --output-format json
```

#### Command Behavior

1. Load configuration from Step 0 settings
2. Load entity definitions from ontology pack (respecting `--entities-dir`)
3. Read input text content
4. Initialize requested extraction backend(s) (real or fake based on `--fake-backends`)
5. Run extraction with error handling and timing
6. Parse and validate results
7. Display mentions and relations in requested format
8. If `--backend both`, show side-by-side comparison with differences highlighted
9. Exit with code 0 on success, non-zero on failure

The command does NOT write to Neo4j and is purely for debugging, verification, and backend comparison.

## Project Structure

```
kg_forge/
├── extraction/
│   ├── __init__.py
│   ├── interface.py       # ExtractionBackend protocol
│   ├── llm_backend.py     # LLM-based extraction implementation
│   ├── spacy_backend.py   # spaCy + GLiNER + GLiREL implementation
│   ├── fake_backend.py    # Mock backend for testing
│   └── exceptions.py      # Extraction-specific exceptions
├── models/
│   ├── __init__.py
│   ├── lexical.py         # LexicalMention, LexicalRelation, LexicalGraph
│   └── extraction.py      # Backend-specific data models
├── llm/
│   ├── __init__.py
│   ├── bedrock_client.py  # AWS Bedrock integration
│   ├── prompt_builder.py  # Prompt construction logic
│   └── response_parser.py # LLM response parsing
├── nlp/
│   ├── __init__.py
│   ├── spacy_pipeline.py  # spaCy integration and setup
│   ├── gliner_wrapper.py  # GLiNER integration
│   └── glirel_wrapper.py  # GLiREL integration  
├── cli/
│   ├── extract_test.py    # CLI command implementation
│   └── main.py           # Updated to include extract-test command
└── config/
    └── settings.py       # Updated with extraction backend configuration

tests/
├── test_extraction/
│   ├── __init__.py
│   ├── test_llm_backend.py        # LLM extraction backend
│   ├── test_spacy_backend.py      # spaCy extraction backend
│   ├── test_fake_backend.py       # Mock backend testing
│   └── test_interface.py          # Protocol compliance testing
├── test_models/
│   ├── __init__.py
│   ├── test_lexical.py           # LexicalGraph data models
│   └── test_serialization.py     # Data model serialization
├── test_llm/
│   ├── __init__.py
│   ├── test_prompt_builder.py    # Prompt construction
│   ├── test_response_parser.py   # Response parsing
│   └── test_bedrock_client.py    # AWS Bedrock integration
├── test_nlp/
│   ├── __init__.py
│   ├── test_spacy_pipeline.py    # spaCy integration
│   ├── test_gliner_wrapper.py    # GLiNER integration
│   └── test_glirel_wrapper.py    # GLiREL integration
├── test_cli/
│   └── test_extract_test.py      # CLI command testing
└── data/
    ├── extraction_responses/
    │   ├── llm_valid.json        # Valid LLM responses
    │   ├── spacy_valid.json      # Valid spaCy outputs
    │   ├── malformed.json        # Invalid responses for testing
    │   └── comparison_cases.json # Side-by-side test cases
    └── sample_documents/
        ├── technical_doc.txt     # Sample extraction inputs
        └── confluence_export.txt # Sample HTML-derived content
```

## Dependencies

### New Runtime Dependencies

Add to `requirements.txt`:

```
# LLM Integration
llama-index-llms-bedrock>=0.1.0
boto3>=1.34.0
botocore>=1.34.0
```

### Development Dependencies

Add to test requirements or dev section:

```
# LLM Testing
responses>=0.24.0    # For mocking HTTP calls in tests
moto[bedrock]>=4.0.0 # For AWS service mocking (optional)
```

### LlamaIndex Integration

Use the official LlamaIndex Bedrock LLM client:
- `llama-index-llms-bedrock` package provides `BedrockLLM` class
- Handles AWS credential management and region configuration
- Provides consistent interface with other LlamaIndex LLM clients
- Supports streaming and non-streaming responses

No heavy additional dependencies unrelated to LLM integration are introduced.

## Implementation Details

### Prompt Builder (`kg_forge/llm/prompt_builder.py`)

```python
class PromptBuilder:
    def __init__(self, entity_loader: EntityDefinitionLoader):
        self.entity_loader = entity_loader
    
    def build_prompt(self, document_content: str, entities_dir: Path, 
                    template_file: Path) -> str:
        # Load and merge entity definitions
        definitions = self.entity_loader.load_entity_definitions(entities_dir)
        template_content = self.entity_loader.load_prompt_template(template_file)
        merged_prompt = self.entity_loader.build_merged_prompt(template_content, definitions)
        
        # Inject document content
        return merged_prompt.replace('{{DOCUMENT_CONTENT}}', document_content)
```

### Response Parser (`kg_forge/llm/parser.py`)

```python
class ResponseParser:
    def parse_extraction_result(self, response_text: str) -> ExtractionResult:
        try:
            # Strict JSON parsing (preferred approach)
            data = json.loads(response_text.strip())
            
            # Validate top-level structure
            if not isinstance(data, dict) or 'entities' not in data:
                raise ValidationError("Response missing 'entities' field")
            
            # Parse entities
            entities = []
            for entity_data in data['entities']:
                entity = self._parse_entity(entity_data)
                entities.append(entity)
            
            return ExtractionResult(entities=entities)
            
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON response: {e}")
    
    def _parse_entity(self, entity_data: dict) -> ExtractedEntity:
        # Validate required fields
        if 'type' not in entity_data or 'name' not in entity_data:
            raise ValidationError("Entity missing required 'type' or 'name' field")
        
        return ExtractedEntity(
            type=entity_data['type'],
            name=entity_data['name'],
            confidence=entity_data.get('confidence', 1.0)
        )
```

### Configuration Integration

LLM configuration uses Step 1's settings system:

```python
@dataclass
class AWSConfig:
    access_key_id: str
    secret_access_key: str  
    default_region: str = "us-east-1"
    bedrock_model_name: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_max_tokens: int = 4000
    bedrock_temperature: float = 0.1
```

### Logging Strategy

Include structured logging with correlation context:

```python
logger.info("Starting entity extraction", extra={
    "doc_id": doc_id,
    "model": model_name,
    "prompt_length": len(prompt)
})

logger.warning("Extraction failed, retrying", extra={
    "doc_id": doc_id,
    "attempt": 2,
    "error": str(exception)
})

logger.error("Consecutive failure threshold exceeded", extra={
    "failure_count": consecutive_failures,
    "abort_threshold": 10
})
```

## Testing Strategy

### Unit Tests

**LLM Backend Tests** (`test_llm_backend.py`):
- Test prompt construction with entity definitions and templates
- Mock Bedrock API calls and verify request parameters
- Test response parsing into LexicalMention and LexicalRelation objects
- Simulate API failures and verify retry/error handling behavior
- Test consecutive failure tracking and abort conditions

**spaCy Backend Tests** (`test_spacy_backend.py`):
- Mock spaCy, GLiNER, and GLiREL components with predictable outputs
- Test entity type mapping from ontology to GLiNER labels
- Verify LexicalMention creation with proper offsets and features
- Test relation extraction and LexicalRelation object creation
- Test error handling for model loading and processing failures

**Data Model Tests** (`test_lexical.py`):
- Test LexicalMention, LexicalRelation, and LexicalGraph serialization
- Validate required fields and data type constraints
- Test conversion between internal models and Neo4j representations
- Test feature dictionary handling and metadata preservation

**Backend Interface Tests** (`test_interface.py`):
- Verify all backend implementations conform to ExtractionBackend protocol
- Test backend factory/registry pattern for runtime selection
- Validate error handling consistency across backends

**Fake Backend Tests** (`test_fake_backend.py`):
- Returns deterministic LexicalGraph objects for known inputs
- Supports injecting malformed data for negative testing
- Configurable via test data files in JSON format
- No external dependencies (spaCy models, Bedrock API)

### Integration Tests

**CLI Command Tests** (`test_extract_test.py`):
- Test `kg-forge extract-test` with both backends against sample documents
- Verify backend comparison output format and accuracy
- Test --fake-backends flag for deterministic testing
- Verify exit codes: 0 for success, non-zero for failures
- Test both text and JSON output formats
- Verify fake LLM mode works without network calls
- Assert printed output contains expected entity information

### Test Data

Create realistic test data in `tests/data/`:
- `sample_documents/`: Curated text samples from Confluence exports
- `extraction_responses/llm_valid.json`: Valid LLM extraction responses  
- `extraction_responses/spacy_valid.json`: Valid spaCy backend outputs
- `extraction_responses/malformed.json`: Invalid responses for error testing
- `extraction_responses/comparison_cases.json`: Side-by-side test scenarios

### CI/CD Considerations

- All tests use fake/mock backends by default - no real API calls or model downloads
- Optional integration tests with real Bedrock/spaCy models behind feature flags
- Environment variables control real backend testing:
  - `KG_FORGE_ENABLE_BEDROCK_TESTS=1` enables real Bedrock API tests
  - `KG_FORGE_ENABLE_SPACY_TESTS=1` enables real spaCy model tests
- Coverage target: >90% for extraction module components

## Success Criteria

Step 6 is considered complete when:

- [ ] **ExtractionBackend Interface**: Common protocol implemented by both LLM and spaCy backends
- [ ] **LLM Backend**: Produces LexicalGraph with mentions and relations from Bedrock responses
- [ ] **spaCy Backend**: Produces LexicalGraph using spaCy + GLiNER + GLiREL pipeline
- [ ] **Data Models**: LexicalMention, LexicalRelation, and LexicalGraph models handle backend-specific features
- [ ] **Error Handling**: Retry logic, consecutive failure tracking, and backend-specific error handling work correctly
- [ ] **CLI Command**: `kg-forge extract-test --fake-backends sample.txt` runs end-to-end with both backends
- [ ] **Backend Comparison**: `kg-forge extract-test sample.txt` shows side-by-side comparison of LLM vs spaCy results
- [ ] **JSON Output**: All backends produce consistent LexicalGraph structures suitable for downstream processing
- [ ] **No Graph Writes**: No Neo4j writes occur anywhere in Step 6 implementations
- [ ] **Configurable Backends**: Backend selection works via configuration and CLI flags
- [ ] All unit tests pass with >90% coverage for LLM modules
- [ ] Integration tests demonstrate the fake LLM can substitute for real Bedrock during development
- [ ] Error handling gracefully manages network failures, parse errors, and invalid responses
- [ ] Configuration integration works with Step 1's settings system for AWS credentials and model parameters

## Next Steps

Step 5 provides the reusable LLM extraction component that Step 6 (Ingest Pipeline) will orchestrate as part of the `kg-forge ingest` command. Step 6 will combine the HTML parsing capabilities from Step 2, entity definitions from Step 3, Neo4j operations from Step 4, and the LLM extraction from Step 5 to create the complete ingestion workflow that reads HTML files, extracts entities, and populates the Knowledge Graph. The extraction engine developed in Step 5 will be called for each curated document during batch ingestion, with the parsed results written to Neo4j using the schema and client from Step 4.