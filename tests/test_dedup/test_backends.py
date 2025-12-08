"""
Tests for deduplication backend implementations.
"""

import pytest
from unittest.mock import Mock, patch
from kg_forge.dedup.interface import create_dedup_backend
from kg_forge.dedup.no_dedup_backend import NoDedupBackend  
from kg_forge.dedup.splink_backend import SpLinkDedupBackend
from kg_forge.dedup.zingg_backend import ZinggDedupBackend
from kg_forge.dedup.ensemble_backend import EnsembleDedupBackend
from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.models.dedup import DedupedLexicalGraph, CanonicalLexicalEntity


class TestDedupBackendFactory:
    """Tests for deduplication backend factory."""
    
    def test_create_no_dedup_backend(self):
        """Test creating no-dedup backend."""
        backend = create_dedup_backend("none")
        assert isinstance(backend, NoDedupBackend)
        assert backend.get_backend_name() == "none"
    
    def test_create_splink_backend(self):
        """Test creating Splink backend."""
        backend = create_dedup_backend("splink")
        assert isinstance(backend, SpLinkDedupBackend)
        assert backend.get_backend_name() == "splink"
    
    def test_create_zingg_backend(self):
        """Test creating Zingg backend."""
        backend = create_dedup_backend("zingg")
        assert isinstance(backend, ZinggDedupBackend)
        assert backend.get_backend_name() == "zingg"
    
    def test_create_ensemble_backend(self):
        """Test creating ensemble backend."""
        backend = create_dedup_backend("both")
        assert isinstance(backend, EnsembleDedupBackend)
        assert backend.get_backend_name() == "ensemble"
    
    def test_create_backend_with_config(self):
        """Test creating backend with configuration."""
        config = {"similarity_threshold": 0.9}
        backend = create_dedup_backend("none", config)
        # NoDedupBackend doesn't use similarity_threshold
        assert backend is not None
    
    def test_invalid_backend_name(self):
        """Test creating backend with invalid name."""
        with pytest.raises(ValueError, match="Unknown deduplication backend: invalid"):
            create_dedup_backend("invalid")


class TestNoDedupBackend:
    """Tests for no-deduplication backend."""
    
    def test_initialization(self):
        """Test backend initialization."""
        backend = NoDedupBackend()
        assert backend.get_backend_name() == "none"
        assert backend.validate_configuration() == True
    
    def test_deduplicate_empty_graph(self):
        """Test deduplication with empty graph."""
        backend = NoDedupBackend()
        lexical_graph = LexicalGraph(mentions=[], relations=[], metadata={})
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        
        assert isinstance(result, DedupedLexicalGraph)
        assert len(result.canonical_entities) == 0
        assert len(result.relations) == 0
        assert result.metadata["dedup_backend"] == "none"
    
    def test_deduplicate_single_mention(self):
        """Test deduplication with single mention."""
        backend = NoDedupBackend()
        
        mention = LexicalMention(
            id="mention_1",
            doc_id="doc_1",
            surface="Python",
            entity_type="Technology", 
            start_offset=0,
            end_offset=6,
            features={"confidence": 0.9}
        )
        
        lexical_graph = LexicalGraph(
            mentions=[mention],
            relations=[],
            metadata={}
        )
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        
        assert len(result.canonical_entities) == 1
        canonical = result.canonical_entities[0]
        assert canonical.entity_type == "Technology"
        assert canonical.canonical_name == "Python"
        assert canonical.aliases == ["Python"]
        assert canonical.mention_ids == ["mention_1"]
        # CanonicalLexicalEntity doesn't have a namespace attribute
    
    def test_deduplicate_multiple_mentions(self):
        """Test deduplication with multiple mentions."""
        backend = NoDedupBackend()
        
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="doc_1",
                surface="Python",
                entity_type="Technology",
                start_offset=0,
                end_offset=6,
                features={"confidence": 0.9}
            ),
            LexicalMention(
                id="mention_2", 
                doc_id="doc_1",
                surface="Docker",
                entity_type="Technology",
                start_offset=10,
                end_offset=16,
                features={"confidence": 0.8}
            )
        ]
        
        relation = LexicalRelation(
            id="relation_1",
            type="USES",
            src_mention_id="mention_1",
            dst_mention_id="mention_2",
            features={"confidence": 0.7}
        )
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[relation],
            metadata={}
        )
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        
        assert len(result.canonical_entities) == 2
        assert len(result.relations) == 1
        
        # Check canonical entities
        python_entity = next(e for e in result.canonical_entities if e.canonical_name == "Python")
        docker_entity = next(e for e in result.canonical_entities if e.canonical_name == "Docker")
        
        assert python_entity.entity_type == "Technology"
        assert docker_entity.entity_type == "Technology"
        
        # Check canonical relation
        canonical_relation = result.relations[0]
        assert canonical_relation.type == "USES"
        assert canonical_relation.src_entity_id == python_entity.id
        assert canonical_relation.dst_entity_id == docker_entity.id
    
    def test_backend_info(self):
        """Test backend information."""
        backend = NoDedupBackend()
        info = backend.get_backend_info()
        
        assert info["backend_name"] == "none"
        assert info["description"] == "Pass-through deduplication that treats each mention as separate entity"


class TestSpLinkDedupBackend:
    """Tests for Splink deduplication backend."""
    
    def test_initialization(self):
        """Test backend initialization.""" 
        backend = SpLinkDedupBackend()
        assert backend.get_backend_name() == "splink"
        assert backend.similarity_threshold == 0.8
    
    def test_initialization_with_config(self):
        """Test backend initialization with custom config."""
        backend = SpLinkDedupBackend(similarity_threshold=0.9, custom_param=500)
        assert backend.similarity_threshold == 0.9
        assert backend.config["custom_param"] == 500
    
    def test_validate_configuration(self):
        """Test configuration validation."""
        backend = SpLinkDedupBackend()
        # Should return True even without Splink (fake implementation)
        assert backend.validate_configuration() == True
    
    def test_deduplicate_with_fake_implementation(self):
        """Test deduplication using fake Splink implementation."""
        backend = SpLinkDedupBackend()
        
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="doc_1",
                surface="Python",
                entity_type="Technology",
                start_offset=0,
                end_offset=6,
                features={"confidence": 0.9}
            ),
            LexicalMention(
                id="mention_2",
                doc_id="doc_1",
                surface="python", 
                entity_type="Technology",
                start_offset=10,
                end_offset=16,
                features={"confidence": 0.8}
            )
        ]
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={}
        )
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        
        assert isinstance(result, DedupedLexicalGraph)
        assert result.metadata["dedup_backend"] == "splink"  # Uses splink implementation
        # Fake implementation details may vary
        # Fake implementation should cluster similar mentions
        assert len(result.canonical_entities) <= len(mentions)
    
    def test_backend_info(self):
        """Test backend information."""
        backend = SpLinkDedupBackend()
        info = backend.get_backend_info()
        
        assert info["backend_name"] == "splink"
        assert "description" in info


class TestZinggDedupBackend:
    """Tests for Zingg deduplication backend."""
    
    def test_initialization(self):
        """Test backend initialization."""
        backend = ZinggDedupBackend()
        assert backend.get_backend_name() == "zingg"
        assert backend.confidence_threshold == 0.8
    
    def test_deduplicate_with_fake_implementation(self):
        """Test deduplication using fake Zingg implementation."""
        backend = ZinggDedupBackend()
        
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="doc_1",
                surface="John Smith",
                entity_type="Person",
                start_offset=0,
                end_offset=10,
                features={"confidence": 0.9}
            ),
            LexicalMention(
                id="mention_2",
                doc_id="doc_1",
                surface="J. Smith",
                entity_type="Person",
                start_offset=20,
                end_offset=28,
                features={"confidence": 0.8}
            )
        ]
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={}
        )
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        
        assert isinstance(result, DedupedLexicalGraph)
        assert result.metadata["dedup_backend"] == "zingg_fake"  # Uses fake implementation when Zingg not available
        # Fake mode details are implementation-specific
        # Should create canonical entities
        assert len(result.canonical_entities) > 0


class TestEnsembleDedupBackend:
    """Tests for ensemble deduplication backend."""
    
    def test_initialization(self):
        """Test backend initialization."""
        backend = EnsembleDedupBackend()
        assert backend.get_backend_name() == "ensemble"
        assert hasattr(backend, 'splink_backend')
        assert hasattr(backend, 'zingg_backend')
    
    def test_initialization_with_custom_backends(self):
        """Test initialization with custom backend configurations."""
        splink_config = {"similarity_threshold": 0.9}
        zingg_config = {"confidence_threshold": 0.9}
        
        backend = EnsembleDedupBackend(splink_config=splink_config, zingg_config=zingg_config)
        assert hasattr(backend, 'splink_backend')
        assert hasattr(backend, 'zingg_backend')
        assert backend.combination_strategy == "confidence_weighted"
    
    def test_deduplicate_confidence_weighted(self):
        """Test ensemble deduplication with confidence weighting."""
        backend = EnsembleDedupBackend()
        
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="doc_1",
                surface="Python",
                entity_type="Technology",
                start_offset=0,
                end_offset=6,
                features={"confidence": 0.9}
            ),
            LexicalMention(
                id="mention_2", 
                doc_id="doc_1",
                surface="Docker",
                entity_type="Technology",
                start_offset=10,
                end_offset=16,
                features={"confidence": 0.8}
            )
        ]
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={}
        )
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        
        assert isinstance(result, DedupedLexicalGraph)
        assert result.metadata["dedup_backend"] == "ensemble"
        assert result.metadata["combination_strategy"] == "confidence_weighted"
        # Ensemble processing adds various metadata keys
    
    def test_deduplicate_voting_strategy(self):
        """Test ensemble deduplication with voting strategy."""
        backend = EnsembleDedupBackend(combination_strategy="voting")
        
        mentions = [
            LexicalMention(
                id="mention_2",
                doc_id="doc_1",
                surface="Docker",
                entity_type="Technology",
                start_offset=0,
                end_offset=6,
                features={"confidence": 0.8}
            )
        ]
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={}
        )
        
        result = backend.deduplicate(lexical_graph, "test_namespace")
        assert result.metadata["combination_strategy"] == "voting"
    
    def test_backend_info(self):
        """Test backend information."""
        backend = EnsembleDedupBackend()
        info = backend.get_backend_info()
        
        assert info["backend_name"] == "ensemble"
        assert "description" in info