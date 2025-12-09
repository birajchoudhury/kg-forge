"""Base classes and interfaces for ontology packs."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from kg_forge.entities.models import EntityDefinition
from .schema import OntologySchema


@dataclass
class OntologyPackInfo:
    """Metadata about an ontology pack."""
    
    id: str
    name: str
    description: str
    version: str
    author: Optional[str] = None
    homepage: Optional[str] = None
    license: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class StyleConfig:
    """Style configuration for visualization."""
    
    entity_colors: Dict[str, str]
    entity_shapes: Dict[str, str] = None
    relationship_colors: Dict[str, str] = None
    relationship_styles: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.entity_shapes is None:
            self.entity_shapes = {}
        if self.relationship_colors is None:
            self.relationship_colors = {}
        if self.relationship_styles is None:
            self.relationship_styles = {}


class OntologyPack(ABC):
    """Abstract base class for ontology packs."""
    
    def __init__(self, pack_path: Path):
        """Initialize ontology pack from directory path."""
        self.pack_path = pack_path
        self._info: Optional[OntologyPackInfo] = None
        self._entities_loaded = False
        self._entity_definitions: List[EntityDefinition] = []
    
    @property
    @abstractmethod
    def info(self) -> OntologyPackInfo:
        """Get ontology pack metadata."""
        pass
    
    @abstractmethod
    def load_entity_definitions(self) -> List[EntityDefinition]:
        """Load entity type definitions from the ontology pack."""
        pass
    
    @abstractmethod
    def load_ontology_schema(self) -> OntologySchema:
        """Load and normalize ontology into OntologySchema.
        
        Auto-detects format (TTL or Markdown) and produces normalized schema.
        """
        pass
    
    @abstractmethod
    def get_style_config(self) -> Optional[StyleConfig]:
        """Get visualization style configuration."""
        pass
    
    @abstractmethod
    def get_prompt_template(self) -> Optional[str]:
        """Get LLM prompt template for entity extraction."""
        pass
    
    def get_entity_definitions(self) -> List[EntityDefinition]:
        """Get cached entity definitions, loading if necessary."""
        if not self._entities_loaded:
            self._entity_definitions = self.load_entity_definitions()
            self._entities_loaded = True
        return self._entity_definitions
    
    def reload_entities(self) -> List[EntityDefinition]:
        """Force reload of entity definitions."""
        self._entities_loaded = False
        return self.get_entity_definitions()
    
    def validate_pack(self) -> List[str]:
        """Validate ontology pack structure and return any issues."""
        issues = []
        
        # Check directory structure
        if not self.pack_path.exists():
            issues.append(f"Pack directory does not exist: {self.pack_path}")
            return issues
        
        if not self.pack_path.is_dir():
            issues.append(f"Pack path is not a directory: {self.pack_path}")
            return issues
        
        # Check for required files
        # Pack must have either:
        # 1. TTL files (.ttl) with pack.yaml, OR
        # 2. entities/ directory with .md files and pack.yaml
        
        pack_yaml = self.pack_path / "pack.yaml"
        has_pack_yaml = pack_yaml.exists()
        
        ttl_files = list(self.pack_path.glob("*.ttl"))
        entities_dir = self.pack_path / "entities"
        has_entities_dir = entities_dir.exists()
        
        if not has_pack_yaml:
            issues.append("Missing 'pack.yaml' configuration file")
        
        if not ttl_files and not has_entities_dir:
            issues.append("Pack must have either .ttl files or entities/ directory with .md files")
        
        # Validate entity definitions or ontology schema
        # TTL-based packs don't need entity definitions
        if not ttl_files:
            try:
                definitions = self.get_entity_definitions()
                if not definitions:
                    issues.append("No entity definitions found")
            except Exception as e:
                issues.append(f"Failed to load entity definitions: {e}")
        
        return issues
    
    def __str__(self) -> str:
        """String representation of the ontology pack."""
        return f"OntologyPack({self.info.id}: {self.info.name})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"OntologyPack(id='{self.info.id}', name='{self.info.name}', path='{self.pack_path}')"


class OntologyPackRegistry:
    """Registry for managing available ontology packs."""
    
    def __init__(self):
        """Initialize empty registry."""
        self._packs: Dict[str, OntologyPack] = {}
        self._default_pack_id: Optional[str] = None
    
    def register_pack(self, pack: OntologyPack) -> None:
        """Register an ontology pack."""
        pack_id = pack.info.id
        if pack_id in self._packs:
            raise ValueError(f"Ontology pack '{pack_id}' is already registered")
        
        self._packs[pack_id] = pack
        
        # Set as default if it's the first pack
        if self._default_pack_id is None:
            self._default_pack_id = pack_id
    
    def unregister_pack(self, pack_id: str) -> None:
        """Unregister an ontology pack."""
        if pack_id not in self._packs:
            raise ValueError(f"Ontology pack '{pack_id}' is not registered")
        
        del self._packs[pack_id]
        
        # Update default if necessary
        if self._default_pack_id == pack_id:
            self._default_pack_id = next(iter(self._packs.keys())) if self._packs else None
    
    def get_pack(self, pack_id: str) -> OntologyPack:
        """Get ontology pack by ID."""
        if pack_id not in self._packs:
            raise ValueError(f"Ontology pack '{pack_id}' is not registered")
        return self._packs[pack_id]
    
    def list_packs(self) -> List[OntologyPackInfo]:
        """List all registered ontology packs."""
        return [pack.info for pack in self._packs.values()]
    
    def get_default_pack(self) -> Optional[OntologyPack]:
        """Get the default ontology pack."""
        if self._default_pack_id is None:
            return None
        return self._packs[self._default_pack_id]
    
    def set_default_pack(self, pack_id: str) -> None:
        """Set the default ontology pack."""
        if pack_id not in self._packs:
            raise ValueError(f"Ontology pack '{pack_id}' is not registered")
        self._default_pack_id = pack_id
    
    def discover_packs(self, packs_dir: Path) -> List[OntologyPack]:
        """Discover ontology packs from directory."""
        from .filesystem_pack import FilesystemOntologyPack
        
        discovered_packs = []
        
        if not packs_dir.exists() or not packs_dir.is_dir():
            return discovered_packs
        
        for pack_dir in packs_dir.iterdir():
            if pack_dir.is_dir():
                try:
                    pack = FilesystemOntologyPack(pack_dir)
                    # Validate pack before registering
                    issues = pack.validate_pack()
                    if not issues:
                        self.register_pack(pack)
                        discovered_packs.append(pack)
                except Exception:
                    # Skip invalid packs silently during discovery
                    continue
        
        return discovered_packs
    
    def clear(self) -> None:
        """Clear all registered packs."""
        self._packs.clear()
        self._default_pack_id = None


# Global registry instance
_global_registry = OntologyPackRegistry()


def get_registry() -> OntologyPackRegistry:
    """Get the global ontology pack registry."""
    return _global_registry