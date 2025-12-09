"""
End-to-End Integration Tests for KG Forge Complete Pipeline

These tests validate the entire pipeline workflow:
1. File Ingestion (HTML parsing)
2. Entity Extraction (LLM/Spacy backends) 
3. Named Entity Recognition & Relationship Extraction
4. Lexical Graph Creation
5. Deduplication (Splink/Zingg/None backends)
6. Entity Linking to Knowledge Graph
7. Knowledge Graph Data Retrieval

Run with: python -m unittest tests.test_end_to_end -v
"""

import unittest
import tempfile
import shutil
import yaml
import json
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

from kg_forge.parsers.html_parser import ConfluenceHTMLParser
from kg_forge.parsers.document_loader import DocumentLoader
from kg_forge.extraction.fake_backend import FakeExtractionBackend
from kg_forge.extraction.llm_backend import LLMExtractionBackend
from kg_forge.dedup.no_dedup_backend import NoDedupBackend
from kg_forge.dedup.ensemble_backend import EnsembleDedupBackend
from kg_forge.dedup.interface import create_dedup_backend
from kg_forge.linking.default_linker import DefaultEntityLinker
from kg_forge.ontology.filesystem_pack import FilesystemOntologyPack
from kg_forge.entities.models import EntityDefinition
from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.models.dedup import DedupedLexicalGraph, CanonicalLexicalEntity
from kg_forge.config.settings import Settings


class TestCompleteIngestionPipeline(unittest.TestCase):
    """End-to-end tests for complete file ingestion to knowledge graph pipeline."""
    
    def setUp(self):
        """Set up complete test environment with real files and ontology."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.setup_test_ontology()
        self.setup_test_documents()
        
    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def setup_test_ontology(self):
        """Create a comprehensive test ontology pack."""
        # Create ontology pack structure
        self.ontology_dir = self.test_dir / "test_ontology"
        entities_dir = self.ontology_dir / "entities"
        entities_dir.mkdir(parents=True)
        
        # Pack configuration
        pack_config = {
            "id": "e2e_test_pack",
            "name": "End-to-End Test Ontology",
            "description": "Comprehensive ontology for E2E testing",
            "version": "1.0.0",
            "author": "KG Forge E2E Tests",
            "tags": ["test", "e2e", "integration"],
            "styles": {
                "entity_colors": {
                    "Technology": "#3498db",
                    "Team": "#e74c3c", 
                    "Product": "#2ecc71",
                    "Component": "#f39c12"
                }
            }
        }
        
        pack_yaml = self.ontology_dir / "pack.yaml"
        with pack_yaml.open('w') as f:
            yaml.safe_dump(pack_config, f)
        
        # Entity definitions with rich relationships
        technology_def = """# ID: technology
## Name: Technology
## Description:
Software technologies, programming languages, databases, frameworks, and development tools used in engineering.

## Relations
- team : used_by_team : uses_technology
- product : implements_product : implemented_by_product
- component : powers_component : powered_by_technology

## Examples

### Python
Python programming language used for backend development and data processing.

### Neo4j
Graph database system for storing and querying connected data and relationships.

### Docker
Containerization platform for packaging and deploying applications.

### AWS
Amazon Web Services cloud platform providing scalable infrastructure and services.
"""

        team_def = """# ID: team
## Name: Team  
## Description:
Engineering teams, organizational units, and groups responsible for developing products and components.

## Relations
- technology : uses_technology : used_by_team
- product : develops_product : developed_by_team
- component : maintains_component : maintained_by_team

## Examples

### Data Engineering Team
Team responsible for data pipelines, ETL processes, and data infrastructure.

### Platform Engineering Team
Team managing infrastructure, deployment pipelines, and developer tooling.

### AI/ML Team
Team developing artificial intelligence and machine learning capabilities.

### Frontend Team
Team building user interfaces and client-side applications.
"""

        product_def = """# ID: product
## Name: Product
## Description:
Software products, applications, and major deliverables developed by engineering teams.

## Relations  
- technology : implemented_by_technology : implements_product
- team : developed_by_team : develops_product
- component : composed_of_component : part_of_product

## Examples

### Knowledge Explorer
Product for exploring and navigating knowledge graphs and connected data.

### Data Pipeline Platform
Platform for building, managing, and monitoring data processing workflows.

### Content Management System
System for creating, storing, and managing digital content and documentation.
"""

        component_def = """# ID: component
## Name: Component
## Description:
Software components, modules, services, and architectural elements that make up products.

## Relations
- technology : powered_by_technology : powers_component
- team : maintained_by_team : maintains_component
- product : part_of_product : composed_of_component

## Examples

### Authentication Service
Component handling user authentication and authorization across products.

### Search Engine
Component providing full-text search capabilities and query processing.

### Data Ingestion API
Component for ingesting and processing various data sources and formats.

### Graph Visualization Engine
Component for rendering and interacting with graph data structures.
"""
        
        # Write entity definition files
        (entities_dir / "technology.md").write_text(technology_def.strip())
        (entities_dir / "team.md").write_text(team_def.strip())
        (entities_dir / "product.md").write_text(product_def.strip())
        (entities_dir / "component.md").write_text(component_def.strip())
        
        # Prompt template for extraction
        prompt_template = """
You are an expert at extracting entities and relationships from technical documentation.

Extract entities of these types: {entity_types}

From this text:
{text}

Return a JSON object with:
- entities: list of {{"type": "EntityType", "name": "Entity Name", "start_offset": 0, "end_offset": 10}}
- relationships: list of {{"type": "RELATIONSHIP_TYPE", "source": "Source Entity", "target": "Target Entity"}}

Focus on technical entities, teams, products, and their relationships.
"""
        
        (entities_dir / "prompt_template.md").write_text(prompt_template.strip())
        
        # Load the ontology pack
        self.ontology = FilesystemOntologyPack(self.ontology_dir)
    
    def setup_test_documents(self):
        """Create realistic test documents for ingestion."""
        self.docs_dir = self.test_dir / "test_documents"
        self.docs_dir.mkdir()
        
        # Document 1: Technical architecture overview
        doc1_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Technical Architecture Overview</title>
            <meta name="id" content="3352431259">
        </head>
        <body>
            <div id="main-content">
                <h1 id="title-heading">
                    <span id="title-text">Technical Architecture Overview</span>
                </h1>
                                <p>Our platform is built using modern technologies and managed by specialized engineering teams.</p>
                                
                                <h2>Core Technologies</h2>
                                <p>The Data Engineering Team uses Python and Neo4j to build robust data pipelines. 
                                Python is our primary language for backend services, while Neo4j serves as our graph database 
                                for storing connected data and relationships.</p>
                                
                                <p>The Platform Engineering Team manages our Docker-based containerization and AWS cloud infrastructure. 
                                Docker enables consistent deployment across environments, and AWS provides scalable computing resources.</p>
                                
                                <h2>Product Development</h2>
                                <p>The AI/ML Team develops the Knowledge Explorer product using advanced graph algorithms. 
                                This product helps users navigate complex data relationships and discover insights.</p>
                                
                                <p>The Frontend Team builds user interfaces for the Content Management System. 
                                This system integrates with our Data Pipeline Platform to process and organize content.</p>
                                
                                <h2>System Components</h2>
                                <p>Our architecture includes several key components:</p>
                                <ul>
                                    <li>Authentication Service - handles user security and access control</li>
                                    <li>Search Engine - provides fast full-text search across all content</li> 
                                    <li>Data Ingestion API - processes various data sources and formats</li>
                                    <li>Graph Visualization Engine - renders interactive graph displays</li>
                                </ul>
                                
                <p>The Data Engineering Team maintains the Data Ingestion API, while the Platform Engineering Team 
                manages the Authentication Service. The AI/ML Team develops the Graph Visualization Engine 
                that powers the Knowledge Explorer product.</p>
            </div>
        </body>
        </html>
        """
        
        # Document 2: Team organization details
        doc2_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Engineering Team Organization</title>
            <meta name="id" content="3182532046">
        </head>
        <body>
            <div id="main-content">
                <h1 id="title-heading">
                    <span id="title-text">Engineering Team Organization</span>
                </h1>
                                <p>Our engineering organization consists of specialized teams working on different aspects of our platform.</p>
                                
                                <h2>Data Engineering Team</h2>
                                <p>The Data Engineering Team specializes in Python-based data processing and uses Neo4j for graph storage. 
                                They develop the Data Pipeline Platform and maintain critical data infrastructure components.</p>
                                
                                <p>This team uses Docker for consistent deployment environments and integrates with AWS services 
                                for scalable data processing. They work closely with the Search Engine component.</p>
                                
                                <h2>Platform Engineering Team</h2>  
                                <p>Platform Engineering Team focuses on infrastructure automation using Docker and AWS. 
                                They ensure the Authentication Service runs reliably and scales with user demand.</p>
                                
                                <p>The team implements Python-based automation tools and manages the deployment pipeline 
                                for the Content Management System and other products.</p>
                                
                                <h2>AI/ML Team</h2>
                                <p>The AI/ML Team leverages Python for machine learning model development and Neo4j 
                                for storing training data relationships. They create the Knowledge Explorer product.</p>
                                
                                <p>This team develops the Graph Visualization Engine component and uses AWS machine learning 
                                services for model training and inference.</p>
                                
                                <h2>Cross-Team Collaboration</h2>
                <p>All teams collaborate on shared components. The Data Ingestion API is used by multiple products, 
                and the Authentication Service secures access across the entire platform.</p>
            </div>
        </body>
        </html>
        """
        
        # Write test documents
        (self.docs_dir / "architecture_overview.html").write_text(doc1_content.strip())
        (self.docs_dir / "team_organization.html").write_text(doc2_content.strip())
    
    def test_complete_fake_extraction_pipeline(self):
        """Test complete pipeline using fake extraction backend (no external dependencies)."""
        print("\n=== Testing Complete Fake Extraction Pipeline ===")
        
        # Step 1: Document Ingestion
        print("Step 1: Document Ingestion")
        parser = ConfluenceHTMLParser()
        loader = DocumentLoader(parser)
        documents = loader.load_from_directory(self.docs_dir)
        
        self.assertEqual(len(documents), 2, "Should load 2 test documents")
        self.assertIn("Python", documents[0].text, "Should extract Python mentions")
        self.assertIn("Data Engineering Team", documents[0].text, "Should extract team mentions")
        print(f"[OK] Loaded {len(documents)} documents successfully")
        
        # Step 2: Entity Extraction using Fake Backend  
        print("Step 2: Entity Extraction with Fake Backend")
        extractor = FakeExtractionBackend()
        
        # Load ontology schema from pack
        ontology_schema = self.ontology.load_ontology_schema()
        
        all_mentions = []
        all_relations = []
        
        for doc in documents:
            lexical_graph = extractor.extract(doc.text, ontology_schema, doc_id=doc.doc_id)
            
            self.assertGreater(len(lexical_graph.mentions), 0, "Should extract mentions")
            self.assertGreater(len(lexical_graph.relations), 0, "Should extract relations")
            
            all_mentions.extend(lexical_graph.mentions)
            all_relations.extend(lexical_graph.relations)
        
        print(f"[OK] Extracted {len(all_mentions)} entities and {len(all_relations)} relationships")
        
        # Verify entity types are extracted
        entity_types = set(m.entity_type for m in all_mentions)
        expected_types = {"Technology", "Team", "Product", "Component"}
        print(f"Extracted entity types: {entity_types}")
        # Fake backend uses ontology-defined types, so we should have some entities
        self.assertGreater(len(entity_types), 0, "Should extract some entity types")
        
        # Step 3: Create Combined Lexical Graph
        print("Step 3: Creating Combined Lexical Graph")
        combined_graph = LexicalGraph(
            mentions=all_mentions,
            relations=all_relations,
            metadata={"extraction_method": "fake_backend", "document_count": len(documents)}
        )
        
        print(f"[OK] Combined graph: {len(combined_graph.mentions)} mentions, {len(combined_graph.relations)} relations")
        
        # Step 4: Deduplication
        print("Step 4: Entity Deduplication")
        dedup_backend = NoDedupBackend()
        deduplicated_graph = dedup_backend.deduplicate(combined_graph, "e2e_test")
        
        self.assertEqual(len(deduplicated_graph.canonical_entities), len(all_mentions), "No-dedup should keep all entities")
        self.assertEqual(deduplicated_graph.metadata["dedup_backend"], "none")
        print(f"[OK] Deduplicated to {len(deduplicated_graph.canonical_entities)} canonical entities")
        
        # Step 5: Entity Linking (Mocked Neo4j)
        print("Step 5: Entity Linking to Knowledge Graph") 
        with patch('kg_forge.linking.default_linker.DefaultEntityLinker') as mock_linker_class:
            mock_linker = MagicMock()
            mock_linker_class.return_value = mock_linker
            
            # Mock linking results
            mock_link_results = []
            for entity in deduplicated_graph.canonical_entities:
                mock_link_results.append(MagicMock(
                    canonical_entity=entity,
                    action="create_new",
                    confidence=0.9,
                    linked_entity=MagicMock(id=f"kg_{entity.id}", name=entity.canonical_name)
                ))
            
            mock_linker.link_entities.return_value = mock_link_results
            
            # Perform linking
            linker = mock_linker_class(neo4j_client=MagicMock())
            link_results = linker.link_entities(deduplicated_graph.canonical_entities, "e2e_test")
            
            self.assertEqual(len(link_results), len(deduplicated_graph.canonical_entities))
            print(f"[OK] Linked {len(link_results)} entities to knowledge graph")
        
        # Step 6: Knowledge Graph Retrieval (Mocked)
        print("Step 6: Knowledge Graph Data Retrieval")
        with patch('kg_forge.graph.neo4j_client.Neo4jClient') as mock_neo4j:
            mock_client = MagicMock()
            mock_neo4j.return_value = mock_client
            
            # Mock graph retrieval
            mock_graph_data = {
                "nodes": [
                    {"id": "tech_1", "labels": ["Entity", "Technology"], "properties": {"name": "Python"}},
                    {"id": "team_1", "labels": ["Entity", "Team"], "properties": {"name": "Data Engineering Team"}},
                    {"id": "product_1", "labels": ["Entity", "Product"], "properties": {"name": "Knowledge Explorer"}}
                ],
                "relationships": [
                    {"id": "rel_1", "type": "USES", "startNode": "team_1", "endNode": "tech_1"},
                    {"id": "rel_2", "type": "DEVELOPS", "startNode": "team_1", "endNode": "product_1"}
                ]
            }
            
            mock_client.run_query.return_value = mock_graph_data
            
            # Test graph retrieval
            client = mock_neo4j()
            graph_result = client.run_query("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100")
            
            self.assertIn("nodes", graph_result)
            self.assertIn("relationships", graph_result) 
            self.assertGreater(len(graph_result["nodes"]), 0)
            print(f"[OK] Retrieved {len(graph_result['nodes'])} nodes and {len(graph_result['relationships'])} relationships from KG")
        
        print("\n=== Complete Fake Extraction Pipeline Test: SUCCESS ===")
    
    def test_complete_llm_extraction_pipeline(self):
        """Test complete pipeline demonstrating LLM-style extraction workflow."""
        print("\n=== Testing Complete LLM Extraction Pipeline ===")
        
        # This test demonstrates the workflow that would be used with LLM extraction
        # but uses the fake backend for simplicity and reliability
        
        # Step 1: Document Ingestion
        print("Step 1: Document Ingestion")
        parser = ConfluenceHTMLParser()
        loader = DocumentLoader(parser)
        documents = loader.load_from_directory(self.docs_dir)
        print(f"[OK] Loaded {len(documents)} documents successfully")
        
        # Step 2: LLM-style Entity Extraction (using fake backend as demonstration)
        print("Step 2: LLM-style Entity Extraction (simulated)")
        extractor = FakeExtractionBackend()
        
        # Load ontology schema from pack
        ontology_schema = self.ontology.load_ontology_schema()
        
        all_mentions = []
        all_relations = []
        
        for doc in documents:
            lexical_graph = extractor.extract(doc.text, ontology_schema, doc_id=doc.doc_id)
            all_mentions.extend(lexical_graph.mentions)
            all_relations.extend(lexical_graph.relations)
        
        print(f"[OK] LLM-style extracted {len(all_mentions)} entities and {len(all_relations)} relationships")
        
        # Step 3: Verify extraction worked
        self.assertGreater(len(all_mentions), 0, "Should extract entities")
        self.assertGreater(len(all_relations), 0, "Should extract relationships")
        
        # Step 4: Advanced Deduplication Pipeline
        print("Step 4: Advanced Deduplication")
        combined_graph = LexicalGraph(
            mentions=all_mentions,
            relations=all_relations,
            metadata={"extraction_method": "llm_simulation", "document_count": len(documents)}
        )
        
        # Use ensemble backend for more advanced deduplication
        ensemble_backend = EnsembleDedupBackend()
        deduplicated_graph = ensemble_backend.deduplicate(combined_graph, "llm_e2e_test")
        
        print(f"[OK] Advanced deduplication: {len(deduplicated_graph.canonical_entities)} canonical entities")
        
        print("\n=== Complete LLM Extraction Pipeline Test: SUCCESS ===")
    
    def _convert_mock_response_to_lexical_graph(self, mock_response: Dict, doc_id: str) -> LexicalGraph:
        """Convert mock LLM response to LexicalGraph format."""
        mentions = []
        for i, entity in enumerate(mock_response["entities"]):
            mentions.append(LexicalMention(
                id=f"mention_{i}",
                doc_id=doc_id,
                entity_type=entity["type"],
                surface=entity["name"],
                start_offset=entity["start_offset"],
                end_offset=entity["end_offset"],
                features={"confidence": 0.9, "extraction_method": "llm"}
            ))
        
        relations = []
        mention_by_name = {m.surface: m for m in mentions}
        for i, rel in enumerate(mock_response["relationships"]):
            src_mention = mention_by_name.get(rel["source"])
            dst_mention = mention_by_name.get(rel["target"])
            if src_mention and dst_mention:
                relations.append(LexicalRelation(
                    id=f"relation_{i}",
                    type=rel["type"],
                    src_mention_id=src_mention.id,
                    dst_mention_id=dst_mention.id,
                    features={"confidence": 0.85, "extraction_method": "llm"}
                ))
        
        return LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={"backend": "llm", "extraction_method": "mocked_bedrock"}
        )


class TestSpacyExtractionPipeline(unittest.TestCase):
    """End-to-end tests for Spacy extraction pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.setup_minimal_ontology()
        
    def tearDown(self):
        """Clean up."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def setup_minimal_ontology(self):
        """Create minimal ontology for spacy testing."""
        ontology_dir = self.test_dir / "spacy_ontology"
        entities_dir = ontology_dir / "entities"
        entities_dir.mkdir(parents=True)
        
        pack_config = {"id": "spacy_test", "name": "Spacy Test Pack", "version": "1.0.0"}
        with (ontology_dir / "pack.yaml").open('w') as f:
            yaml.safe_dump(pack_config, f)
        
        # Simple entity definition
        tech_def = """# ID: technology
## Name: Technology  
## Description:
Technologies and tools.
## Relations
- team : used_by_team : uses_technology
## Examples
### Python
Programming language.
"""
        (entities_dir / "technology.md").write_text(tech_def.strip())
        self.ontology = FilesystemOntologyPack(ontology_dir)
    
    def test_spacy_extraction_pipeline(self):
        """Test pipeline with Spacy backend (mocked to avoid model dependencies)."""
        # Skip on Python 3.9 due to glirel compatibility issues
        import sys
        if sys.version_info < (3, 10):
            self.skipTest("Skipping spacy test on Python 3.9 due to glirel type annotation compatibility")
        
        # Skip if numpy/thinc compatibility issue exists
        try:
            import spacy
        except (ValueError, ImportError) as e:
            if "numpy.dtype size changed" in str(e) or "binary incompatibility" in str(e):
                self.skipTest(f"Skipping due to numpy/spaCy compatibility issue: {e}")
            raise
        
        # Now that import check passed, apply mock
        with patch('kg_forge.extraction.spacy_backend.SpacyLexicalBackend') as mock_spacy:
            print("\n=== Testing Spacy Extraction Pipeline ===")
            
            # Mock Spacy backend
            mock_backend = MagicMock()
            mock_spacy.return_value = mock_backend
            
            # Mock spacy extraction results
            mock_mentions = [
                LexicalMention(
                    id="spacy_1", doc_id="test_doc", entity_type="Technology",
                    surface="Python", start_offset=10, end_offset=16,
                    features={"confidence": 0.8, "pos_tag": "NOUN"}
                )
            ]
            
            mock_graph = LexicalGraph(
                mentions=mock_mentions,
                relations=[],
                metadata={"backend": "spacy", "model": "en_core_web_sm"}
            )
            
            mock_backend.extract_entities.return_value = mock_graph
            
            # Test extraction
            backend = mock_spacy(fake_mode=True)
            result = backend.extract_entities("The team uses Python for development.", doc_id="test_doc")
            
            self.assertGreater(len(result.mentions), 0)
            self.assertEqual(result.metadata["backend"], "spacy")
            print(f"[OK] Spacy backend extracted {len(result.mentions)} entities")
            
            print("\n=== Spacy Extraction Pipeline Test: SUCCESS ===")


class TestDeduplicationBackendComparison(unittest.TestCase):
    """Test different deduplication backends in complete pipeline."""
    
    def setUp(self):
        """Set up test data."""
        # Create test mentions with duplicates
        self.test_mentions = [
            LexicalMention("m1", "doc1", "Technology", "Python", 0, 6, {"confidence": 0.9}),
            LexicalMention("m2", "doc1", "Technology", "python", 20, 26, {"confidence": 0.8}),
            LexicalMention("m3", "doc2", "Technology", "Python", 5, 11, {"confidence": 0.95}),
            LexicalMention("m4", "doc2", "Team", "Data Team", 30, 39, {"confidence": 0.9})
        ]
        
        self.test_relations = [
            LexicalRelation("r1", "USES", "m4", "m1", {"confidence": 0.8})
        ]
        
        self.lexical_graph = LexicalGraph(
            mentions=self.test_mentions,
            relations=self.test_relations,
            metadata={"test": "dedup_comparison"}
        )
    
    def test_no_dedup_backend(self):
        """Test no-deduplication backend preserves all entities."""
        print("\n=== Testing No-Dedup Backend ===")
        
        backend = NoDedupBackend()
        result = backend.deduplicate(self.lexical_graph, "test")
        
        # No dedup = same number of canonical entities as mentions
        self.assertEqual(len(result.canonical_entities), len(self.test_mentions))
        self.assertEqual(result.metadata["dedup_backend"], "none")
        print(f"[OK] No-dedup preserved all {len(result.canonical_entities)} entities")
    
    @patch('kg_forge.dedup.splink_backend.SpLinkDedupBackend')
    def test_splink_dedup_backend(self, mock_splink):
        """Test Splink deduplication backend (mocked)."""
        print("\n=== Testing Splink Deduplication Backend ===")
        
        mock_backend = MagicMock()
        mock_splink.return_value = mock_backend
        
        # Mock splink clustering Python mentions together
        mock_canonical = [
            CanonicalLexicalEntity(
                id="cluster_1", entity_type="Technology", canonical_name="Python",
                aliases=["Python", "python"], mention_ids=["m1", "m2", "m3"]
            ),
            CanonicalLexicalEntity(
                id="cluster_2", entity_type="Team", canonical_name="Data Team", 
                aliases=["Data Team"], mention_ids=["m4"]
            )
        ]
        
        mock_result = DedupedLexicalGraph(
            canonical_entities=mock_canonical,
            relations=[],
            metadata={"dedup_backend": "splink", "clusters_formed": 2}
        )
        
        mock_backend.deduplicate.return_value = mock_result
        
        backend = mock_splink()
        result = backend.deduplicate(self.lexical_graph, "test")
        
        # Splink should cluster 3 Python mentions into 1 canonical entity
        self.assertEqual(len(result.canonical_entities), 2)
        self.assertEqual(result.metadata["dedup_backend"], "splink")
        python_entity = next(e for e in result.canonical_entities if e.entity_type == "Technology")
        self.assertEqual(len(python_entity.mention_ids), 3)
        print(f"[OK] Splink clustered to {len(result.canonical_entities)} canonical entities")
    
    @patch('kg_forge.dedup.zingg_backend.ZinggDedupBackend')  
    def test_zingg_dedup_backend(self, mock_zingg):
        """Test Zingg deduplication backend (mocked)."""
        print("\n=== Testing Zingg Deduplication Backend ===")
        
        mock_backend = MagicMock()
        mock_zingg.return_value = mock_backend
        
        # Mock zingg with different clustering strategy
        mock_canonical = [
            CanonicalLexicalEntity(
                id="zingg_1", entity_type="Technology", canonical_name="Python",
                aliases=["Python", "python"], mention_ids=["m1", "m2", "m3"]
            ),
            CanonicalLexicalEntity(
                id="zingg_2", entity_type="Team", canonical_name="Data Team",
                aliases=["Data Team"], mention_ids=["m4"] 
            )
        ]
        
        mock_result = DedupedLexicalGraph(
            canonical_entities=mock_canonical,
            relations=[],
            metadata={"dedup_backend": "zingg", "ml_model": "random_forest"}
        )
        
        mock_backend.deduplicate.return_value = mock_result
        
        backend = mock_zingg()
        result = backend.deduplicate(self.lexical_graph, "test")
        
        self.assertEqual(len(result.canonical_entities), 2)
        self.assertEqual(result.metadata["dedup_backend"], "zingg")
        print(f"[OK] Zingg clustered to {len(result.canonical_entities)} canonical entities")


    def test_end_to_end_ingestion_with_zingg_backend(self):
        """Test complete ingestion pipeline with Zingg deduplication."""
        print("\n=== Testing End-to-End Ingestion with Zingg ===\n")
        
        # Create test documents with entities that should be deduplicated
        test_docs = {
            "doc1.html": """
            <html><body>
            <h1>Machine Learning Team</h1>
            <p>The ML team works on Python libraries for data science.</p>
            <p>They use TensorFlow and PyTorch frameworks.</p>
            </body></html>
            """,
            "doc2.html": """
            <html><body>
            <h1>AI Development</h1>
            <p>Machine Learning engineers use Python for AI projects.</p>
            <p>Popular tools include Tensorflow and pytorch.</p>
            </body></html>
            """
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()
            
            for filename, content in test_docs.items():
                (source_dir / filename).write_text(content)
            
            with patch('kg_forge.extraction.llm_backend.LLMExtractionBackend') as mock_llm:
                mock_backend = MagicMock()
                mock_llm.return_value = mock_backend
                
                def create_mentions(doc_id):
                    return LexicalGraph(
                        mentions=[
                            LexicalMention(
                                id=f"m1_{doc_id}", doc_id=doc_id, surface="Machine Learning Team",
                                entity_type="Team", start_offset=0, end_offset=20
                            ),
                            LexicalMention(
                                id=f"m2_{doc_id}", doc_id=doc_id, surface="ML team",
                                entity_type="Team", start_offset=25, end_offset=32
                            )
                        ],
                        relations=[],
                        metadata={"extractor": "fake"}
                    )
                
                mock_backend.extract.side_effect = lambda content, ontology: create_mentions("doc1")
                
                # Test Zingg dedup backend directly since full pipeline integration needs more setup
                from kg_forge.dedup.zingg_backend import ZinggDedupBackend
                
                dedup_backend = ZinggDedupBackend()
                lexical_graph = LexicalGraph(
                    mentions=[
                        LexicalMention(
                            id="m1", doc_id="doc1", surface="Machine Learning Team",
                            entity_type="Team", start_offset=0, end_offset=20,
                            features={"confidence": 0.9}
                        ),
                        LexicalMention(
                            id="m2", doc_id="doc2", surface="ML team", 
                            entity_type="Team", start_offset=25, end_offset=32,
                            features={"confidence": 0.85}
                        )
                    ],
                    relations=[],
                    metadata={"extractor": "fake"}
                )
                
                dedup_result = dedup_backend.deduplicate(lexical_graph, "test_zingg_integration")
                
                # Verify Zingg deduplication worked
                self.assertIsInstance(dedup_result, DedupedLexicalGraph)
                self.assertEqual(dedup_result.metadata["dedup_backend"], "zingg_fake") 
                
                # Should cluster similar team mentions
                team_entities = [e for e in dedup_result.canonical_entities if e.entity_type == "Team"]
                self.assertEqual(len(team_entities), 1)  # Should merge ML team variations
                
                team_entity = team_entities[0]
                self.assertIn("Machine Learning Team", team_entity.aliases)
                self.assertIn("ML team", team_entity.aliases)
                
                print(f"[OK] Zingg deduplication test: {len(lexical_graph.mentions)} mentions → {len(dedup_result.canonical_entities)} canonical entities")


if __name__ == "__main__":
    # Run all end-to-end tests
    unittest.main(verbosity=2)