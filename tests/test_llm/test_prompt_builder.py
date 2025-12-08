"""
Tests for prompt builder functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from kg_forge.llm.prompt_builder import PromptBuilder
from kg_forge.ontology.schema import OntologySchema
from kg_forge.entities.definitions import EntityDefinition


class TestPromptBuilder:
    """Tests for PromptBuilder class."""
    
    def test_prompt_builder_initialization(self):
        """Test PromptBuilder initialization."""
        ontology = Mock(spec=OntologySchema)
        builder = PromptBuilder(ontology)
        
        assert builder.ontology is ontology
    
    def test_build_prompt_basic(self):
        """Test basic prompt building."""
        # Mock ontology schema
        ontology = Mock(spec=OntologySchema)
        ontology.to_llm_prompt_snippet.return_value = """
{
  "entities": [
    {"type": "Product", "description": "Software products"},
    {"type": "Team", "description": "Development teams"}
  ],
  "relations": []
}
"""
        ontology.entities = {"Product": Mock(), "Team": Mock()}
        ontology.relations = {}
        
        builder = PromptBuilder(ontology)
        
        document_content = "This is test document content."
        
        result = builder.build_extraction_prompt(document_content)
        
        # Check that document content is in the result
        assert document_content in result
        assert "Product" in result
        assert "Team" in result
        assert "Software products" in result
        assert "Development teams" in result
    
    def test_build_prompt_with_custom_template(self):
        """Test prompt building with custom template."""
        ontology = Mock(spec=OntologySchema)
        ontology.to_llm_prompt_snippet.return_value = """
{
  "entities": [
    {"type": "Product", "description": "Software products"}
  ],
  "relations": []
}
"""
        ontology.entities = {"Product": Mock()}
        ontology.relations = {}
        
        builder = PromptBuilder(ontology)
        
        document_content = "The Platform Engineering team built the Knowledge Discovery product."
        custom_template = "Find entities: {{ENTITY_TYPE_DEFINITIONS}} in {{DOCUMENT_CONTENT}}"
        
        result = builder.build_extraction_prompt(document_content, custom_template)
        
        assert "Find entities:" in result
        assert document_content in result
        assert "Product" in result
    
    def test_build_prompt_empty_content(self):
        """Test prompt building with empty document content."""
        ontology = Mock(spec=OntologySchema)
        ontology.to_llm_prompt_snippet.return_value = '{"entities": [], "relations": []}'
        ontology.entities = {}
        ontology.relations = {}
        
        builder = PromptBuilder(ontology)
        
        result = builder.build_extraction_prompt("")
        
        # Empty content should still produce a valid prompt
        assert isinstance(result, str)
        assert len(result) > 0
        assert "{{DOCUMENT_CONTENT}}" not in result  # Template should be processed
    
    def test_build_prompt_no_entities(self):
        """Test prompt building when no entities are defined."""
        ontology = Mock(spec=OntologySchema)
        ontology.to_llm_prompt_snippet.return_value = '{"entities": [], "relations": []}'
        ontology.entities = {}
        ontology.relations = {}
        
        builder = PromptBuilder(ontology)
        
        result = builder.build_extraction_prompt("Document content")
        
        assert "Document content" in result
        assert isinstance(result, str)
    
    def test_build_prompt_multiple_placeholders(self):
        """Test prompt building with multiple DOCUMENT_CONTENT placeholders."""
        ontology = Mock(spec=OntologySchema)
        ontology.to_llm_prompt_snippet.return_value = '{"entities": [], "relations": []}'
        ontology.entities = {}
        ontology.relations = {}
        
        builder = PromptBuilder(ontology)
        
        template = "Start: {{DOCUMENT_CONTENT}} Middle: {{DOCUMENT_CONTENT}} End"
        document_content = "TEST_CONTENT"
        
        result = builder.build_extraction_prompt(document_content, template)
        
        assert result == "Start: TEST_CONTENT Middle: TEST_CONTENT End"
    
    def test_build_prompt_entity_definition_formatting(self):
        """Test proper formatting of entity definitions."""
        ontology = Mock(spec=OntologySchema)
        ontology.to_llm_prompt_snippet.return_value = """ 
{
  "entities": [
    {"type": "Product", "description": "Software products and services"},
    {"type": "Team", "description": "Development and engineering teams"}
  ],
  "relations": []
}
"""
        ontology.entities = {"Product": Mock(), "Team": Mock()}
        ontology.relations = {}
        
        builder = PromptBuilder(ontology)
        
        result = builder.build_extraction_prompt("Test document")
        
        # Check that entity definitions and content are included
        assert "Product" in result
        assert "Software products and services" in result
        assert "Team" in result
        assert "Development and engineering teams" in result
        assert "Test document" in result