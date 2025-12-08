"""Test export-entities command."""

import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch

from kg_forge.cli.main import cli


def test_export_entities_help():
    """Test export-entities help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['export-entities', '--help'])
    
    assert result.exit_code == 0
    assert "Export entities from knowledge graph" in result.output
    assert "--output-dir" in result.output
    assert "--namespace" in result.output


def test_export_entities_with_default_options():
    """Test export-entities with default options."""
    runner = CliRunner()
    
    # Mock the Neo4j client and configuration
    mock_config = Mock()
    mock_config.app.default_namespace = "test"
    mock_config.validate_namespace = Mock()
    
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.run = Mock(return_value=[])  # No entities found
    
    with patch('kg_forge.cli.export_entities.get_settings', return_value=mock_config), \
         patch('kg_forge.cli.export_entities.Neo4jClient', return_value=mock_client):
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['export-entities'])
            
            assert result.exit_code == 0
            assert "Exporting entities from namespace: test" in result.output
            assert "No entities found" in result.output


def test_export_entities_with_custom_namespace():
    """Test export-entities with custom namespace."""
    runner = CliRunner()
    
    # Mock the configuration
    mock_config = Mock()
    mock_config.validate_namespace = Mock()
    
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.run = Mock(return_value=[])  # No entities found
    
    with patch('kg_forge.cli.export_entities.get_settings', return_value=mock_config), \
         patch('kg_forge.cli.export_entities.Neo4jClient', return_value=mock_client):
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['export-entities', '--namespace', 'custom'])
            
            assert result.exit_code == 0
            assert "Exporting entities from namespace: custom" in result.output
            mock_config.validate_namespace.assert_called_with('custom')


def test_export_entities_with_custom_output_dir():
    """Test export-entities with custom output directory."""
    runner = CliRunner()
    
    # Mock the configuration
    mock_config = Mock()
    mock_config.app.default_namespace = "test"
    mock_config.validate_namespace = Mock()
    
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.run = Mock(return_value=[])  # No entities found
    
    with patch('kg_forge.cli.export_entities.get_settings', return_value=mock_config), \
         patch('kg_forge.cli.export_entities.Neo4jClient', return_value=mock_client):
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['export-entities', '--output-dir', 'custom_entities'])
            
            assert result.exit_code == 0
            assert Path('custom_entities').exists()


def test_export_entities_invalid_namespace():
    """Test export-entities with invalid namespace."""
    runner = CliRunner()
    
    # Mock the configuration with validation error
    mock_config = Mock()
    mock_config.app.default_namespace = "test"
    mock_config.validate_namespace = Mock(side_effect=ValueError("Invalid namespace"))
    
    with patch('kg_forge.cli.export_entities.get_settings', return_value=mock_config):
        
        result = runner.invoke(cli, ['export-entities', '--namespace', 'invalid-name'])
        
        assert result.exit_code == 0  # Command doesn't exit with error code, just prints message
        assert "Invalid namespace" in result.output