"""Test TTL to KG Forge config JSON converter."""

import pytest
import json
from pathlib import Path
from kg_forge.ontology.ttl_to_config import (
    ontology_to_kgforge_config,
    _get_local_name,
    _infer_datatype,
    _extract_role_name,
    _determine_cardinality
)
from rdflib import URIRef, Graph, Literal, OWL


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_get_local_name_with_hash(self):
        """Test extracting local name from URI with #."""
        uri = URIRef("http://example.org/ont#Product")
        assert _get_local_name(uri) == "Product"
    
    def test_get_local_name_with_slash(self):
        """Test extracting local name from URI with /."""
        uri = URIRef("http://example.org/ont/Product")
        assert _get_local_name(uri) == "Product"
    
    def test_infer_datatype_string(self):
        """Test inferring string datatype."""
        uri = URIRef("http://www.w3.org/2001/XMLSchema#string")
        assert _infer_datatype(uri) == "string"
    
    def test_infer_datatype_integer(self):
        """Test inferring number datatype."""
        uri = URIRef("http://www.w3.org/2001/XMLSchema#integer")
        assert _infer_datatype(uri) == "number"
    
    def test_infer_datatype_boolean(self):
        """Test inferring boolean datatype."""
        uri = URIRef("http://www.w3.org/2001/XMLSchema#boolean")
        assert _infer_datatype(uri) == "boolean"
    
    def test_infer_datatype_date(self):
        """Test inferring date datatype."""
        uri = URIRef("http://www.w3.org/2001/XMLSchema#date")
        assert _infer_datatype(uri) == "date"
    
    def test_infer_datatype_datetime(self):
        """Test inferring datetime datatype."""
        uri = URIRef("http://www.w3.org/2001/XMLSchema#dateTime")
        assert _infer_datatype(uri) == "datetime"
    
    def test_extract_role_name_of_prefix(self):
        """Test extracting role name with 'of' prefix."""
        assert _extract_role_name("ofContract") == "contract"
        assert _extract_role_name("of Contract") == "contract"
    
    def test_extract_role_name_has_prefix(self):
        """Test extracting role name with 'has' prefix."""
        assert _extract_role_name("hasTemplate") == "template"
        assert _extract_role_name("has Template") == "template"
    
    def test_extract_role_name_camel_case(self):
        """Test extracting role name from camelCase."""
        assert _extract_role_name("contractTemplate") == "contract_template"
    
    def test_determine_cardinality_exact(self):
        """Test determining exact cardinality."""
        g = Graph()
        restriction = URIRef("http://example.org/restriction1")
        g.add((restriction, OWL.qualifiedCardinality, Literal(1)))
        
        result = _determine_cardinality(g, restriction)
        assert result == "1"
    
    def test_determine_cardinality_optional(self):
        """Test determining optional cardinality (0..1)."""
        g = Graph()
        restriction = URIRef("http://example.org/restriction1")
        g.add((restriction, OWL.minQualifiedCardinality, Literal(0)))
        g.add((restriction, OWL.maxQualifiedCardinality, Literal(1)))
        
        result = _determine_cardinality(g, restriction)
        assert result == "0..1"
    
    def test_determine_cardinality_required_many(self):
        """Test determining required many cardinality (1..*)."""
        g = Graph()
        restriction = URIRef("http://example.org/restriction1")
        g.add((restriction, OWL.minQualifiedCardinality, Literal(1)))
        
        result = _determine_cardinality(g, restriction)
        assert result == "1..*"


class TestOntologyToConfig:
    """Test ontology to config conversion."""
    
    def test_simple_ontology_conversion(self, tmp_path):
        """Test converting a simple ontology to config."""
        # Create a simple TTL file
        ttl_content = '''@prefix : <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A software product" .

:productName a owl:DatatypeProperty ;
    rdfs:label "productName" ;
    rdfs:domain :Product ;
    rdfs:range xsd:string .

:price a owl:DatatypeProperty ;
    rdfs:label "price" ;
    rdfs:domain :Product ;
    rdfs:range xsd:decimal .
'''
        
        ttl_file = tmp_path / "test_ontology.ttl"
        ttl_file.write_text(ttl_content)
        
        config = ontology_to_kgforge_config(str(ttl_file))
        
        assert "entities" in config
        assert "Product" in config["entities"]
        
        product = config["entities"]["Product"]
        assert product["kind"] == "core"  # default
        assert product["label"] == "Product"
        assert product["description"] == "A software product"
        assert "productName" in product["properties"]
        assert product["properties"]["productName"]["type"] == "string"
        assert product["properties"]["price"]["type"] == "number"
    
    def test_ontology_with_relations(self, tmp_path):
        """Test converting ontology with object properties."""
        ttl_content = '''@prefix : <http://example.org/ont#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Team a owl:Class ;
    rdfs:label "Team" ;
    rdfs:comment "A team" .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A product" .

:worksOn a owl:ObjectProperty ;
    rdfs:label "worksOn" ;
    rdfs:comment "Team works on product" ;
    rdfs:domain :Team ;
    rdfs:range :Product .
'''
        
        ttl_file = tmp_path / "test_ontology.ttl"
        ttl_file.write_text(ttl_content)
        
        config = ontology_to_kgforge_config(str(ttl_file))
        
        assert "Team" in config["entities"]
        team = config["entities"]["Team"]
        assert "worksOn" in team["relations"]
        assert team["relations"]["worksOn"]["target"] == "Product"
        assert team["relations"]["worksOn"]["source"] == "object_property"
    
    def test_ontology_with_occurrence_entities(self, tmp_path):
        """Test converting ontology with occurrence entities."""
        ttl_content = '''@prefix : <http://example.org/ont#> .
@prefix ex: <http://example.org/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:CoreEntity a owl:Class ;
    rdfs:label "CoreEntity" .

:OccurrenceEntity a owl:Class ;
    rdfs:label "OccurrenceEntity" .

:Contract a owl:Class ;
    rdfs:label "Contract" ;
    rdfs:comment "A contract" ;
    rdfs:subClassOf :CoreEntity .

:ContractExecution a owl:Class ;
    rdfs:label "ContractExecution" ;
    rdfs:comment "A contract execution event" ;
    rdfs:subClassOf :OccurrenceEntity .
'''
        
        ttl_file = tmp_path / "test_ontology.ttl"
        ttl_file.write_text(ttl_content)
        
        config = ontology_to_kgforge_config(str(ttl_file))
        
        assert "Contract" in config["entities"]
        assert config["entities"]["Contract"]["kind"] == "core"
        
        assert "ContractExecution" in config["entities"]
        assert config["entities"]["ContractExecution"]["kind"] == "occurrence"
