# Hybrid Extraction Backend

## Overview

The **Hybrid Extraction Backend** combines the robustness of transformer-based spaCy NER with the flexibility of LLM-based property and relation extraction.

## Architecture

### Two-Phase Extraction

#### Phase 1: Entity Detection (spaCy NER)
- Uses `en_core_web_trf` transformer model for entity recognition
- Detects standard entity types: PERSON, ORG, PRODUCT, GPE, DATE, etc.
- Maps spaCy labels to ontology entity types
- Produces high-quality entity mentions with precise character offsets

#### Phase 2: Enrichment (LLM)
- Takes detected entities as context
- Extracts:
  - Additional entity properties based on ontology
  - Relationships between entities based on ontology schema
- Uses specialized prompts referencing detected entities
- Validates against ontology-defined relationship types

## Benefits

### 🎯 Accuracy
- **Transformer NER**: More reliable than zero-shot models for standard entities
- **Ontology-guided**: LLM ensures properties and relations match schema
- **Validated relations**: Only creates relationships defined in ontology

### ⚡ Efficiency
- **Focused LLM usage**: Only for complex property/relation extraction
- **Reduced token usage**: Entities pre-detected, LLM processes smaller context
- **Faster processing**: spaCy NER is faster than full LLM extraction

### 🛡️ Resilience
- **Graceful degradation**: If LLM fails, still returns entities from spaCy
- **Fallback mode**: Returns entities-only graph on LLM failure
- **Statistics tracking**: Monitors LLM success/failure rates

## Usage

### CLI

```bash
# Use hybrid extraction backend
kg-forge ingest /path/to/docs \
  --extractor hybrid \
  --namespace my_namespace

# With custom LLM model
kg-forge ingest /path/to/docs \
  --extractor hybrid \
  --model anthropic.claude-3-sonnet-20240229-v1:0

# With chunking enabled
kg-forge ingest /path/to/docs \
  --extractor hybrid \
  --chunking on
```

### Programmatic

```python
from kg_forge.extraction.hybrid_backend import HybridExtractionBackend
from kg_forge.ontology.manager import OntologyManager

# Initialize backend
backend = HybridExtractionBackend(
    spacy_model="en_core_web_trf",
    llm_model_name="anthropic.claude-3-haiku-20240307-v1:0",
    llm_region="us-east-1",
    entity_confidence_threshold=0.7
)

# Load ontology
ontology_manager = OntologyManager()
ontology = ontology_manager.load_pack("my_ontology")

# Extract from text
text = "The Platform Engineering team is building Knowledge Discovery..."
graph = backend.extract(text, ontology, doc_id="doc123")

# Access results
print(f"Found {len(graph.mentions)} entities")
print(f"Found {len(graph.relations)} relations")
```

## Configuration

### Backend Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `spacy_model` | `en_core_web_trf` | spaCy transformer model for NER |
| `llm_model_name` | `anthropic.claude-3-haiku-20240307-v1:0` | AWS Bedrock model for enrichment |
| `llm_region` | `us-east-1` | AWS region |
| `max_tokens` | `4000` | Maximum LLM response tokens |
| `temperature` | `0.1` | LLM sampling temperature |
| `timeout` | `30` | LLM request timeout (seconds) |
| `max_retries` | `3` | Maximum LLM retry attempts |
| `consecutive_failure_threshold` | `10` | Abort after N consecutive LLM failures |
| `entity_confidence_threshold` | `0.7` | Minimum confidence for entities |
| `fake_mode` | `False` | Use fake models for testing |

### Entity Label Mapping

The backend maps spaCy NER labels to ontology types:

| spaCy Label | Ontology Types (priority order) |
|-------------|--------------------------------|
| PERSON | person, engineer, author, team_member, employee |
| ORG | organization, team, company, department, workstream |
| PRODUCT | product, software, service, component, tool |
| GPE | location, place, region |
| DATE | date, time, temporal |
| EVENT | event, milestone, release |
| WORK_OF_ART | document, publication, artifact |
| LAW | standard, regulation, policy |
| LANGUAGE | language, programming_language |

**Fallback**: If no mapping found, defaults to `Topic` type if available.

### Custom Mapping

Extend mapping by subclassing `HybridExtractionBackend`:

```python
class CustomHybridBackend(HybridExtractionBackend):
    def _build_label_mapping(self, ontology_types):
        mapping = super()._build_label_mapping(ontology_types)
        
        # Add custom mappings
        mapping["CUSTOM_LABEL"] = "CustomEntityType"
        
        return mapping
```

## Output Format

### LexicalGraph Structure

```python
LexicalGraph(
    mentions=[
        LexicalMention(
            id="doc123_mention_0",
            doc_id="doc123",
            entity_type="Team",
            surface="Platform Engineering team",
            start_offset=9,
            end_offset=34,
            features={
                "spacy_label": "ORG",
                "confidence": 0.9,
                "detection_method": "spacy_ner"
            }
        ),
        # ... more mentions
    ],
    relations=[
        LexicalRelation(
            id="rel_1",
            type="DEVELOPS",
            src_mention_id="doc123_mention_0",
            dst_mention_id="doc123_mention_1",
            features={
                "source_entity": "Platform Engineering team",
                "target_entity": "Knowledge Discovery",
                "confidence": 0.95,
                "context": "team is building Knowledge Discovery",
                "extraction_method": "llm_hybrid"
            }
        ),
        # ... more relations
    ],
    metadata={
        "backend": "hybrid",
        "spacy_model": "en_core_web_trf",
        "llm_model": "anthropic.claude-3-haiku-20240307-v1:0",
        "total_entities": 5,
        "total_relations": 3,
        "detection_method": "spacy_ner",
        "enrichment_method": "llm"
    }
)
```

## Error Handling

### LLM Failure Modes

1. **Retry with backoff**: Up to `max_retries` attempts with exponential backoff
2. **Fallback to entities-only**: If all retries fail, returns graph with spaCy entities only
3. **Consecutive failure tracking**: Aborts pipeline after `consecutive_failure_threshold` failures
4. **Graceful degradation**: Metadata indicates enrichment failure

### Example Fallback Output

```python
# When LLM enrichment fails
LexicalGraph(
    mentions=[...],  # Entities from spaCy
    relations=[],    # No relations (LLM failed)
    metadata={
        "backend": "hybrid",
        "enrichment_method": "failed",
        "note": "LLM enrichment failed, returning entities only"
    }
)
```

## Performance Characteristics

### Speed Comparison

| Backend | Entity Detection | Relation Extraction | Overall |
|---------|-----------------|---------------------|---------|
| LLM | Slow (LLM) | Slow (LLM) | ~5-10s/doc |
| spaCy | Very Fast (GLiNER) | Fast (GLiREL) | ~1-2s/doc |
| **Hybrid** | **Fast (Transformer)** | **Slow (LLM)** | **~3-6s/doc** |

### Token Usage

- **LLM backend**: ~2000-4000 tokens per document
- **spaCy backend**: 0 tokens (local models)
- **Hybrid backend**: ~1000-2000 tokens per document (50% reduction)

### Accuracy Trade-offs

- **Entity Detection**: Higher accuracy than GLiNER, comparable to LLM
- **Relation Extraction**: Same as LLM (uses LLM)
- **Overall**: Best balance of accuracy and performance

## Statistics and Monitoring

### Backend Info

```python
info = backend.get_backend_info()
print(info)
```

Output:
```python
{
    "name": "hybrid",
    "description": "Hybrid spaCy NER + LLM extraction",
    "spacy_model": "en_core_web_trf",
    "llm_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "llm_region": "us-east-1",
    "entity_confidence_threshold": 0.7,
    "statistics": {
        "total_extractions": 42,
        "total_entities_detected": 387,
        "total_entities_enriched": 387,
        "total_relations": 152,
        "total_llm_calls": 42,
        "total_llm_failures": 2,
        "consecutive_llm_failures": 0
    }
}
```

## Testing

### Unit Tests

```bash
pytest tests/test_extraction/test_hybrid_backend.py -v
```

### Integration Test

```python
from kg_forge.extraction.hybrid_backend import HybridExtractionBackend

# Fake mode for testing (no real API calls)
backend = HybridExtractionBackend(fake_mode=True)

# Test extraction
graph = backend.extract(
    content="Test document...",
    ontology=test_ontology,
    doc_id="test_doc"
)

assert len(graph.mentions) > 0
assert graph.metadata["backend"] == "hybrid"
```

## Troubleshooting

### Issue: No entities detected

**Cause**: spaCy model not recognizing entity types

**Solutions**:
1. Check entity label mapping configuration
2. Verify ontology defines matching entity types
3. Try different spaCy model (e.g., `en_core_web_lg`)

### Issue: LLM enrichment always fails

**Cause**: AWS Bedrock configuration or connectivity

**Solutions**:
1. Verify AWS credentials and region
2. Check Bedrock model access permissions
3. Review CloudWatch logs for detailed errors
4. Increase timeout and retry settings

### Issue: Relations not matching ontology

**Cause**: LLM not following ontology schema

**Solutions**:
1. Verify ontology relation definitions are clear
2. Check prompt template includes ontology schema
3. Increase temperature for more creative relation extraction
4. Review LLM response parsing logic

## Future Enhancements

- [ ] Support for custom spaCy NER models
- [ ] Configurable label mapping via config file
- [ ] Caching of spaCy NER results
- [ ] Parallel LLM calls for large documents
- [ ] Alternative LLM providers (OpenAI, Anthropic Direct)
- [ ] Property extraction validation against ontology schema
- [ ] Confidence score calibration for entity types
