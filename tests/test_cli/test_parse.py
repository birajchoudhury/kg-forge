"""Tests for parse CLI command."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from kg_forge.cli.parse import parse_html


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_data_dir():
    """Get path to test data directory."""
    return Path(__file__).parent.parent.parent / "test_docs"


def test_parse_directory(runner, test_data_dir):
    """Test parsing a directory of HTML files."""
    result = runner.invoke(parse_html, ["--source", str(test_data_dir)])
    
    assert result.exit_code == 0
    assert "Successfully parsed" in result.output
    assert "document" in result.output.lower()


def test_parse_single_file(runner, test_data_dir):
    """Test parsing a single HTML file."""
    html_file = test_data_dir / "Content-Lake---focus_3352234692.html"
    result = runner.invoke(parse_html, ["--source", str(html_file)])
    
    assert result.exit_code == 0
    assert "Successfully parsed" in result.output
    assert "Content Lake - focus" in result.output


def test_parse_with_show_links(runner, test_data_dir):
    """Test parsing with --show-links option."""
    result = runner.invoke(parse_html, [
        "--source", str(test_data_dir),
        "--show-links"
    ])
    
    assert result.exit_code == 0
    assert "Links:" in result.output


def test_parse_with_show_content(runner, test_data_dir):
    """Test parsing with --show-content option."""
    html_file = test_data_dir / "Content-Lake---focus_3352234692.html"
    result = runner.invoke(parse_html, [
        "--source", str(html_file),
        "--show-content"
    ])
    
    assert result.exit_code == 0
    assert "Markdown Content:" in result.output


def test_parse_with_all_options(runner, test_data_dir):
    """Test parsing with both options enabled."""
    html_file = test_data_dir / "Content-Lake---focus_3352234692.html"
    result = runner.invoke(parse_html, [
        "--source", str(html_file),
        "--show-links",
        "--show-content"
    ])
    
    assert result.exit_code == 0
    assert "Links:" in result.output
    assert "Markdown Content:" in result.output


def test_parse_nonexistent_path(runner):
    """Test parsing a path that doesn't exist."""
    result = runner.invoke(parse_html, ["--source", "/nonexistent/path"])
    
    assert result.exit_code != 0


def test_parse_empty_directory(runner, tmp_path):
    """Test parsing an empty directory."""
    result = runner.invoke(parse_html, ["--source", str(tmp_path)])
    
    assert result.exit_code == 0
    assert "0" in result.output  # Should mention 0 documents
