"""Test configuration backend validation."""

import pytest
from pydantic import ValidationError

from kg_forge.config.settings import AppConfig


def test_valid_extractor_llm():
    """Test valid LLM extractor."""
    config = AppConfig(default_extractor="llm")
    assert config.default_extractor == "llm"


def test_valid_extractor_spacy():
    """Test valid spaCy extractor."""
    config = AppConfig(default_extractor="spacy")
    assert config.default_extractor == "spacy"


def test_valid_extractor_case_insensitive():
    """Test extractor is case insensitive."""
    config = AppConfig(default_extractor="LLM")
    assert config.default_extractor == "llm"
    
    config = AppConfig(default_extractor="SpaCy")
    assert config.default_extractor == "spacy"


def test_invalid_extractor():
    """Test invalid extractor raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(default_extractor="invalid")
    
    assert "Extractor must be one of" in str(exc_info.value)


def test_valid_dedup_backend_none():
    """Test valid none dedup backend."""
    config = AppConfig(default_dedup_backend="none")
    assert config.default_dedup_backend == "none"


def test_valid_dedup_backend_splink():
    """Test valid splink dedup backend."""
    config = AppConfig(default_dedup_backend="splink")
    assert config.default_dedup_backend == "splink"


def test_valid_dedup_backend_zingg():
    """Test valid zingg dedup backend."""
    config = AppConfig(default_dedup_backend="zingg")
    assert config.default_dedup_backend == "zingg"


def test_valid_dedup_backend_both():
    """Test valid both dedup backend."""
    config = AppConfig(default_dedup_backend="both")
    assert config.default_dedup_backend == "both"


def test_valid_dedup_backend_case_insensitive():
    """Test dedup backend is case insensitive."""
    config = AppConfig(default_dedup_backend="SPLINK")
    assert config.default_dedup_backend == "splink"
    
    config = AppConfig(default_dedup_backend="Zingg")
    assert config.default_dedup_backend == "zingg"


def test_invalid_dedup_backend():
    """Test invalid dedup backend raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(default_dedup_backend="invalid")
    
    assert "Dedup backend must be one of" in str(exc_info.value)


def test_valid_namespace():
    """Test valid namespace."""
    config = AppConfig(default_namespace="test123")
    assert config.default_namespace == "test123"


def test_invalid_namespace_with_space():
    """Test invalid namespace with space."""
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(default_namespace="test space")
    
    assert "alphanumeric only" in str(exc_info.value)


def test_invalid_namespace_with_special_chars():
    """Test invalid namespace with special characters."""
    with pytest.raises(ValidationError) as exc_info:
        AppConfig(default_namespace="test-namespace")
    
    assert "alphanumeric only" in str(exc_info.value)


def test_valid_namespace_alphanumeric():
    """Test valid alphanumeric namespace."""
    config = AppConfig(default_namespace="TestNamespace123")
    assert config.default_namespace == "TestNamespace123"