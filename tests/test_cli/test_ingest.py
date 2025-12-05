"""Tests for ingest CLI command."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from kg_forge.cli.main import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_data_dir():
    """Get path to test data directory."""
    return Path(__file__).parent.parent.parent / "test_data"


def test_ingest_help_command(runner):
    """Test that ingest help works correctly."""
    result = runner.invoke(cli, ["ingest", "--help"])
    
    assert result.exit_code == 0
    assert "Ingest document files from source directory" in result.output
    assert "--source" in result.output
    assert "--namespace" in result.output
    assert "--dry-run" in result.output
    assert "--fake-llm" in result.output
    assert "--max-docs" in result.output


def test_ingest_missing_required_source(runner):
    """Test ingest without required source parameter."""
    result = runner.invoke(cli, [
        "ingest",
        "--namespace", "test"
    ])
    
    assert result.exit_code != 0
    assert "Missing option" in result.output or "required" in result.output.lower()


def test_ingest_invalid_source(runner):
    """Test ingest with invalid source directory."""
    result = runner.invoke(cli, [
        "ingest",
        "--source", "/nonexistent/path",
        "--namespace", "test",
        "--dry-run"
    ])
    
    assert result.exit_code != 0


def test_ingest_invalid_namespace(runner, test_data_dir):
    """Test ingest with invalid namespace containing spaces."""
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--namespace", "invalid namespace with spaces",
        "--dry-run"
    ])
    
    assert result.exit_code != 0
    assert "Invalid namespace" in result.output


def test_ingest_command_line_option_parsing(runner, test_data_dir):
    """Test that ingest command correctly accepts all expected options."""
    # Test with all valid options but expect failure due to missing config/Neo4j
    # This tests that the CLI parsing works correctly
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--namespace", "test", 
        "--dry-run",
        "--fake-llm",
        "--max-docs", "1",
        "--refresh",
        "--interactive"
    ])
    
    # Should not fail due to option parsing issues
    # May fail due to missing config or other dependencies, but that's expected
    assert "Invalid namespace" not in result.output
    assert "Missing option" not in result.output
    

def test_ingest_displays_configuration_info(runner, test_data_dir):
    """Test that ingest displays basic configuration information.""" 
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--namespace", "test",
        "--dry-run",
        "--fake-llm",
        "--max-docs", "1"
    ])
    
    # Should display basic config info even if pipeline fails
    assert "KG Forge Ingest Pipeline" in result.output
    assert "Source:" in result.output
    assert "Namespace: test" in result.output
    assert "DRY RUN" in result.output
    assert "FAKE" in result.output
    assert "Limit: 1 documents" in result.output