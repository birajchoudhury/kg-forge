"""Integration tests for the render CLI command."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from kg_forge.cli.render import render, _build_seed_config, _parse_type_list
from kg_forge.render.graph_query import GraphData, NodeRecord, RelationshipRecord, SeedConfig


class TestRenderCLI:
    """Test render CLI command functionality."""
    
    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock()
        settings.app.default_namespace = "test_namespace"
        settings.validate_namespace = Mock()
        return settings
    
    @pytest.fixture
    def sample_graph_data(self):
        """Create sample graph data for testing."""
        nodes = [
            NodeRecord("doc1", ["Doc"], {"id": "doc1", "title": "Test Doc"}),
            NodeRecord("entity1", ["Entity"], {"id": "entity1", "name": "Product A", "entity_type": "Product"})
        ]
        relationships = [
            RelationshipRecord("rel1", "doc1", "entity1", "MENTIONS", {})
        ]
        return GraphData(nodes=nodes, relationships=relationships)
    
    @patch('kg_forge.cli.render.get_settings')
    @patch('kg_forge.cli.render.Neo4jClient')
    @patch('kg_forge.cli.render.GraphQuery')
    @patch('kg_forge.cli.render.HtmlBuilder')
    def test_render_command_basic(self, mock_html_builder, mock_graph_query, mock_neo4j_client, mock_get_settings, runner, mock_settings, sample_graph_data):
        """Test basic render command execution."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        mock_client_instance = Mock()
        mock_client_instance.connect = Mock()
        mock_neo4j_client.return_value = mock_client_instance
        
        mock_query_instance = Mock()
        mock_query_instance.get_subgraph.return_value = sample_graph_data
        mock_graph_query.return_value = mock_query_instance
        
        mock_builder_instance = Mock()
        mock_builder_instance.generate_html = Mock()
        mock_html_builder.return_value = mock_builder_instance
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output_path = f.name
        
        try:
            # Run command
            result = runner.invoke(render, [
                '--out', output_path,
                '--namespace', 'test_ns',
                '--depth', '3',
                '--max-nodes', '150'
            ])
            
            # Check result
            assert result.exit_code == 0
            
            # Verify mocks were called appropriately
            mock_get_settings.assert_called_once()
            mock_settings.validate_namespace.assert_called_once_with('test_ns')
            mock_client_instance.connect.assert_called_once()
            mock_query_instance.get_subgraph.assert_called_once()
            mock_builder_instance.generate_html.assert_called_once()
            
            # Check subgraph query parameters
            query_call_args = mock_query_instance.get_subgraph.call_args
            assert query_call_args[1]['namespace'] == 'test_ns'
            assert query_call_args[1]['depth'] == 3
            assert query_call_args[1]['max_nodes'] == 150
            
        finally:
            # Clean up
            Path(output_path).unlink(missing_ok=True)
    
    @patch('kg_forge.cli.render.get_settings')
    @patch('kg_forge.cli.render.Neo4jClient')
    def test_render_command_neo4j_connection_error(self, mock_neo4j_client, mock_get_settings, runner, mock_settings):
        """Test render command with Neo4j connection error."""
        mock_get_settings.return_value = mock_settings
        
        # Setup Neo4j client to fail connection
        mock_client_instance = Mock()
        from kg_forge.graph.exceptions import Neo4jConnectionError as GraphConnectionError
        mock_client_instance.connect.side_effect = GraphConnectionError("Connection failed")
        mock_neo4j_client.return_value = mock_client_instance
        
        result = runner.invoke(render, ['--out', 'test.html'])
        
        # Should exit with error code 1
        assert result.exit_code == 1
        assert "Connection failed" in result.output
    
    @patch('kg_forge.cli.render.get_settings')
    def test_render_command_invalid_namespace(self, mock_get_settings, runner, mock_settings):
        """Test render command with invalid namespace."""
        mock_get_settings.return_value = mock_settings
        mock_settings.validate_namespace.side_effect = ValueError("Invalid namespace")
        
        result = runner.invoke(render, ['--namespace', 'invalid-namespace'])

        # Should exit with non-zero error code (Click may transform exit codes)
        assert result.exit_code != 0
        assert "Invalid namespace" in result.output
    
    def test_render_command_seed_entity_without_type(self, runner):
        """Test render command with seed entity but no entity type."""
        result = runner.invoke(render, [
            '--seed-entity', 'Product A'
            # Missing --entity-type
        ])
        
        # Should exit with error code 2
        assert result.exit_code == 2
        assert "--seed-entity requires --entity-type" in result.output
    
    @patch('kg_forge.cli.render.get_settings')
    @patch('kg_forge.cli.render.Neo4jClient')
    @patch('kg_forge.cli.render.GraphQuery')
    @patch('kg_forge.cli.render.HtmlBuilder')
    def test_render_command_with_seeds(self, mock_html_builder, mock_graph_query, mock_neo4j_client, mock_get_settings, runner, mock_settings, sample_graph_data):
        """Test render command with seed configuration."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        mock_client_instance = Mock()
        mock_client_instance.connect = Mock()
        mock_neo4j_client.return_value = mock_client_instance
        
        mock_query_instance = Mock()
        mock_query_instance.get_subgraph.return_value = sample_graph_data
        mock_graph_query.return_value = mock_query_instance
        
        mock_builder_instance = Mock()
        mock_builder_instance.generate_html = Mock()
        mock_builder_instance.generate_seed_info.return_value = "Seed info"
        mock_html_builder.return_value = mock_builder_instance
        
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output_path = f.name
        
        try:
            result = runner.invoke(render, [
                '--out', output_path,
                '--seed-doc-id', 'doc123',
                '--seed-entity', 'Product X',
                '--entity-type', 'Product'
            ])
            
            assert result.exit_code == 0
            
            # Check that seed config was built correctly
            query_call_args = mock_query_instance.get_subgraph.call_args
            seeds = query_call_args[1]['seeds']
            
            assert isinstance(seeds, SeedConfig)
            assert "doc123" in seeds.doc_ids
            assert any(e['name'] == 'Product X' and e['type'] == 'Product' for e in seeds.entities)
            
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    @patch('kg_forge.cli.render.get_settings')
    @patch('kg_forge.cli.render.Neo4jClient')
    @patch('kg_forge.cli.render.GraphQuery')
    @patch('kg_forge.cli.render.HtmlBuilder')
    def test_render_command_with_type_filters(self, mock_html_builder, mock_graph_query, mock_neo4j_client, mock_get_settings, runner, mock_settings, sample_graph_data):
        """Test render command with include/exclude type filters."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        mock_client_instance = Mock()
        mock_client_instance.connect = Mock()
        mock_neo4j_client.return_value = mock_client_instance
        
        mock_query_instance = Mock()
        mock_query_instance.get_subgraph.return_value = sample_graph_data
        mock_graph_query.return_value = mock_query_instance
        
        mock_builder_instance = Mock()
        mock_builder_instance.generate_html = Mock()
        mock_html_builder.return_value = mock_builder_instance
        
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output_path = f.name
        
        try:
            result = runner.invoke(render, [
                '--out', output_path,
                '--include-types', 'Product,Team',
                '--exclude-types', 'Technology'
            ])
            
            assert result.exit_code == 0
            
            # Check that type filters were passed correctly
            query_call_args = mock_query_instance.get_subgraph.call_args
            include_types = query_call_args[1]['include_types']
            exclude_types = query_call_args[1]['exclude_types']
            
            assert include_types == ['Product', 'Team']
            assert exclude_types == ['Technology']
            
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    @patch('kg_forge.cli.render.get_settings')
    @patch('kg_forge.cli.render.Neo4jClient')
    @patch('kg_forge.cli.render.GraphQuery')
    @patch('kg_forge.cli.render.HtmlBuilder')
    def test_render_command_empty_graph(self, mock_html_builder, mock_graph_query, mock_neo4j_client, mock_get_settings, runner, mock_settings):
        """Test render command with empty graph data."""
        # Setup mocks
        mock_get_settings.return_value = mock_settings
        
        mock_client_instance = Mock()
        mock_client_instance.connect = Mock()
        mock_neo4j_client.return_value = mock_client_instance
        
        empty_graph = GraphData(nodes=[], relationships=[])
        mock_query_instance = Mock()
        mock_query_instance.get_subgraph.return_value = empty_graph
        mock_graph_query.return_value = mock_query_instance
        
        mock_builder_instance = Mock()
        mock_builder_instance.generate_html = Mock()
        mock_html_builder.return_value = mock_builder_instance
        
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            output_path = f.name
        
        try:
            result = runner.invoke(render, ['--out', output_path])
            
            assert result.exit_code == 0
            assert "No graph data found" in result.output
            
            # Should still generate HTML file
            mock_builder_instance.generate_html.assert_called_once()
            
        finally:
            Path(output_path).unlink(missing_ok=True)


class TestRenderCLIHelpers:
    """Test helper functions used by render CLI."""
    
    def test_build_seed_config_empty(self):
        """Test building empty seed configuration."""
        result = _build_seed_config(None, None, None)
        
        assert isinstance(result, SeedConfig)
        assert result.is_empty is True
        assert len(result.doc_ids) == 0
        assert len(result.entities) == 0
    
    def test_build_seed_config_doc_id_only(self):
        """Test building seed config with document ID only."""
        result = _build_seed_config("doc123", None, None)
        
        assert isinstance(result, SeedConfig)
        assert result.is_empty is False
        assert "doc123" in result.doc_ids
        assert len(result.entities) == 0
    
    def test_build_seed_config_entity_only(self):
        """Test building seed config with entity only."""
        result = _build_seed_config(None, "Product A", "Product")
        
        assert isinstance(result, SeedConfig)
        assert result.is_empty is False
        assert len(result.doc_ids) == 0
        assert len(result.entities) == 1
        assert result.entities[0]["name"] == "Product A"
        assert result.entities[0]["type"] == "Product"
    
    def test_build_seed_config_both(self):
        """Test building seed config with both doc ID and entity."""
        result = _build_seed_config("doc123", "Product A", "Product")
        
        assert isinstance(result, SeedConfig)
        assert result.is_empty is False
        assert "doc123" in result.doc_ids
        assert len(result.entities) == 1
        assert result.entities[0]["name"] == "Product A"
        assert result.entities[0]["type"] == "Product"
    
    def test_parse_type_list_empty(self):
        """Test parsing empty type list."""
        result = _parse_type_list("")
        
        assert result == []
    
    def test_parse_type_list_single(self):
        """Test parsing single type."""
        result = _parse_type_list("Product")
        
        assert result == ["Product"]
    
    def test_parse_type_list_multiple(self):
        """Test parsing multiple types."""
        result = _parse_type_list("Product,Team,Technology")
        
        assert result == ["Product", "Team", "Technology"]
    
    def test_parse_type_list_with_spaces(self):
        """Test parsing type list with spaces."""
        result = _parse_type_list(" Product , Team , Technology ")
        
        assert result == ["Product", "Team", "Technology"]
    
    def test_parse_type_list_with_empty_entries(self):
        """Test parsing type list with empty entries."""
        result = _parse_type_list("Product,,Team,")
        
        assert result == ["Product", "Team"]


class TestRenderCLIIntegration:
    """Integration tests for render CLI with more realistic scenarios."""
    
    @pytest.fixture
    def realistic_graph_data(self):
        """Create realistic graph data for testing."""
        # Create a small but realistic knowledge graph
        nodes = [
            NodeRecord("doc1", ["Doc"], {
                "id": "doc1",
                "title": "Product Documentation",
                "file_path": "/docs/product-guide.html"
            }),
            NodeRecord("doc2", ["Doc"], {
                "id": "doc2", 
                "title": "Team Overview",
                "file_path": "/docs/team-info.html"
            }),
            NodeRecord("prod1", ["Entity"], {
                "id": "prod1",
                "name": "CloudService Pro",
                "entity_type": "Product",
                "description": "Enterprise cloud platform"
            }),
            NodeRecord("team1", ["Entity"], {
                "id": "team1",
                "name": "Platform Team",
                "entity_type": "Team", 
                "description": "Core platform development team"
            }),
            NodeRecord("tech1", ["Entity"], {
                "id": "tech1",
                "name": "Kubernetes",
                "entity_type": "Technology",
                "description": "Container orchestration platform"
            })
        ]
        
        relationships = [
            RelationshipRecord("rel1", "doc1", "prod1", "MENTIONS", {"confidence": 0.95}),
            RelationshipRecord("rel2", "doc1", "tech1", "MENTIONS", {"confidence": 0.87}),
            RelationshipRecord("rel3", "doc2", "team1", "MENTIONS", {"confidence": 0.92}),
            RelationshipRecord("rel4", "prod1", "tech1", "USES", {"confidence": 0.89}),
            RelationshipRecord("rel5", "team1", "prod1", "DEVELOPS", {"confidence": 0.94})
        ]
        
        return GraphData(nodes=nodes, relationships=relationships)
    
    @patch('kg_forge.cli.render.get_settings')
    @patch('kg_forge.cli.render.Neo4jClient')
    @patch('kg_forge.cli.render.GraphQuery')
    @patch('kg_forge.cli.render.HtmlBuilder')
    def test_realistic_render_scenario(self, mock_html_builder, mock_graph_query, mock_neo4j_client, mock_get_settings, realistic_graph_data):
        """Test a realistic render scenario with actual file output."""
        runner = CliRunner()
        
        # Setup mocks
        mock_settings = Mock()
        mock_settings.app.default_namespace = "production"
        mock_settings.validate_namespace = Mock()
        mock_get_settings.return_value = mock_settings
        
        mock_client_instance = Mock()
        mock_client_instance.connect = Mock()
        mock_neo4j_client.return_value = mock_client_instance
        
        mock_query_instance = Mock()
        mock_query_instance.get_subgraph.return_value = realistic_graph_data
        mock_graph_query.return_value = mock_query_instance
        
        # Use real HtmlBuilder to test actual file generation
        from kg_forge.render.html_builder import HtmlBuilder
        real_builder = HtmlBuilder()
        mock_html_builder.return_value = real_builder
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "realistic_graph.html"
            
            result = runner.invoke(render, [
                '--out', str(output_path),
                '--namespace', 'production',
                '--depth', '2',
                '--max-nodes', '100',
                '--seed-doc-id', 'doc1'
            ])
            
            # Command should succeed
            assert result.exit_code == 0
            
            # HTML file should be created
            assert output_path.exists()
            
            # File should contain expected content
            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content
            assert "production" in content
            assert "CloudService Pro" in content
            assert "vis-network" in content.lower() or "vis.js" in content.lower()
            
            # Should contain valid JSON data
            # Look for graphData assignment
            import re
            graph_data_match = re.search(r'const graphData = ({.*?});', content, re.DOTALL)
            if graph_data_match:
                graph_json = graph_data_match.group(1)
                parsed_data = json.loads(graph_json)
                
                assert "nodes" in parsed_data
                assert "relationships" in parsed_data
                assert len(parsed_data["nodes"]) > 0
                assert len(parsed_data["relationships"]) > 0