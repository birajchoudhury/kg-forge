# Step 0: CLI Foundation

## Overview

Implement the core CLI infrastructure with command parsing, configuration management, and help system. This step establishes the foundation without any actual processing logic or external service integrations.

## Scope

### In Scope
- CLI command structure using Click with `kg-forge` as entry point
- Version management (`kg-forge --version`)
- Configuration loading from `.env` file and YAML config files
- Command-line argument parsing and validation
- Help system and usage documentation
- Basic project structure and packaging
- Unit tests for CLI components
- README documentation
- Error handling and logging setup (stdout/stderr)
- Namespace validation (alphanumeric only, no spaces)

### Out of Scope
- Neo4j integration
- LLM/Bedrock calls
- HTML parsing and content curation
- Entity definition loading
- Graph operations
- Interactive mode implementation (flag parsing only)
- Command aliases

## CLI Commands Structure

### Main Commands

#### `kg-forge ingest`
```bash
kg-forge ingest --source <path> [options]
```

**Required Arguments:**
- `--source` - Path to source directory containing document files (HTML, PDF, DOCX, etc.)

**Optional Arguments:**
- `--namespace` - Experiment namespace (default: "default", alphanumeric only)
- `--curator` - Curation backend: docling|hyland_ke (default: docling)
- `--dry-run` - Extract entities but don't write to graph
- `--refresh` - Re-import even if content hash matches
- `--prompt-template` - Override prompt template file
- `--model` - Override bedrock model name
- `--extractor` - Extraction backend: llm|spacy (default: llm)
- `--dedup-backend` - Deduplication backend: none|splink|zingg|both (default: splink)
- `--max-results` - Maximum results to return (default: 10)

#### `kg-forge query`
```bash
kg-forge query <subcommand> [options]
```

**Subcommands:**
- `list-types` - List all entity types
- `list-entities --type <type>` - List entities of specific type
- `list-docs` - List all documents
- `show-doc --id <doc-id>` - Show document details
- `find-related --entity <name> --type <type>` - Find related entities

**Common Options:**
- `--namespace` - Target namespace (default: "default", alphanumeric only)
- `--format` - Output format: json|text (default: text)
- `--max-results` - Maximum results (default: 10)

#### `kg-forge render`
```bash
kg-forge render [options]
```

**Options:**
- `--out` - Output HTML file (default: graph.html)
- `--depth` - Graph traversal depth (default: 2)
- `--max-nodes` - Maximum nodes to include (default: 100)
- `--namespace` - Target namespace (default: "default", alphanumeric only)

#### `kg-forge neo4j-start`
```bash
kg-forge neo4j-start
```

#### `kg-forge neo4j-stop`
```bash
kg-forge neo4j-stop
```

#### `kg-forge export-entities`
```bash
kg-forge export-entities [options]
```

**Options:**
- `--output-dir` - Directory to write entity markdown files (default: entities_extract/)
- `--namespace` - Source namespace (default: "default", alphanumeric only)

#### `kg-forge --version`
```bash
kg-forge --version
```

Display version information for the CLI tool.

## Configuration Management

### Configuration Sources and Priority

Configuration values are loaded in the following priority order (highest to lowest):

1. **Command-line arguments** (highest priority)
2. **YAML configuration file** (`kg_forge.yaml` or `config.yaml`)
3. **Environment variables**
4. **`.env` file values**
5. **Default values** (lowest priority)

### Environment Variables (.env file)

```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0

# Application Configuration
LOG_LEVEL=INFO
DEFAULT_NAMESPACE=default

# Extraction Configuration
DEFAULT_EXTRACTOR=llm
DEFAULT_CURATOR=docling
DEFAULT_DEDUP_BACKEND=splink

# Hyland KE Configuration (optional, for future use)
HYLAND_KE_API_ENDPOINT=https://api.hyland.example.com
HYLAND_KE_API_KEY=your_api_key
```

### YAML Configuration File

Example `kg_forge.yaml`:

```yaml
# Neo4j Configuration
neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: password

# AWS Bedrock Configuration
aws:
  access_key_id: your_access_key
  secret_access_key: your_secret_key
  default_region: us-east-1
  bedrock_model_name: anthropic.claude-3-haiku-20240307-v1:0

# Application Configuration
app:
  log_level: INFO
  default_namespace: default
  default_extractor: llm
  default_curator: docling
  default_dedup_backend: splink

# Curation Configuration
curation:
  output_base_dir: output/markdowns
  
# Hyland KE Configuration (optional)
hyland_ke:
  api_endpoint: https://api.hyland.example.com
  api_key: your_api_key
```

### Configuration Loading

The CLI will search for configuration files in the following order:
1. `./kg_forge.yaml` (current directory)
2. `./config.yaml` (current directory)
3. `~/.kg_forge.yaml` (user home directory)

## Project Structure

```
kg_forge/
├── kg_forge/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py          # Main CLI entry point
│   │   ├── ingest.py        # Ingest command group
│   │   ├── query.py         # Query command group
│   │   ├── render.py        # Render command
│   │   └── neo4j_ops.py     # Neo4j operations commands
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # Configuration management
│   └── utils/
│       ├── __init__.py
│       └── logging.py       # Logging setup
├── tests/
│   ├── __init__.py
│   ├── test_cli/
│   │   ├── __init__.py
│   │   ├── test_main.py
│   │   ├── test_ingest.py
│   │   ├── test_query.py
│   │   └── test_render.py
│   ├── test_config/
│   │   ├── __init__.py
│   │   └── test_settings.py
│   └── fixtures/
│       ├── __init__.py
│       ├── sample.env
│       └── sample_config.yaml
├── requirements.txt
├── setup.py
├── .env.example
├── kg_forge.yaml.example
├── .gitignore
├── README.md
└── specs/
    ├── seed_product_md
    |── seed_architecture_md
    └── 01-cli-foundation.md
```

## Dependencies

### Core Dependencies
- `click` - CLI framework
- `python-dotenv` - Environment variable loading
- `pydantic` - Configuration validation
- `pyyaml` - YAML configuration file support
- `rich` - Enhanced console output and logging

### Additional Dependencies for Full Architecture
- `neo4j` - Neo4j graph database driver
- `llama-index` - LLM and KnowledgeGraphIndex integration
- `spacy` - NLP pipeline for lexical graph extraction
- `splink` - Probabilistic entity resolution
- `zingg` - ML-based entity resolution (optional)

### Development Dependencies
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `black` - Code formatting
- `flake8` - Code linting
- `mypy` - Type checking

## Implementation Details

### CLI Entry Point
- Use Click's command groups for organizing commands
- Implement proper error handling with user-friendly messages
- Add `--help` for all commands and subcommands
- Use Click's built-in validation where possible
- Add `--version` flag to show version information
- Support curation backend selection via `--curator` flag (docling|hyland_ke)
- Support extraction backend selection via `--extractor` flag (llm|spacy)
- Support deduplication backend selection via `--dedup-backend` flag (none|splink|zingg|both)
- Validate all backend choices with clear error messages

### Configuration Management
- Use Pydantic for configuration validation and type safety
- Support .env file, YAML config files, and environment variables
- Implement configuration precedence (CLI args > YAML > env vars > .env > defaults)
- Provide clear error messages for missing or invalid configuration
- Validate curation backend choices (docling, hyland_ke)
- Validate extraction backend choices (llm, spacy)
- Validate deduplication backend choices (none, splink, zingg, both)
- Support default values for curator, extractor, and deduplication settings
- Include curation output directory configuration

### Logging
- Use Python's standard logging module with Rich handler for enhanced output
- Default output to stdout/stderr
- Support different log levels via configuration
- Include proper context in log messages

### Error Handling
- Use Click's exception handling mechanism
- Provide user-friendly error messages
- Use appropriate exit codes (0 for success, non-zero for errors)

### Namespace Validation
- Validate namespace names to ensure they are alphanumeric only (no spaces)
- Provide clear error messages for invalid namespace names

### Version Management
- Implement `--version` flag using Click's built-in version option
- Store version information in `kg_forge/__init__.py`

## Testing Strategy

### Unit Tests
- Test all CLI command parsing and validation
- Test configuration loading from various sources (env, YAML, CLI args)
- Test configuration precedence order
- Test namespace validation
- Test curation backend validation (docling, hyland_ke, invalid choices)
- Test extraction backend validation (llm, spacy, invalid choices)
- Test deduplication backend validation (none, splink, zingg, both, invalid choices)
- Test error handling scenarios for all invalid backend choices
- Mock external dependencies (not applicable in this step)

### Test Data
- Sample .env files with various configurations including curator and extraction settings
- Sample YAML configuration files with all backend configurations
- Sample command-line invocations with --curator, --extractor, and --dedup-backend flags
- Invalid configuration scenarios including all types of invalid backend choices
- Invalid namespace examples
- Valid curator backend choices (docling, hyland_ke)
- Invalid curator backend choices (invalid_curator)
- Valid extractor backend choices (llm, spacy)
- Invalid extractor backend choices (invalid_extractor)
- Valid deduplication backend choices (none, splink, zingg, both)
- Invalid deduplication backend choices (invalid_dedup)

### Coverage Target
- Aim for >90% code coverage
- Focus on edge cases and error conditions

## Success Criteria

1. **CLI Commands**: All main commands and subcommands can be invoked with `--help`
2. **Version Info**: `kg-forge --version` displays version information
3. **Configuration**: Config loading works from .env file, YAML files, and environment variables with correct precedence
4. **Namespace Validation**: Invalid namespace names are properly rejected
5. **Curator Backend Validation**: Invalid curator choices are properly rejected with helpful error messages (valid: docling, hyland_ke)
6. **Extractor Backend Validation**: Invalid extractor choices are properly rejected with helpful error messages (valid: llm, spacy)
7. **Dedup Backend Validation**: Invalid dedup-backend choices are properly rejected with helpful error messages (valid: none, splink, zingg, both)
8. **Default Values**: Backend settings use proper defaults (curator: docling, extractor: llm, dedup-backend: splink)
9. **Error Handling**: Invalid commands/arguments show helpful error messages
10. **Tests**: Unit tests pass with good coverage including all backend validation scenarios
11. **Documentation**: README provides clear installation and usage instructions including multi-format document support
12. **Package Structure**: Project follows Python best practices for packaging

## Next Steps

After completing this foundation step:
1. All CLI commands should be callable with proper help text
2. Configuration system should be fully functional with support for curator, extractor, and dedup backends
3. Backend selection flags (--curator, --extractor, --dedup-backend) should be validated
4. The foundation will support Step 3 (multi-format document curation) integration
5. Subsequent steps (3-7) can build upon this CLI and configuration infrastructure
3. Project structure should be in place for subsequent development
4. Unit tests should provide confidence in the CLI infrastructure

The next step will focus on implementing data curation (HTML parsing and text extraction).
