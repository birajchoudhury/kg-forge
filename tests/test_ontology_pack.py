"""Simple test ontology pack for integration tests."""

from pathlib import Path
from typing import List, Optional

from kg_forge.ontology.base import OntologyPack, OntologyPackInfo, StyleConfig
from kg_forge.entities.models import EntityDefinition


class TestOntologyPack(OntologyPack):
    """Simple in-memory ontology pack for testing."""
    
    def __init__(self, entity_definitions: List[EntityDefinition]):
        """Initialize with entity definitions."""
        super().__init__(Path("/tmp/test_pack"))
        self.entity_definitions = entity_definitions
        self._info = OntologyPackInfo(
            id="test_pack",
            name="Test Ontology Pack",
            description="Simple ontology pack for testing",
            version="1.0.0"
        )
    
    @property
    def info(self) -> OntologyPackInfo:
        """Return pack info."""
        return self._info
    
    def load_entity_definitions(self) -> List[EntityDefinition]:
        """Return the entity definitions."""
        return self.entity_definitions
    
    def get_style_config(self) -> Optional[StyleConfig]:
        """Return basic style config."""
        return StyleConfig(
            entity_colors={
                "Technology": "#3498db",
                "Team": "#e74c3c",
                "Product": "#2ecc71"
            }
        )
    
    def get_prompt_template(self) -> Optional[str]:
        """Return basic prompt template."""
        return "Extract entities of types: {entity_types} from the following text:\n{text}"