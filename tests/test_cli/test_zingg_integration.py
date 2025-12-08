"""
Integration tests specifically for Zingg deduplication with CLI commands.

These tests validate the complete Zingg integration including:
- CLI argument parsing for --dedup-backend zingg
- End-to-end ingestion with Zingg deduplication
- Real-world entity clustering scenarios

Run with: python -m pytest tests/test_cli/test_zingg_integration.py -v
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner

from kg_forge.cli.main import cli
from kg_forge.dedup.zingg_backend import ZinggDedupBackend, ZINGG_AVAILABLE, PYSPARK_AVAILABLE, PANDAS_AVAILABLE
from kg_forge.models.lexical import LexicalGraph, LexicalMention
from kg_forge.models.dedup import DedupedLexicalGraph


class TestZinggCLIIntegration:
    """Test Zingg deduplication through CLI interface."""
    
    def test_zingg_backend_selection_via_cli(self):
        """Test that --dedup-backend zingg correctly selects ZinggDedupBackend."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test HTML files with duplicate entities
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            
            test_content = """
            <html><body>
            <h1>Machine Learning Projects</h1>
            <p>The ML team uses Python for data analysis.</p>
            <p>Machine Learning engineers work with TensorFlow.</p>
            </body></html>
            """
            
            (source_dir / "test_doc.html").write_text(test_content)
            
            # Test dry-run with Zingg backend
            result = runner.invoke(cli, [
                'ingest',
                '--source', str(source_dir),
                '--dedup-backend', 'zingg',
                '--fake-llm',  # Use fake LLM to avoid API calls
                '--dry-run',
                '--namespace', 'testzinggcli'
            ])
            
            # Should not crash and should indicate Zingg was used
            if result.exit_code != 0:
                print(f"CLI Error Output: {result.output}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            assert "zingg" in result.output.lower() or "dedup" in result.output.lower()
    
    def test_zingg_help_documentation(self):
        """Test that Zingg is documented in CLI help."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ['ingest', '--help'])
        
        assert result.exit_code == 0
        assert "zingg" in result.output
        assert "dedup-backend" in result.output
    
    def test_zingg_backend_real_clustering_behavior(self):
        """Test Zingg backend clustering with realistic entity variations."""
        # This tests the fake Zingg implementation's clustering logic
        backend = ZinggDedupBackend(confidence_threshold=0.8)
        
        # Create mentions with realistic variations
        mentions = [
            # Technology variations
            LexicalMention(
                id="tech_1", doc_id="doc1", surface="Machine Learning",
                entity_type="Technology", start_offset=0, end_offset=16,
                features={"confidence": 0.95, "section": "title"}
            ),
            LexicalMention(
                id="tech_2", doc_id="doc2", surface="ML", 
                entity_type="Technology", start_offset=10, end_offset=12,
                features={"confidence": 0.85, "section": "body"}
            ),
            LexicalMention(
                id="tech_3", doc_id="doc3", surface="machine learning",
                entity_type="Technology", start_offset=5, end_offset=21,
                features={"confidence": 0.90, "section": "body"}  
            ),
            
            # Team variations
            LexicalMention(
                id="team_1", doc_id="doc1", surface="Data Science Team",
                entity_type="Team", start_offset=30, end_offset=47,
                features={"confidence": 0.92, "section": "body"}
            ),
            LexicalMention(
                id="team_2", doc_id="doc2", surface="DS Team",
                entity_type="Team", start_offset=25, end_offset=32, 
                features={"confidence": 0.88, "section": "body"}
            ),
            
            # Distinct entity (should not cluster)
            LexicalMention(
                id="tech_4", doc_id="doc3", surface="TensorFlow",
                entity_type="Technology", start_offset=50, end_offset=60,
                features={"confidence": 0.93, "section": "body"}
            )
        ]
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={"extractor": "test", "source": "cli_integration"}
        )
        
        # Run Zingg deduplication
        result = backend.deduplicate(lexical_graph, "cli_test")
        
        # Verify clustering results - the improved algorithm should cluster intelligently:
        # ML + Machine Learning + machine learning → 1 ML cluster (3 mentions)
        # Data Science Team + DS Team → 1 DS cluster (2 mentions)  
        # TensorFlow → separate (1 mention)
        assert len(result.canonical_entities) == 3  # Improved clustering behavior

        # Verify that clustering occurred - find the largest cluster
        cluster_sizes = [len(e.mention_ids) for e in result.canonical_entities]
        max_cluster_size = max(cluster_sizes)
        assert max_cluster_size >= 2  # At least one cluster should have multiple mentions
        
        # Find clustered entities (those with multiple mentions)
        clustered_entities = [e for e in result.canonical_entities if len(e.mention_ids) > 1]
        assert len(clustered_entities) == 2  # Both ML and DS should cluster

        # Check ML clustering - should have clustered all ML variations
        tech_entities = [e for e in result.canonical_entities if e.entity_type == "Technology"]
        ml_cluster = next((e for e in tech_entities if len(e.mention_ids) > 1), None)
        assert ml_cluster is not None
        assert len(ml_cluster.mention_ids) == 3  # Should cluster all ML variations
        assert "Machine Learning" in ml_cluster.aliases or "machine learning" in ml_cluster.aliases
        assert "ML" in ml_cluster.aliases
        
        # Check DS Team clustering
        team_entities = [e for e in result.canonical_entities if e.entity_type == "Team"]
        assert len(team_entities) == 1
        ds_cluster = team_entities[0]
        assert len(ds_cluster.mention_ids) == 2  # Should cluster DS Team variations        # Verify TensorFlow remains separate
        tech_entities = [e for e in result.canonical_entities if e.entity_type == "Technology"]
        tf_entities = [e for e in tech_entities if "tensorflow" in e.canonical_name.lower()]
        assert len(tf_entities) == 1
        assert len(tf_entities[0].mention_ids) == 1  # Should not cluster with ML
        
        # Verify metadata includes Zingg-specific info
        backend_type = "zingg_real" if backend.zingg_available else "zingg_fake"
        assert result.metadata["dedup_backend"] == backend_type
        assert "clusters_formed" in result.metadata
        assert "duplicate_pairs" in result.metadata
    
    def test_zingg_configuration_validation(self):
        """Test Zingg backend configuration validation."""
        # Test valid configuration
        valid_config = {
            "confidence_threshold": 0.85,
            "model_config": {
                "algorithm": "random_forest",
                "features": ["surface", "context", "phonetic"]
            }
        }
        
        backend = ZinggDedupBackend(**valid_config)
        assert backend.confidence_threshold == 0.85
        assert backend.model_config["algorithm"] == "random_forest"
        
        # Test default configuration
        default_backend = ZinggDedupBackend()
        assert default_backend.confidence_threshold == 0.8
        assert default_backend.model_config == {}
    
    def test_zingg_ensemble_integration(self):
        """Test Zingg working within ensemble dedup backend."""
        from kg_forge.dedup.ensemble_backend import EnsembleDedupBackend
        
        ensemble = EnsembleDedupBackend(
            splink_config={"threshold": 0.7},
            zingg_config={"confidence_threshold": 0.85}
        )
        
        # Verify Zingg backend is initialized
        assert hasattr(ensemble, 'zingg_backend')
        assert isinstance(ensemble.zingg_backend, ZinggDedupBackend)
        assert ensemble.zingg_backend.confidence_threshold == 0.85
        
        # Test ensemble deduplication includes Zingg results
        mentions = [
            LexicalMention(
                id="ens_1", doc_id="doc1", surface="Python Programming",
                entity_type="Technology", start_offset=0, end_offset=18,
                features={"confidence": 0.9}
            ),
            LexicalMention(
                id="ens_2", doc_id="doc2", surface="Python", 
                entity_type="Technology", start_offset=10, end_offset=16,
                features={"confidence": 0.95}
            )
        ]
        
        lexical_graph = LexicalGraph(mentions=mentions, relations=[], metadata={})
        result = ensemble.deduplicate(lexical_graph, "ensemble_test")
        
        # Should cluster Python variations
        assert len(result.canonical_entities) <= len(mentions)
        assert "ensemble" in result.metadata["dedup_backend"]

    @pytest.mark.skipif(not (ZINGG_AVAILABLE and PYSPARK_AVAILABLE and PANDAS_AVAILABLE), 
                       reason="Real Zingg dependencies not available")
    def test_real_zingg_implementation(self):
        """Test real Zingg implementation when all dependencies are available."""
        backend = ZinggDedupBackend(confidence_threshold=0.8)
        
        # Verify real implementation is being used
        assert backend.zingg_available == True
        
        # Create test mentions for real Zingg processing
        mentions = [
            LexicalMention(
                id="real_1", doc_id="doc1", surface="Machine Learning",
                entity_type="Technology", start_offset=0, end_offset=16,
                features={"confidence": 0.95}
            ),
            LexicalMention(
                id="real_2", doc_id="doc2", surface="ML",
                entity_type="Technology", start_offset=10, end_offset=12,
                features={"confidence": 0.88}
            ),
            LexicalMention(
                id="real_3", doc_id="doc3", surface="Deep Learning",
                entity_type="Technology", start_offset=20, end_offset=33,
                features={"confidence": 0.92}
            )
        ]
        
        lexical_graph = LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={"extractor": "test"}
        )
        
        # Run real Zingg deduplication
        result = backend.deduplicate(lexical_graph, "real_zingg_test")
        
        # Verify real Zingg was used
        assert result.metadata["dedup_backend"] == "zingg_real"
        assert isinstance(result, DedupedLexicalGraph)
        assert len(result.canonical_entities) <= len(mentions)  # Should have some deduplication


if __name__ == "__main__":
    pytest.main([__file__, "-v"])