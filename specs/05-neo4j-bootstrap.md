# Step 5: Neo4j Bootstrap

**Status**: Completed (Updated for Multi-Format Support)  
**Created**: 2025-11-28  
**Updated**: 2025-12-05  
**Related to**: Step 5 - Neo4j Database Connection and Schema Initialization

## Overview

Step 5 implements the Neo4j database foundation that establishes connections, initializes the graph schema, and provides CLI tools for database management. This step creates the database infrastructure needed to store documents and entities extracted in later steps, setting up proper constraints, indexes, and the basic graph schema that will support the knowledge graph operations.

Step 5 builds upon the entity definitions from Step 4 to create the corresponding database schema and provides the foundation for graph storage operations that will be used in Steps 6 and 7. It focuses purely on database connection, schema setup, and basic query capabilities without performing any content ingestion or entity extraction.

Step 5 explicitly does NOT:
- Call any LLMs or connect to Bedrock  
- Process HTML content or documents
- Perform entity extraction or content ingestion
- Implement complex graph algorithms or analytics

## Scope

### In Scope

- Establish reliable Neo4j database connections with proper configuration
- Initialize graph schema for `:Doc` and `:Entity` nodes as defined in the architecture
- Create indexes and constraints on merge keys (namespace, doc_id) and (namespace, entity_type, normalized_name)
- Implement CLI commands for database lifecycle management (create schema, clear database, health checks)
- Basic query operations to verify database connectivity and schema setup
- Integration tests using Docker-based Neo4j fixture in pytest
- Configuration management for Neo4j connection parameters (URI, credentials, database name)
- Error handling for database connection failures and schema conflicts

### Out of Scope

- Actual document or entity ingestion (handled in Step 6)
- LLM calls or AWS Bedrock integration
- Complex graph traversal or analytics queries
- Graph visualization or rendering capabilities  
- Entity deduplication or merging logic
- Content processing or HTML parsing

## Neo4j Schema Design

### Node Types

Based on section 7.1 of the architecture document:

#### `:Doc` Nodes
Represents ingested documents (one document file = one Doc in v1). Supports multiple formats including HTML, PDF, DOCX, etc.

**Required Properties:**
- `namespace` (string): Experiment/environment name (e.g., "default")
- `doc_id` (string): Stable ID including file extension (e.g., "platform/kd/intro.html", "reports/q4.pdf")
- `source_path` (string): Relative file path (e.g., "platform/kd/intro.html", "reports/q4.pdf")
- `source_format` (string): Document format (e.g., "html", "pdf", "docx", "pptx")
- `content_hash` (string): MD5 of curated text (for change detection)

**Optional Properties:**
- `markdown_path` (string): Path to saved markdown representation (e.g., "output/markdowns/default/intro.html.md")
- `page_count` (int): Number of pages (for paginated formats like PDF)
- `file_size` (int): Source file size in bytes

**Merge Key:** `(namespace, doc_id)`

**Note:** The `doc_id` includes the file extension to allow the same logical document in different formats to coexist (e.g., both `intro.html` and `intro.pdf` can exist in the same namespace).

#### `:Entity` Nodes  
Represents both entities and topics extracted from content.

**Labels:**
- Always `:Entity`
- Optionally additional type-specific labels (e.g., `:Entity:Product`, `:Entity:Topic`)

**Required Properties:**
- `namespace` (string): Experiment/environment name
- `entity_type` (string): Type from entity definitions (e.g., "Product", "Team", "Topic")
- `name` (string): Canonical name (e.g., "Knowledge Discovery")
- `normalized_name` (string): Normalized name for matching (lowercase, trimmed, punctuation removed)

**Merge Key:** `(namespace, entity_type, normalized_name)`

### Relationship Types

#### `:MENTIONS` Relationships
Links documents to entities they mention: `(:Doc)-[:MENTIONS]->(:Entity)`

**Required Properties:**
- `namespace` (string): Same namespace as connected nodes

#### Typed Domain Relationships
Entity-to-entity relationships based on ontology: `(:Entity)-[:<RELATION_TYPE>]->(:Entity)`

**Examples:** `:WORKS_ON`, `:USES`, `:OWNED_BY`, etc. (derived from entity definition relations)

**Required Properties:**
- `namespace` (string): Same namespace as connected nodes

### Multi-Format Document Strategy

The schema supports ingesting the same logical document in multiple formats:

**Example:**
- `doc_id: "platform/intro.html"` → HTML version from Confluence export
- `doc_id: "platform/intro.pdf"` → PDF version of same document

Both can coexist in the same namespace as separate `:Doc` nodes because `doc_id` includes the file extension. This allows:
- Comparing extraction quality across formats
- Handling scenarios where different formats contain different information
- Clear provenance of which format was used for extraction

### Constraints and Indexes

```cypher
-- Unique constraints (serve as both constraint and index)
CREATE CONSTRAINT doc_unique FOR (d:Doc) REQUIRE (d.namespace, d.doc_id) IS UNIQUE;
CREATE CONSTRAINT entity_unique FOR (e:Entity) REQUIRE (e.namespace, e.entity_type, e.normalized_name) IS UNIQUE;

-- Additional indexes for query performance  
CREATE INDEX doc_namespace FOR (d:Doc) ON (d.namespace);
CREATE INDEX doc_content_hash FOR (d:Doc) ON (d.content_hash);
CREATE INDEX doc_source_format FOR (d:Doc) ON (d.source_format);
CREATE INDEX entity_namespace FOR (e:Entity) ON (e.namespace);
CREATE INDEX entity_type FOR (e:Entity) ON (e.entity_type);
CREATE INDEX entity_name FOR (e:Entity) ON (e.name);
```

**Index on `source_format`** enables efficient filtering by document type:
```cypher
// Find all PDF documents in namespace
MATCH (d:Doc {namespace: 'default', source_format: 'pdf'})
RETURN d.doc_id, d.source_path
```

## Data Structures & Neo4j APIs

### Core Models

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from pathlib import Path

@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"  
    password: str = "password"
    database: str = "neo4j"

@dataclass
class DocNode:
    """Represents a :Doc node in Neo4j."""
    namespace: str
    doc_id: str  # Includes extension: "platform/intro.html"
    source_path: str
    source_format: str  # "html", "pdf", "docx", etc.
    content_hash: str
    markdown_path: Optional[str] = None
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    
@dataclass
class SchemaConstraint:
    """Database constraint definition."""
    name: str
    node_label: str
    properties: List[str]
    constraint_type: str = "UNIQUE"

@dataclass  
class SchemaIndex:
    """Database index definition."""
    name: str
    node_label: str
    properties: List[str]
```

### Neo4j Client API

```python
# kg_forge/graph/neo4j_client.py
from neo4j import GraphDatabase
from typing import List, Dict, Any

class Neo4jClient:
    """Neo4j database client with schema management."""
    
    def __init__(self, config: Neo4jConfig):
        """Initialize client with connection configuration."""
        self.config = config
        self.driver = None
        
    def connect(self) -> None:
        """
        Establish connection to Neo4j database.
        
        Raises:
            Neo4jConnectionError: If connection fails
        """
        
    def disconnect(self) -> None:
        """Close database connection and clean up resources."""
        
    def test_connection(self) -> bool:
        """Test database connectivity and return status."""
        
    def initialize_schema(self) -> None:
        """
        Create all constraints and indexes for KG Forge schema.
        
        - Creates unique constraints for Doc and Entity nodes
        - Creates performance indexes
        - Handles existing constraints gracefully
        """
        
    def clear_database(self, namespace: Optional[str] = None) -> int:
        """
        Clear all nodes and relationships, optionally filtered by namespace.
        
        Args:
            namespace: If provided, only clear nodes in this namespace
            
        Returns:
            Number of nodes deleted
        """
        
    def get_schema_info(self) -> Dict[str, Any]:
        """Return current database schema information (constraints, indexes)."""
        
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """Execute arbitrary Cypher query and return results."""
        
    def get_entity_types(self, namespace: str = "default") -> List[str]:
        """Get list of distinct entity_type values in namespace."""
        
    def get_node_counts(self, namespace: str = "default") -> Dict[str, int]:
        """Get count of Doc and Entity nodes by namespace."""
```

### Schema Management API

```python
# kg_forge/graph/schema.py
class SchemaManager:
    """Manages Neo4j schema initialization and validation."""
    
    def __init__(self, client: Neo4jClient):
        self.client = client
        
    def get_required_constraints(self) -> List[SchemaConstraint]:
        """Return list of constraints required for KG Forge schema."""
        
    def get_required_indexes(self) -> List[SchemaIndex]:
        """Return list of indexes required for KG Forge schema."""
        
    def create_constraints(self, constraints: List[SchemaConstraint]) -> None:
        """Create database constraints, handling existing ones gracefully."""
        
    def create_indexes(self, indexes: List[SchemaIndex]) -> None:
        """Create database indexes, handling existing ones gracefully."""
        
    def validate_schema(self) -> Dict[str, bool]:
        """Validate that all required constraints and indexes exist."""
```

## CLI Integration

### New CLI Commands

Add Neo4j management commands under the main CLI structure:

```bash
# Initialize Neo4j schema
kg-forge neo4j init-schema

# Test database connection  
kg-forge neo4j test-connection

# Show database status and schema info
kg-forge neo4j status

# Clear database (with confirmation)
kg-forge neo4j clear-database [--namespace TEXT] [--force]

# Start/stop local Neo4j (development helper)
kg-forge neo4j start
kg-forge neo4j stop
```

### Command Specifications

#### `neo4j init-schema`
```bash
kg-forge neo4j init-schema [--force]
```
- Creates all required constraints and indexes for KG Forge
- Validates schema after creation
- `--force`: Recreate constraints if they already exist
- Exit code 0 on success, 1 on database errors

#### `neo4j test-connection`
```bash  
kg-forge neo4j test-connection [--verbose]
```
- Tests connectivity to configured Neo4j instance
- Shows connection parameters (without password)
- `--verbose`: Include detailed connection diagnostics
- Exit code 0 if connected, 1 if connection fails

#### `neo4j status`
```bash
kg-forge neo4j status [--namespace TEXT]
```
- Shows database schema information (constraints, indexes)
- Displays node counts by namespace
- Shows database version and configuration
- Exit code 0 on success, 1 on connection errors

#### `neo4j clear-database`
```bash
kg-forge neo4j clear-database [--namespace TEXT] [--force]
```
- Removes all nodes and relationships from database
- `--namespace`: Only clear specified namespace (default: all)
- `--force`: Skip confirmation prompt
- Shows deletion count and confirmation
- Exit code 0 on success, 1 on errors

#### `neo4j start/stop`
```bash
kg-forge neo4j start [--port INT]
kg-forge neo4j stop
```
- Development helper commands for local Neo4j management
- `start`: Launch Neo4j using Docker or local installation
- `stop`: Stop running Neo4j instance
- Exit code 0 on success, 1 on errors

## Project Structure

```
kg_forge/
├── kg_forge/
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── neo4j_client.py         # Core Neo4j client implementation
│   │   ├── schema.py              # Schema management utilities
│   │   └── exceptions.py          # Custom graph database exceptions
│   ├── cli/
│   │   ├── neo4j_ops.py          # Neo4j CLI commands (updated from skeleton)
│   │   └── main.py               # Updated to include neo4j commands
│   ├── config/
│   │   └── settings.py           # Updated with Neo4j configuration
├── tests/
│   ├── test_graph/
│   │   ├── __init__.py
│   │   ├── test_neo4j_client.py      # Neo4j client tests
│   │   ├── test_schema.py           # Schema management tests
│   │   └── test_cli_neo4j.py        # CLI command tests
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── neo4j_fixture.py        # Docker-based Neo4j test fixture
│   └── integration/
│       ├── __init__.py
│       └── test_neo4j_integration.py # End-to-end database tests
└── docker/
    └── neo4j-test/                  # Docker compose for test Neo4j
        ├── docker-compose.yml
        └── neo4j.conf
```

## Dependencies

### New Dependencies Required

```python
# Add to requirements.txt:
neo4j>=5.0.0                 # Official Neo4j Python driver
testcontainers>=3.7.0        # Docker containers for testing (dev dependency)

# Optional development dependencies:
docker>=6.0.0               # Docker management for neo4j start/stop commands
```

### Configuration Integration

Update existing configuration system from Step 1:

```python
# kg_forge/config/settings.py (additions)
from pydantic import BaseModel

class Neo4jSettings(BaseModel):
    """Neo4j database configuration."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password" 
    database: str = "neo4j"
    connection_timeout: int = 30
    max_connection_lifetime: int = 3600

# Add to main Settings class:
class Settings(BaseModel):
    # ... existing settings ...
    neo4j: Neo4jSettings = Neo4jSettings()
```

## Implementation Details

### Connection Management

- Use Neo4j Python driver with connection pooling
- Implement proper connection lifecycle (connect/disconnect)
- Handle connection timeouts and retry logic for transient failures
- Support both authentication and unauthenticated connections for development

### Schema Creation Strategy

```python
def initialize_schema(self) -> None:
    """Create schema with proper error handling."""
    
    # Create constraints first (they provide indexing)
    constraints = [
        "CREATE CONSTRAINT doc_unique IF NOT EXISTS FOR (d:Doc) REQUIRE (d.namespace, d.doc_id) IS UNIQUE",
        "CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.namespace, e.entity_type, e.normalized_name) IS UNIQUE"
    ]
    
    # Create additional performance indexes
    indexes = [
        "CREATE INDEX doc_namespace IF NOT EXISTS FOR (d:Doc) ON (d.namespace)",
        "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)"
    ]
    
    # Execute with proper error handling and logging
```

### Error Handling Strategy

- **Connection Errors**: Clear error messages with connection troubleshooting hints
- **Schema Conflicts**: Graceful handling of existing constraints, option to recreate with `--force`
- **Permission Errors**: Helpful messages about required database privileges
- **Version Compatibility**: Check Neo4j version compatibility and warn about unsupported versions

### Logging Strategy

- **INFO**: "Connected to Neo4j at {uri}", "Created {count} constraints and {count} indexes"
- **DEBUG**: "Executing query: {query}", "Connection pool statistics: {stats}"
- **WARNING**: "Constraint already exists: {constraint_name}", "Database version {version} not fully tested"
- **ERROR**: "Failed to connect to Neo4j: {error}", "Schema creation failed: {error}"

### Configuration Integration

```python
# Environment variable support
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j  
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# YAML configuration support
neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: password
  database: neo4j
  connection_timeout: 30
```

## Testing Strategy

### Unit Tests

#### Neo4j Client Tests (`test_neo4j_client.py`)

```python
class TestNeo4jClient:
    def test_connection_success(self):
        """Test successful database connection."""
        
    def test_connection_failure_handling(self):
        """Test handling of connection failures."""
        
    def test_schema_initialization(self):
        """Test creation of constraints and indexes."""
        
    def test_clear_database_with_namespace(self):
        """Test namespace-filtered database clearing."""
        
    def test_query_execution(self):
        """Test basic query execution and result handling."""

class TestSchemaManager:
    def test_constraint_creation(self):
        """Test constraint creation with conflict handling."""
        
    def test_index_creation(self):
        """Test index creation with existing index handling."""
        
    def test_schema_validation(self):
        """Test validation of required schema elements."""
```

#### CLI Tests (`test_cli_neo4j.py`)

```python
class TestNeo4jCLI:
    def test_init_schema_command(self):
        """Test neo4j init-schema command."""
        
    def test_test_connection_command(self):
        """Test neo4j test-connection command."""
        
    def test_status_command(self):
        """Test neo4j status command output."""
        
    def test_clear_database_command(self):
        """Test neo4j clear-database with confirmation."""
```

### Integration Tests

#### Docker-based Neo4j Fixture

```python
# tests/fixtures/neo4j_fixture.py
import pytest
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def neo4j_container():
    """Provide Docker-based Neo4j instance for testing."""
    with Neo4jContainer("neo4j:5.0") as neo4j:
        neo4j.with_env("NEO4J_AUTH", "neo4j/testpassword")
        yield neo4j

@pytest.fixture  
def neo4j_client(neo4j_container):
    """Provide configured Neo4j client for tests."""
    config = Neo4jConfig(
        uri=neo4j_container.get_connection_url(),
        username="neo4j",
        password="testpassword"
    )
    client = Neo4jClient(config)
    client.connect()
    yield client
    client.disconnect()
```

#### End-to-End Tests (`test_neo4j_integration.py`)

```python
class TestNeo4jIntegration:
    def test_full_schema_lifecycle(self, neo4j_client):
        """Test complete schema creation and validation cycle."""
        
    def test_namespace_isolation(self, neo4j_client):
        """Test that namespace filtering works correctly."""
        
    def test_cli_commands_integration(self, neo4j_container):
        """Test CLI commands against real database."""
        
    def test_connection_configuration(self):
        """Test various connection configuration scenarios."""
```

### Test Data Requirements

- Docker Compose configuration for consistent Neo4j test environment
- Test configuration files with different connection scenarios
- Sample Cypher queries for validation
- Test documents with various formats (HTML, PDF, DOCX) for schema validation

### Multi-Format Document Tests

```python
class TestDocNodeSchema:
    def test_create_doc_with_all_properties(self, neo4j_client):
        """Test creating Doc node with all properties including format-specific ones."""
        node_id = neo4j_client.create_doc(
            namespace="test",
            doc_id="platform/intro.pdf",
            source_path="platform/intro.pdf",
            source_format="pdf",
            content_hash="abc123",
            markdown_path="output/markdowns/test/intro.pdf.md",
            page_count=42,
            file_size=1024000
        )
        assert node_id is not None
        
    def test_multiple_formats_same_doc(self, neo4j_client):
        """Test that same document in different formats creates separate nodes."""
        # Create HTML version
        html_id = neo4j_client.create_doc(
            namespace="test",
            doc_id="intro.html",
            source_path="intro.html",
            source_format="html",
            content_hash="hash1"
        )
        
        # Create PDF version
        pdf_id = neo4j_client.create_doc(
            namespace="test",
            doc_id="intro.pdf",
            source_path="intro.pdf",
            source_format="pdf",
            content_hash="hash2",
            page_count=10
        )
        
        assert html_id != pdf_id
        
        # Verify both exist
        result = neo4j_client.execute_query(
            "MATCH (d:Doc {namespace: 'test'}) WHERE d.doc_id STARTS WITH 'intro.' RETURN count(d) as count"
        )
        assert result[0]['count'] == 2
        
    def test_query_by_source_format(self, neo4j_client):
        """Test filtering documents by format."""
        # Create docs in different formats
        neo4j_client.create_doc("test", "doc1.html", "doc1.html", "html", "h1")
        neo4j_client.create_doc("test", "doc2.pdf", "doc2.pdf", "pdf", "h2", page_count=5)
        neo4j_client.create_doc("test", "doc3.pdf", "doc3.pdf", "pdf", "h3", page_count=10)
        
        # Query only PDFs
        result = neo4j_client.execute_query(
            "MATCH (d:Doc {namespace: 'test', source_format: 'pdf'}) RETURN count(d) as count"
        )
        assert result[0]['count'] == 2
```
- Mock data for namespace and node count testing

## Success Criteria

### Functional Requirements

- [ ] Neo4j client successfully connects to database with proper authentication
- [ ] Schema initialization creates all required constraints and indexes without errors
- [ ] **:Doc nodes support multi-format documents with source_format, markdown_path, page_count properties**
- [ ] **Document IDs with extensions (e.g., "intro.html", "intro.pdf") work correctly with unique constraints**
- [ ] Namespace filtering works correctly for queries and database clearing operations
- [ ] CLI commands (`init-schema`, `test-connection`, `status`, `clear-database`) execute successfully
- [ ] Database connection failures are handled gracefully with helpful error messages
- [ ] **Index on source_format enables efficient filtering by document type**

### Technical Requirements

- [ ] All schema operations are idempotent (can be run multiple times safely)
- [ ] Connection pooling and resource management work correctly (no connection leaks)
- [ ] Error handling provides actionable guidance for common configuration issues
- [ ] Configuration integrates properly with Step 1 settings system
- [ ] Docker-based test fixture provides reliable testing environment

### Quality Requirements

- [ ] Unit test coverage >90% for graph modules
- [ ] Integration tests cover all CLI commands and database operations
- [ ] Error messages provide clear guidance for troubleshooting connection issues
- [ ] Performance is acceptable for typical development workflows (schema init < 10 seconds)
- [ ] No data loss during database operations (proper confirmation prompts)

### Integration Requirements

- [ ] Schema supports entity types loaded from Step 4 entity definitions
- [ ] **Database structure ready for multi-format document storage from Step 3 curation backends**
- [ ] **:Doc node properties accommodate metadata from both Docling and future HylandKE backends**
- [ ] Database structure ready for document and entity storage in Step 6
- [ ] CLI commands integrate cleanly with existing `kg-forge` command structure
- [ ] Configuration values can be overridden via existing mechanisms (CLI, env, YAML)

## Next Steps

Step 5 creates the database foundation that will store the structured knowledge graph built from curated content (Step 3) and entity definitions (Step 4). The initialized Neo4j schema provides the storage infrastructure needed for:

- **Step 3**: Multi-format document curation results (markdown_path, source_format, page_count)
- **Step 6**: LLM Integration and extraction to persist extracted entities
- **Step 7**: Ingest Pipeline to store document-entity relationships

The updated schema supports the new multi-format document architecture where:
- Documents from different formats can coexist (doc_id includes extension)
- Format-specific metadata (page_count for PDFs, etc.) is preserved
- Curation artifacts (markdown files) are tracked via markdown_path
- Efficient queries by document format are enabled via source_format index

The constraints and indexes established in Step 5 ensure data integrity and query performance for the graph operations that will be implemented in subsequent steps. The CLI database management commands provide essential tools for development, testing, and experimentation workflows, allowing users to easily reset and inspect the database state during ontology iteration cycles.

The modular Neo4j client design ensures that database operations can be easily tested and that the graph storage layer can be extended or replaced in future versions while maintaining the same API interface.