"""Tests for TTL ontology loading and OntologySchema."""

import pytest
from pathlib import Path
import tempfile
import shutil

from kg_forge.ontology.schema import OntologySchema, EntityType, RelationType, Property
from kg_forge.ontology.ttl_loader import TTLOntologyLoader


# Sample TTL ontology for testing
SAMPLE_TTL = """
@prefix : <http://example.org/ont#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A software product or service offering" .

:Team a owl:Class ;
    rdfs:label "Team" ;
    rdfs:comment "An engineering team or organizational unit" .

:worksOn a owl:ObjectProperty ;
    rdfs:label "works on" ;
    rdfs:domain :Team ;
    rdfs:range :Product ;
    rdfs:comment "Indicates that a team works on a product" .
"""


@pytest.fixture
def ttl_file(tmp_path):
    """Create a temporary TTL file for testing."""
    ttl_path = tmp_path / "test_ontology.ttl"
    ttl_path.write_text(SAMPLE_TTL)
    return ttl_path


class TestOntologySchema:
    """Test OntologySchema dataclass and helper methods."""
    
    def test_to_gliner_config(self):
        """Test GLiNER config generation."""
        schema = OntologySchema(
            entities={
                "Product": EntityType(
                    name="Product",
                    iri="http://example.org/ont#Product",
                    description="A software product or service offering"
                ),
                "Team": EntityType(
                    name="Team",
                    iri="http://example.org/ont#Team",
                    description="An engineering team or organizational unit"
                )
            },
            relations={}
        )
        
        gliner_config = schema.to_gliner_config()
        
        assert "Product" in gliner_config
        assert "Team" in gliner_config
        assert gliner_config["Product"] == "A software product or service offering"
        assert gliner_config["Team"] == "An engineering team or organizational unit"
    
    def test_to_glirel_config(self):
        """Test GLiREL config generation."""
        schema = OntologySchema(
            entities={},
            relations={
                "WORKS_ON": RelationType(
                    name="WORKS_ON",
                    iri="http://example.org/ont#worksOn",
                    head_types=["Team"],
                    tail_types=["Product"],
                    description="Indicates that a team works on a product"
                )
            }
        )
        
        glirel_config = schema.to_glirel_config()
        
        assert "WORKS_ON" in glirel_config
        assert glirel_config["WORKS_ON"]["head_types"] == ["Team"]
        assert glirel_config["WORKS_ON"]["tail_types"] == ["Product"]
        assert glirel_config["WORKS_ON"]["description"] == "Indicates that a team works on a product"
    
    def test_to_llm_prompt_snippet(self):
        """Test LLM prompt snippet generation."""
        schema = OntologySchema(
            entities={
                "Product": EntityType(
                    name="Product",
                    iri="http://example.org/ont#Product",
                    description="A software product",
                    examples=["Content Lake", "HXPR"]
                )
            },
            relations={
                "WORKS_ON": RelationType(
                    name="WORKS_ON",
                    iri="http://example.org/ont#worksOn",
                    head_types=["Team"],
                    tail_types=["Product"],
                    description="Team works on product"
                )
            }
        )
        
        prompt_snippet = schema.to_llm_prompt_snippet()
        
        assert "Product" in prompt_snippet
        assert "A software product" in prompt_snippet
        assert "Content Lake" in prompt_snippet
        assert "WORKS_ON" in prompt_snippet
        assert "Team" in prompt_snippet
    
    def test_validate_relation(self):
        """Test relation validation."""
        schema = OntologySchema(
            entities={},
            relations={
                "WORKS_ON": RelationType(
                    name="WORKS_ON",
                    iri="http://example.org/ont#worksOn",
                    head_types=["Team"],
                    tail_types=["Product"],
                    description="Team works on product"
                )
            }
        )
        
        # Valid relation
        assert schema.validate_relation("WORKS_ON", "Team", "Product") is True
        
        # Invalid head type
        assert schema.validate_relation("WORKS_ON", "Person", "Product") is False
        
        # Invalid tail type
        assert schema.validate_relation("WORKS_ON", "Team", "Technology") is False
        
        # Unknown relation
        assert schema.validate_relation("UNKNOWN", "Team", "Product") is False


class TestTTLOntologyLoader:
    """Test TTL ontology loading with rdflib."""
    
    def test_load_from_file(self, ttl_file):
        """Test loading ontology from a single TTL file."""
        try:
            loader = TTLOntologyLoader()
            schema = loader.load_from_file(ttl_file)
            
            # Check entities were loaded
            assert "Product" in schema.entities
            assert "Team" in schema.entities
            
            # Check entity details
            product = schema.entities["Product"]
            assert product.iri == "http://example.org/ont#Product"
            assert product.description == "A software product or service offering"
            
            # Check relations were loaded
            assert "WORKS_ON" in schema.relations
            
            # Check relation details
            works_on = schema.relations["WORKS_ON"]
            assert works_on.iri == "http://example.org/ont#worksOn"
            assert "Team" in works_on.head_types
            assert "Product" in works_on.tail_types
            
            # Check metadata
            assert schema.metadata["format"] == "ttl"
            assert schema.metadata["triple_count"] > 0
            
        except ImportError:
            pytest.skip("rdflib not installed")
    
    def test_load_from_directory(self, tmp_path):
        """Test loading ontology from multiple TTL files."""
        try:
            # Create multiple TTL files
            ttl1 = tmp_path / "entities.ttl"
            ttl1.write_text("""
@prefix : <http://example.org/ont#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A software product" .
""")
            
            ttl2 = tmp_path / "relations.ttl"
            ttl2.write_text("""
@prefix : <http://example.org/ont#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

:Team a owl:Class ;
    rdfs:label "Team" ;
    rdfs:comment "An engineering team" .

:worksOn a owl:ObjectProperty ;
    rdfs:label "works on" ;
    rdfs:domain :Team ;
    rdfs:range :Product ;
    rdfs:comment "Team works on product" .
""")
            
            loader = TTLOntologyLoader()
            schema = loader.load_from_directory(tmp_path)
            
            # Both entities should be loaded from separate files
            assert "Product" in schema.entities
            assert "Team" in schema.entities
            
            # Relation should be loaded
            assert "WORKS_ON" in schema.relations
            
        except ImportError:
            pytest.skip("rdflib not installed")


class TestOntologySchemaSerialization:
    """Test OntologySchema serialization."""
    
    def test_to_dict_and_from_dict(self):
        """Test converting to dict and back."""
        schema = OntologySchema(
            entities={
                "Product": EntityType(
                    name="Product",
                    iri="http://example.org/ont#Product",
                    description="A software product",
                    examples=["Content Lake"]
                )
            },
            relations={
                "WORKS_ON": RelationType(
                    name="WORKS_ON",
                    iri="http://example.org/ont#worksOn",
                    head_types=["Team"],
                    tail_types=["Product"],
                    description="Team works on product"
                )
            },
            metadata={"version": "1.0"}
        )
        
        # Convert to dict
        schema_dict = schema.to_dict()
        
        assert "entities" in schema_dict
        assert "relations" in schema_dict
        assert "metadata" in schema_dict
        assert schema_dict["metadata"]["version"] == "1.0"
        
        # Convert back from dict
        restored_schema = OntologySchema.from_dict(schema_dict)
        
        assert "Product" in restored_schema.entities
        assert "WORKS_ON" in restored_schema.relations
        assert restored_schema.metadata["version"] == "1.0"
        assert restored_schema.entities["Product"].description == "A software product"
