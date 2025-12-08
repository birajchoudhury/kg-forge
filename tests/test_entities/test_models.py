"""Tests for entity definition models."""

import pytest
from kg_forge.entities.models import EntityDefinition, RelationDefinition, ExampleDefinition


class TestRelationDefinition:
    """Tests for RelationDefinition parsing."""
    
    def test_parse_valid_relation(self):
        """Test parsing valid relation format."""
        relation_line = "- Component : USES : USED_BY"
        relation = RelationDefinition.parse(relation_line)
        
        assert relation is not None
        assert relation.target_type == "Component"
        assert relation.to_label == "USES"
        assert relation.from_label == "USED_BY"
    
    def test_parse_with_extra_whitespace(self):
        """Test parsing with extra whitespace."""
        relation_line = "-  Technology  :  IMPLEMENTS  :  IMPLEMENTED_BY  "
        relation = RelationDefinition.parse(relation_line)
        
        assert relation is not None
        assert relation.target_type == "Technology"
        assert relation.to_label == "IMPLEMENTS"
        assert relation.from_label == "IMPLEMENTED_BY"
    
    def test_parse_invalid_format(self):
        """Test parsing invalid relation format."""
        invalid_lines = [
            "Component : USES",  # Missing from_label
            "Component USES USED_BY",  # Missing colons
            "- : USES : USED_BY",  # Empty target_type
            "- Component : : USED_BY",  # Empty to_label
            "- Component : USES :",  # Empty from_label
        ]
        
        for line in invalid_lines:
            relation = RelationDefinition.parse(line)
            assert relation is None
    
    def test_parse_empty_line(self):
        """Test parsing empty or whitespace-only line."""
        relation = RelationDefinition.parse("")
        assert relation is None
        
        relation = RelationDefinition.parse("   ")
        assert relation is None


class TestEntityDefinition:
    """Tests for EntityDefinition functionality."""
    
    def test_to_dict_minimal(self):
        """Test to_dict with minimal entity definition."""
        entity = EntityDefinition(id="TestEntity")
        result = entity.to_dict()
        
        expected = {
            "id": "TestEntity",
            "name": None,
            "description": None,
            "relations": [],
            "examples": [],
            "source_file": None
        }
        
        assert result == expected
    
    def test_to_dict_complete(self):
        """Test to_dict with complete entity definition."""
        relations = [
            RelationDefinition("Component", "USES", "USED_BY"),
            RelationDefinition("Technology", "IMPLEMENTS", "IMPLEMENTED_BY")
        ]
        
        examples = [
            ExampleDefinition("Example 1", "First example description"),
            ExampleDefinition("Example 2", "Second example description")
        ]
        
        entity = EntityDefinition(
            id="Product",
            name="Product Management",
            description="Product-related entities and concepts",
            relations=relations,
            examples=examples,
            source_file="product.md"
        )
        
        result = entity.to_dict()
        
        expected = {
            "id": "Product",
            "name": "Product Management", 
            "description": "Product-related entities and concepts",
            "relations": [
                {
                    "target_type": "Component",
                    "to_label": "USES",
                    "from_label": "USED_BY"
                },
                {
                    "target_type": "Technology",
                    "to_label": "IMPLEMENTS",
                    "from_label": "IMPLEMENTED_BY"
                }
            ],
            "examples": [
                {
                    "title": "Example 1",
                    "description": "First example description"
                },
                {
                    "title": "Example 2", 
                    "description": "Second example description"
                }
            ],
            "source_file": "product.md"
        }
        
        assert result == expected


class TestExampleDefinition:
    """Tests for ExampleDefinition."""
    
    def test_creation(self):
        """Test basic ExampleDefinition creation."""
        example = ExampleDefinition("Test Title", "Test description")
        
        assert example.title == "Test Title"
        assert example.description == "Test description"
    
    def test_empty_values(self):
        """Test ExampleDefinition with empty values."""
        example = ExampleDefinition("", "")
        
        assert example.title == ""
        assert example.description == ""