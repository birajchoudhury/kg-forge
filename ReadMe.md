# Knowledge Graph Forge (kg-forge)

[![CI](https://github.com/birajchoudhury/kg-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/birajchoudhury/kg-forge/actions/workflows/ci.yml)
![Coverage](https://raw.githubusercontent.com/birajchoudhury/kg-forge/badges/.github/coverage.svg)
![Tests](https://img.shields.io/badge/tests-577%20passed-brightgreen)

A comprehensive CLI tool for building knowledge graphs from unstructured documents. Extract entities and relationships using flexible curation and extraction backends, with built-in deduplication and interactive graph visualization.

## Description

Knowledge Graph Forge is a powerful command-line tool that transforms unstructured documents into structured knowledge graphs. It provides flexible document curation, multiple extraction backends, advanced deduplication capabilities, and interactive visualization tools.

### Key Features

- **Flexible Document Curation**: Choose between Docling (local, fast) or Hyland Knowledge Enrichment (cloud-based, optimized)
- **Multiple Extraction Approaches**: 
  - **Config-Driven**: Define entity schemas with core/occurrence entity types and dependencies in JSON config
  - **Schema-Driven**: Extract structured entities with properties, links, and span information using LLM
  - **LLM-based**: Full entity and relation extraction using AWS Bedrock
  - **Neural NLP**: Zero-shot extraction with spaCy + GLiNER + GLiREL (no training required)
  - **Hybrid**: Combines GLiNER entity detection with LLM property/relation enrichment
- **Ontology Format Support**: 
  - TTL (Turtle/RDF) format with automatic conversion to extraction configs
  - Markdown format for simple entity definitions
  - JSON entity configs with core/occurrence entities and dependencies
- **Advanced Entity Deduplication**: Built-in support for Splink (probabilistic) and Zingg (ML-based) deduplication
- **Ontology Management**: Define entity types, relationships, and extraction rules using modular, swappable ontology packs
- **Interactive Visualization**: Generate beautiful HTML visualizations of knowledge graphs and ontologies
- **Neo4j Integration**: Full Neo4j support with namespace isolation for multi-tenant experimentation
- **Production Ready**: Comprehensive test suite (577+ passing) with both unit and integration testing

The tool addresses key challenges in knowledge graph construction:
- How to curate and extract meaningful entities from diverse document formats (HTML, PDF, DOCX, TXT, XML)
- Optimal strategies for storing, organizing, merging, and pruning knowledge graphs
- Creating and evolving useful ontologies for domain-specific use cases
- Scaling entity resolution and deduplication across large document collections

## Project Structure

```
kg_forge/
├── kg_forge/                    # Main package  
│   ├── cli/                     # CLI commands (15+ commands)
│   │   ├── main.py              # Main CLI entry point
│   │   ├── ingest.py            # Complete ingestion pipeline
│   │   ├── query.py             # Knowledge graph querying
│   │   ├── render.py            # Graph visualization
│   │   ├── render_ontology.py   # Ontology visualization
│   │   ├── parse.py             # Document parsing and exploration
│   │   ├── extract_test.py      # Extraction backend testing
│   │   ├── entities.py          # Entity management (legacy CLI)
│   │   ├── ontology.py          # Ontology pack management
│   │   ├── neo4j_ops.py         # Neo4j operations
│   │   └── export_entities.py   # Entity export
│   ├── curation/                # Document curation backends
│   │   ├── factory.py           # Curation backend factory
│   │   ├── docling_backend.py   # Docling (local processing)
│   │   ├── hyland_backend.py    # Hyland KE (cloud API)
│   │   ├── base.py              # Base interfaces
│   │   └── errors.py            # Curation exceptions
│   ├── extraction/              # Entity extraction backends
│   │   ├── interface.py         # Common interfaces
│   │   ├── config_driven.py     # Config-driven extraction (core + occurrence entities)
│   │   ├── schema_driven_extractor.py  # Schema-driven structured extraction
│   │   ├── llm_backend.py       # LLM-based extraction
│   │   ├── spacy_backend.py     # Neural NLP pipeline (GLiNER + GLiREL)
│   │   ├── hybrid_backend.py    # Hybrid GLiNER + LLM extraction
│   │   ├── fake_backend.py      # Testing backend
│   │   └── exceptions.py        # Extraction exceptions
│   ├── llm/                     # LLM integrations
│   │   ├── bedrock_client.py    # AWS Bedrock client
│   │   ├── bedrock_extractor.py # Bedrock extraction wrapper
│   │   ├── prompt_builder.py    # Prompt construction
│   │   ├── response_parser.py   # JSON response parsing
│   │   ├── client.py            # Base LLM client
│   │   ├── parser.py            # Response parsing utilities
│   │   ├── fake_extractor.py    # Fake LLM for testing
│   │   └── exceptions.py        # LLM-specific exceptions
│   ├── dedup/                   # Deduplication backends
│   │   ├── interface.py         # Common interfaces
│   │   ├── splink_backend.py    # Probabilistic deduplication
│   │   ├── zingg_backend.py     # ML-based deduplication
│   │   ├── ensemble_backend.py  # Combined approach
│   │   └── no_dedup_backend.py  # Pass-through backend
│   ├── linking/                 # Entity linking
│   │   ├── interface.py         # Linking interfaces
│   │   └── default_linker.py    # Canonical entity resolution
│   ├── nlp/                     # Neural NLP components
│   │   ├── spacy_pipeline.py    # spaCy integration
│   │   ├── gliner_wrapper.py    # GLiNER entity recognition
│   │   └── glirel_wrapper.py    # GLiREL relation extraction
│   ├── ontology/                # Ontology management system
│   │   ├── base.py              # Base classes and registry
│   │   ├── filesystem_pack.py   # File-based ontology packs
│   │   ├── schema.py            # Normalized OntologySchema with dependencies support
│   │   ├── ttl_loader.py        # TTL/RDF ontology loader (industry standard)
│   │   ├── ttl_to_config.py     # TTL to JSON config converter
│   │   ├── markdown_loader.py   # Markdown ontology loader (legacy)
│   │   └── models.py            # Ontology data models (deprecated, use entities/)
│   ├── entities/                # Entity definition system
│   │   ├── definitions.py       # Entity definition loader
│   │   └── models.py            # Entity type models
│   ├── graph/                   # Graph database abstraction
│   │   ├── neo4j_client.py      # Neo4j client wrapper
│   │   ├── schema.py            # Schema management
│   │   └── exceptions.py        # Graph exceptions
│   ├── ingest/                  # Ingestion pipeline
│   │   ├── pipeline.py          # Complete pipeline orchestration
│   │   ├── filesystem.py        # File discovery
│   │   ├── hooks.py             # Hook system
│   │   └── metrics.py           # Pipeline metrics
│   ├── render/                  # Visualization engines
│   │   ├── graph_renderer.py    # Knowledge graph visualization
│   │   └── ontology_visualizer.py # Ontology visualization
│   ├── parsers/                 # HTML parsing utilities
│   │   ├── html_parser.py       # Confluence HTML parser
│   │   └── document_loader.py   # Bulk document loading
│   ├── models/                  # Data models
│   │   ├── lexical.py           # Lexical graph models
│   │   ├── curation.py          # Curation result models
│   │   ├── dedup.py             # Deduplication models
│   │   └── document.py          # Document models
│   ├── config/                  # Configuration system
│   │   └── settings.py          # Pydantic-based config
│   ├── hooks/                   # Extensibility hooks
│   │   ├── registry.py          # Hook registry
│   │   └── examples/            # Example hook implementations
│   ├── utils/                   # Common utilities
│   │   ├── hashing.py           # Content hashing
│   │   ├── logging.py           # Logging setup
│   │   └── interactive.py       # Interactive session
│   └── ontology_manager.py      # Global ontology manager
├── tests/                       # Test suite (475+ tests)
│   ├── test_cli/                # CLI command tests
│   ├── test_config/             # Configuration tests
│   ├── test_curation/           # Curation backend tests
│   │   ├── test_docling_backend.py    # Docling tests
│   │   ├── test_hyland_backend.py     # Hyland KE tests (29 tests)
│   │   └── test_factory.py            # Factory tests
│   ├── test_extraction/         # Extraction backend tests
│   ├── test_llm/                # LLM integration tests
│   ├── test_parsers/            # Parser tests
│   ├── test_entities/           # Entity definition tests
│   ├── test_dedup/              # Deduplication tests
│   ├── test_linking/            # Entity linking tests
│   ├── test_models/             # Data model tests
│   ├── test_render/             # Visualization tests
│   ├── test_graph/              # Graph database tests
│   │   ├── conftest.py          # Shared fixtures (Rancher-compatible)
│   │   └── test_integration.py  # Integration tests (Docker)
│   ├── test_cli_e2e.py          # End-to-end CLI tests
│   ├── test_core_integration.py # Core integration tests
│   └── test_end_to_end.py       # Full pipeline tests
├── ontology_packs/              # Ontology pack definitions
│   ├── contracts/               # Contracts domain ontology (TTL format)
│   │   ├── ontology.ttl         # Contract entity definitions in RDF/OWL
│   │   └── pack.yaml            # Pack metadata
│   └── confluence/              # Confluence documentation ontology
│       ├── entities/            # Entity type definitions (Markdown)
│       ├── templates/           # Prompt templates
│       ├── styles/              # Visualization styles
│       └── ontology.yaml        # Pack configuration
├── specs/                       # Implementation specifications
│   ├── seed_product.md          # Product vision
│   ├── seed_architecture.md     # Architecture specification
│   ├── 00-cli-foundation.md     # CLI foundation
│   ├── 01-ontology-management.md            # Ontology system
│   ├── 02-ontology-visualization.md         # Ontology rendering
│   ├── 03-html-parsing-and-document-model.md # Document parsing
│   ├── 04-load-entity-definitions.md        # Entity loading
│   ├── 05-neo4j-bootstrap.md                # Neo4j setup
│   ├── 06-llm-integration-and-extractor.md  # LLM extraction
│   ├── 07-ingest-pipeline.md                # Pipeline orchestration
│   └── 08-graph-rendering-and-exploration.md # Graph visualization
├── docs/                        # Documentation
│   ├── CONFIG_DRIVEN_EXTRACTION.md  # Config-driven extraction guide
│   ├── CONTRACTS_ONTOLOGY_SETUP.md  # Contracts ontology setup
│   ├── CI_SETUP.md              # CI/CD setup guide
│   ├── HYLAND_KE_IMPLEMENTATION.md  # Hyland KE guide
│   ├── ONTOLOGY_PACKS.md        # Ontology pack system
│   ├── PARSING_HTML.md          # HTML parsing
│   └── AWS_AUTHENTICATION.md    # AWS credentials setup
├── examples/                    # Usage examples
│   └── config_driven_extraction_example.py  # Config-driven extraction demo
├── test_data/                   # Test documents
├── requirements.txt             # Project dependencies
├── setup.py                     # Package setup file
├── docker-compose.yml           # Neo4j container configuration
├── .env.example                 # Example environment variables
├── kg_forge.yaml.example        # Example YAML configuration
└── .gitignore                   # Git ignore file
```

**Note on structure:**
- `parsers/` and `entities/` directories are actively used (not legacy)
- `parsers/` provides HTML parsing utilities used by the `parse` CLI command
- `entities/` contains the entity definition system used by ontology packs
- Root-level test scripts (e.g., `test_real_hyland_e2e.py`, `test_docling_e2e.py`) are development/validation scripts, not part of the main package

## Installation

### Prerequisites

- Python 3.11 or higher
- Neo4j instance (for graph operations - Docker supported)
- **For document curation** (choose one or both):
  - **Docling**: Local processing (included in dependencies, no credentials needed)
  - **Hyland Knowledge Enrichment**: Cloud API (requires OAuth credentials - see Configuration)
- **For entity extraction** (choose one or combine):
  - **LLM-based**: AWS account with Bedrock access (requires AWS credentials)
  - **Neural NLP**: spaCy + GLiNER + GLiREL models (auto-downloads ~3.5GB on first use, no credentials)
  - **Hybrid**: Combines GLiNER entity detection with LLM property extraction (requires AWS credentials)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd kg-forge
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the package in development mode:**
   ```bash
   pip install -e .
   ```

4. **Configure your environment:**
   ```bash
   # Copy example files
   cp .env.example .env
   cp kg_forge.yaml.example kg_forge.yaml

   # Edit configuration with your settings
   # nano .env
   # nano kg_forge.yaml
   ```

## Quick Start

### 1. Start Neo4j Database
```bash
# Start Neo4j using Docker Compose
kg-forge neo4j start

# Initialize database schema
kg-forge neo4j init-schema

# Check connection
kg-forge neo4j status
```

### 2. Configure Credentials (as needed)

**For Docling (local curation) - No configuration needed**

**For Hyland Knowledge Enrichment (cloud curation):**
```bash
# Add to .env
echo "HYLAND_KE_CLIENT_ID=your-client-id" >> .env
echo "HYLAND_KE_CLIENT_SECRET=your-client-secret" >> .env
```

**For AWS Bedrock (LLM extraction):**
```bash
# Add to .env  
echo "AWS_ACCESS_KEY_ID=your-key" >> .env
echo "AWS_SECRET_ACCESS_KEY=your-secret" >> .env
echo "AWS_DEFAULT_REGION=us-east-1" >> .env
```

### 3. Process Your First Documents
```bash
# Parse and explore content
kg-forge parse --source /path/to/documents/

# Test extraction on a single document
kg-forge extract-test sample.html --backend llm

# Run full ingestion pipeline (Docling + Bedrock LLM)
kg-forge ingest --source /path/to/documents/ --curator docling --extractor llm

# Use Hyland KE for curation with hybrid extraction
kg-forge ingest --source /path/to/documents/ --curator hyland_ke --extractor hybrid

# Query results
kg-forge query list-types
kg-forge query list-entities --type Product

# Generate visualization
kg-forge render --out my_graph.html
```

### 4. Try Different Backend Combinations
```bash
# Fast local processing: Docling + spaCy (no API calls)
kg-forge ingest --source /path/to/documents/ --curator docling --extractor spacy

# Cloud-optimized: Hyland KE + LLM
kg-forge ingest --source /path/to/documents/ --curator hyland_ke --extractor llm

# Best of both: Hyland KE + Hybrid (GLiNER precision + LLM enrichment)
kg-forge ingest --source /path/to/documents/ --curator hyland_ke --extractor hybrid

# Compare results across namespaces
kg-forge query list-entities --namespace default --type Product
```

## Usage

### Main Commands

kg-forge provides several commands for working with knowledge graphs:

#### Ingest Content
```bash
# Basic ingestion with Docling curation + Bedrock LLM extraction
kg-forge ingest --source <path/to/documents>

# Use Hyland Knowledge Enrichment for curation
kg-forge ingest --source <path> --curator hyland_ke --extractor llm

# Use neural NLP pipeline (spaCy + GLiNER + GLiREL, all local)
kg-forge ingest --source <path> --curator docling --extractor spacy

# Use hybrid extraction (GLiNER + LLM enrichment)
kg-forge ingest --source <path> --curator hyland_ke --extractor hybrid

# Configure deduplication backend
kg-forge ingest --source <path> --dedup-backend splink  # or zingg/both/none

# With namespace and other options
kg-forge ingest --source <path> --namespace test --dry-run --interactive

# Supported document formats: HTML, PDF, DOCX, PPTX, TXT, XML
```

#### Query Knowledge Graph
```bash
# List entity types
kg-forge query list-types

# List entities of a specific type
kg-forge query list-entities --type Product

# List all documents
kg-forge query list-docs

# Show document details
kg-forge query show-doc --id <doc-id>

# Find related entities
kg-forge query find-related --entity "Knowledge Discovery" --type Product
```

#### Extract Entities (Testing)
Test entity extraction backends without running the full ingestion pipeline:

```bash
# Test LLM-based extraction
kg-forge extract-test test-doc.html --backend llm

# Test neural NLP pipeline
kg-forge extract-test test-doc.html --backend spacy

# Filter by confidence threshold
kg-forge extract-test test-doc.html --min-confidence 0.7

# Output as JSON
kg-forge extract-test test-doc.html --format json

# Use fake backend for testing without API calls
kg-forge extract-test test-doc.html --backend fake
```

#### Visualization
```bash
# Render knowledge graph
kg-forge render --out graph.html --depth 3 --max-nodes 200

# Render ontology structure
kg-forge render-ontology --out ontology.html --layout force-directed --theme dark

# Render with custom layout and examples
kg-forge render-ontology --layout hierarchical --include-examples --theme light
```

#### Database Operations
```bash
# Start Neo4j database (via Docker Compose)
kg-forge neo4j start

# Stop Neo4j database
kg-forge neo4j stop

# Check Neo4j connection status
kg-forge neo4j status

# Initialize database schema
kg-forge neo4j init-schema

# Clear database (purge all data)
kg-forge neo4j clear-database --yes                    # Delete all namespaces
kg-forge neo4j clear-database --namespace test --yes   # Delete specific namespace only
kg-forge neo4j clear-database --namespace test         # Interactive confirmation
```

#### Ontology Management
```bash
# List available ontology packs
kg-forge ontology list

# Get detailed info about an ontology pack
kg-forge ontology info ai_ml_confluence

# Activate a specific ontology pack
kg-forge ontology activate ai_ml_confluence

# Validate ontology pack structure
kg-forge ontology validate --pack-dir custom_ontology/

# Discover and register new ontology packs
kg-forge ontology discover --directory /path/to/ontologies/
```

**Ontology Format Support:**
- **TTL (Turtle/RDF)**: Industry-standard format using RDF/OWL semantics (`.ttl` files)
  - Supports core/occurrence entity classification
  - Automatic dependency extraction from OWL restrictions
  - Converts to JSON entity config for config-driven extraction
- **JSON Entity Config**: Direct entity configuration with core/occurrence entities and dependencies
  - Core entities: Standalone entities extracted first
  - Occurrence entities: Event-like entities that link to core entities
  - Dependency specification with cardinality (1, 0..1, 1..*)
- **Markdown**: Legacy format for simple entity definitions (`entities/*.md` files)
- Automatic format detection based on files present in ontology pack
- All formats normalized to common `OntologySchema` for consistent extraction

#### Export/Import Operations
```bash
# Export entities from graph to markdown files
kg-forge export-entities --output-dir custom_entities/

# Export with specific namespace
kg-forge export-entities --namespace test --output-dir test_entities/
```

## Configuration Options

You can configure kg-forge using:

1. Command-line arguments (highest priority)
2. YAML configuration file (kg_forge.yaml or config.yaml)
3. Environment variables
4. .env file values
5. Default values (lowest priority)

### Example Environment Variables

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Document Curation (choose backend)
DEFAULT_CURATOR=docling                 # or 'hyland_ke'

# Hyland Knowledge Enrichment (if using hyland_ke curator)
HYLAND_KE_CLIENT_ID=your_client_id
HYLAND_KE_CLIENT_SECRET=your_client_secret
# Optional: override default endpoints
# HYLAND_KE_API_URL=https://knowledge-enrichment.ai.experience.hyland.com/latest/api/data-curation
# HYLAND_KE_OAUTH_URL=https://auth.iam.experience.hyland.com/idp/connect/token

# AWS Bedrock Configuration (if using LLM extractor)
AWS_ACCESS_KEY_ID=your_access_key_here  
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0

# Extraction Configuration
DEFAULT_EXTRACTOR=llm                   # or 'spacy' for neural pipeline
DEFAULT_DEDUP_BACKEND=splink            # or 'zingg', 'both', 'none'

# Application Configuration
LOG_LEVEL=INFO
DEFAULT_NAMESPACE=default
ONTOLOGY_PACK=ai_ml_confluence          # Optional: default ontology pack
```

### Example YAML Configuration

```yaml
# Neo4j Configuration
neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: password

# Hyland Knowledge Enrichment Configuration (optional)
hyland_ke:
  client_id: your_client_id
  client_secret: your_client_secret
  # Optional curation options:
  enable_chunking: false
  normalize_quotations: true
  normalize_dashes: true

# AWS Bedrock Configuration (optional)
aws:
  access_key_id: your_access_key_here
  secret_access_key: your_secret_key_here
  default_region: us-east-1
  bedrock_model_name: anthropic.claude-3-haiku-20240307-v1:0

# Application Configuration
app:
  log_level: INFO
  default_namespace: default
  default_curator: docling              # or 'hyland_ke'
  default_extractor: llm                # or 'spacy'
  default_dedup_backend: splink         # or 'zingg', 'both', 'none'
  ontology_pack: ai_ml_confluence       # Optional
```

## Development

### Running Tests

kg-forge includes comprehensive unit and integration tests.

#### Unit Tests (Fast, No Dependencies)

```bash
# Activate virtual environment first
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run all unit tests
pytest tests/test_cli tests/test_parsers tests/test_entities tests/test_graph/test_entity_repo.py -v

# Run specific test module
pytest tests/test_graph/test_entity_repo.py -v

# With coverage report
pytest --cov=kg_forge tests/
```

#### Integration Tests (Requires Docker or Rancher Desktop)

The integration tests spin up a real Neo4j container to test database operations end-to-end.

**For Docker Desktop:**
```bash
source venv/bin/activate
pytest tests/test_graph/test_integration.py -v -s
```

**For Rancher Desktop:**
```bash
source venv/bin/activate

# Option 1: Use --rancher flag
pytest tests/test_graph/test_integration.py -v -s --rancher

# Option 2: Use environment variable
USE_RANCHER=true pytest tests/test_graph/test_integration.py -v -s
```

The integration tests cover:
- Schema management (constraints & indexes)
- Entity CRUD operations
- Entity relationships
- Document operations
- Document-entity linking (MENTIONS relationships)
- Namespace isolation

#### Test Coverage

- **Unit Tests**: 490+ tests covering all components (CLI, curation, extraction, deduplication, linking, parsers, ontology management)
- **Integration Tests**: 90+ tests with real Neo4j database operations and end-to-end pipeline testing
- **Total**: 577 passing tests (97% pass rate) with continuous integration
- **Coverage**: Extensive coverage of core functionality, edge cases, and error conditions including:
  - Config-driven extraction with core/occurrence entities
  - Schema-driven extraction with structured output
  - TTL to config conversion
  - Enhanced OntologySchema with dependencies
  - Real-world API testing for Hyland KE and AWS Bedrock

## Features

### ✅ Complete Implementation

**Core Pipeline Architecture**
- Flexible document curation: Docling (local, fast) and Hyland KE (cloud-based, optimized)
- Multiple extraction backends: LLM-based (AWS Bedrock), neural NLP (spaCy + GLiNER + GLiREL), and Hybrid (GLiNER + LLM)
- Advanced deduplication: Splink (probabilistic) and Zingg (ML-based) backends
- Entity linking and canonical entity management
- Complete ingestion pipeline with hooks and extensibility

**Content Processing**
- Multi-format document support: HTML, PDF, DOCX, PPTX, TXT, XML
- Dual curation backends with automatic format detection
- Markdown conversion with metadata extraction
- Content hash-based change detection
- Bulk document processing with progress tracking

**Knowledge Graph Management**
- Neo4j integration with full schema management
- Namespace isolation for multi-tenant experimentation  
- Entity and document repositories with relationship management
- Comprehensive query and manipulation capabilities

**Ontology System**
- Industry-standard TTL (Turtle/RDF) ontology support with automatic parsing
- TTL to JSON entity config converter for config-driven extraction
- Support for core/occurrence entity types with dependencies
- Cardinality specification for entity relationships (1, 0..1, 1..*)
- Legacy Markdown format support for backward compatibility
- Automatic format detection and normalization to unified `OntologySchema`
- Backend-specific config generation (GLiNER, GLiREL, LLM prompts, Entity Config)
- Dynamic ontology activation and validation
- Entity relationship schema management with domain/range constraints

**Visualization & Export**
- Interactive knowledge graph visualization (vis.js)
- Ontology structure visualization (Cytoscape.js) 
- Multiple layout algorithms and themes
- Entity export to markdown format

**Developer Experience**  
- Comprehensive CLI with 15+ commands
- Extensive test suite (577 passing tests, 97% pass rate) with full CI/CD pipeline
- Multiple extraction patterns: config-driven, schema-driven, backend-based
- Docker integration for Neo4j
- Rich configuration management (YAML + environment variables)
- Example scripts and detailed documentation
- Detailed logging and error handling

## Practical Use Cases

### Knowledge Graph Construction from Documentation
Extract entities and relationships from various document formats:
```bash
# Initial exploration of content
kg-forge parse --source ~/documents/ 

# Fast local processing (Docling + LLM)
kg-forge ingest --source ~/documents/ --curator docling --extractor llm --dedup-backend splink

# Cloud-optimized processing (Hyland KE + LLM)
kg-forge ingest --source ~/documents/ --curator hyland_ke --extractor llm --dedup-backend splink

# Best of both worlds: Hybrid extraction (GLiNER precision + LLM enrichment)
kg-forge ingest --source ~/documents/ --curator hyland_ke --extractor hybrid --dedup-backend splink

# Neural NLP pipeline for complete local processing (no API calls)
kg-forge ingest --source ~/documents/ --curator docling --extractor spacy --dedup-backend zingg
```

### Domain-Specific Entity Extraction
Use custom ontology packs for specialized domains:
```bash
# List available ontology packs
kg-forge ontology list

# Activate AI/ML domain ontology
kg-forge ontology activate ai_ml_confluence

# Run extraction with domain-specific definitions
kg-forge ingest --source ~/research_docs/ --extractor spacy
```

### Multi-Tenant Experimentation
Use namespaces to compare different backend combinations:
```bash
# Test different curation and extraction approaches
kg-forge ingest --source ~/docs/ --namespace docling_llm --curator docling --extractor llm
kg-forge ingest --source ~/docs/ --namespace hyland_hybrid --curator hyland_ke --extractor hybrid
kg-forge ingest --source ~/docs/ --namespace docling_spacy --curator docling --extractor spacy

# Compare results
kg-forge query list-entities --namespace docling_llm --type Product
kg-forge query list-entities --namespace hyland_llm --type Product
kg-forge query list-entities --namespace docling_spacy --type Product

# Visualize differences
kg-forge render --namespace docling_llm --out docling_llm_graph.html
kg-forge render --namespace hyland_llm --out hyland_llm_graph.html
kg-forge render --namespace docling_spacy --out docling_spacy_graph.html
```

### Interactive Development Workflow
```bash
# 1. Start with content exploration
kg-forge parse --source ~/new_content/ --show-content

# 2. Test extraction without persistence
kg-forge extract-test sample_doc.html --backend llm --format json

# 3. Dry-run full pipeline
kg-forge ingest --source ~/new_content/ --dry-run --interactive

# 4. Run actual ingestion
kg-forge ingest --source ~/new_content/ --namespace production

# 5. Visualize and analyze results
kg-forge render --namespace production --out results.html
```

### Architecture

**Extraction Pipeline Architecture:**
- `ExtractionBackend` interface with LLM, spaCy, and Hybrid implementations
- `DedupBackend` interface supporting Splink, Zingg, and ensemble methods
- `EntityLinkerBackend` for canonical entity resolution
- Extensible hook system for custom processing logic

**Graph Abstraction Layer:**
- `kg_forge/graph/base.py` - Abstract interfaces (GraphClient, SchemaManager, EntityRepository, DocumentRepository)
- `kg_forge/graph/factory.py` - Factory for backend-agnostic access  
- `kg_forge/graph/neo4j/` - Complete Neo4j implementation

**Ontology Management:**
- `OntologyPack` system for modular entity definitions
- Support for TTL (Turtle/RDF) and Markdown ontology formats
- `OntologySchema` normalization layer for backend-agnostic extraction
- Registry-based discovery and activation
- Filesystem-based ontology storage with validation
- Helper methods for generating backend-specific configs (GLiNER, GLiREL, LLM)

**Key Design Decisions:**
- Modular backend system for easy experimentation
- Single Entity label with entity_type property (flexible schema)  
- Canonical relationships with ontology-driven direction
- Namespace property on all nodes for multi-tenancy
- Content hash tracking for incremental processing
- Normalized entity names for fuzzy matching and deduplication

## License

MIT License - see LICENSE file for details.