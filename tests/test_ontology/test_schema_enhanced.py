"""Tests for enhanced OntologySchema with dependencies and kind."""

import pytest
import json
from kg_forge.ontology.schema import (
    OntologySchema, EntityType, RelationType, Property, Dependency
)


class TestDependency:
    """Test Dependency dataclass."""
    
    def test_create_dependency(self):
        """Test creating a Dependency."""
        dep = Dependency(
            role="contract",
            entity="Contract",
            cardinality="1"
        )
        
        assert dep.role == "contract"
        assert dep.entity == "Contract"
        assert dep.cardinality == "1"
    
    def test_dependency_to_dict(self):
        """Test Dependency serialization."""
        dep = Dependency(
            role="template",
            entity="Template",
            cardinality="0..1"
        )
        
        result = dep.to_dict()
        
        assert result == {
            "role": "template",
            "entity": "Template",
            "cardinality": "0..1"
        }


class TestEntityTypeWithKind:
    """Test EntityType with kind field."""
    
    def test_core_entity_default(self):
        """Test that default kind is 'core'."""
        entity = EntityType(
            name="Product",
            iri="http://example.org/ont#Product",
            description="A product"
        )
        
        assert entity.kind == "core"
        assert entity.depends_on == []
    
    def test_occurrence_entity(self):
        """Test occurrence entity."""
        entity = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="A contract execution event",
            kind="occurrence"
        )
        
        assert entity.kind == "occurrence"
    
    def test_entity_with_dependencies(self):
        """Test entity with dependencies."""
        dep1 = Dependency("contract", "Contract", "1")
        dep2 = Dependency("template", "Template", "0..1")
        
        entity = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="A contract execution",
            kind="occurrence",
            depends_on=[dep1, dep2]
        )
        
        assert len(entity.depends_on) == 2
        assert entity.depends_on[0].role == "contract"
        assert entity.depends_on[1].entity == "Template"
    
    def test_entity_to_dict_with_kind_and_dependencies(self):
        """Test EntityType.to_dict includes kind and dependencies."""
        dep = Dependency("contract", "Contract", "1")
        
        entity = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="A contract execution",
            kind="occurrence",
            depends_on=[dep]
        )
        
        result = entity.to_dict()
        
        assert result["kind"] == "occurrence"
        assert len(result["depends_on"]) == 1
        assert result["depends_on"][0]["role"] == "contract"
        assert result["depends_on"][0]["entity"] == "Contract"
        assert result["depends_on"][0]["cardinality"] == "1"


class TestOntologySchemaEnhanced:
    """Test enhanced OntologySchema methods."""
    
    def test_get_dependencies_for_occurrence(self):
        """Test getting dependencies for occurrence entity."""
        dep = Dependency("contract", "Contract", "1")
        
        occurrence_entity = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="A contract execution",
            kind="occurrence",
            depends_on=[dep]
        )
        
        core_entity = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A contract",
            kind="core"
        )
        
        schema = OntologySchema(
            entities={
                "ContractExecution": occurrence_entity,
                "Contract": core_entity
            },
            relations={}
        )
        
        deps = schema.get_dependencies("ContractExecution")
        assert len(deps) == 1
        assert deps[0].entity == "Contract"
    
    def test_get_dependencies_for_core_returns_empty(self):
        """Test getting dependencies for core entity returns empty list."""
        entity = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A contract",
            kind="core"
        )
        
        schema = OntologySchema(
            entities={"Contract": entity},
            relations={}
        )
        
        deps = schema.get_dependencies("Contract")
        assert deps == []
    
    def test_is_occurrence_entity(self):
        """Test checking if entity is occurrence type."""
        occurrence = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="A contract execution",
            kind="occurrence"
        )
        
        core = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A contract",
            kind="core"
        )
        
        schema = OntologySchema(
            entities={
                "ContractExecution": occurrence,
                "Contract": core
            },
            relations={}
        )
        
        assert schema.is_occurrence_entity("ContractExecution") is True
        assert schema.is_occurrence_entity("Contract") is False
        assert schema.is_occurrence_entity("Unknown") is False
    
    def test_from_dict_with_dependencies(self):
        """Test OntologySchema.from_dict with dependencies."""
        data = {
            "entities": {
                "ContractExecution": {
                    "name": "ContractExecution",
                    "iri": "http://example.org/ont#ContractExecution",
                    "description": "A contract execution",
                    "kind": "occurrence",
                    "properties": [],
                    "examples": [],
                    "depends_on": [
                        {
                            "role": "contract",
                            "entity": "Contract",
                            "cardinality": "1"
                        }
                    ]
                },
                "Contract": {
                    "name": "Contract",
                    "iri": "http://example.org/ont#Contract",
                    "description": "A contract",
                    "kind": "core",
                    "properties": [],
                    "examples": [],
                    "depends_on": []
                }
            },
            "relations": {}
        }
        
        schema = OntologySchema.from_dict(data)
        
        assert len(schema.entities) == 2
        assert schema.entities["ContractExecution"].kind == "occurrence"
        assert len(schema.entities["ContractExecution"].depends_on) == 1
        assert schema.entities["Contract"].kind == "core"
        assert len(schema.entities["Contract"].depends_on) == 0
    
    def test_backward_compatibility_to_dict(self):
        """Test that to_dict works with entities without kind/dependencies."""
        entity = EntityType(
            name="Product",
            iri="http://example.org/ont#Product",
            description="A product"
        )
        
        result = entity.to_dict()
        
        # Should have default values
        assert result["kind"] == "core"
        assert result["depends_on"] == []


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def test_to_gliner_config_still_works(self):
        """Test that to_gliner_config still works with enhanced schema."""
        entity1 = EntityType(
            name="Product",
            iri="http://example.org/ont#Product",
            description="A software product",
            kind="core"
        )
        
        entity2 = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="A contract execution event",
            kind="occurrence"
        )
        
        schema = OntologySchema(
            entities={
                "Product": entity1,
                "ContractExecution": entity2
            },
            relations={}
        )
        
        config = schema.to_gliner_config()
        
        assert len(config) == 2
        assert config["Product"] == "A software product"
        assert config["ContractExecution"] == "A contract execution event"
    
    def test_to_glirel_config_still_works(self):
        """Test that to_glirel_config still works with enhanced schema."""
        relation = RelationType(
            name="WORKS_ON",
            iri="http://example.org/ont#worksOn",
            head_types=["Team"],
            tail_types=["Product"],
            description="Team works on product"
        )
        
        schema = OntologySchema(
            entities={},
            relations={"WORKS_ON": relation}
        )
        
        config = schema.to_glirel_config()
        
        assert "WORKS_ON" in config
        assert config["WORKS_ON"]["head_types"] == ["Team"]
    
    def test_to_llm_prompt_snippet_still_works(self):
        """Test that to_llm_prompt_snippet still works."""
        entity = EntityType(
            name="Product",
            iri="http://example.org/ont#Product",
            description="A product",
            kind="core",
            examples=["Microsoft Office", "Adobe Photoshop"]
        )
        
        relation = RelationType(
            name="USES",
            iri="http://example.org/ont#uses",
            head_types=["Team"],
            tail_types=["Product"],
            description="Team uses product"
        )
        
        schema = OntologySchema(
            entities={"Product": entity},
            relations={"USES": relation}
        )
        
        snippet = schema.to_llm_prompt_snippet()
        
        assert "Product" in snippet
        assert "A product" in snippet
        assert "USES" in snippet


class TestEntityConfigSerialization:
    """Test OntologySchema.to_entity_config() method."""
    
    def test_to_entity_config_basic_core_entity(self):
        """Test conversion of simple core entity to config format."""
        entity = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A legal contract",
            kind="core",
            properties=[
                Property(name="title", description="Contract title", datatype="string", required=True),
                Property(name="value", description="Contract value", datatype="number", required=False)
            ]
        )
        
        schema = OntologySchema(entities={"Contract": entity}, relations={})
        config = schema.to_entity_config()
        
        assert "entities" in config
        assert "Contract" in config["entities"]
        
        contract_config = config["entities"]["Contract"]
        assert contract_config["kind"] == "core"
        assert contract_config["label"] == "Contract"
        assert contract_config["description"] == "A legal contract"
        
        # Properties should be dict, not array
        assert isinstance(contract_config["properties"], dict)
        assert "title" in contract_config["properties"]
        assert contract_config["properties"]["title"]["type"] == "string"
        assert "value" in contract_config["properties"]
        assert contract_config["properties"]["value"]["type"] == "number"
        
        # Core entities should have empty relations and depends_on
        assert contract_config["relations"] == {}
        assert contract_config["depends_on"] == []
    
    def test_to_entity_config_occurrence_entity_with_dependencies(self):
        """Test conversion of occurrence entity with dependencies."""
        core_entity = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A contract",
            kind="core",
            properties=[Property(name="title", description="Title", datatype="string")]
        )
        
        occurrence_entity = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="Execution of a contract",
            kind="occurrence",
            properties=[
                Property(name="executionDate", description="Date executed", datatype="date")
            ],
            depends_on=[
                Dependency(role="contract", entity="Contract", cardinality="1")
            ]
        )
        
        schema = OntologySchema(
            entities={"Contract": core_entity, "ContractExecution": occurrence_entity},
            relations={}
        )
        config = schema.to_entity_config()
        
        exec_config = config["entities"]["ContractExecution"]
        assert exec_config["kind"] == "occurrence"
        assert exec_config["label"] == "ContractExecution"
        
        # Check dependencies
        assert len(exec_config["depends_on"]) == 1
        assert exec_config["depends_on"][0]["role"] == "contract"
        assert exec_config["depends_on"][0]["entity"] == "Contract"
        assert exec_config["depends_on"][0]["cardinality"] == "1"
    
    def test_to_entity_config_with_relations(self):
        """Test that relations are nested within entities."""
        contract_entity = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A contract",
            kind="core"
        )
        
        party_entity = EntityType(
            name="Party",
            iri="http://example.org/ont#Party",
            description="A party",
            kind="core"
        )
        
        involves_relation = RelationType(
            name="INVOLVES",
            iri="http://example.org/ont#involves",
            head_types=["Contract"],
            tail_types=["Party"],
            description="Contract involves party"
        )
        
        schema = OntologySchema(
            entities={"Contract": contract_entity, "Party": party_entity},
            relations={"INVOLVES": involves_relation}
        )
        config = schema.to_entity_config()
        
        # Relation should be nested in Contract entity
        contract_config = config["entities"]["Contract"]
        assert "relations" in contract_config
        assert "INVOLVES" in contract_config["relations"]
        assert contract_config["relations"]["INVOLVES"]["target"] == "Party"
        
        # Party should not have this relation (it's not the head)
        party_config = config["entities"]["Party"]
        assert "INVOLVES" not in party_config["relations"]
    
    def test_to_entity_config_multiple_tail_types(self):
        """Test relations with multiple tail types (takes first)."""
        team_entity = EntityType(
            name="Team",
            iri="http://example.org/ont#Team",
            description="A team",
            kind="core"
        )
        
        product_entity = EntityType(
            name="Product",
            iri="http://example.org/ont#Product",
            description="A product",
            kind="core"
        )
        
        service_entity = EntityType(
            name="Service",
            iri="http://example.org/ont#Service",
            description="A service",
            kind="core"
        )
        
        uses_relation = RelationType(
            name="USES",
            iri="http://example.org/ont#uses",
            head_types=["Team"],
            tail_types=["Product", "Service"],  # Multiple possible targets
            description="Team uses product or service"
        )
        
        schema = OntologySchema(
            entities={"Team": team_entity, "Product": product_entity, "Service": service_entity},
            relations={"USES": uses_relation}
        )
        config = schema.to_entity_config()
        
        # Should take first tail type
        team_config = config["entities"]["Team"]
        assert "USES" in team_config["relations"]
        assert team_config["relations"]["USES"]["target"] == "Product"
    
    def test_to_entity_config_empty_properties(self):
        """Test entity with no properties."""
        entity = EntityType(
            name="SimpleEntity",
            iri="http://example.org/ont#SimpleEntity",
            description="Simple entity with no properties",
            kind="core",
            properties=[]
        )
        
        schema = OntologySchema(entities={"SimpleEntity": entity}, relations={})
        config = schema.to_entity_config()
        
        simple_config = config["entities"]["SimpleEntity"]
        assert simple_config["properties"] == {}
    
    def test_to_entity_config_preserves_datatype_fallback(self):
        """Test that properties without datatype default to 'string'."""
        entity = EntityType(
            name="Entity",
            iri="http://example.org/ont#Entity",
            description="Test entity",
            kind="core",
            properties=[
                Property(name="typedProp", description="Has type", datatype="number"),
                Property(name="untypedProp", description="No type", datatype=None)
            ]
        )
        
        schema = OntologySchema(entities={"Entity": entity}, relations={})
        config = schema.to_entity_config()
        
        entity_config = config["entities"]["Entity"]
        assert entity_config["properties"]["typedProp"]["type"] == "number"
        assert entity_config["properties"]["untypedProp"]["type"] == "string"
    
    def test_to_entity_config_complex_scenario(self):
        """Test complex scenario with multiple entities, relations, and dependencies."""
        # Core entities
        contract = EntityType(
            name="Contract",
            iri="http://example.org/ont#Contract",
            description="A contract",
            kind="core",
            properties=[
                Property(name="title", description="Title", datatype="string"),
                Property(name="value", description="Value", datatype="number")
            ]
        )
        
        party = EntityType(
            name="Party",
            iri="http://example.org/ont#Party",
            description="A party",
            kind="core",
            properties=[
                Property(name="name", description="Name", datatype="string")
            ]
        )
        
        # Occurrence entity
        execution = EntityType(
            name="ContractExecution",
            iri="http://example.org/ont#ContractExecution",
            description="Execution event",
            kind="occurrence",
            properties=[
                Property(name="executionDate", description="Date", datatype="date")
            ],
            depends_on=[
                Dependency(role="contract", entity="Contract", cardinality="1"),
                Dependency(role="parties", entity="Party", cardinality="1..*")
            ]
        )
        
        # Relations
        involves = RelationType(
            name="INVOLVES",
            iri="http://example.org/ont#involves",
            head_types=["Contract"],
            tail_types=["Party"],
            description="Contract involves party"
        )
        
        schema = OntologySchema(
            entities={"Contract": contract, "Party": party, "ContractExecution": execution},
            relations={"INVOLVES": involves}
        )
        config = schema.to_entity_config()
        
        # Verify structure
        assert len(config["entities"]) == 3
        
        # Contract
        contract_config = config["entities"]["Contract"]
        assert contract_config["kind"] == "core"
        assert len(contract_config["properties"]) == 2
        assert "INVOLVES" in contract_config["relations"]
        assert len(contract_config["depends_on"]) == 0
        
        # Party
        party_config = config["entities"]["Party"]
        assert party_config["kind"] == "core"
        assert len(party_config["properties"]) == 1
        assert len(party_config["relations"]) == 0
        
        # Execution
        execution_config = config["entities"]["ContractExecution"]
        assert execution_config["kind"] == "occurrence"
        assert len(execution_config["properties"]) == 1
        assert len(execution_config["depends_on"]) == 2
        
    def test_to_entity_config_can_be_json_serialized(self):
        """Test that output can be serialized to JSON."""
        entity = EntityType(
            name="Test",
            iri="http://example.org/ont#Test",
            description="Test entity",
            kind="core",
            properties=[Property(name="prop", description="Prop", datatype="string")]
        )
        
        schema = OntologySchema(entities={"Test": entity}, relations={})
        config = schema.to_entity_config()
        
        # Should not raise
        json_str = json.dumps(config, indent=2)
        assert isinstance(json_str, str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed == config
