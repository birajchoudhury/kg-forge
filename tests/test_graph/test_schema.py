"""Tests for SchemaManager."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from kg_forge.graph.schema import SchemaManager, SchemaConstraint, SchemaIndex
from kg_forge.graph.exceptions import SchemaError
from kg_forge.graph.neo4j_client import Neo4jClient


class TestSchemaConstraint:
    """Test SchemaConstraint dataclass."""
    
    def test_constraint_creation(self):
        """Test constraint object creation."""
        constraint = SchemaConstraint(
            name="test_unique",
            node_label="Test",
            properties=["id", "name"],
            constraint_type="UNIQUE"
        )
        
        assert constraint.name == "test_unique"
        assert constraint.node_label == "Test"
        assert constraint.properties == ["id", "name"]
        assert constraint.constraint_type == "UNIQUE"
        
    def test_constraint_to_cypher_single_property(self):
        """Test Cypher generation for single property constraint."""
        constraint = SchemaConstraint(
            name="doc_id_unique",
            node_label="Doc",
            properties=["doc_id"]
        )
        
        cypher = constraint.to_cypher()
        expected = (
            "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS "
            "FOR (n:Doc) "
            "REQUIRE (n.doc_id) IS UNIQUE"
        )
        
        assert cypher == expected
        
    def test_constraint_to_cypher_multiple_properties(self):
        """Test Cypher generation for multi-property constraint."""
        constraint = SchemaConstraint(
            name="entity_unique",
            node_label="Entity",
            properties=["namespace", "entity_type", "name"]
        )
        
        cypher = constraint.to_cypher()
        expected = (
            "CREATE CONSTRAINT entity_unique IF NOT EXISTS "
            "FOR (n:Entity) "
            "REQUIRE (n.namespace, n.entity_type, n.name) IS UNIQUE"
        )
        
        assert cypher == expected


class TestSchemaIndex:
    """Test SchemaIndex dataclass."""
    
    def test_index_creation(self):
        """Test index object creation."""
        index = SchemaIndex(
            name="test_idx",
            node_label="Test",
            properties=["name"]
        )
        
        assert index.name == "test_idx"
        assert index.node_label == "Test"
        assert index.properties == ["name"]
        
    def test_index_to_cypher_single_property(self):
        """Test Cypher generation for single property index."""
        index = SchemaIndex(
            name="doc_namespace_idx",
            node_label="Doc",
            properties=["namespace"]
        )
        
        cypher = index.to_cypher()
        expected = (
            "CREATE INDEX doc_namespace_idx IF NOT EXISTS "
            "FOR (n:Doc) ON (n.namespace)"
        )
        
        assert cypher == expected
        
    def test_index_to_cypher_multiple_properties(self):
        """Test Cypher generation for multi-property index."""
        index = SchemaIndex(
            name="entity_compound_idx",
            node_label="Entity",
            properties=["entity_type", "name"]
        )
        
        cypher = index.to_cypher()
        expected = (
            "CREATE INDEX entity_compound_idx IF NOT EXISTS "
            "FOR (n:Entity) ON (n.entity_type, n.name)"
        )
        
        assert cypher == expected


class TestSchemaManager:
    """Test SchemaManager functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_client = Mock(spec=Neo4jClient)
        self.schema_manager = SchemaManager(self.mock_client)
        
    def test_init(self):
        """Test SchemaManager initialization."""
        assert self.schema_manager.client == self.mock_client
        
    def test_get_required_constraints(self):
        """Test getting required constraints for KG Forge."""
        constraints = self.schema_manager.get_required_constraints()
        
        assert len(constraints) == 2
        
        # Check doc constraint
        doc_constraint = next(c for c in constraints if c.name == "doc_unique")
        assert doc_constraint.node_label == "Doc"
        assert doc_constraint.properties == ["namespace", "doc_id"]
        assert doc_constraint.constraint_type == "UNIQUE"
        
        # Check entity constraint
        entity_constraint = next(c for c in constraints if c.name == "entity_unique")
        assert entity_constraint.node_label == "Entity"
        assert entity_constraint.properties == ["namespace", "entity_type", "normalized_name"]
        assert entity_constraint.constraint_type == "UNIQUE"
        
    def test_get_required_indexes(self):
        """Test getting required indexes for KG Forge."""
        indexes = self.schema_manager.get_required_indexes()
        
        assert len(indexes) == 5
        
        index_names = {idx.name for idx in indexes}
        expected_names = {
            "doc_namespace", "doc_content_hash", 
            "entity_namespace", "entity_type", "entity_name"
        }
        
        assert index_names == expected_names
        
    def test_create_constraints_success(self):
        """Test successful constraint creation."""
        # Mock successful constraint creation
        self.mock_client.execute_query.return_value = []
        
        constraints = [
            SchemaConstraint("test_unique", "Test", ["id"])
        ]
        
        self.schema_manager.create_constraints(constraints)
        
        # Verify query was executed
        self.mock_client.execute_query.assert_called_once()
        cypher_call = self.mock_client.execute_query.call_args[0][0]
        assert "CREATE CONSTRAINT test_unique" in cypher_call
        
    def test_create_constraints_already_exists(self):
        """Test constraint creation when constraint already exists."""
        # Mock constraint already exists error
        self.mock_client.execute_query.side_effect = Exception("already exists")
        
        constraints = [
            SchemaConstraint("existing_constraint", "Test", ["id"])
        ]
        
        # Should not raise exception for existing constraints
        self.schema_manager.create_constraints(constraints)
        
    def test_create_constraints_actual_error(self):
        """Test constraint creation with actual error."""
        # Mock real error
        self.mock_client.execute_query.side_effect = Exception("syntax error")
        
        constraints = [
            SchemaConstraint("bad_constraint", "Test", ["id"])
        ]
        
        with pytest.raises(SchemaError) as exc_info:
            self.schema_manager.create_constraints(constraints)
            
        assert "Constraint creation failed" in str(exc_info.value)
        
    def test_create_indexes_success(self):
        """Test successful index creation."""
        # Mock successful index creation
        self.mock_client.execute_query.return_value = []
        
        indexes = [
            SchemaIndex("test_idx", "Test", ["name"])
        ]
        
        self.schema_manager.create_indexes(indexes)
        
        # Verify query was executed
        self.mock_client.execute_query.assert_called_once()
        cypher_call = self.mock_client.execute_query.call_args[0][0]
        assert "CREATE INDEX test_idx" in cypher_call
        
    def test_create_indexes_already_exists(self):
        """Test index creation when index already exists."""
        # Mock index already exists error
        self.mock_client.execute_query.side_effect = Exception("already exists")
        
        indexes = [
            SchemaIndex("existing_index", "Test", ["name"])
        ]
        
        # Should not raise exception for existing indexes
        self.schema_manager.create_indexes(indexes)
        
    def test_initialize_schema_success(self):
        """Test successful schema initialization."""
        # Mock successful execution
        self.mock_client.execute_query.return_value = []
        
        self.schema_manager.initialize_schema()
        
        # Verify multiple queries were executed (constraints + indexes)
        assert self.mock_client.execute_query.call_count > 5
        
    def test_initialize_schema_failure(self):
        """Test schema initialization failure."""
        # Mock failure
        self.mock_client.execute_query.side_effect = Exception("Database error")
        
        with pytest.raises(SchemaError) as exc_info:
            self.schema_manager.initialize_schema()
            
        assert "Schema initialization failed" in str(exc_info.value)
        
    def test_validate_schema_valid(self):
        """Test schema validation when schema is valid."""
        # Mock schema info with all required constraints and indexes
        mock_schema_info = {
            "constraints": [
                {"name": "doc_unique"},
                {"name": "entity_unique"}
            ],
            "indexes": [
                {"name": "doc_namespace"},
                {"name": "doc_content_hash"},
                {"name": "entity_namespace"},
                {"name": "entity_type"},
                {"name": "entity_name"}
            ]
        }
        
        self.mock_client.get_schema_info.return_value = mock_schema_info
        
        result = self.schema_manager.validate_schema()
        
        assert result["schema_valid"] is True
        assert result["constraints_valid"] is True
        assert result["indexes_valid"] is True
        assert result["missing_constraints"] == []
        assert result["missing_indexes"] == []
        
    def test_validate_schema_missing_constraints(self):
        """Test schema validation with missing constraints."""
        # Mock schema info missing doc constraint
        mock_schema_info = {
            "constraints": [
                {"name": "entity_unique"}
            ],
            "indexes": [
                {"name": "doc_namespace"},
                {"name": "doc_content_hash"},
                {"name": "entity_namespace"},
                {"name": "entity_type"},
                {"name": "entity_name"}
            ]
        }
        
        self.mock_client.get_schema_info.return_value = mock_schema_info
        
        result = self.schema_manager.validate_schema()
        
        assert result["schema_valid"] is False
        assert result["constraints_valid"] is False
        assert result["indexes_valid"] is True
        assert "doc_unique" in result["missing_constraints"]
        
    def test_validate_schema_missing_indexes(self):
        """Test schema validation with missing indexes."""
        # Mock schema info missing some indexes
        mock_schema_info = {
            "constraints": [
                {"name": "doc_unique"},
                {"name": "entity_unique"}
            ],
            "indexes": [
                {"name": "doc_namespace"},
                {"name": "entity_namespace"}
                # Missing doc_content_hash, entity_type, entity_name
            ]
        }
        
        self.mock_client.get_schema_info.return_value = mock_schema_info
        
        result = self.schema_manager.validate_schema()
        
        assert result["schema_valid"] is False
        assert result["constraints_valid"] is True
        assert result["indexes_valid"] is False
        assert len(result["missing_indexes"]) == 3
        assert "doc_content_hash" in result["missing_indexes"]
        assert "entity_type" in result["missing_indexes"]
        assert "entity_name" in result["missing_indexes"]
        
    def test_validate_schema_error(self):
        """Test schema validation with client error."""
        # Mock client error
        self.mock_client.get_schema_info.side_effect = Exception("Connection failed")
        
        with pytest.raises(SchemaError) as exc_info:
            self.schema_manager.validate_schema()
            
        assert "Schema validation failed" in str(exc_info.value)
        
    def test_drop_schema_success(self):
        """Test successful schema drop."""
        # Mock successful execution
        self.mock_client.execute_query.return_value = []
        
        self.schema_manager.drop_schema()
        
        # Verify DROP queries were executed
        assert self.mock_client.execute_query.call_count > 5
        
        # Check that DROP statements were used
        calls = self.mock_client.execute_query.call_args_list
        drop_calls = [call for call in calls if "DROP" in str(call)]
        assert len(drop_calls) > 0
        
    def test_drop_schema_partial_failure(self):
        """Test schema drop with some failures (should continue)."""
        # Mock some failures (should be handled gracefully)
        self.mock_client.execute_query.side_effect = [
            [],  # Success
            Exception("Constraint not found"),  # Failure (handled)
            [],  # Success
            Exception("Index not found"),  # Failure (handled)
            []   # Success
        ] + [[]] * 10  # More successes
        
        # Should not raise exception
        self.schema_manager.drop_schema()
