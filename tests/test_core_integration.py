"""
Focused integration tests for core KG Forge functionality without mocking.

These tests validate real component interactions:
- Deduplication backends
- Entity model operations
- Ontology pack functionality
- File system operations

Run with: python -m unittest tests.test_core_integration
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import yaml

from kg_forge.models.lexical import LexicalMention, LexicalRelation, LexicalGraph
from kg_forge.dedup.no_dedup_backend import NoDedupBackend
from kg_forge.dedup.interface import create_dedup_backend
from kg_forge.entities.models import EntityDefinition
from kg_forge.ontology.filesystem_pack import FilesystemOntologyPack


class TestDeduplicationIntegration(unittest.TestCase):
    """Integration tests for deduplication without mocking."""
    
    def test_no_dedup_backend_workflow(self):
        """Test complete no-dedup backend workflow with real data."""
        # Create real lexical mentions with various scenarios
        mentions = [
            LexicalMention(
                id="mention_1",
                doc_id="doc_1", 
                surface="Python",
                entity_type="Technology",
                start_offset=0,
                end_offset=6,
                features={"confidence": 0.9, "source": "header"}
            ),
            LexicalMention(
                id="mention_2",
                doc_id="doc_1",
                surface="python",  # Different case - should stay separate with no-dedup
                entity_type="Technology", 
                start_offset=20,
                end_offset=26,
                features={"confidence": 0.8, "source": "body"}
            ),
            LexicalMention(
                id="mention_3",
                doc_id="doc_2",
                surface="Data Team",
                entity_type="Team",
                start_offset=0,
                end_offset=9,
                features={"confidence": 0.95, "department": "engineering"}
            )
        ]
        
        relations = [
            LexicalRelation(
                id="rel_1",
                type="USES",
                src_mention_id="mention_3",
                dst_mention_id="mention_1",
                features={"confidence": 0.85, "context": "development"}
            ),
            LexicalRelation(
                id="rel_2", 
                type="IMPLEMENTS",
                src_mention_id="mention_3",
                dst_mention_id="mention_2",
                features={"confidence": 0.75, "context": "scripting"}
            )
        ]
        
        input_graph = LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={
                "source": "integration_test",
                "total_docs": 2,
                "extraction_method": "fake"
            }
        )
        
        # Test deduplication workflow
        backend = NoDedupBackend()
        
        # Validate backend
        self.assertTrue(backend.validate_configuration())
        self.assertEqual(backend.get_backend_name(), "none")
        
        # Get backend info
        info = backend.get_backend_info()
        self.assertEqual(info["backend_name"], "none")
        self.assertIn("description", info)
        self.assertIn("version", info)
        
        # Perform deduplication
        result = backend.deduplicate(input_graph, "test_namespace")
        
        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(len(result.canonical_entities), 3)  # No dedup = 3 entities
        self.assertEqual(len(result.relations), 2)
        
        # Check metadata includes deduplication info
        self.assertEqual(result.metadata["dedup_backend"], "none")
        self.assertIn("clusters_formed", result.metadata)
        self.assertIn("original_mentions", result.metadata)
        self.assertEqual(result.metadata["original_mentions"], 3)
        
        # Check canonical entities created correctly
        python_entities = [e for e in result.canonical_entities if e.canonical_name.lower() == "python"]
        self.assertEqual(len(python_entities), 2)  # Both "Python" and "python" kept separate
        
        # Check entity types preserved
        tech_entities = [e for e in result.canonical_entities if e.entity_type == "Technology"]
        team_entities = [e for e in result.canonical_entities if e.entity_type == "Team"]
        self.assertEqual(len(tech_entities), 2)
        self.assertEqual(len(team_entities), 1)
        
        # Check namespacing is in metadata
        self.assertEqual(result.metadata["namespace"], "test_namespace")
    
    def test_dedup_backend_factory(self):
        """Test deduplication backend factory creates real backends."""
        # Test valid backend creation
        backend = create_dedup_backend("none")
        self.assertIsInstance(backend, NoDedupBackend)
        self.assertEqual(backend.get_backend_name(), "none")
        
        # Test backend is functional
        self.assertTrue(backend.validate_configuration())
        
        # Test invalid backend
        with self.assertRaises(ValueError):
            create_dedup_backend("invalid_backend")


class TestOntologyPackIntegration(unittest.TestCase):
    """Integration tests for ontology pack functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_filesystem_ontology_pack_creation(self):
        """Test creating and using a filesystem ontology pack."""
        # Create pack structure
        entities_dir = self.test_dir / "entities"
        entities_dir.mkdir()
        
        # Create pack.yaml
        pack_config = {
            "id": "integration_test_pack",
            "name": "Integration Test Pack",
            "description": "Ontology pack for integration testing",
            "version": "1.0.0",
            "author": "KG Forge Test",
            "tags": ["test", "integration"],
            "styles": {
                "entity_colors": {
                    "Technology": "#3498db",
                    "Team": "#e74c3c"
                },
                "entity_shapes": {
                    "Technology": "diamond",
                    "Team": "circle"
                }
            }
        }
        
        pack_yaml = self.test_dir / "pack.yaml"
        with pack_yaml.open('w') as f:
            yaml.safe_dump(pack_config, f)
        
        # Create entity definition markdown files (expected format)
        tech_content = """# ID: technology
## Name: Technology
## Description:
Programming languages, frameworks, and tools used in development.

## Relations
- team : used_by_team : uses_technology  
- product : implements_product : implemented_by_product

## Examples

### Python
Python programming language for backend development.

### Neo4j
Graph database system for storing connected data.
""".strip()
        
        team_content = """# ID: team
## Name: Team
## Description:
Engineering teams and organizational groups working on products.

## Relations
- technology : uses_technology : used_by_team
- product : works_on_product : worked_on_by_team

## Examples

### Data Team
Data engineering team focused on data pipelines.

### Platform Team
Platform engineering team managing infrastructure.
""".strip()
        
        tech_file = entities_dir / "technology.md"
        tech_file.write_text(tech_content)
        
        team_file = entities_dir / "team.md"
        team_file.write_text(team_content)
        
        # Create prompt template
        prompt_template = """
        Extract entities of the following types from the text:
        {entity_types}
        
        Text to analyze:
        {text}
        
        Return structured information about entities and their relationships.
        """
        
        prompt_file = entities_dir / "prompt_template.md"
        prompt_file.write_text(prompt_template.strip())
        
        # Test ontology pack loading
        pack = FilesystemOntologyPack(self.test_dir)
        
        # Test pack info
        info = pack.info
        self.assertEqual(info.id, "integration_test_pack")
        self.assertEqual(info.name, "Integration Test Pack")
        self.assertEqual(info.version, "1.0.0")
        self.assertEqual(info.author, "KG Forge Test")
        self.assertIn("test", info.tags)
        self.assertIn("integration", info.tags)
        
        # Test entity definitions loading
        entity_defs = pack.load_entity_definitions()
        self.assertEqual(len(entity_defs), 2)
        
        entity_names = [ed.name for ed in entity_defs]
        self.assertIn("Technology", entity_names)
        self.assertIn("Team", entity_names)
        
        # Verify entity definition details
        tech_def = next((ed for ed in entity_defs if ed.name == "Technology"), None)
        if tech_def:
            self.assertEqual(tech_def.name, "Technology")
            self.assertIsInstance(tech_def.relations, list)
            self.assertIsInstance(tech_def.examples, list)
        
        # Test style config loading
        style_config = pack.get_style_config()
        self.assertIsNotNone(style_config)
        self.assertEqual(style_config.entity_colors["Technology"], "#3498db")
        self.assertEqual(style_config.entity_shapes["Team"], "circle")
        
        # Test prompt template loading
        template = pack.get_prompt_template()
        self.assertIsNotNone(template)
        self.assertIn("Extract entities", template)
        self.assertIn("{entity_types}", template)
        self.assertIn("{text}", template)


class TestEntityModelIntegration(unittest.TestCase):
    """Integration tests for entity model operations."""
    
    def test_entity_definition_workflow(self):
        """Test complete entity definition creation and usage."""
        # Create entity definition with comprehensive data
        entity_def = EntityDefinition(
            id="technology",
            name="Technology",
            description="Software technologies, programming languages, and development tools"
        )
        
        # Test entity definition properties
        self.assertEqual(entity_def.id, "technology")
        self.assertEqual(entity_def.name, "Technology")
        self.assertIsInstance(entity_def.relations, list)
        self.assertIsInstance(entity_def.examples, list)
        
        # Test entity definition can be serialized/deserialized
        entity_dict = entity_def.to_dict()
        self.assertIn("id", entity_dict)
        self.assertEqual(entity_dict["name"], "Technology")
        self.assertEqual(entity_dict["id"], "technology")


class TestLexicalModelIntegration(unittest.TestCase):
    """Integration tests for lexical model operations."""
    
    def test_lexical_graph_operations(self):
        """Test comprehensive lexical graph creation and manipulation."""
        # Create mentions with rich features
        mentions = [
            LexicalMention(
                id="tech_1",
                doc_id="doc_architecture",
                surface="Python",
                entity_type="Technology",
                start_offset=145,
                end_offset=151,
                features={
                    "confidence": 0.95,
                    "context": "backend development",
                    "sentence": "We use Python for our backend APIs.",
                    "pos_tag": "NOUN"
                }
            ),
            LexicalMention(
                id="tech_2",
                doc_id="doc_architecture", 
                surface="Neo4j",
                entity_type="Technology",
                start_offset=200,
                end_offset=205,
                features={
                    "confidence": 0.92,
                    "context": "graph database",
                    "sentence": "Neo4j stores our knowledge graph.",
                    "pos_tag": "NOUN"
                }
            ),
            LexicalMention(
                id="team_1",
                doc_id="doc_organization",
                surface="Platform Engineering Team",
                entity_type="Team", 
                start_offset=50,
                end_offset=74,
                features={
                    "confidence": 0.98,
                    "context": "organizational structure",
                    "department": "Engineering"
                }
            )
        ]
        
        # Create relations with detailed features
        relations = [
            LexicalRelation(
                id="rel_uses_1",
                type="USES",
                src_mention_id="team_1",
                dst_mention_id="tech_1", 
                features={
                    "confidence": 0.88,
                    "context": "technology adoption",
                    "evidence": "Platform Engineering Team uses Python for development"
                }
            ),
            LexicalRelation(
                id="rel_uses_2", 
                type="USES",
                src_mention_id="team_1",
                dst_mention_id="tech_2",
                features={
                    "confidence": 0.85,
                    "context": "data storage",
                    "evidence": "Platform Engineering Team uses Neo4j for graph storage"
                }
            ),
            LexicalRelation(
                id="rel_integrates",
                type="INTEGRATES_WITH",
                src_mention_id="tech_1",
                dst_mention_id="tech_2",
                features={
                    "confidence": 0.80,
                    "context": "system architecture",
                    "evidence": "Python applications integrate with Neo4j database"
                }
            )
        ]
        
        # Create lexical graph
        graph = LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={
                "source": "architecture_docs",
                "extraction_date": "2024-01-15",
                "total_documents": 2,
                "extraction_method": "llm_based",
                "model_version": "test-1.0"
            }
        )
        
        # Test graph properties
        self.assertEqual(len(graph.mentions), 3)
        self.assertEqual(len(graph.relations), 3)
        
        # Test mention filtering
        tech_mentions = [m for m in graph.mentions if m.entity_type == "Technology"]
        team_mentions = [m for m in graph.mentions if m.entity_type == "Team"]
        self.assertEqual(len(tech_mentions), 2)
        self.assertEqual(len(team_mentions), 1)
        
        # Test relation types
        relation_types = set(r.type for r in graph.relations)
        self.assertIn("USES", relation_types)
        self.assertIn("INTEGRATES_WITH", relation_types)
        
        # Test serialization/deserialization
        graph_dict = graph.to_dict()
        recreated_graph = LexicalGraph.from_dict(graph_dict)
        
        self.assertEqual(len(recreated_graph.mentions), len(graph.mentions))
        self.assertEqual(len(recreated_graph.relations), len(graph.relations))
        self.assertEqual(recreated_graph.metadata, graph.metadata)


if __name__ == "__main__":
    # Run integration tests
    unittest.main(verbosity=2)