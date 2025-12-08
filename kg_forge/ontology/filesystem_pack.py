"""Filesystem-based ontology pack implementation."""

import yaml
import logging
from pathlib import Path
from typing import List, Optional

from .base import OntologyPack, OntologyPackInfo, StyleConfig
from .schema import OntologySchema
from .ttl_loader import TTLOntologyLoader
from .markdown_loader import MarkdownOntologyLoader
from kg_forge.entities.models import EntityDefinition
from kg_forge.entities.definitions import EntityDefinitionLoader

logger = logging.getLogger(__name__)


class FilesystemOntologyPack(OntologyPack):
    """Ontology pack stored in filesystem directory."""
    
    def __init__(self, pack_path: Path):
        """Initialize filesystem ontology pack."""
        super().__init__(pack_path)
        self._config: Optional[dict] = None
        self._ontology_schema: Optional[OntologySchema] = None
    
    @property
    def info(self) -> OntologyPackInfo:
        """Load pack metadata from pack.yaml."""
        if self._info is None:
            config = self._load_config()
            
            # Extract required fields with defaults
            pack_id = config.get('id')
            if not pack_id:
                # Use directory name as fallback ID
                pack_id = self.pack_path.name
            
            self._info = OntologyPackInfo(
                id=pack_id,
                name=config.get('name', pack_id.title()),
                description=config.get('description', 'No description available'),
                version=config.get('version', '1.0.0'),
                author=config.get('author'),
                homepage=config.get('homepage'),
                license=config.get('license'),
                tags=config.get('tags', [])
            )
        
        return self._info
    
    def load_entity_definitions(self) -> List[EntityDefinition]:
        """Load entity definitions from entities/ directory."""
        entities_dir = self.pack_path / "entities"
        
        if not entities_dir.exists():
            logger.warning(f"Entities directory not found in pack: {self.pack_path}")
            return []
        
        loader = EntityDefinitionLoader()
        return loader.load_entity_definitions(entities_dir)
    
    def load_ontology_schema(self) -> OntologySchema:
        """Load and normalize ontology into OntologySchema.
        
        Auto-detects format:
        - If .ttl files present: Use TTLOntologyLoader
        - Else: Use MarkdownOntologyLoader (legacy)
        
        Returns:
            Normalized OntologySchema
        """
        if self._ontology_schema is not None:
            return self._ontology_schema
        
        # Check for TTL files (standard format)
        ttl_files = list(self.pack_path.glob("*.ttl"))
        entities_dir = self.pack_path / "entities"
        
        if ttl_files:
            # TTL format (standard)
            logger.info(f"Detected TTL ontology format in {self.pack_path}")
            loader = TTLOntologyLoader()
            
            if len(ttl_files) == 1:
                self._ontology_schema = loader.load_from_file(ttl_files[0])
            else:
                self._ontology_schema = loader.load_from_directory(self.pack_path)
        
        elif entities_dir.exists() and list(entities_dir.glob("*.md")):
            # Markdown format (legacy)
            logger.info(f"Detected Markdown ontology format in {self.pack_path}")
            loader = MarkdownOntologyLoader()
            self._ontology_schema = loader.load_from_directory(entities_dir)
        
        else:
            raise ValueError(
                f"No ontology files found in {self.pack_path}. "
                "Expected either .ttl files or entities/*.md files."
            )
        
        return self._ontology_schema
    
    def get_style_config(self) -> Optional[StyleConfig]:
        """Load style configuration from pack config."""
        config = self._load_config()
        style_config = config.get('styles')
        
        if not style_config:
            return None
        
        return StyleConfig(
            entity_colors=style_config.get('entity_colors', {}),
            entity_shapes=style_config.get('entity_shapes', {}),
            relationship_colors=style_config.get('relationship_colors', {}),
            relationship_styles=style_config.get('relationship_styles', {})
        )
    
    def get_prompt_template(self) -> Optional[str]:
        """Load prompt template from entities/prompt_template.md."""
        template_path = self.pack_path / "entities" / "prompt_template.md"
        
        if not template_path.exists():
            return None
        
        try:
            return template_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to load prompt template from {template_path}: {e}")
            return None
    
    def _load_config(self) -> dict:
        """Load pack configuration from pack.yaml."""
        if self._config is None:
            config_path = self.pack_path / "pack.yaml"
            
            if not config_path.exists():
                logger.warning(f"Pack config not found: {config_path}")
                self._config = {}
            else:
                try:
                    with config_path.open('r', encoding='utf-8') as f:
                        self._config = yaml.safe_load(f) or {}
                except Exception as e:
                    logger.error(f"Failed to load pack config {config_path}: {e}")
                    self._config = {}
        
        return self._config
    
    def validate_pack(self) -> List[str]:
        """Validate filesystem ontology pack structure."""
        issues = super().validate_pack()
        
        # Additional filesystem-specific validation
        config_path = self.pack_path / "pack.yaml"
        if config_path.exists():
            try:
                config = self._load_config()
                
                # Validate required config fields
                if not config.get('id'):
                    issues.append("Missing required 'id' field in pack.yaml")
                
                if not config.get('name'):
                    issues.append("Missing required 'name' field in pack.yaml")
                    
            except Exception as e:
                issues.append(f"Invalid pack.yaml format: {e}")
        
        return issues