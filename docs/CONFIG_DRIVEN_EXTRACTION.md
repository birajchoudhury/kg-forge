# Config-Driven LLM Extraction

## Overview

This document describes the config-driven entity extraction system in KG Forge. This system enables generic LLM-based extraction using ontology definitions, with special support for distinguishing between **core entities** (persistent domain objects) and **occurrence entities** (events/temporal instances).

## Architecture

### Key Components

1. **OntologySchema.to_entity_config()** - Transforms ontology schema into LLM-friendly entity config JSON
2. **config_driven.extract_entities_from_document()** - Main extraction function using entity config
3. **LLMClient Interface** - Abstract interface for LLM backends (Bedrock, OpenAI, local models, etc.)

### Entity Types

The system distinguishes between two kinds of entities:

#### Core Entities (`kind: "core"`)
- Represent **persistent domain objects** (e.g., Contract, Person, Product)
- Have properties but **no temporal dependencies**
- Can exist independently
- Examples: Contract, Party, Template, Organization

#### Occurrence Entities (`kind: "occurrence"`)
- Represent **events or temporal instances** (e.g., ContractExecution, Meeting, Transaction)
- **Must link to one or more core entities** via dependencies
- Cannot exist without their linked core entities
- Examples: ContractExecution, ContractAmendment, ProjectMilestone

### Dependencies

Occurrence entities declare dependencies on core entities with cardinality constraints:

- `"1"` - Exactly one (required)
- `"0..1"` - Zero or one (optional)
- `"1..*"` - One or more (required, multiple allowed)
- `"0..*"` - Zero or more (optional, multiple allowed)

Example:
```json
{
  "depends_on": [
    {"role": "contract", "entity": "Contract", "cardinality": "1"},
    {"role": "parties", "entity": "Party", "cardinality": "1..*"}
  ]
}
```

## Entity Config JSON Format

The entity configuration uses this structure:

```json
{
  "entities": {
    "Contract": {
      "kind": "core",
      "label": "Contract",
      "description": "A legal contract",
      "properties": {
        "title": {"type": "string"},
        "value": {"type": "number"},
        "startDate": {"type": "date"}
      },
      "relations": {
        "INVOLVES": {"target": "Party"}
      },
      "depends_on": []
    },
    "ContractExecution": {
      "kind": "occurrence",
      "label": "Contract Execution",
      "description": "An execution event of a contract",
      "properties": {
        "executionDate": {"type": "date"},
        "location": {"type": "string"}
      },
      "relations": {},
      "depends_on": [
        {"role": "contract", "entity": "Contract", "cardinality": "1"}
      ]
    }
  }
}
```

## Extraction Output Format

The extraction system returns entities in two separate lists:

```json
{
  "core_entities": [
    {
      "entity_id": "contract-1",
      "type": "Contract",
      "properties": {
        "title": "Employment Agreement",
        "value": 100000,
        "startDate": "2024-01-01"
      },
      "span": {"page": 1, "start_char": 0, "end_char": 50}
    }
  ],
  "occurrence_entities": [
    {
      "entity_id": "execution-1",
      "type": "ContractExecution",
      "properties": {
        "executionDate": "2024-01-15",
        "location": "New York"
      },
      "links": {
        "contract": "contract-1"
      },
      "span": {"page": 1, "start_char": 200, "end_char": 250}
    }
  ]
}
```

### Key Features

- **Separation of Concerns**: Core and occurrence entities are extracted into separate lists
- **Entity Linking**: Occurrence entities link to core entities via `links` field
- **Span Information**: Each entity includes location in source document
- **Validation**: Dependencies are validated to ensure required links exist

## Usage

### 1. Create Ontology and Convert to Config

```python
from kg_forge.ontology.schema import OntologySchema, EntityType, Property, Dependency

# Define entities
contract = EntityType(
    name="Contract",
    iri="http://example.org/ont#Contract",
    description="A legal contract",
    kind="core",
    properties=[
        Property(name="title", description="Contract title", datatype="string"),
        Property(name="value", description="Contract value", datatype="number")
    ]
)

execution = EntityType(
    name="ContractExecution",
    iri="http://example.org/ont#ContractExecution",
    description="Execution of a contract",
    kind="occurrence",
    properties=[
        Property(name="executionDate", description="Execution date", datatype="date")
    ],
    depends_on=[
        Dependency(role="contract", entity="Contract", cardinality="1")
    ]
)

# Create schema
schema = OntologySchema(
    entities={"Contract": contract, "ContractExecution": execution},
    relations={}
)

# Convert to entity config
entity_config = schema.to_entity_config()
```

### 2. Implement LLM Client

```python
from kg_forge.extraction.config_driven import LLMClient

class BedrockLLMClient(LLMClient):
    def __init__(self, model_id: str, region: str):
        self.model_id = model_id
        self.region = region
        # Initialize Bedrock client...
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Call Bedrock API
        response = self.bedrock_client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 4096
            })
        )
        return response_body["content"][0]["text"]
```

### 3. Extract Entities

```python
from kg_forge.extraction.config_driven import extract_entities_from_document

# Initialize LLM client
llm_client = BedrockLLMClient(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region="us-east-1"
)

# Extract entities
result = extract_entities_from_document(
    entity_config=entity_config,
    doc_id="DOC-123",
    doc_title="Employment Contract",
    doc_text="This Employment Agreement...",
    llm_client=llm_client
)

# Access results
for entity in result["core_entities"]:
    print(f"Core: {entity['type']} - {entity['properties']}")

for entity in result["occurrence_entities"]:
    print(f"Occurrence: {entity['type']} links to {entity['links']}")
```

## Validation

The extraction system performs comprehensive validation:

### Config Validation
- Entity config must have `entities` key
- Each entity must have `kind` field ("core" or "occurrence")
- Entity kinds must be valid values

### Result Validation
- Response must have `core_entities` and `occurrence_entities` keys
- Each entity must have `entity_id`, `type`, and `properties`
- Entity types must exist in config
- Entities must be in correct list based on `kind`
- Occurrence entities must have `links` field

### Dependency Validation
- Required links (cardinality "1" or "1..*") must be present
- Linked entities must exist in core entities list
- Linked entities must have correct type

## Benefits

1. **Ontology-Driven**: Extraction is driven by formal ontology definitions
2. **Generic**: Works with any ontology that follows the schema format
3. **Type-Safe**: Strong validation ensures data integrity
4. **Flexible**: Supports any LLM backend via simple interface
5. **Maintainable**: Ontology changes automatically flow to extraction
6. **Core/Occurrence Distinction**: Properly models persistent vs temporal entities

## Testing

Comprehensive test suite covers:

- System prompt generation
- User prompt building with entity config
- Entity config validation
- LLM response parsing (JSON and markdown formats)
- Extraction result validation
- Dependency validation
- End-to-end extraction scenarios

Run tests:
```bash
pytest tests/test_extraction/test_config_driven.py -v
pytest tests/test_ontology/test_schema_enhanced.py::TestEntityConfigSerialization -v
```

## Integration with Existing Backends

The config-driven extraction system can be integrated with existing extraction backends:

```python
from kg_forge.extraction.llm_backend import LLMExtractionBackend

class ConfigDrivenLLMBackend(LLMExtractionBackend):
    def extract(self, doc: Document, ontology: OntologySchema) -> List[Entity]:
        # Convert ontology to config
        entity_config = ontology.to_entity_config()
        
        # Extract using config-driven approach
        result = extract_entities_from_document(
            entity_config=entity_config,
            doc_id=doc.id,
            doc_title=doc.title,
            doc_text=doc.text,
            llm_client=self.llm_client
        )
        
        # Convert to Entity objects
        return self._convert_to_entities(result)
```

## Future Enhancements

1. **Chunking Support**: Handle large documents by chunking and merging results
2. **Relation Extraction**: Extract relations between entities (not just occurrence links)
3. **Multi-Modal**: Support image/table extraction in addition to text
4. **Few-Shot Learning**: Include examples in prompts for better accuracy
5. **Incremental Extraction**: Support streaming/incremental extraction
6. **Confidence Scores**: Include confidence/probability for extracted entities
7. **Provenance**: Track which parts of prompt influenced extraction

## See Also

- `specs/seed_architecture.md` - Overall system architecture
- `specs/06-llm-integration-and-extractor.md` - LLM integration details
- `kg_forge/extraction/config_driven.py` - Implementation
- `kg_forge/ontology/schema.py` - OntologySchema with to_entity_config()
- `tests/test_extraction/test_config_driven.py` - Test suite
