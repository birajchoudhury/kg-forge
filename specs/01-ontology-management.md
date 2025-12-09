# Step 1: Ontology Management

## Overview

Step 1 implements the ontology management system that provides foundational capabilities for organizing, loading, and validating entity definitions. This step establishes the framework for managing ontology packs, which are collections of entity definitions that can be dynamically loaded and activated at runtime.

## Scope

### In Scope

- **Ontology pack system**: 
  - Organize entity definitions into reusable, modular packs
  - Support for multiple ontology packs with different domains/contexts
  - Dynamic loading and activation of ontology packs at runtime

- **Entity definition management**:
  - Load entity definitions from markdown files
  - Parse entity relationships, examples, and descriptions
  - Support for extensible entity definition formats

- **Validation framework**:
  - Validate ontology definitions for completeness and consistency
  - Check entity relationships and dependencies
  - Provide detailed validation reports and error messages

- **CLI ontology commands**:
  - Inspect available ontology packs
  - Activate/deactivate ontology packs
  - Validate ontology definitions
  - Export ontology summaries

- **Extensible architecture**:
  - Plugin system for custom ontology formats
  - Support for external ontology sources
  - Integration hooks for ontology transformation

### Out of Scope

- Visual ontology editing (covered in Step 2: Ontology Visualization)
- Graph-based ontology storage (covered in Step 5: Neo4j Bootstrap)
- LLM-based ontology enhancement (covered in Step 6: LLM Integration)

## Technical Requirements

### Core Components

#### OntologyManager
Central component responsible for ontology pack lifecycle management:

```python
class OntologyManager:
    def register_pack(self, pack_id: str, pack_path: str) -> None:
        """Register an ontology pack for use."""
        
    def activate_pack(self, pack_id: str) -> bool:
        """Activate a registered ontology pack."""
        
    def get_active_pack(self) -> Optional[OntologyPack]:
        """Get the currently active ontology pack."""
        
    def validate_pack(self, pack_id: str) -> ValidationResult:
        """Validate an ontology pack for consistency."""
```

#### OntologyPack
Represents a collection of entity definitions and metadata:

```python
class OntologyPack:
    def __init__(self, pack_id: str, definitions_dir: str):
        self.pack_id = pack_id
        self.definitions_dir = definitions_dir
        self.entities = {}
        self.metadata = {}
        
    def load_entities(self) -> Dict[str, EntityDefinition]:
        """Load all entity definitions from the pack directory."""
        
    def validate(self) -> ValidationResult:
        """Validate the ontology pack for consistency."""
```

#### ValidationResult
Encapsulates validation results with detailed feedback:

```python
class ValidationResult:
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.info = []
        
    def add_error(self, message: str, entity_id: str = None):
        """Add a validation error."""
        
    def add_warning(self, message: str, entity_id: str = None):
        """Add a validation warning."""
```

### CLI Commands

#### ontology list-packs
List all registered ontology packs:
```bash
kg-forge ontology list-packs [--format json|table]
```

#### ontology activate
Activate an ontology pack:
```bash
kg-forge ontology activate PACK_ID
```

#### ontology validate
Validate an ontology pack:
```bash
kg-forge ontology validate [PACK_ID] [--detailed]
```

#### ontology info
Show information about the active ontology pack:
```bash
kg-forge ontology info [--entities] [--relationships]
```

### Configuration Integration

Ontology management integrates with the existing configuration system:

```yaml
# kg_forge.yaml
app:
  ontology_pack: "ai_ml_confluence"  # Default active pack
  ontologies_dir: "ontology_packs"   # Directory containing ontology packs

ontology:
  auto_activate: true                # Auto-activate default pack on startup
  validation_level: "strict"         # strict|permissive|disabled
  cache_definitions: true            # Cache loaded definitions
```

### Directory Structure

```
ontology_packs/
├── ai_ml_confluence/              # Example ontology pack
│   ├── ontology.yaml             # Pack metadata
│   ├── entities/
│   │   ├── product.md
│   │   ├── component.md
│   │   ├── team.md
│   │   └── ...
│   └── templates/
│       └── prompt_template.md
├── software_architecture/         # Another ontology pack
│   ├── ontology.yaml
│   ├── entities/
│   │   ├── service.md
│   │   ├── database.md
│   │   └── ...
│   └── templates/
│       └── prompt_template.md
└── ...
```

### Ontology Pack Metadata

Each ontology pack includes a metadata file (`ontology.yaml`):

```yaml
# ontology_packs/ai_ml_confluence/ontology.yaml
name: "AI/ML Confluence Ontology"
description: "Entity definitions for AI/ML domain content from Confluence"
version: "1.0.0"
author: "KG Forge Team"
created: "2024-01-15"
updated: "2024-01-20"

dependencies: []  # Other ontology packs this depends on
tags: ["ai", "ml", "confluence", "technical"]

entities:
  - product
  - component  
  - team
  - technology
  - domain
  
relationships:
  - team_works_on_product
  - product_uses_technology
  - component_part_of_product
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. **OntologyManager implementation**
   - Basic pack registration and activation
   - Integration with existing configuration system
   - Error handling and logging

2. **OntologyPack implementation**
   - Entity definition loading
   - Metadata parsing
   - Basic validation

3. **Configuration integration**
   - Extend Settings class for ontology configuration
   - Default pack activation on startup

### Phase 2: Validation Framework
1. **ValidationResult implementation**
   - Structured error/warning/info reporting
   - Detailed validation messages

2. **Comprehensive validation logic**
   - Entity definition completeness
   - Relationship consistency
   - Circular dependency detection

3. **Validation CLI commands**
   - `ontology validate` command
   - Integration with other CLI commands

### Phase 3: CLI Interface
1. **Core ontology commands**
   - `ontology list-packs`
   - `ontology activate`  
   - `ontology info`

2. **Advanced features**
   - Output formatting (JSON, table)
   - Detailed information display
   - Interactive pack selection

### Phase 4: Integration & Extensions
1. **Integration with existing systems**
   - Schema-driven extraction backend compatibility
   - CLI help system updates

2. **Extensibility features**
   - Plugin system for custom formats
   - External ontology source support
   - Transformation hooks

## Testing Strategy

### Unit Tests
- **OntologyManager**: Pack registration, activation, validation
- **OntologyPack**: Entity loading, metadata parsing  
- **ValidationResult**: Error handling, message formatting
- **CLI commands**: Command parsing, output formatting

### Integration Tests
- **Pack lifecycle**: Registration → Activation → Usage → Deactivation
- **Configuration integration**: Settings loading, default activation
- **Cross-component**: Integration with schema-driven extraction backend

### Test Data
- **Sample ontology packs**: Multiple packs with different structures
- **Invalid ontologies**: Test cases for validation edge cases  
- **Configuration scenarios**: Different configuration combinations

## Success Criteria

### Functional Requirements
- ✅ Register and activate ontology packs dynamically
- ✅ Load entity definitions from pack directories  
- ✅ Validate ontology pack consistency
- ✅ CLI commands for ontology management
- ✅ Integration with existing configuration system

### Non-Functional Requirements  
- ✅ **Performance**: Pack loading < 1 second for typical sizes
- ✅ **Reliability**: Graceful handling of malformed ontologies
- ✅ **Usability**: Clear error messages and validation feedback
- ✅ **Maintainability**: Extensible architecture for future enhancements

### Test Coverage
- ✅ **Unit test coverage**: > 95% for all ontology management components
- ✅ **Integration test coverage**: All CLI commands and workflows
- ✅ **Error scenario coverage**: All validation and error handling paths

## Dependencies

### Internal Dependencies
- **kg_forge.config**: Settings and configuration management
- **kg_forge.entities**: EntityDefinition and related models
- **kg_forge.cli**: CLI framework and command structure

### External Dependencies
- **PyYAML**: For ontology metadata parsing
- **pathlib**: For filesystem operations
- **click**: For CLI command implementation

## Future Considerations

### Planned Extensions
- **Ontology versioning**: Support for multiple versions of the same pack
- **Remote ontologies**: Load ontology packs from remote sources (git, HTTP)
- **Ontology merging**: Combine multiple packs into a unified view
- **Visual ontology editor**: Integration with web-based ontology editing tools

### Integration Points
- **Step 2 (Ontology Visualization)**: Visualize loaded ontology structures
- **Step 6 (LLM Integration)**: Use active ontology for prompt generation
- **Step 5 (Neo4j Bootstrap)**: Initialize graph schema from ontology definitions