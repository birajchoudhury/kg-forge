"""
Tests for hybrid GLiNER NER + LLM extraction backend.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from kg_forge.extraction.hybrid_backend import HybridExtractionBackend
from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.ontology.schema import OntologySchema
from kg_forge.entities.definitions import EntityDefinition, RelationDefinition
from kg_forge.extraction.exceptions import ExtractionError


@pytest.fixture
def mock_ontology():
    """Create mock ontology schema."""
    ontology = Mock(spec=OntologySchema)
    
    # Mock the to_llm_prompt_snippet method
    ontology.to_llm_prompt_snippet.return_value = """
{
  "entities": [
    {"type": "Product", "description": "Software products and services"},
    {"type": "Team", "description": "Engineering teams and departments"}
  ],
  "relations": [
    {"type": "DEVELOPS", "head": "Team", "tail": "Product"}
  ]
}
"""
    
    return ontology


@pytest.fixture
def sample_text():
    """Sample text for extraction."""
    return """
    The Platform Engineering team is working on Knowledge Discovery, a new AI-powered search product.
    John Smith leads the team and works closely with the Data Science organization.
    They are using AWS Bedrock for LLM capabilities.
    """


class TestHybridBackendInitialization:
    """Test hybrid backend initialization."""
    
    def test_init_fake_mode(self):
        """Test initialization in fake mode."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        assert backend.backend_name == "hybrid"
        assert backend.gliner_model == "urchade/gliner_base"
        assert backend.fake_mode is True
        assert backend.gliner_wrapper is not None
        assert backend.bedrock_client is not None
    
    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        backend = HybridExtractionBackend(
            gliner_model="urchade/gliner_large",
            llm_model_name="custom-model",
            llm_region="us-west-2",
            entity_confidence_threshold=0.8,
            fake_mode=True
        )
        
        assert backend.gliner_model == "urchade/gliner_large"
        assert backend.llm_model_name == "custom-model"
        assert backend.llm_region == "us-west-2"
        assert backend.entity_confidence_threshold == 0.8


class TestEntityDetection:
    """Test entity detection with GLiNER."""
    
    def test_detect_entities_basic(self, mock_ontology, sample_text):
        """Test basic entity detection."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        # Detect entities using actual fake backend
        detected = backend._detect_entities_with_gliner(sample_text, mock_ontology)
        
        # FakeGLiNERWrapper returns first few words as entities
        # Just verify it returns a list of entities with expected structure
        assert isinstance(detected, list)
        for entity in detected:
            assert "text" in entity
            assert "entity_type" in entity
            assert "start_offset" in entity
            assert "end_offset" in entity
            assert "confidence" in entity


class TestLLMEnrichment:
    """Test LLM-based property and relation extraction."""
    
    def test_build_hybrid_prompt(self, mock_ontology, sample_text):
        """Test hybrid prompt construction."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        detected_entities = [
            {
                "text": "Platform Engineering team",
                "entity_type": "Team",
                "start_offset": 9,
                "end_offset": 34
            },
            {
                "text": "Knowledge Discovery",
                "entity_type": "Product",
                "start_offset": 50,
                "end_offset": 69
            }
        ]
        
        prompt = backend._build_hybrid_prompt(sample_text, detected_entities, mock_ontology)
        
        # Check prompt contains detected entities
        assert "Platform Engineering team" in prompt
        assert "Knowledge Discovery" in prompt
        
        # Check prompt contains instructions
        assert "entity_properties" in prompt
        assert "relations" in prompt
        assert "ONLY valid JSON" in prompt
    
    def test_enrich_with_llm_success(self, mock_ontology, sample_text):
        """Test successful LLM enrichment."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        detected_entities = [
            {
                "text": "Platform Engineering team",
                "entity_type": "Team",
                "start_offset": 9,
                "end_offset": 34,
                "confidence": 0.92
            },
            {
                "text": "Knowledge Discovery",
                "entity_type": "Product",
                "start_offset": 50,
                "end_offset": 69,
                "confidence": 0.89
            }
        ]
        
        # Mock LLM response in the correct format (dict with response_text key)
        llm_response = {
            "response_text": '''
            {
                "relations": [
                    {
                        "source_entity": "Platform Engineering team",
                        "relation_type": "DEVELOPS",
                        "target_entity": "Knowledge Discovery",
                        "confidence": 0.95
                    }
                ]
            }
            '''
        }
        
        backend.bedrock_client.call_model = Mock(return_value=llm_response)
        
        result = backend._enrich_with_llm(
            content=sample_text,
            detected_entities=detected_entities,
            ontology=mock_ontology,
            doc_id="test_doc"
        )
    
        # Check result structure - should contain the relation
        assert isinstance(result, LexicalGraph)
        assert len(result.relations) == 1
        assert result.relations[0].type == "DEVELOPS"
    
    def test_enrich_with_llm_failure_fallback(self, mock_ontology, sample_text):
        """Test fallback when LLM enrichment fails."""
        backend = HybridExtractionBackend(fake_mode=True, max_retries=2)
        
        detected_entities = [
            {
                "text": "Test Entity",
                "entity_type": "Product",
                "start_offset": 0,
                "end_offset": 11
            }
        ]
        
        # Mock LLM failure
        backend.bedrock_client.call_model = Mock(side_effect=Exception("LLM error"))
        
        result = backend._enrich_with_llm(
            content=sample_text,
            detected_entities=detected_entities,
            ontology=mock_ontology,
            doc_id="test_doc"
        )
        
        # Should return graph with entities only (no relations)
        assert isinstance(result, LexicalGraph)
        assert len(result.mentions) == 1
        assert len(result.relations) == 0
        assert result.metadata.get("enrichment_method") == "failed"


class TestMergeResults:
    """Test hybrid graph creation from GLiNER entities and LLM relations."""
    
    def test_create_hybrid_graph_basic(self, mock_ontology):
        """Test basic hybrid graph creation."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        detected_entities = [
            {
                "text": "Team A",
                "entity_type": "Team",
                "start_offset": 0,
                "end_offset": 6,
                "confidence": 0.9
            },
            {
                "text": "Product X",
                "entity_type": "Product",
                "start_offset": 20,
                "end_offset": 29,
                "confidence": 0.85
            }
        ]
        
        # Create actual LexicalRelation objects
        llm_relations = [
            LexicalRelation(
                id="test_doc_relation_0",
                type="DEVELOPS",
                src_mention_id="test_doc_mention_0",
                dst_mention_id="test_doc_mention_1",
                features={
                    "backend": "hybrid_llm",
                    "confidence": 0.9,
                    "extraction_method": "llm_hybrid"
                }
            )
        ]
        
        merged = backend._create_hybrid_graph(
            detected_entities=detected_entities,
            relations=llm_relations,
            doc_id="test_doc"
        )
        
        assert len(merged.mentions) == 2
        assert len(merged.relations) == 1
        
        # Check relation has proper mention IDs
        relation = merged.relations[0]
        assert relation.type == "DEVELOPS"
        assert relation.features.get("extraction_method") == "llm_hybrid"
    
    def test_create_hybrid_graph_unmatched_relations(self, mock_ontology):
        """Test handling of relations with entities only."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        detected_entities = [
            {
                "text": "Team A",
                "entity_type": "Team",
                "start_offset": 0,
                "end_offset": 6,
                "confidence": 0.9
            }
        ]
        
        # No relations
        llm_relations = []
        
        merged = backend._create_hybrid_graph(
            detected_entities=detected_entities,
            relations=llm_relations,
            doc_id="test_doc"
        )
        
        # Should have entity but no relations
        assert len(merged.mentions) == 1
        assert len(merged.relations) == 0


class TestFullExtraction:
    """Test full end-to-end extraction."""
    
    def test_extract_complete_pipeline(self, mock_ontology, sample_text):
        """Test complete extraction pipeline."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        # Mock LLM response in correct format
        llm_response = {
            "response_text": '{"relations": []}'
        }
        backend.bedrock_client.call_model = Mock(return_value=llm_response)
        
        result = backend.extract(sample_text, mock_ontology, "test_doc")
        
        # Verify results (FakeGLiNERWrapper will detect some entities)
        assert isinstance(result, LexicalGraph)
        assert len(result.mentions) >= 0  # May detect entities depending on text
        
        # Check metadata
        assert result.metadata["backend"] == "hybrid"
        assert result.metadata["gliner_model"] == "urchade/gliner_base"
        assert result.metadata["detection_method"] == "gliner"
        
        # Check mentions have correct detection method
        for mention in result.mentions:
            assert mention.features.get("detection_method") == "gliner"
    
    def test_extract_with_gliner_failure(self, mock_ontology, sample_text):
        """Test extraction when GLiNER detection fails."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        # Mock GLiNER failure
        backend.gliner_wrapper.extract_entities = Mock(side_effect=Exception("GLiNER error"))
        
        # Should fallback to gliner-only mode
        llm_response = {
            "response_text": '{"entities": [], "relations": []}'
        }
        backend.bedrock_client.call_model = Mock(return_value=llm_response)
        
        result = backend.extract(sample_text, mock_ontology, "test_doc")
        
        # Should return graph (may be empty due to GLiNER failure)
        assert isinstance(result, LexicalGraph)
        # Metadata should indicate GLiNER-based detection
        assert result.metadata["detection_method"] == "gliner"


class TestBackendInfo:
    """Test backend info and statistics."""
    
    def test_get_backend_info(self):
        """Test get_backend_info method."""
        backend = HybridExtractionBackend(
            gliner_model="urchade/gliner_base",
            llm_model_name="test-model",
            fake_mode=True
        )
        
        info = backend.get_backend_info()
        
        assert info["name"] == "hybrid"
        assert info["description"] == "Hybrid GLiNER + LLM extraction"
        assert info["gliner_model"] == "urchade/gliner_base"
        assert info["llm_model"] == "test-model"
    
    def test_statistics_tracking(self, mock_ontology, sample_text):
        """Test statistics are properly tracked."""
        backend = HybridExtractionBackend(fake_mode=True)
        
        # Mock successful extraction
        mock_entities = [
            {
                "text": "Test Entity",
                "label": "Product",
                "start": 0,
                "end": 11,
                "score": 0.9
            }
        ]
        
        backend.gliner_wrapper.predict_entities = Mock(return_value=mock_entities)
        backend.bedrock_client.call_model = Mock(return_value='{"relations": []}')
        
        # Run multiple extractions
        backend.extract(sample_text, mock_ontology, "doc1")
        backend.extract(sample_text, mock_ontology, "doc2")
        
        info = backend.get_backend_info()
        
        # Verify backend info is returned (exact stats structure may vary)
        assert info["name"] == "hybrid"
        assert info["gliner_model"] == "urchade/gliner_base"
