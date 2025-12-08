"""Tests for Neo4j CLI commands."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from kg_forge.cli.neo4j_ops import (
    neo4j, init_schema, test_connection, status, 
    clear_database, start, stop
)
from kg_forge.graph.exceptions import Neo4jConnectionError, SchemaError


class TestNeo4jCLI:
    """Test Neo4j CLI commands."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    @patch('kg_forge.cli.neo4j_ops.SchemaManager')
    def test_init_schema_success_table(self, mock_schema_manager_class, mock_client_class, mock_get_settings):
        """Test successful schema initialization with table output."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client
        
        mock_schema_manager = Mock()
        mock_schema_manager.initialize_schema.return_value = None
        mock_schema_manager.validate_schema.return_value = {
            "constraints_valid": True,
            "indexes_valid": True
        }
        mock_schema_manager.get_required_constraints.return_value = [Mock(), Mock()]
        mock_schema_manager.get_required_indexes.return_value = [Mock(), Mock(), Mock()]
        mock_schema_manager_class.return_value = mock_schema_manager
        
        result = self.runner.invoke(init_schema, [])
        
        assert result.exit_code == 0
        assert "Schema initialized successfully" in result.output
        mock_schema_manager.initialize_schema.assert_called_once_with(force=False)
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    @patch('kg_forge.cli.neo4j_ops.SchemaManager')
    def test_init_schema_success_json(self, mock_schema_manager_class, mock_client_class, mock_get_settings):
        """Test successful schema initialization with JSON output."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client_class.return_value = mock_client
        
        mock_schema_manager = Mock()
        mock_schema_manager.initialize_schema.return_value = None
        mock_validation = {
            "constraints_valid": True,
            "indexes_valid": True
        }
        mock_schema_manager.validate_schema.return_value = mock_validation
        mock_schema_manager_class.return_value = mock_schema_manager
        
        result = self.runner.invoke(init_schema, ["--output", "json"])
        
        assert result.exit_code == 0
        
        # Parse and validate JSON output
        # Extract JSON from output (may be mixed with logging)
        output_text = result.output.strip()
        
        # Find the JSON block
        json_start = output_text.find('{')
        if json_start == -1:
            raise ValueError(f"No JSON found in output: {output_text}")
            
        # Count braces to find the end
        brace_count = 0
        json_end = json_start
        
        for i, char in enumerate(output_text[json_start:], json_start):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break
        
        json_output = output_text[json_start:json_end]
        output_data = json.loads(json_output)
        assert output_data["status"] == "success"
        assert output_data["message"] == "Schema initialized successfully"
        assert output_data["validation"] == mock_validation
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_init_schema_connection_error(self, mock_client_class, mock_get_settings):
        """Test schema initialization with connection error."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client_class.side_effect = Neo4jConnectionError("Connection failed")
        
        result = self.runner.invoke(init_schema, [])
        
        assert result.exit_code != 0
        assert "Neo4j connection failed" in result.output
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_test_connection_success_table(self, mock_client_class, mock_get_settings):
        """Test successful connection test with table output."""
        # Setup mocks
        mock_settings = Mock()
        mock_settings.neo4j.database = "test_db"
        mock_settings.neo4j.uri = "bolt://localhost:7687"
        mock_settings.neo4j.username = "neo4j"
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.test_connection.return_value = True
        mock_client.get_schema_info.return_value = {
            "constraints": [{}, {}],
            "indexes": [{}, {}, {}]
        }
        mock_client.get_node_counts.return_value = {
            "docs": 10,
            "entities": 25
        }
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(test_connection, [])
        
        assert result.exit_code == 0
        assert "Neo4j connection successful" in result.output
        mock_client.test_connection.assert_called_once()
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_test_connection_success_json(self, mock_client_class, mock_get_settings):
        """Test successful connection test with JSON output."""
        # Setup mocks
        mock_settings = Mock()
        mock_settings.neo4j.database = "test_db"
        mock_settings.neo4j.uri = "bolt://localhost:7687"
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.test_connection.return_value = True
        mock_schema_info = {"constraints": [], "indexes": []}
        mock_client.get_schema_info.return_value = mock_schema_info
        mock_node_counts = {"docs": 5, "entities": 15}
        mock_client.get_node_counts.return_value = mock_node_counts
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(test_connection, ["--output", "json"])
        
        assert result.exit_code == 0
        
        # Parse and validate JSON output
        output_data = json.loads(result.output)
        assert output_data["status"] == "success"
        assert output_data["connected"] is True
        assert output_data["database"] == "test_db"
        assert output_data["uri"] == "bolt://localhost:7687"
        assert output_data["node_counts"] == mock_node_counts
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_test_connection_failure(self, mock_client_class, mock_get_settings):
        """Test connection test failure."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.test_connection.return_value = False
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(test_connection, [])
        
        assert result.exit_code != 0
        assert "Connection test failed" in result.output
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    @patch('kg_forge.cli.neo4j_ops.SchemaManager')
    def test_status_command_table(self, mock_schema_manager_class, mock_client_class, mock_get_settings):
        """Test status command with table output."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.get_node_counts.return_value = {"docs": 5, "entities": 10}
        mock_client.get_entity_types.return_value = ["Product", "Technology"]
        mock_client.get_schema_info.return_value = {"constraints": [], "indexes": []}
        mock_client_class.return_value = mock_client
        
        mock_schema_manager = Mock()
        mock_schema_manager.validate_schema.return_value = {
            "schema_valid": True,
            "constraints_valid": True,
            "indexes_valid": True,
            "missing_constraints": [],
            "missing_indexes": []
        }
        mock_schema_manager_class.return_value = mock_schema_manager
        
        result = self.runner.invoke(status, [])
        
        assert result.exit_code == 0
        assert "Neo4j Database Status" in result.output
        mock_client.get_node_counts.assert_called_once_with("default")
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_clear_database_with_confirmation(self, mock_client_class, mock_get_settings):
        """Test database clear with user confirmation."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.clear_database.return_value = 15
        mock_client_class.return_value = mock_client
        
        # Simulate user confirming the action
        result = self.runner.invoke(clear_database, input="y\n")
        
        assert result.exit_code == 0
        assert "Cleared entire database" in result.output
        mock_client.clear_database.assert_called_once_with(None)
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_clear_database_with_yes_flag(self, mock_client_class, mock_get_settings):
        """Test database clear with --yes flag (no confirmation)."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.clear_database.return_value = 20
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(clear_database, ["--yes"])
        
        assert result.exit_code == 0
        assert "Cleared entire database" in result.output
        mock_client.clear_database.assert_called_once_with(None)
        
    @patch('kg_forge.cli.neo4j_ops.get_settings')
    @patch('kg_forge.cli.neo4j_ops.Neo4jClient')
    def test_clear_database_namespace(self, mock_client_class, mock_get_settings):
        """Test database clear for specific namespace."""
        # Setup mocks
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=None)
        mock_client.clear_database.return_value = 8
        mock_client_class.return_value = mock_client
        
        result = self.runner.invoke(clear_database, ["--namespace", "test", "--yes"])
        
        assert result.exit_code == 0
        assert "namespace 'test'" in result.output
        mock_client.clear_database.assert_called_once_with("test")
        
    def test_clear_database_cancelled(self):
        """Test database clear when user cancels."""
        # Simulate user cancelling the action
        result = self.runner.invoke(clear_database, input="n\n")
        
        assert result.exit_code == 0
        assert "Operation cancelled" in result.output
        
    @patch('subprocess.run')
    def test_start_existing_container(self, mock_subprocess_run):
        """Test starting existing Neo4j container."""
        # Mock docker ps to show existing container
        mock_result = Mock()
        mock_result.stdout = "neo4j-kg-forge\n"
        mock_subprocess_run.return_value = mock_result
        
        result = self.runner.invoke(start, [])
        
        assert result.exit_code == 0
        assert "Starting existing Neo4j container" in result.output
        
        # Verify docker start was called
        start_call = None
        for call in mock_subprocess_run.call_args_list:
            if "start" in str(call):
                start_call = call
                break
        assert start_call is not None
        
    @patch('subprocess.run')
    def test_start_new_container(self, mock_subprocess_run):
        """Test creating new Neo4j container."""
        # Mock docker ps to show no existing container
        mock_result = Mock()
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        
        # Simulate user confirming container creation
        result = self.runner.invoke(start, input="y\n")
        
        assert result.exit_code == 0
        assert "Creating new Neo4j container" in result.output
        
    @patch('subprocess.run')
    def test_stop_container(self, mock_subprocess_run):
        """Test stopping Neo4j container."""
        result = self.runner.invoke(stop, [])
        
        assert result.exit_code == 0
        assert "Neo4j container stopped" in result.output
        
        # Verify docker stop was called
        mock_subprocess_run.assert_called_with(["docker", "stop", "neo4j-kg-forge"], check=True)
        
    @patch('subprocess.run')
    def test_start_docker_not_found(self, mock_subprocess_run):
        """Test start command when Docker is not available."""
        mock_subprocess_run.side_effect = FileNotFoundError()
        
        result = self.runner.invoke(start, [])
        
        assert result.exit_code != 0
        assert "Docker not found" in result.output
        
    @patch('subprocess.run')
    def test_stop_docker_error(self, mock_subprocess_run):
        """Test stop command with Docker error."""
        import subprocess
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "docker")
        
        result = self.runner.invoke(stop, [])
        
        assert result.exit_code != 0
        assert "Failed to stop Neo4j container" in result.output
