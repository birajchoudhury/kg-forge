"""Configuration management for kg-forge CLI."""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import yaml


class Neo4jConfig(BaseModel):
    """Neo4j connection configuration."""
    uri: str = Field(default="bolt://localhost:7687")
    username: str = Field(default="neo4j")
    password: str = Field(default="password")
    database: str = Field(default="neo4j")


class AWSConfig(BaseModel):
    """AWS Bedrock configuration."""
    # Credential options - use any combination that works for your setup:
    # 1. Explicit credentials (access_key_id + secret_access_key + optional session_token)
    # 2. AWS profile (profile_name)
    # 3. Environment variables (AWS_ACCESS_KEY_ID, etc.)
    # 4. IAM roles, SSO, etc. (leave all credential fields None)
    access_key_id: Optional[str] = Field(default=None)
    secret_access_key: Optional[str] = Field(default=None)
    session_token: Optional[str] = Field(default=None)
    profile_name: Optional[str] = Field(default=None)
    default_region: str = Field(default="us-east-1")
    bedrock_model_name: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0")
    bedrock_max_tokens: int = Field(default=4000)
    bedrock_temperature: float = Field(default=0.1)


class AppConfig(BaseModel):
    """Application configuration."""
    log_level: str = Field(default="INFO")
    default_namespace: str = Field(default="default")
    entities_extract_dir: str = Field(default="entities_extract")
    ontology_pack: Optional[str] = Field(default=None)
    ontology_packs_dir: str = Field(default="ontology_packs")
    default_extractor: str = Field(default="llm")
    default_dedup_backend: str = Field(default="splink")
    
    # Deduplication backend configuration
    dedup_similarity_threshold: float = Field(default=0.8)
    dedup_max_clusters: int = Field(default=1000)
    dedup_ensemble_strategy: str = Field(default="confidence_weighted")
    
    # Entity linking configuration
    linking_similarity_threshold: float = Field(default=0.8)
    linking_max_candidates: int = Field(default=5)
    linking_create_missing: bool = Field(default=True)

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @field_validator('default_namespace')
    @classmethod
    def validate_namespace(cls, v):
        """Validate namespace format - alphanumeric only, no spaces."""
        if not re.match(r'^[a-zA-Z0-9]+$', v):
            raise ValueError("Namespace must be alphanumeric only (no spaces or special characters)")
        return v

    @field_validator('default_extractor')
    @classmethod
    def validate_extractor(cls, v):
        """Validate extraction backend."""
        valid_extractors = ["llm", "spacy"]
        if v.lower() not in valid_extractors:
            raise ValueError(f"Extractor must be one of {valid_extractors}")
        return v.lower()

    @field_validator('default_dedup_backend')
    @classmethod
    def validate_dedup_backend(cls, v):
        """Validate deduplication backend."""
        valid_backends = ["none", "splink", "zingg", "both"]
        if v.lower() not in valid_backends:
            raise ValueError(f"Dedup backend must be one of {valid_backends}")
        return v.lower()
    
    @field_validator('dedup_similarity_threshold', 'linking_similarity_threshold')
    @classmethod
    def validate_similarity_threshold(cls, v):
        """Validate similarity threshold is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")
        return v
    
    @field_validator('dedup_max_clusters', 'linking_max_candidates')
    @classmethod
    def validate_positive_int(cls, v):
        """Validate positive integer values."""
        if v <= 0:
            raise ValueError("Value must be a positive integer")
        return v
    
    @field_validator('dedup_ensemble_strategy')
    @classmethod
    def validate_ensemble_strategy(cls, v):
        """Validate ensemble strategy."""
        valid_strategies = ["confidence_weighted", "voting", "union"]
        if v.lower() not in valid_strategies:
            raise ValueError(f"Ensemble strategy must be one of {valid_strategies}")
        return v.lower()


class Settings(BaseModel):
    """Main configuration class."""
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    aws: AWSConfig = Field(default_factory=AWSConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    @classmethod
    def load_config(cls, config_overrides: Optional[Dict[str, Any]] = None) -> "Settings":
        """
        Load configuration from multiple sources with proper precedence:
        1. Command-line arguments (highest priority)
        2. YAML configuration file
        3. Environment variables
        4. .env file values
        5. Default values (lowest priority)
        """
        # Load .env file first (lowest priority)
        load_dotenv()

        # Load configuration from YAML file
        yaml_config = cls._load_yaml_config()

        # Merge configurations with proper precedence
        config_data = {}
        
        # Start with defaults (handled by Pydantic)
        
        # Apply .env and environment variables
        env_config = cls._load_env_config()
        config_data = cls._merge_config(config_data, env_config)
        
        # Apply YAML config
        if yaml_config:
            config_data = cls._merge_config(config_data, yaml_config)
        
        # Apply command-line overrides (highest priority)
        if config_overrides:
            config_data = cls._merge_config(config_data, config_overrides)

        return cls(**config_data)

    @classmethod
    def _load_yaml_config(cls) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file."""
        config_paths = [
            Path("./kg_forge.yaml"),
            Path("./config.yaml"),
            Path.home() / ".kg_forge.yaml"
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        return yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Error parsing YAML config file {config_path}: {e}")
                except Exception as e:
                    raise ValueError(f"Error reading config file {config_path}: {e}")
        
        return None

    @classmethod
    def _load_env_config(cls) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # Neo4j configuration
        neo4j_config = {}
        if os.getenv("NEO4J_URI"):
            neo4j_config["uri"] = os.getenv("NEO4J_URI")
        if os.getenv("NEO4J_USERNAME"):
            neo4j_config["username"] = os.getenv("NEO4J_USERNAME")
        if os.getenv("NEO4J_PASSWORD"):
            neo4j_config["password"] = os.getenv("NEO4J_PASSWORD")
        if neo4j_config:
            config["neo4j"] = neo4j_config

        # AWS configuration
        aws_config = {}
        if os.getenv("AWS_ACCESS_KEY_ID"):
            aws_config["access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
        if os.getenv("AWS_SECRET_ACCESS_KEY"):
            aws_config["secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")
        if os.getenv("AWS_SESSION_TOKEN"):
            aws_config["session_token"] = os.getenv("AWS_SESSION_TOKEN")
        if os.getenv("AWS_PROFILE"):
            aws_config["profile_name"] = os.getenv("AWS_PROFILE")
        if os.getenv("AWS_DEFAULT_REGION"):
            aws_config["default_region"] = os.getenv("AWS_DEFAULT_REGION")
        if os.getenv("BEDROCK_MODEL_NAME"):
            aws_config["bedrock_model_name"] = os.getenv("BEDROCK_MODEL_NAME")
        if os.getenv("BEDROCK_MAX_TOKENS"):
            aws_config["bedrock_max_tokens"] = int(os.getenv("BEDROCK_MAX_TOKENS"))
        if os.getenv("BEDROCK_TEMPERATURE"):
            aws_config["bedrock_temperature"] = float(os.getenv("BEDROCK_TEMPERATURE"))
        if aws_config:
            config["aws"] = aws_config

        # App configuration
        app_config = {}
        if os.getenv("LOG_LEVEL"):
            app_config["log_level"] = os.getenv("LOG_LEVEL")
        if os.getenv("DEFAULT_NAMESPACE"):
            app_config["default_namespace"] = os.getenv("DEFAULT_NAMESPACE")
        if os.getenv("ENTITIES_EXTRACT_DIR"):
            app_config["entities_extract_dir"] = os.getenv("ENTITIES_EXTRACT_DIR")
        if os.getenv("ONTOLOGY_PACK"):
            app_config["ontology_pack"] = os.getenv("ONTOLOGY_PACK")
        if os.getenv("ONTOLOGY_PACKS_DIR"):
            app_config["ontology_packs_dir"] = os.getenv("ONTOLOGY_PACKS_DIR")
        if app_config:
            config["app"] = app_config

        return config

    @classmethod
    def _merge_config(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration dictionaries recursively."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result

    def validate_namespace(self, namespace: str) -> str:
        """Validate namespace format."""
        if not re.match(r'^[a-zA-Z0-9]+$', namespace):
            raise ValueError("Namespace must be alphanumeric only (no spaces or special characters)")
        return namespace


def get_settings(config_overrides: Optional[Dict[str, Any]] = None) -> Settings:
    """Get application settings with optional overrides."""
    return Settings.load_config(config_overrides)
