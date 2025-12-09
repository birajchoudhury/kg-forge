# Contracts Ontology Pack - Setup Complete

## Summary

The Contracts Ontology Pack is now fully functional and ready for use in KG Forge. This ontology provides comprehensive support for contract analysis including entities like Contract, Organization, Person, and various occurrence entities (Clause, Signature, Renewal, Price Increase).

## Components

### 1. Pack Structure
```
ontology_packs/contracts/
├── pack.yaml                    # Pack metadata and styling
└── contracts_ontology.ttl       # TTL ontology definition
```

### 2. Ontology Content
- **10 Entity Types**: Core entities (Contract, Organization, Person) and occurrence entities
- **17 Relation Types**: Relationships between entities (HAS_PARTY, HAS_SIGNATORY, etc.)
- **Comprehensive Properties**: Contract dates, terms, values, contact info, etc.

## Usage

### Python API (Recommended for Python 3.9 users)

```python
from kg_forge.ontology_manager import get_ontology_manager

# 1. Get ontology manager
ontology_manager = get_ontology_manager()

# 2. Activate contracts pack
ontology_manager.set_active_ontology('contracts')

# 3. Load schema
active_pack = ontology_manager.get_active_ontology()
schema = active_pack.load_ontology_schema()

# 4. Convert to entity config for LLM extraction
config = schema.to_entity_config()

# 5. Use with config-driven extraction
from kg_forge.extraction.config_driven import ConfigDrivenExtractor

extractor = ConfigDrivenExtractor(
    entity_config=config,
    llm_provider="bedrock",
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
)

# Extract entities from contract text
result = extractor.extract(text="Your contract text here...")
```

### CLI (Requires Python 3.10+)

⚠️ **Note**: CLI commands require Python 3.10+ due to `glirel` dependency. If you're on Python 3.9, use the Python API above.

```bash
# List available packs
kg-forge ontology list

# Activate contracts pack
kg-forge ontology activate contracts

# Show pack info
kg-forge ontology show
```

## Known Issues

### Python 3.9 Compatibility

The CLI does not work on Python 3.9 due to the `glirel` library requiring Python 3.10+. Error:
```
ImportError: glirel requires Python 3.10 or newer
```

**Workaround**: Use the Python API directly (as shown above) instead of CLI commands.

**Fix Applied**: Made glirel imports lazy in `kg_forge/extraction/__init__.py` to allow LLM and fake extractors to work on Python 3.9.

### Real LLM Extraction Required

The fake LLM mode (`--fake-llm`) returns hardcoded entities ("Product", "Technology") and does not use the contracts ontology. For actual entity extraction with the contracts ontology, you must:

1. **Remove `--fake-llm` flag** or use real AWS Bedrock credentials
2. **Ensure AWS credentials are valid** in `.env` or `kg_forge.yaml`
3. **Use chunking for large documents** (recommended):

```bash
# Real extraction with chunking (RECOMMENDED for contract documents)
python -m kg_forge.cli.main ingest --source test_data\ --namespace contracts --curator hyland_ke --extractor llm --chunking on

# Or using Python API with config-driven extraction
from kg_forge.extraction.config_driven import ConfigDrivenExtractor

extractor = ConfigDrivenExtractor(
    entity_config=config,  # From schema.to_entity_config()
    llm_provider="bedrock",
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",  # Sonnet recommended
    chunk_size=8000,  # Adjust based on model
    chunk_overlap=500
)

result = extractor.extract(text=content)
```

**Why Chunking?**
Contract documents are typically 50k-100k+ characters. Without chunking, the LLM may:
- Return empty responses (prompt too large)
- Exceed token limits
- Miss entities due to context window constraints

**Alternative Models:**
- Claude 3.5 Sonnet: Better for complex contracts (200k context)
- Claude 3 Haiku: Faster but may need smaller chunks (200k context)

Use `--model` parameter to override:
```bash
python -m kg_forge.cli.main ingest --source test_data\ --namespace contracts --curator hyland_ke --extractor llm --chunking on --model us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

### Config File Takes Precedence

Make sure `kg_forge.yaml` has the correct ontology pack set:

```yaml
app:
  ontology_pack: contracts  # Must be 'contracts' not 'ai_ml_confluence'
```

The CLI loads the default pack from config even if you activate a different one programmatically.

## Testing

Run the test scripts to verify setup:

```bash
# Test pack registration
python test_contracts_pack_registration.py

# Test extraction workflow
python test_contracts_extraction.py
```

Expected output:
```
✓ Pack structure is valid
✓ Pack 'contracts' registered successfully
✓ Schema loaded: 10 entities, 17 relations
✓ Config generated with 10 entities
```

## Entity Types

### Core Entities
- **Contract**: Legal contract between parties
- **Organization**: Legal entity (customer/vendor)
- **Person**: Natural person (signatory, contact)

### Occurrence Entities
- **Clause Occurrence**: Specific clause instance in contract
- **Signature Event**: Signature action with date/location
- **Renewal Event**: Contract renewal occurrence
- **Price Increase Event**: Price adjustment occurrence

## Sample Extraction

```python
# Example: Extract from contract text
contract_text = """
MASTER SERVICES AGREEMENT

This Agreement is entered into on January 15, 2024 between:
- ACME Corporation, a Delaware corporation ("Customer")
- TechVendor Inc., a California corporation ("Vendor")

Initial Term: 3 years ending January 14, 2027
Total Contract Value: $500,000 USD
Auto-Renewal: Yes, for successive 1-year terms
Notice Period: 90 days prior to renewal

Signed by:
John Smith, CEO, ACME Corporation, Date: January 15, 2024
Jane Doe, VP Sales, TechVendor Inc., Date: January 15, 2024
"""

result = extractor.extract(text=contract_text)

# Result will include:
# - Contract entity with dates, terms, value
# - Organization entities (ACME Corporation, TechVendor Inc.)
# - Person entities (John Smith, Jane Doe)
# - Signature Event occurrences
# - Relationships (HAS_CUSTOMER, HAS_VENDOR, HAS_SIGNATORY, etc.)
```

## Next Steps

1. **Ingest Pipeline**: Use `kg-forge ingest` to load extracted entities into Neo4j
2. **Graph Rendering**: Visualize contract relationships with `kg-forge render`
3. **Query**: Query the knowledge graph for contract analysis
4. **Extend Ontology**: Add custom entity types or properties as needed

## Changes Made

### 1. Created `pack.yaml`
Added complete metadata with styling configuration for visualization.

### 2. Updated Validation Logic
Modified `kg_forge/ontology/base.py` to support TTL-only packs:
- No longer requires `entities/` directory for TTL packs
- Validates TTL packs by checking for `.ttl` files
- Skips entity definition check for TTL-based packs

### 3. Updated Entity Loading
Modified `kg_forge/ontology/filesystem_pack.py` to gracefully handle TTL packs without entity definitions.

## Related Documentation

- **TTL Ontology Format**: See `kg_forge/ontology/ttl_loader.py` for TTL parsing
- **Config-Driven Extraction**: See `docs/CONFIG_DRIVEN_EXTRACTION.md`
- **Ontology Schema**: See `kg_forge/ontology/schema.py` for schema structure
- **Entity Definitions**: See `kg_forge/entities/models.py` for entity models
