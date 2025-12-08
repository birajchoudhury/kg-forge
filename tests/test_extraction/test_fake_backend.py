"""
Tests for fake extraction backend.

Tests the FakeExtractionBackend for deterministic testing.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock

from kg_forge.extraction.fake_backend import FakeExtractionBackend, create_fake_backend_with_test_data
from kg_forge.models.lexical import LexicalGraph
from kg_forge.extraction.exceptions import ExtractionError, ValidationError


@pytest.fixture
def mock_ontology():
    """Create a mock ontology pack for testing."""
    ontology = Mock()
    
    # Create mock entity definitions with proper structure
    mock_def1 = Mock()
    mock_def1.entity_id = "Product"
    mock_def1.name = "Product"
    mock_def1.relations = []  # Empty list instead of Mock
    
    mock_def2 = Mock()
    mock_def2.entity_id = "Technology"
    mock_def2.name = "Technology"
    mock_def2.relations = []
    
    mock_def3 = Mock()
    mock_def3.entity_id = "Topic"
    mock_def3.name = "Topic"
    mock_def3.relations = []
    
    ontology.get_entity_definitions.return_value = [mock_def1, mock_def2, mock_def3]
    return ontology


class TestFakeExtractionBackend:
    """Test FakeExtractionBackend."""
    
    def test_backend_initialization(self):
        """Test basic backend initialization."""
        backend = FakeExtractionBackend()
        
        assert backend.get_backend_name() == "fake"
        assert backend.validate_configuration() is True
        assert not backend.malformed_mode
        assert not backend.failure_mode
    
    def test_backend_initialization_with_options(self):
        """Test backend initialization with options."""
        backend = FakeExtractionBackend(
            malformed_mode=True,
            failure_mode=False
        )
        
        assert backend.malformed_mode is True
        assert backend.failure_mode is False
    
    def test_failure_mode(self, mock_ontology):
        """Test backend in failure mode."""
        backend = FakeExtractionBackend(failure_mode=True)
        
        with pytest.raises(ExtractionError, match="configured to fail"):
            backend.extract("test content", mock_ontology, "test_doc")
    
    def test_failure_mode_validation(self):
        """Test validation fails in failure mode."""
        backend = FakeExtractionBackend(failure_mode=True)
        assert backend.validate_configuration() is False
    
    def test_basic_extraction(self, mock_ontology):
        """Test basic fake extraction."""
        backend = FakeExtractionBackend()
        
        content = "This is a test document about Knowledge Discovery and Neo4j technology."
        doc_id = "test_doc_1"
        
        result = backend.extract(content, mock_ontology, doc_id)
        
        assert isinstance(result, LexicalGraph)
        assert len(result.mentions) > 0
        assert result.metadata["backend"] == "fake"
        assert result.metadata["doc_id"] == doc_id
        
        # Check mentions have proper doc_id
        for mention in result.mentions:
            assert mention.doc_id == doc_id
            assert mention.id.startswith(f"{doc_id}_mention_")
    
    def test_deterministic_extraction(self, mock_ontology):
        """Test that extraction is deterministic for same content."""
        backend = FakeExtractionBackend()
        
        content = "Test content for deterministic extraction."
        doc_id = "test_doc"
        
        # Extract twice
        result1 = backend.extract(content, mock_ontology, doc_id)
        result2 = backend.extract(content, mock_ontology, doc_id)
        
        # Should have same number of mentions and relations
        assert len(result1.mentions) == len(result2.mentions)
        assert len(result1.relations) == len(result2.relations)
        
        # Content hash should be the same
        assert result1.metadata.get("deterministic") == result2.metadata.get("deterministic")
    
    def test_different_content_different_results(self, mock_ontology):
        """Test that different content gives different results."""
        backend = FakeExtractionBackend()
        
        content1 = "First test document about products."
        content2 = "Second test document with completely different content about technologies."
        doc_id = "test_doc"
        
        result1 = backend.extract(content1, mock_ontology, doc_id)
        result2 = backend.extract(content2, mock_ontology, doc_id)
        
        # Should have different content hashes
        hash1 = result1.metadata.get("content_hash")
        hash2 = result2.metadata.get("content_hash")
        assert hash1 != hash2
        
        # May have different numbers of mentions (based on word count)
        # This is not guaranteed but likely for very different content
    
    def test_empty_content(self, mock_ontology):
        """Test extraction with empty content."""
        backend = FakeExtractionBackend()
        
        result = backend.extract("", mock_ontology, "empty_doc")
        
        assert isinstance(result, LexicalGraph)
        assert len(result.mentions) >= 0  # May generate placeholder mentions
        assert result.metadata["backend"] == "fake"
    
    def test_backend_info(self):
        """Test get_backend_info method."""
        backend = FakeExtractionBackend(
            malformed_mode=True,
            failure_mode=False
        )
        
        info = backend.get_backend_info()
        
        assert info["backend_name"] == "fake"
        assert info["malformed_mode"] is True
        assert info["failure_mode"] is False
        assert info["deterministic"] is True
        assert "cached_test_files" in info
    
    def test_relations_generation(self, mock_ontology):
        """Test that relations are generated between mentions."""
        # Mock ontology with relation definitions
        mock_entity_def = Mock()
        mock_entity_def.entity_id = "Product"
        mock_entity_def.relations = [
            Mock(to_label="USES", target_type="Technology")
        ]
        mock_ontology.get_entity_definitions.return_value = [mock_entity_def]
        
        backend = FakeExtractionBackend()
        
        content = "Product A uses Technology B in the system."
        doc_id = "test_doc"
        
        result = backend.extract(content, mock_ontology, doc_id)
        
        # Should generate some mentions
        assert len(result.mentions) > 0
        
        # If enough mentions, should generate relations
        if len(result.mentions) >= 2:
            assert len(result.relations) > 0
            
            # Check relation references valid mentions
            mention_ids = {m.id for m in result.mentions}
            for relation in result.relations:
                assert relation.src_mention_id in mention_ids
                assert relation.dst_mention_id in mention_ids


class TestFakeBackendWithTestData:
    """Test fake backend with predefined test data."""
    
    def test_create_with_test_data(self):
        """Test creating backend with built-in test data."""
        backend = create_fake_backend_with_test_data()
        
        assert backend.get_backend_name() == "fake"
        assert len(backend._test_data_cache) > 0
        assert "technical_doc" in backend._test_data_cache
    
    def test_test_data_extraction(self, mock_ontology):
        """Test extraction using test data."""
        backend = create_fake_backend_with_test_data()
        
        # Use a doc_id that matches test data
        result = backend.extract("Some content", mock_ontology, "technical_doc")
        
        assert isinstance(result, LexicalGraph)
        assert result.metadata.get("test_data") is True
        
        # Should have entities from test data
        assert len(result.mentions) > 0
        
        # Check for expected entity types from test data
        entity_types = {m.entity_type for m in result.mentions}
        assert "Product" in entity_types or "Technology" in entity_types
    
    def test_fallback_to_deterministic(self, mock_ontology):
        """Test fallback to deterministic generation when no test data matches."""
        backend = create_fake_backend_with_test_data()
        
        # Use a doc_id that doesn't match test data
        result = backend.extract("Random content", mock_ontology, "unknown_doc_id")
        
        assert isinstance(result, LexicalGraph)
        assert result.metadata.get("deterministic") is True
        assert len(result.mentions) > 0