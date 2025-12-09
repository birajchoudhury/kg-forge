"""
Tests for schema-driven entity extraction.
"""
import json
import pytest
from kg_forge.extraction.schema_driven_extractor import (
    build_system_prompt,
    build_user_prompt,
    extract_entities_from_document,
    LLMClient,
    _parse_json_response,
    _normalize_entity,
    _normalize_entities,
)


class FakeLLMClient(LLMClient):
    """Fake LLM client for testing."""
    
    def __init__(self, response: str):
        self.response = response
        self.last_system_prompt = None
        self.last_user_prompt = None
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.response


def test_build_system_prompt():
    """Test system prompt generation."""
    prompt = build_system_prompt()
    
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "entity_config" in prompt.lower()
    assert "core_entities" in prompt
    assert "occurrence_entities" in prompt
    assert "JSON" in prompt
    assert "depends_on" in prompt
    assert "cardinality" in prompt


def test_build_user_prompt():
    """Test user prompt generation."""
    entity_config = {
        "entities": {
            "Contract": {
                "kind": "core",
                "label": "Contract",
                "properties": {
                    "title": {"type": "string"}
                }
            }
        }
    }
    
    prompt = build_user_prompt(
        entity_config,
        "doc_1",
        "Test Document",
        "This is a contract."
    )
    
    assert "ENTITY CONFIG JSON:" in prompt
    assert "Contract" in prompt
    assert "doc_1" in prompt
    assert "Test Document" in prompt
    assert "This is a contract." in prompt


def test_parse_json_response_valid():
    """Test parsing valid JSON response."""
    response = '{"core_entities": [], "occurrence_entities": []}'
    result = _parse_json_response(response)
    
    assert result == {"core_entities": [], "occurrence_entities": []}


def test_parse_json_response_with_markdown():
    """Test parsing JSON wrapped in markdown code blocks."""
    response = '''```json
{
  "core_entities": [],
  "occurrence_entities": []
}
```'''
    result = _parse_json_response(response)
    
    assert result == {"core_entities": [], "occurrence_entities": []}


def test_parse_json_response_with_extra_text():
    """Test parsing JSON with extra text before/after."""
    response = '''Here is the result:
{"core_entities": [{"entity_id": "e1", "type": "Contract"}], "occurrence_entities": []}
That's all!'''
    result = _parse_json_response(response)
    
    assert "core_entities" in result
    assert len(result["core_entities"]) == 1


def test_parse_json_response_invalid():
    """Test parsing invalid response raises error."""
    with pytest.raises(ValueError):
        _parse_json_response("This is not JSON at all")


def test_normalize_entity_core():
    """Test normalizing a core entity."""
    entity = {
        "entity_id": "contract_1",
        "type": "Contract",
        "properties": {
            "title": "Service Agreement",
            "unknown_prop": "value"  # Should be filtered
        }
    }
    
    type_config = {
        "kind": "core",
        "properties": {
            "title": {"type": "string"}
        }
    }
    
    result = _normalize_entity(entity, type_config, is_occurrence=False)
    
    assert result["entity_id"] == "contract_1"
    assert result["type"] == "Contract"
    assert result["properties"] == {"title": "Service Agreement"}
    assert "span" in result
    assert result["span"]["start_offset"] is None
    assert result["span"]["end_offset"] is None


def test_normalize_entity_occurrence_with_links():
    """Test normalizing an occurrence entity with links."""
    entity = {
        "entity_id": "sig_1",
        "type": "SignatureEvent",
        "properties": {
            "date": "2025-01-01"
        },
        "links": {
            "contract": "contract_1"
        },
        "span": {
            "start_offset": 100,
            "end_offset": 150
        }
    }
    
    type_config = {
        "kind": "occurrence",
        "properties": {
            "date": {"type": "date"}
        },
        "depends_on": [
            {
                "role": "contract",
                "entity": "Contract",
                "cardinality": "1"
            }
        ]
    }
    
    result = _normalize_entity(entity, type_config, is_occurrence=True)
    
    assert result["entity_id"] == "sig_1"
    assert result["links"]["contract"] == "contract_1"
    assert result["span"]["start_offset"] == 100


def test_normalize_entity_occurrence_missing_required_link():
    """Test that missing required link raises error."""
    entity = {
        "entity_id": "sig_1",
        "type": "SignatureEvent",
        "properties": {},
        "links": {}  # Missing required "contract" link
    }
    
    type_config = {
        "kind": "occurrence",
        "properties": {},
        "depends_on": [
            {
                "role": "contract",
                "entity": "Contract",
                "cardinality": "1"  # Required
            }
        ]
    }
    
    with pytest.raises(ValueError, match="requires link 'contract'"):
        _normalize_entity(entity, type_config, is_occurrence=True)


def test_normalize_entities():
    """Test normalizing a list of entities."""
    entities = [
        {
            "entity_id": "c1",
            "type": "Contract",
            "properties": {"title": "Agreement"}
        },
        {
            "entity_id": "c2",
            "type": "UnknownType",  # Should be skipped
            "properties": {}
        },
        {
            "type": "Contract",  # Missing entity_id - should be skipped
            "properties": {}
        }
    ]
    
    entity_config = {
        "entities": {
            "Contract": {
                "kind": "core",
                "properties": {
                    "title": {"type": "string"}
                }
            }
        }
    }
    
    result = _normalize_entities(entities, entity_config, is_occurrence=False)
    
    # Only the first entity should be normalized
    assert len(result) == 1
    assert result[0]["entity_id"] == "c1"


def test_extract_entities_from_document():
    """Test full extraction pipeline."""
    entity_config = {
        "entities": {
            "Contract": {
                "kind": "core",
                "label": "Contract",
                "properties": {
                    "title": {"type": "string"}
                }
            },
            "SignatureEvent": {
                "kind": "occurrence",
                "label": "Signature Event",
                "properties": {
                    "date": {"type": "date"}
                },
                "depends_on": [
                    {
                        "role": "contract",
                        "entity": "Contract",
                        "cardinality": "1"
                    }
                ]
            }
        }
    }
    
    llm_response = json.dumps({
        "core_entities": [
            {
                "entity_id": "contract_1",
                "type": "Contract",
                "properties": {
                    "title": "Service Agreement"
                },
                "span": {
                    "start_offset": 0,
                    "end_offset": 20
                }
            }
        ],
        "occurrence_entities": [
            {
                "entity_id": "sig_1",
                "type": "SignatureEvent",
                "properties": {
                    "date": "2025-01-01"
                },
                "links": {
                    "contract": "contract_1"
                },
                "span": {
                    "start_offset": 100,
                    "end_offset": 150
                }
            }
        ]
    })
    
    llm_client = FakeLLMClient(llm_response)
    
    result = extract_entities_from_document(
        entity_config,
        "doc_1",
        "Test Contract",
        "This is a service agreement signed on 2025-01-01.",
        llm_client
    )
    
    assert len(result["core_entities"]) == 1
    assert result["core_entities"][0]["entity_id"] == "contract_1"
    assert result["core_entities"][0]["type"] == "Contract"
    
    assert len(result["occurrence_entities"]) == 1
    assert result["occurrence_entities"][0]["entity_id"] == "sig_1"
    assert result["occurrence_entities"][0]["type"] == "SignatureEvent"
    assert result["occurrence_entities"][0]["links"]["contract"] == "contract_1"


def test_extract_entities_misclassified():
    """Test that misclassified entities are moved to correct lists."""
    entity_config = {
        "entities": {
            "Contract": {
                "kind": "core",
                "properties": {}
            },
            "SignatureEvent": {
                "kind": "occurrence",
                "properties": {},
                "depends_on": [
                    {
                        "role": "contract",
                        "entity": "Contract",
                        "cardinality": "1"
                    }
                ]
            }
        }
    }
    
    # LLM incorrectly put SignatureEvent in core_entities
    llm_response = json.dumps({
        "core_entities": [
            {
                "entity_id": "sig_1",
                "type": "SignatureEvent",  # Should be in occurrence_entities
                "properties": {},
                "links": {"contract": "contract_1"}  # Has links
            }
        ],
        "occurrence_entities": []
    })
    
    llm_client = FakeLLMClient(llm_response)
    
    result = extract_entities_from_document(
        entity_config,
        "doc_1",
        "Test",
        "Test document",
        llm_client
    )
    
    # Should be moved to occurrence_entities
    assert len(result["core_entities"]) == 0
    assert len(result["occurrence_entities"]) == 1
    assert result["occurrence_entities"][0]["entity_id"] == "sig_1"


def test_extract_entities_empty_response():
    """Test extraction with empty response."""
    entity_config = {
        "entities": {
            "Contract": {
                "kind": "core",
                "properties": {}
            }
        }
    }
    
    llm_response = json.dumps({
        "core_entities": [],
        "occurrence_entities": []
    })
    
    llm_client = FakeLLMClient(llm_response)
    
    result = extract_entities_from_document(
        entity_config,
        "doc_1",
        "Empty Doc",
        "No entities here",
        llm_client
    )
    
    assert result["core_entities"] == []
    assert result["occurrence_entities"] == []


def test_extract_entities_invalid_response_structure():
    """Test extraction with invalid response structure."""
    entity_config = {
        "entities": {
            "Contract": {"kind": "core", "properties": {}}
        }
    }
    
    # Missing occurrence_entities key
    llm_response = json.dumps({
        "core_entities": []
    })
    
    llm_client = FakeLLMClient(llm_response)
    
    with pytest.raises(ValueError, match="must have 'core_entities' and 'occurrence_entities'"):
        extract_entities_from_document(
            entity_config,
            "doc_1",
            "Test",
            "Test",
            llm_client
        )
