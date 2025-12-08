"""Tests for style configuration functionality."""

import pytest
import json

from kg_forge.render.style_config import StyleConfig, COLORS
from kg_forge.render.graph_query import NodeRecord, RelationshipRecord


class TestStyleConfig:
    """Test StyleConfig class functionality."""
    
    def test_style_config_initialization(self):
        """Test StyleConfig initialization."""
        config = StyleConfig()
        
        # Should be able to create without errors
        assert config is not None
    
    def test_get_node_style_for_document(self):
        """Test getting node style for document."""
        config = StyleConfig()
        
        # Create a proper NodeRecord
        doc_node = NodeRecord("1", ["Doc"], {"doc_id": "test_doc"})

        # Should return a style dictionary
        style = config.get_node_style(doc_node)
        
        assert style is not None
        assert isinstance(style, dict)
        assert "color" in style
    
    def test_get_node_style_for_entity(self):
        """Test getting node style for entity."""
        config = StyleConfig()
        
        # Create a proper NodeRecord for entity
        entity_node = NodeRecord("2", ["Entity"], {"name": "Product A", "entity_type": "Product"})

        # Test with entity
        style = config.get_node_style(entity_node)
        
        assert style is not None
        assert isinstance(style, dict)
        assert "color" in style
    
    def test_get_relationship_style(self):
        """Test getting relationship style."""
        config = StyleConfig()
        
        # Create a proper RelationshipRecord
        relationship = RelationshipRecord("r1", "1", "2", "MENTIONS", {})

        style = config.get_relationship_style(relationship)
        
        assert style is not None
        assert isinstance(style, dict)
        assert "color" in style
    
    def test_generate_neovis_config_structure(self):
        """Test generating neovis.js configuration structure."""
        config = StyleConfig()
        
        # Create sample nodes and relationships
        nodes = [NodeRecord("1", ["Doc"], {"doc_id": "test"})]
        relationships = [RelationshipRecord("r1", "1", "2", "MENTIONS", {})]

        neovis_config = config.generate_neovis_config(nodes, relationships)        # Should have required neovis.js structure
        assert "labels" in neovis_config
        assert "relationships" in neovis_config
        
        # Labels should include both Doc and Entity configurations
        labels_config = neovis_config["labels"]
        assert "Doc" in labels_config
        # Check for expected structure - may not have Entity if no Entity nodes in test data
        assert isinstance(labels_config, dict)
        assert len(labels_config) > 0  # Should have at least one label configured
        
        # Each label should have required neovis.js properties
        doc_config = labels_config["Doc"]
        assert "color" in doc_config

        # Entity config only exists if there are Entity nodes in the test data
        # Since we only passed Doc nodes, we shouldn't expect Entity config
        assert len(labels_config) >= 1  # Should have at least Doc config
    
    def test_neovis_config_serializable(self):
        """Test that neovis.js config is JSON serializable."""
        config = StyleConfig()
        
        # Create sample nodes and relationships  
        nodes = [NodeRecord("1", ["Doc"], {"doc_id": "test"})]
        relationships = [RelationshipRecord("r1", "1", "2", "MENTIONS", {})]

        neovis_config = config.generate_neovis_config(nodes, relationships)        # Should be able to serialize to JSON without errors
        try:
            json_str = json.dumps(neovis_config)
            # And deserialize back
            parsed = json.loads(json_str)
            assert parsed == neovis_config
        except (TypeError, ValueError) as e:
            pytest.fail(f"Neovis config is not JSON serializable: {e}")


class TestStyleConfigDefaults:
    """Test default configurations and color palettes."""
    
    def test_default_color_palette_completeness(self):
        """Test that default color palette has expected colors."""
        # Should have colors defined
        assert "doc" in COLORS
        assert "entity_product" in COLORS
        assert "entity_team" in COLORS
        
        # Colors should be hex format
        for color_name, color_value in COLORS.items():
            assert color_value.startswith("#")
            assert len(color_value) == 7  # Hex color format
    
    def test_color_palette_uniqueness(self):
        """Test that color palette has reasonably unique colors."""
        colors = list(COLORS.values())
        unique_colors = set(colors)
        
        # Should have mostly unique colors
        assert len(unique_colors) >= len(colors) * 0.7