"""
Tests for lexical data models.

Tests the LexicalMention, LexicalRelation, and LexicalGraph data models.
"""
import pytest
from kg_forge.models.lexical import LexicalMention, LexicalRelation, LexicalGraph, empty_lexical_graph


class TestLexicalMention:
    """Test LexicalMention data model."""
    
    def test_valid_mention_creation(self):
        """Test creating a valid LexicalMention."""
        mention = LexicalMention(
            id="test_mention_1",
            doc_id="test_doc",
            entity_type="Product",
            surface="Knowledge Discovery",
            start_offset=0,
            end_offset=19
        )
        
        assert mention.id == "test_mention_1"
        assert mention.doc_id == "test_doc"
        assert mention.entity_type == "Product"
        assert mention.surface == "Knowledge Discovery"
        assert mention.start_offset == 0
        assert mention.end_offset == 19
        assert mention.features == {}
    
    def test_mention_with_features(self):
        """Test LexicalMention with features."""
        features = {"confidence": 0.9, "context": "test context"}
        
        mention = LexicalMention(
            id="test_mention_1",
            doc_id="test_doc",
            entity_type="Product", 
            surface="Test Product",
            start_offset=0,
            end_offset=12,
            features=features
        )
        
        assert mention.features == features
        assert mention.features["confidence"] == 0.9
    
    def test_invalid_offsets(self):
        """Test that invalid offsets raise ValueError."""
        with pytest.raises(ValueError, match="Invalid offsets"):
            LexicalMention(
                id="test_mention_1",
                doc_id="test_doc",
                entity_type="Product",
                surface="Test",
                start_offset=10,
                end_offset=5  # Invalid: end before start
            )
    
    def test_empty_surface_text(self):
        """Test that empty surface text raises ValueError."""
        with pytest.raises(ValueError, match="Surface text cannot be empty"):
            LexicalMention(
                id="test_mention_1", 
                doc_id="test_doc",
                entity_type="Product",
                surface="   ",  # Whitespace only
                start_offset=0,
                end_offset=3
            )
    
    def test_empty_entity_type(self):
        """Test that empty entity type raises ValueError."""
        with pytest.raises(ValueError, match="Entity type cannot be empty"):
            LexicalMention(
                id="test_mention_1",
                doc_id="test_doc", 
                entity_type="",  # Empty type
                surface="Test",
                start_offset=0,
                end_offset=4
            )
    
    def test_mention_serialization(self):
        """Test mention to_dict and from_dict."""
        mention = LexicalMention(
            id="test_mention_1",
            doc_id="test_doc",
            entity_type="Product",
            surface="Test Product",
            start_offset=0,
            end_offset=12,
            features={"confidence": 0.8}
        )
        
        # Test to_dict
        data = mention.to_dict()
        expected_keys = {'id', 'doc_id', 'entity_type', 'surface', 'start_offset', 'end_offset', 'features'}
        assert set(data.keys()) == expected_keys
        
        # Test from_dict
        restored_mention = LexicalMention.from_dict(data)
        assert restored_mention.id == mention.id
        assert restored_mention.doc_id == mention.doc_id
        assert restored_mention.entity_type == mention.entity_type
        assert restored_mention.surface == mention.surface
        assert restored_mention.start_offset == mention.start_offset
        assert restored_mention.end_offset == mention.end_offset
        assert restored_mention.features == mention.features


class TestLexicalRelation:
    """Test LexicalRelation data model."""
    
    def test_valid_relation_creation(self):
        """Test creating a valid LexicalRelation."""
        relation = LexicalRelation(
            id="test_relation_1",
            type="USES",
            src_mention_id="mention_1",
            dst_mention_id="mention_2"
        )
        
        assert relation.id == "test_relation_1"
        assert relation.type == "USES"
        assert relation.src_mention_id == "mention_1"
        assert relation.dst_mention_id == "mention_2"
        assert relation.features == {}
    
    def test_relation_with_features(self):
        """Test LexicalRelation with features."""
        features = {"confidence": 0.7, "distance": 5}
        
        relation = LexicalRelation(
            id="test_relation_1",
            type="WORKS_ON",
            src_mention_id="mention_1",
            dst_mention_id="mention_2",
            features=features
        )
        
        assert relation.features == features
        assert relation.features["confidence"] == 0.7
    
    def test_empty_relation_type(self):
        """Test that empty relation type raises ValueError."""
        with pytest.raises(ValueError, match="Relation type cannot be empty"):
            LexicalRelation(
                id="test_relation_1",
                type="",  # Empty type
                src_mention_id="mention_1",
                dst_mention_id="mention_2"
            )
    
    def test_self_relation(self):
        """Test that self-relations raise ValueError."""
        with pytest.raises(ValueError, match="Source and destination mentions cannot be the same"):
            LexicalRelation(
                id="test_relation_1",
                type="SELF_REF",
                src_mention_id="mention_1",
                dst_mention_id="mention_1"  # Same as source
            )
    
    def test_relation_serialization(self):
        """Test relation to_dict and from_dict."""
        relation = LexicalRelation(
            id="test_relation_1",
            type="USES",
            src_mention_id="mention_1",
            dst_mention_id="mention_2",
            features={"confidence": 0.6}
        )
        
        # Test to_dict
        data = relation.to_dict()
        expected_keys = {'id', 'type', 'src_mention_id', 'dst_mention_id', 'features'}
        assert set(data.keys()) == expected_keys
        
        # Test from_dict
        restored_relation = LexicalRelation.from_dict(data)
        assert restored_relation.id == relation.id
        assert restored_relation.type == relation.type
        assert restored_relation.src_mention_id == relation.src_mention_id
        assert restored_relation.dst_mention_id == relation.dst_mention_id
        assert restored_relation.features == relation.features


class TestLexicalGraph:
    """Test LexicalGraph data model."""
    
    def test_empty_graph_creation(self):
        """Test creating an empty LexicalGraph."""
        graph = LexicalGraph(mentions=[], relations=[])
        
        assert graph.mentions == []
        assert graph.relations == []
        assert graph.metadata == {}
    
    def test_graph_with_mentions_and_relations(self):
        """Test LexicalGraph with valid mentions and relations."""
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="test_doc",
                entity_type="Product",
                surface="Product A",
                start_offset=0,
                end_offset=9
            ),
            LexicalMention(
                id="mention_2",
                doc_id="test_doc",
                entity_type="Technology",
                surface="Neo4j",
                start_offset=20,
                end_offset=25
            )
        ]
        
        relations = [
            LexicalRelation(
                id="relation_1",
                type="USES",
                src_mention_id="mention_1",
                dst_mention_id="mention_2"
            )
        ]
        
        metadata = {"backend": "test", "version": "1.0"}
        
        graph = LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata=metadata
        )
        
        assert len(graph.mentions) == 2
        assert len(graph.relations) == 1
        assert graph.metadata == metadata
    
    def test_duplicate_mention_ids(self):
        """Test that duplicate mention IDs raise ValueError."""
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="test_doc",
                entity_type="Product",
                surface="Product A",
                start_offset=0,
                end_offset=9
            ),
            LexicalMention(
                id="mention_1",  # Duplicate ID
                doc_id="test_doc",
                entity_type="Product",
                surface="Product B",
                start_offset=10,
                end_offset=19
            )
        ]
        
        with pytest.raises(ValueError, match="Duplicate mention IDs found"):
            LexicalGraph(mentions=mentions, relations=[])
    
    def test_invalid_relation_references(self):
        """Test that invalid relation references raise ValueError."""
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="test_doc",
                entity_type="Product",
                surface="Product A",
                start_offset=0,
                end_offset=9
            )
        ]
        
        relations = [
            LexicalRelation(
                id="relation_1",
                type="USES",
                src_mention_id="mention_1",
                dst_mention_id="mention_999"  # Non-existent mention
            )
        ]
        
        with pytest.raises(ValueError, match="references unknown destination mention"):
            LexicalGraph(mentions=mentions, relations=relations)
    
    def test_graph_utility_methods(self):
        """Test LexicalGraph utility methods."""
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="test_doc",
                entity_type="Product",
                surface="Product A",
                start_offset=0,
                end_offset=9
            ),
            LexicalMention(
                id="mention_2",
                doc_id="test_doc",
                entity_type="Product",
                surface="Product B",
                start_offset=10,
                end_offset=19
            ),
            LexicalMention(
                id="mention_3",
                doc_id="test_doc",
                entity_type="Technology",
                surface="Neo4j",
                start_offset=20,
                end_offset=25
            )
        ]
        
        relations = [
            LexicalRelation(
                id="relation_1",
                type="USES",
                src_mention_id="mention_1",
                dst_mention_id="mention_3"
            ),
            LexicalRelation(
                id="relation_2", 
                type="USES",
                src_mention_id="mention_2",
                dst_mention_id="mention_3"
            )
        ]
        
        graph = LexicalGraph(mentions=mentions, relations=relations)
        
        # Test get_mention_by_id
        found_mention = graph.get_mention_by_id("mention_1")
        assert found_mention is not None
        assert found_mention.surface == "Product A"
        
        missing_mention = graph.get_mention_by_id("mention_999")
        assert missing_mention is None
        
        # Test get_mentions_by_type
        product_mentions = graph.get_mentions_by_type("Product")
        assert len(product_mentions) == 2
        
        tech_mentions = graph.get_mentions_by_type("Technology")
        assert len(tech_mentions) == 1
        
        # Test get_relations_by_type
        uses_relations = graph.get_relations_by_type("USES")
        assert len(uses_relations) == 2
        
        # Test get_outgoing_relations
        mention_1_outgoing = graph.get_outgoing_relations("mention_1")
        assert len(mention_1_outgoing) == 1
        assert mention_1_outgoing[0].dst_mention_id == "mention_3"
        
        # Test get_incoming_relations
        mention_3_incoming = graph.get_incoming_relations("mention_3")
        assert len(mention_3_incoming) == 2
    
    def test_graph_serialization(self):
        """Test LexicalGraph serialization."""
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="test_doc",
                entity_type="Product",
                surface="Test Product",
                start_offset=0,
                end_offset=12
            )
        ]
        
        metadata = {"backend": "test"}
        
        graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata=metadata
        )
        
        # Test to_dict
        data = graph.to_dict()
        assert "mentions" in data
        assert "relations" in data
        assert "metadata" in data
        assert len(data["mentions"]) == 1
        
        # Test from_dict
        restored_graph = LexicalGraph.from_dict(data)
        assert len(restored_graph.mentions) == 1
        assert restored_graph.mentions[0].surface == "Test Product"
        assert restored_graph.metadata == metadata
        
        # Test JSON serialization
        json_str = graph.to_json()
        assert isinstance(json_str, str)
        assert "Test Product" in json_str
        
        # Test JSON deserialization
        restored_from_json = LexicalGraph.from_json(json_str)
        assert len(restored_from_json.mentions) == 1
        assert restored_from_json.mentions[0].surface == "Test Product"
    
    def test_graph_summary(self):
        """Test LexicalGraph summary statistics."""
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="test_doc", 
                entity_type="Product",
                surface="Product A",
                start_offset=0,
                end_offset=9
            ),
            LexicalMention(
                id="mention_2",
                doc_id="test_doc",
                entity_type="Technology", 
                surface="Neo4j",
                start_offset=10,
                end_offset=15
            )
        ]
        
        relations = [
            LexicalRelation(
                id="relation_1",
                type="USES",
                src_mention_id="mention_1",
                dst_mention_id="mention_2"
            )
        ]
        
        metadata = {"backend": "test", "extraction_time": 1.5}
        
        graph = LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata=metadata
        )
        
        summary = graph.summary()
        
        assert summary["total_mentions"] == 2
        assert summary["total_relations"] == 1
        assert summary["entity_types"]["Product"] == 1
        assert summary["entity_types"]["Technology"] == 1
        assert summary["relation_types"]["USES"] == 1
        assert summary["backend"] == "test"
        assert summary["extraction_time"] == 1.5


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_empty_lexical_graph(self):
        """Test empty_lexical_graph utility function."""
        graph = empty_lexical_graph("test_backend")
        
        assert len(graph.mentions) == 0
        assert len(graph.relations) == 0
        assert graph.metadata["backend"] == "test_backend"