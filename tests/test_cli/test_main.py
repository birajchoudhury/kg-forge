"""Test main CLI functionality."""

import pytest
from click.testing import CliRunner

from kg_forge.cli.main import cli
from kg_forge import __version__


def test_cli_help():
    """Test that CLI shows help message."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    
    assert result.exit_code == 0
    assert "Knowledge Graph Forge" in result.output
    assert "Extract entities from unstructured content" in result.output


def test_cli_version():
    """Test CLI version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--version'])
    
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_version_subcommand():
    """Test CLI version subcommand."""
    runner = CliRunner()
    result = runner.invoke(cli, ['version'])
    
    assert result.exit_code == 0
    assert __version__ in result.output
    assert "kg-forge" in result.output


def test_cli_invalid_log_level():
    """Test CLI with invalid log level."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--log-level', 'INVALID'])
    
    assert result.exit_code != 0
    assert "Invalid value for '--log-level'" in result.output or "Error" in result.output


def test_cli_valid_log_level():
    """Test CLI with valid log level."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--log-level', 'DEBUG', '--help'])
    
    assert result.exit_code == 0


def test_ingest_help():
    """Test ingest command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--help'])
    
    assert result.exit_code == 0
    assert "Ingest document files" in result.output
    assert "--source" in result.output


def test_query_help():
    """Test query command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['query', '--help'])
    
    assert result.exit_code == 0
    assert "Query the knowledge graph" in result.output


def test_render_help():
    """Test render command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['render', '--help'])
    
    assert result.exit_code == 0
    assert "Render knowledge graph visualization" in result.output


def test_render_ontology_help():
    """Test render-ontology command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['render-ontology', '--help'])
    
    assert result.exit_code == 0
    assert "Render ontology visualization" in result.output


def test_neo4j_start_help():
    """Test neo4j start command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['neo4j', 'start', '--help'])
    
    assert result.exit_code == 0
    assert "Start Neo4j Docker container" in result.output


def test_neo4j_stop_help():
    """Test neo4j stop command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['neo4j', 'stop', '--help'])
    
    assert result.exit_code == 0
    assert "Stop Neo4j Docker container" in result.output


# def test_export_entities_help():
#     """Test export-entities command help."""
#     # Note: export-entities command not implemented yet
#     pass
