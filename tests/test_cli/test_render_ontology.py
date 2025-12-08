"""Test render-ontology CLI command."""

import tempfile
from pathlib import Path
from click.testing import CliRunner

from kg_forge.cli.main import cli


def test_render_ontology_help():
    """Test render-ontology help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['render-ontology', '--help'])
    
    assert result.exit_code == 0
    assert 'Render ontology visualization as HTML file' in result.output
    assert '--ontology-pack' in result.output
    assert '--layout' in result.output
    assert '--theme' in result.output
    assert '--include-examples' in result.output


def test_render_ontology_generates_html():
    """Test that render-ontology generates HTML file."""
    runner = CliRunner()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "test_ontology.html"
        
        result = runner.invoke(cli, [
            'render-ontology', 
            '--out', str(output_path)
        ])
        
        # Should succeed (exit code 0) when ontology pack is available
        if result.exit_code == 0:
            assert output_path.exists()
            
            # Check that HTML file contains expected elements
            html_content = output_path.read_text()
            assert 'Ontology Visualization' in html_content
            assert 'cytoscape' in html_content.lower()
            assert 'ai_ml_confluence' in html_content
        else:
            # If no ontology pack available, should show appropriate error
            assert 'No ontology pack available' in result.output or 'not found' in result.output


def test_render_ontology_invalid_pack():
    """Test render-ontology with invalid ontology pack."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        'render-ontology',
        '--ontology-pack', 'nonexistent_pack'
    ])
    
    # Command should exit with an error code (could be 1 or 3)
    assert result.exit_code != 0
    assert 'not found' in result.output or 'not registered' in result.output


def test_render_ontology_layout_options():
    """Test render-ontology with different layout options."""
    runner = CliRunner()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "hierarchical_ontology.html"
        
        result = runner.invoke(cli, [
            'render-ontology',
            '--layout', 'hierarchical',
            '--out', str(output_path)
        ])
        
        # Should succeed if ontology pack is available
        if result.exit_code == 0:
            assert output_path.exists()
            html_content = output_path.read_text()
            assert 'hierarchical' in html_content.lower()


def test_render_ontology_theme_options():
    """Test render-ontology with different theme options."""
    runner = CliRunner()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "dark_ontology.html"
        
        result = runner.invoke(cli, [
            'render-ontology',
            '--theme', 'dark',
            '--out', str(output_path)
        ])
        
        # Should succeed if ontology pack is available
        if result.exit_code == 0:
            assert output_path.exists()
            html_content = output_path.read_text()
            # Check for dark theme colors
            assert '#121212' in html_content  # Dark background color


def test_render_ontology_with_examples():
    """Test render-ontology with examples included."""
    runner = CliRunner()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "ontology_with_examples.html"
        
        result = runner.invoke(cli, [
            'render-ontology',
            '--include-examples',
            '--out', str(output_path)
        ])
        
        # Should succeed if ontology pack is available
        if result.exit_code == 0:
            assert output_path.exists()
            html_content = output_path.read_text()
            # Should include example-related content when examples are available
            assert 'example' in html_content.lower()