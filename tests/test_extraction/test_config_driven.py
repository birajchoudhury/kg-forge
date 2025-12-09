"""Tests for config-driven LLM extraction."""

import pytest
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path for direct import
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import directly from module to avoid glirel dependency issue
import importlib.util
spec = importlib.util.spec_from_file_location(
    "config_driven",
    project_root / "kg_forge" / "extraction" / "config_driven.py"
)
config_driven = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_driven)

# Extract what we need
LLMClient = config_driven.LLMClient
build_system_prompt = config_driven.build_system_prompt
build_user_prompt = config_driven.build_user_prompt
extract_entities_from_document = config_driven.extract_entities_from_document
_validate_entity_config = config_driven._validate_entity_config
_parse_llm_response = config_driven._parse_llm_response
_extract_json_from_markdown = config_driven._extract_json_from_markdown
_validate_extraction_result = config_driven._validate_extraction_result
_validate_entity = config_driven._validate_entity
_validate_dependencies = config_driven._validate_dependencies


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""
    
    def __init__(self, response: str):
        self.response = response
        self.last_system_prompt = None
        self.last_user_prompt = None
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.response


@pytest.fixture
def sample_entity_config():
    """Sample entity configuration with core and occurrence entities."""
    return {
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
                "relations": {},
                "depends_on": []
            },
            "Party": {
                "kind": "core",
                "label": "Party",
                "description": "A contracting party",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"}
                },
                "relations": {},
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
                    {"role": "contract", "entity": "Contract", "cardinality": "1"},
                    {"role": "parties", "entity": "Party", "cardinality": "1..*"}
                ]
            }
        }
    }


@pytest.fixture
def valid_extraction_result():
    """Valid extraction result with core and occurrence entities."""
    return {
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
            },
            {
                "entity_id": "party-1",
                "type": "Party",
                "properties": {
                    "name": "ACME Corp",
                    "role": "employer"
                },
                "span": {"page": 1, "start_char": 100, "end_char": 120}
            },
            {
                "entity_id": "party-2",
                "type": "Party",
                "properties": {
                    "name": "John Doe",
                    "role": "employee"
                },
                "span": {"page": 1, "start_char": 150, "end_char": 170}
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
                    "contract": "contract-1",
                    "parties": "party-1"
                },
                "span": {"page": 1, "start_char": 200, "end_char": 250}
            }
        ]
    }


# Test build_system_prompt
def test_build_system_prompt():
    """Test that system prompt contains key instructions."""
    prompt = build_system_prompt()
    
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "core_entities" in prompt
    assert "occurrence_entities" in prompt
    assert "depends_on" in prompt
    assert "cardinality" in prompt
    assert "JSON" in prompt.upper()


# Test build_user_prompt
def test_build_user_prompt(sample_entity_config):
    """Test building user prompt with config and document."""
    prompt = build_user_prompt(
        entity_config=sample_entity_config,
        doc_id="DOC-123",
        doc_title="Test Document",
        doc_text="This is a test document about contracts."
    )
    
    assert isinstance(prompt, str)
    assert "DOC-123" in prompt
    assert "Test Document" in prompt
    assert "test document about contracts" in prompt
    assert "Contract" in prompt  # From entity config
    assert "ENTITY CONFIG JSON" in prompt


def test_build_user_prompt_escapes_special_chars(sample_entity_config):
    """Test that user prompt handles special characters in document text."""
    doc_text = 'Document with "quotes" and {braces} and $symbols'
    
    prompt = build_user_prompt(
        entity_config=sample_entity_config,
        doc_id="DOC-456",
        doc_title="Special Chars",
        doc_text=doc_text
    )
    
    assert doc_text in prompt
    assert "DOC-456" in prompt


# Test _validate_entity_config
def test_validate_entity_config_valid(sample_entity_config):
    """Test validation passes for valid config."""
    # Should not raise
    _validate_entity_config(sample_entity_config)


def test_validate_entity_config_missing_entities():
    """Test validation fails if 'entities' key missing."""
    with pytest.raises(ValueError, match="must have 'entities' key"):
        _validate_entity_config({"foo": "bar"})


def test_validate_entity_config_invalid_kind():
    """Test validation fails for invalid entity kind."""
    config = {
        "entities": {
            "BadEntity": {
                "kind": "invalid"
            }
        }
    }
    
    with pytest.raises(ValueError, match="invalid kind"):
        _validate_entity_config(config)


def test_validate_entity_config_missing_kind():
    """Test validation fails if entity missing kind."""
    config = {
        "entities": {
            "BadEntity": {
                "label": "Bad"
            }
        }
    }
    
    with pytest.raises(ValueError, match="missing 'kind' field"):
        _validate_entity_config(config)


# Test _parse_llm_response
def test_parse_llm_response_valid_json(valid_extraction_result):
    """Test parsing valid JSON response."""
    json_str = json.dumps(valid_extraction_result)
    result = _parse_llm_response(json_str)
    
    assert result == valid_extraction_result


def test_parse_llm_response_with_markdown_fence(valid_extraction_result):
    """Test parsing JSON from markdown code block."""
    json_str = json.dumps(valid_extraction_result, indent=2)
    markdown_response = f"```json\n{json_str}\n```"
    
    result = _parse_llm_response(markdown_response)
    
    assert result == valid_extraction_result


def test_parse_llm_response_with_text_around_json(valid_extraction_result):
    """Test extracting JSON from response with extra text."""
    json_str = json.dumps(valid_extraction_result)
    response_with_text = f"Here are the results:\n\n{json_str}\n\nEnd of extraction."
    
    result = _parse_llm_response(response_with_text)
    
    assert result == valid_extraction_result


def test_parse_llm_response_invalid_json():
    """Test parsing fails for invalid JSON."""
    with pytest.raises(json.JSONDecodeError):
        _parse_llm_response("This is not JSON at all")


# Test _extract_json_from_markdown
def test_extract_json_from_markdown_with_fence():
    """Test extracting JSON from markdown code fence."""
    json_data = {"foo": "bar", "baz": 123}
    markdown = f"```json\n{json.dumps(json_data)}\n```"
    
    result = _extract_json_from_markdown(markdown)
    
    assert result == json_data


def test_extract_json_from_markdown_without_language():
    """Test extracting JSON from code fence without language tag."""
    json_data = {"test": True}
    markdown = f"```\n{json.dumps(json_data)}\n```"
    
    result = _extract_json_from_markdown(markdown)
    
    assert result == json_data


def test_extract_json_from_markdown_embedded_in_text():
    """Test extracting JSON embedded in text."""
    json_data = {"embedded": "value"}
    text = f"Some text before\n{json.dumps(json_data)}\nSome text after"
    
    result = _extract_json_from_markdown(text)
    
    assert result == json_data


def test_extract_json_from_markdown_no_json():
    """Test extraction fails when no JSON present."""
    with pytest.raises(json.JSONDecodeError):
        _extract_json_from_markdown("No JSON here at all!")


# Test _validate_extraction_result
def test_validate_extraction_result_valid(valid_extraction_result, sample_entity_config):
    """Test validation passes for valid extraction result."""
    # Should not raise
    _validate_extraction_result(valid_extraction_result, sample_entity_config)


def test_validate_extraction_result_missing_core_entities(sample_entity_config):
    """Test validation fails if core_entities missing."""
    result = {"occurrence_entities": []}
    
    with pytest.raises(ValueError, match="missing 'core_entities'"):
        _validate_extraction_result(result, sample_entity_config)


def test_validate_extraction_result_missing_occurrence_entities(sample_entity_config):
    """Test validation fails if occurrence_entities missing."""
    result = {"core_entities": []}
    
    with pytest.raises(ValueError, match="missing 'occurrence_entities'"):
        _validate_extraction_result(result, sample_entity_config)


def test_validate_extraction_result_unknown_entity_type(sample_entity_config):
    """Test validation fails for unknown entity type."""
    result = {
        "core_entities": [
            {
                "entity_id": "unknown-1",
                "type": "UnknownType",
                "properties": {}
            }
        ],
        "occurrence_entities": []
    }
    
    with pytest.raises(ValueError, match="Unknown entity type"):
        _validate_extraction_result(result, sample_entity_config)


def test_validate_extraction_result_wrong_kind_placement(sample_entity_config):
    """Test validation fails when entity placed in wrong list based on kind."""
    result = {
        "core_entities": [
            {
                "entity_id": "exec-1",
                "type": "ContractExecution",  # This is occurrence, not core
                "properties": {},
                "links": {}
            }
        ],
        "occurrence_entities": []
    }
    
    with pytest.raises(ValueError, match="was placed in core entities list"):
        _validate_extraction_result(result, sample_entity_config)


# Test _validate_entity
def test_validate_entity_valid_core(sample_entity_config):
    """Test validation passes for valid core entity."""
    entity = {
        "entity_id": "contract-1",
        "type": "Contract",
        "properties": {"title": "Test"}
    }
    
    # Should not raise
    _validate_entity(entity, sample_entity_config, is_occurrence=False)


def test_validate_entity_missing_required_field(sample_entity_config):
    """Test validation fails when required field missing."""
    entity = {
        "entity_id": "contract-1",
        # Missing "type"
        "properties": {}
    }
    
    with pytest.raises(ValueError, match="missing required field"):
        _validate_entity(entity, sample_entity_config, is_occurrence=False)


def test_validate_entity_occurrence_missing_links(sample_entity_config):
    """Test validation fails when occurrence entity missing links."""
    entity = {
        "entity_id": "exec-1",
        "type": "ContractExecution",
        "properties": {}
        # Missing "links"
    }
    
    with pytest.raises(ValueError, match="missing 'links' field"):
        _validate_entity(entity, sample_entity_config, is_occurrence=True)


# Test _validate_dependencies
def test_validate_dependencies_satisfied(sample_entity_config):
    """Test validation passes when all dependencies satisfied."""
    occurrence_entity = {
        "entity_id": "exec-1",
        "type": "ContractExecution",
        "properties": {},
        "links": {
            "contract": "contract-1",
            "parties": "party-1"
        }
    }
    
    core_entities = [
        {"entity_id": "contract-1", "type": "Contract", "properties": {}},
        {"entity_id": "party-1", "type": "Party", "properties": {}}
    ]
    
    # Should not raise
    _validate_dependencies(occurrence_entity, sample_entity_config, core_entities)


def test_validate_dependencies_missing_required_link(sample_entity_config):
    """Test validation fails when required link missing."""
    occurrence_entity = {
        "entity_id": "exec-1",
        "type": "ContractExecution",
        "properties": {},
        "links": {
            # Missing "contract" link (cardinality "1")
            "parties": "party-1"
        }
    }
    
    core_entities = [
        {"entity_id": "party-1", "type": "Party", "properties": {}}
    ]
    
    with pytest.raises(ValueError, match="missing required link 'contract'"):
        _validate_dependencies(occurrence_entity, sample_entity_config, core_entities)


def test_validate_dependencies_link_to_nonexistent_entity(sample_entity_config):
    """Test validation fails when link points to non-existent entity."""
    occurrence_entity = {
        "entity_id": "exec-1",
        "type": "ContractExecution",
        "properties": {},
        "links": {
            "contract": "contract-999",  # Does not exist
            "parties": "party-1"
        }
    }
    
    core_entities = [
        {"entity_id": "party-1", "type": "Party", "properties": {}}
    ]
    
    with pytest.raises(ValueError, match="links to non-existent entity"):
        _validate_dependencies(occurrence_entity, sample_entity_config, core_entities)


def test_validate_dependencies_wrong_entity_type(sample_entity_config):
    """Test validation fails when linked entity has wrong type."""
    occurrence_entity = {
        "entity_id": "exec-1",
        "type": "ContractExecution",
        "properties": {},
        "links": {
            "contract": "party-1",  # Links to Party instead of Contract
            "parties": "party-1"
        }
    }
    
    core_entities = [
        {"entity_id": "party-1", "type": "Party", "properties": {}}
    ]
    
    with pytest.raises(ValueError, match="but expected type 'Contract'"):
        _validate_dependencies(occurrence_entity, sample_entity_config, core_entities)


# Test extract_entities_from_document (integration)
def test_extract_entities_from_document_success(sample_entity_config, valid_extraction_result):
    """Test successful end-to-end extraction."""
    mock_llm = MockLLMClient(json.dumps(valid_extraction_result))
    
    result = extract_entities_from_document(
        entity_config=sample_entity_config,
        doc_id="DOC-123",
        doc_title="Test Contract",
        doc_text="This is a test contract document.",
        llm_client=mock_llm
    )
    
    assert result == valid_extraction_result
    assert mock_llm.last_system_prompt is not None
    assert mock_llm.last_user_prompt is not None
    assert "DOC-123" in mock_llm.last_user_prompt


def test_extract_entities_from_document_with_markdown_response(
    sample_entity_config,
    valid_extraction_result
):
    """Test extraction handles markdown-formatted response."""
    json_str = json.dumps(valid_extraction_result, indent=2)
    markdown_response = f"```json\n{json_str}\n```"
    
    mock_llm = MockLLMClient(markdown_response)
    
    result = extract_entities_from_document(
        entity_config=sample_entity_config,
        doc_id="DOC-456",
        doc_title="Test",
        doc_text="Test document",
        llm_client=mock_llm
    )
    
    assert result == valid_extraction_result


def test_extract_entities_from_document_invalid_config():
    """Test extraction fails with invalid config."""
    invalid_config = {"wrong": "structure"}
    mock_llm = MockLLMClient("{}")
    
    with pytest.raises(ValueError, match="must have 'entities' key"):
        extract_entities_from_document(
            entity_config=invalid_config,
            doc_id="DOC-789",
            doc_title="Test",
            doc_text="Test",
            llm_client=mock_llm
        )


def test_extract_entities_from_document_llm_failure(sample_entity_config):
    """Test extraction handles LLM generation failure."""
    class FailingLLM(LLMClient):
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("LLM service unavailable")
    
    failing_llm = FailingLLM()
    
    with pytest.raises(RuntimeError, match="LLM service unavailable"):
        extract_entities_from_document(
            entity_config=sample_entity_config,
            doc_id="DOC-999",
            doc_title="Test",
            doc_text="Test",
            llm_client=failing_llm
        )


def test_extract_entities_from_document_invalid_result(sample_entity_config):
    """Test extraction validates LLM output."""
    invalid_result = {
        "core_entities": [
            {
                "entity_id": "unknown-1",
                "type": "UnknownEntityType",  # Not in config
                "properties": {}
            }
        ],
        "occurrence_entities": []
    }
    
    mock_llm = MockLLMClient(json.dumps(invalid_result))
    
    with pytest.raises(ValueError, match="Unknown entity type"):
        extract_entities_from_document(
            entity_config=sample_entity_config,
            doc_id="DOC-111",
            doc_title="Test",
            doc_text="Test",
            llm_client=mock_llm
        )
