"""Test CLI backend validation."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from kg_forge.cli.main import cli
from kg_forge.cli.ingest import ingest


def test_ingest_valid_extractor():
    """Test ingest command with valid extractor."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--extractor', 'llm', '--dry-run'])
    
    # Should not exit with invalid extractor error (may fail for other reasons like missing test_dir)
    assert "Invalid value for '--extractor'" not in result.output


def test_ingest_valid_extractor_spacy():
    """Test ingest command with valid spacy extractor."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--extractor', 'spacy', '--dry-run'])
    
    # Should not exit with invalid extractor error (may fail for other reasons like missing test_dir)
    assert "Invalid value for '--extractor'" not in result.output


def test_ingest_invalid_extractor():
    """Test ingest command with invalid extractor."""
    runner = CliRunner()
    
    with runner.isolated_filesystem():
        # Create a test directory so source validation passes
        import os
        os.makedirs('test_dir')
        
        result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--extractor', 'invalid'])
        
        assert result.exit_code != 0
        assert "Invalid value for '--extractor'" in result.output


def test_ingest_valid_dedup_backend():
    """Test ingest command with valid dedup backend."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--dedup-backend', 'splink', '--dry-run'])
    
    # Should not exit with invalid backend error (may fail for other reasons like missing test_dir)
    assert "Invalid value for '--dedup-backend'" not in result.output


def test_ingest_valid_dedup_backend_none():
    """Test ingest command with none dedup backend."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--dedup-backend', 'none', '--dry-run'])
    
    # Should not exit with invalid backend error (may fail for other reasons like missing test_dir)
    assert "Invalid value for '--dedup-backend'" not in result.output


def test_ingest_valid_dedup_backend_both():
    """Test ingest command with both dedup backend."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--dedup-backend', 'both', '--dry-run'])
    
    # Should not exit with invalid backend error (may fail for other reasons like missing test_dir)
    assert "Invalid value for '--dedup-backend'" not in result.output


def test_ingest_invalid_dedup_backend():
    """Test ingest command with invalid dedup backend."""
    runner = CliRunner()
    
    with runner.isolated_filesystem():
        # Create a test directory so source validation passes
        import os
        os.makedirs('test_dir')
        
        result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--dedup-backend', 'invalid'])
        
        assert result.exit_code != 0
        assert "Invalid value for '--dedup-backend'" in result.output


def test_ingest_help_shows_extractor_options():
    """Test that ingest help shows extractor options."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--help'])
    
    assert result.exit_code == 0
    assert "--extractor" in result.output
    assert "llm" in result.output
    assert "spacy" in result.output


def test_ingest_help_shows_dedup_backend_options():
    """Test that ingest help shows dedup-backend options."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--help'])
    
    assert result.exit_code == 0
    assert "--dedup-backend" in result.output
    assert "none" in result.output
    assert "splink" in result.output
    assert "zingg" in result.output
    assert "both" in result.output


class TestCuratorBackendValidation:
    """Tests for curator backend validation."""
    
    def test_ingest_valid_curator_docling(self):
        """Test that ingest accepts 'docling' as valid curator."""
        runner = CliRunner()
        result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--curator', 'docling', '--dry-run'])
        
        # Should not fail on curator validation
        assert "Invalid value for '--curator'" not in result.output
    
    def test_ingest_valid_curator_hyland_ke(self):
        """Test that ingest accepts 'hyland_ke' as valid curator."""
        runner = CliRunner()
        result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--curator', 'hyland_ke', '--dry-run'])
        
        # Should not fail on curator validation
        assert "Invalid value for '--curator'" not in result.output
    
    def test_ingest_invalid_curator(self):
        """Test that ingest rejects invalid curator."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create a test directory so source validation passes
            import os
            os.makedirs('test_dir')
            
            result = runner.invoke(cli, ['ingest', '--source', 'test_dir', '--curator', 'invalid_curator'])
            
            assert result.exit_code != 0
            assert "Invalid value for '--curator'" in result.output


def test_ingest_help_shows_curator_options():
    """Test that ingest help shows curator options."""
    runner = CliRunner()
    result = runner.invoke(cli, ['ingest', '--help'])
    
    assert result.exit_code == 0
    assert "--curator" in result.output
    assert "docling" in result.output
    assert "hyland_ke" in result.output