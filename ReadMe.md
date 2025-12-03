# Knowledge Graph Forge (kg-forge)

[![CI](https://github.com/birajchoudhury/kg-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/birajchoudhury/kg-forge/actions/workflows/ci.yml)
![Coverage](https://raw.githubusercontent.com/birajchoudhury/kg-forge/badges/.github/coverage.svg)
![Tests](https://img.shields.io/badge/tests-387%20passed-brightgreen)

A comprehensive CLI tool for building knowledge graphs from unstructured content. Extract entities and relationships using either LLM-based extraction or advanced neural NLP pipelines (spaCy + GLiNER + GLiREL), with built-in deduplication and interactive graph visualization.

## Description

Knowledge Graph Forge is a powerful command-line tool designed to extract entities and relationships from unstructured content and build sophisticated knowledge graphs. It provides flexible extraction backends, advanced deduplication capabilities, and interactive visualization tools.

### Key Features

- **Dual Extraction Pipelines**: Choose between LLM-based extraction (AWS Bedrock) or neural NLP pipelines (spaCy + GLiNER + GLiREL)
- **Advanced Entity Deduplication**: Built-in support for Splink (probabilistic) and Zingg (ML-based) deduplication backends
- **Ontology Management**: Flexible ontology pack system for defining entity types, relationships, and extraction rules
- **Interactive Visualization**: Generate beautiful HTML visualizations of your knowledge graphs and ontologies
- **Neo4j Integration**: Full Neo4j support with namespace isolation for multi-tenant experimentation
- **Production Ready**: Comprehensive test suite (387+ tests) with both unit and integration testing

The tool addresses key challenges in knowledge graph construction:
- How to extract meaningful entities and topics from diverse content sources
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
│   │   ├── parse.py             # HTML parsing and exploration
│   │   ├── extract_test.py      # Extraction backend testing
│   │   ├── entities.py          # Entity management
│   │   ├── ontology.py          # Ontology pack management
│   │   ├── neo4j_ops.py         # Neo4j operations
│   │   └── export_entities.py   # Entity export
│   ├── extraction/              # Extraction backends
│   │   ├── llm_backend.py       # LLM-based extraction
│   │   ├── spacy_backend.py     # Neural NLP pipeline
│   │   ├── fake_backend.py      # Testing backend
│   │   └── interface.py         # Common interfaces
│   ├── dedup/                   # Deduplication backends
│   │   ├── splink_backend.py    # Probabilistic deduplication
│   │   ├── zingg_backend.py     # ML-based deduplication
│   │   ├── ensemble_backend.py  # Combined approach
│   │   └── no_dedup_backend.py  # Pass-through backend
│   ├── linking/                 # Entity linking
│   │   └── entity_linker.py     # Canonical entity resolution
│   ├── nlp/                     # Neural NLP components
│   │   ├── spacy_wrapper.py     # spaCy integration
│   │   ├── gliner_wrapper.py    # GLiNER entity recognition
│   │   └── glirel_wrapper.py    # GLiREL relation extraction
│   ├── ontology/               # Ontology management system
│   │   ├── base.py             # Base classes and registry
│   │   ├── filesystem_pack.py  # File-based ontology packs
│   │   └── models.py           # Ontology data models
│   ├── graph/                  # Graph database abstraction
│   │   ├── base.py             # Abstract interfaces
│   │   ├── factory.py          # Backend factory
│   │   └── neo4j/              # Neo4j implementation
│   ├── ingest/                 # Ingestion pipeline
│   │   └── pipeline.py         # Complete pipeline orchestration
│   ├── render/                 # Visualization engines
│   │   ├── graph_renderer.py   # Knowledge graph visualization
│   │   └── ontology_renderer.py # Ontology visualization
│   ├── parsers/                # Content parsing
│   │   ├── html_parser.py      # Confluence HTML parsing
│   │   └── document_loader.py  # Bulk document loading
│   ├── entities/               # Legacy entity management
│   ├── models/                 # Data models
│   ├── config/                 # Configuration system
│   ├── hooks/                  # Extensibility hooks
│   ├── llm/                    # LLM integrations
│   └── utils/                  # Common utilities
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_cli/           # CLI tests
│   ├── test_config/        # Config tests
│   ├── test_parsers/       # Parser tests
│   ├── test_entities/      # Entity tests
│   └── test_graph/         # Graph database tests
│       ├── __init__.py
│       ├── conftest.py     # Shared fixtures (Rancher-compatible)
│       ├── test_entity_repo.py    # Unit tests (mocks)
│       └── test_integration.py    # Integration tests (Docker)
├── ontology_packs/         # Ontology pack definitions
│   └── ai_ml_confluence/   # AI/ML domain ontology pack
│       ├── entities/       # Entity type definitions
│       ├── templates/      # Prompt templates
│       ├── styles/         # Visualization styles
│       └── ontology.yaml   # Pack configuration
├── specs/                  # Specification documents
│   ├── seed.md             # Initial specification
│   ├── 01-cli-foundation.md         # CLI foundation
│   ├── 02-html-parsing-and-document-model.md  # HTML parsing
│   ├── 03-entity-definitions-loading.md  # Entity loading
│   └── 04-neo4j-bootstrap.md        # Neo4j implementation
├── docs/                   # Documentation
│   ├── CI_SETUP.md         # CI/CD setup guide
│   └── PARSING_HTML.md     # HTML parsing documentation
├── requirements.txt        # Project dependencies
├── setup.py               # Package setup file
├── docker-compose.yml     # Neo4j container configuration
├── .env.example           # Example environment variables
├── kg_forge.yaml.example  # Example YAML configuration
└── .gitignore             # Git ignore file
```

## Installation

### Prerequisites

- Python 3.11 or higher
- Neo4j instance (for graph operations - Docker supported)
- **For LLM-based extraction**:
  - AWS account with Bedrock access
- **For neural NLP pipeline** (automatic installation):
  - spaCy models (en_core_web_sm)
  - GLiNER models (urchade/gliner_base - ~800MB)
  - GLiREL models (jackboyla/glirel-large-v0 - ~2.7GB)

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
kg-forge neo4j init

# Check connection
kg-forge neo4j status
```

### 2. Configure AWS Bedrock Access
```bash
# Add to .env  
echo "AWS_ACCESS_KEY_ID=your-key" >> .env
echo "AWS_SECRET_ACCESS_KEY=your-secret" >> .env
echo "BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0" >> .env
```

### 3. Process Your First Documents
```bash
# Parse and explore content
kg-forge parse --source /path/to/html/files/

# Test extraction on a single document
kg-forge extract-test sample.html --backend llm

# Run full ingestion pipeline
kg-forge ingest --source /path/to/html/files/

# Query results
kg-forge query list-types
kg-forge query list-entities --type Product

# Generate visualization
kg-forge render --out my_graph.html
```

### 4. Try the Neural NLP Pipeline
```bash
# Use spaCy + GLiNER + GLiREL (downloads ~3.5GB models on first use)
kg-forge ingest --source /path/to/html/files/ --extractor spacy --namespace neural_test

# Compare with LLM results
kg-forge query list-entities --namespace neural_test --type Product
```

## Usage

### Main Commands

kg-forge provides several commands for working with knowledge graphs:

#### Ingest Content
```bash
# Basic LLM-based ingest from source directory
kg-forge ingest --source <path/to/html/files>

# Use neural NLP pipeline (spaCy + GLiNER + GLiREL)
kg-forge ingest --source <path> --extractor spacy

# Configure deduplication backend
kg-forge ingest --source <path> --dedup-backend splink  # or zingg/both/none

# With namespace and other options
kg-forge ingest --source <path> --namespace test --dry-run --interactive
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
kg-forge neo4j init

# Clear namespace data
kg-forge neo4j clear --namespace test --confirm
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

# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=your_access_key_here  
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0

# Extraction Configuration
DEFAULT_EXTRACTOR=llm                    # or 'spacy' for neural pipeline
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

# AWS Bedrock Configuration
aws:
  access_key_id: your_access_key_here
  secret_access_key: your_secret_key_here
  default_region: us-east-1
  bedrock_model_name: anthropic.claude-3-haiku-20240307-v1:0

# Extraction Configuration
extraction:
  default_backend: llm                   # or 'spacy'
  default_dedup_backend: splink         # or 'zingg', 'both', 'none'

# Application Configuration
app:
  log_level: INFO
  default_namespace: default
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

- **Unit Tests**: 300+ tests covering all components (CLI, extraction, deduplication, linking, parsers, ontology management)
- **Integration Tests**: 87+ tests with real Neo4j database operations and end-to-end pipeline testing
- **Total**: 387+ comprehensive tests with continuous integration
- **Coverage**: Extensive coverage of core functionality, edge cases, and error conditions

## Features

### ✅ Complete Implementation

**Core Pipeline Architecture**
- Dual extraction backends: LLM-based (AWS Bedrock) and neural NLP (spaCy + GLiNER + GLiREL)
- Advanced deduplication: Splink (probabilistic) and Zingg (ML-based) backends
- Entity linking and canonical entity management
- Complete ingestion pipeline with hooks and extensibility

**Content Processing**
- HTML parsing and content curation (optimized for Confluence exports)
- Markdown conversion with metadata extraction
- Content hash-based change detection
- Bulk document processing with progress tracking

**Knowledge Graph Management**
- Neo4j integration with full schema management
- Namespace isolation for multi-tenant experimentation  
- Entity and document repositories with relationship management
- Comprehensive query and manipulation capabilities

**Ontology System**
- Flexible ontology pack system for entity type definitions
- Dynamic ontology activation and validation
- Prompt template merging for LLM extraction
- Entity relationship schema management

**Visualization & Export**
- Interactive knowledge graph visualization (vis.js)
- Ontology structure visualization (Cytoscape.js) 
- Multiple layout algorithms and themes
- Entity export to markdown format

**Developer Experience**  
- Comprehensive CLI with 15+ commands
- Extensive test suite (387+ tests) with 100% CI/CD pipeline
- Docker integration for Neo4j
- Rich configuration management (YAML + environment variables)
- Detailed logging and error handling

## Practical Use Cases

### Knowledge Graph Construction from Documentation
Extract entities and relationships from Confluence exports, wikis, or documentation:
```bash
# Initial exploration of content
kg-forge parse --source ~/confluence_export/ 

# LLM-based extraction with deduplication
kg-forge ingest --source ~/confluence_export/ --extractor llm --dedup-backend splink

# Neural NLP pipeline for higher precision
kg-forge ingest --source ~/confluence_export/ --extractor spacy --dedup-backend zingg
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
Use namespaces to compare extraction strategies:
```bash
# Test different extraction approaches
kg-forge ingest --source ~/docs/ --namespace llm_experiment --extractor llm
kg-forge ingest --source ~/docs/ --namespace spacy_experiment --extractor spacy

# Compare results
kg-forge query list-entities --namespace llm_experiment --type Product
kg-forge query list-entities --namespace spacy_experiment --type Product

# Visualize differences
kg-forge render --namespace llm_experiment --out llm_graph.html
kg-forge render --namespace spacy_experiment --out spacy_graph.html
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
- `ExtractionBackend` interface with LLM and spaCy implementations
- `DedupBackend` interface supporting Splink, Zingg, and ensemble methods
- `EntityLinkerBackend` for canonical entity resolution
- Extensible hook system for custom processing logic

**Graph Abstraction Layer:**
- `kg_forge/graph/base.py` - Abstract interfaces (GraphClient, SchemaManager, EntityRepository, DocumentRepository)
- `kg_forge/graph/factory.py` - Factory for backend-agnostic access  
- `kg_forge/graph/neo4j/` - Complete Neo4j implementation

**Ontology Management:**
- `OntologyPack` system for modular entity definitions
- Registry-based discovery and activation
- Filesystem-based ontology storage with validation

**Key Design Decisions:**
- Modular backend system for easy experimentation
- Single Entity label with entity_type property (flexible schema)  
- Canonical relationships with ontology-driven direction
- Namespace property on all nodes for multi-tenancy
- Content hash tracking for incremental processing
- Normalized entity names for fuzzy matching and deduplication

## License

MIT License - see LICENSE file for details.