"""Ontology management for KG Forge - pluggable ontology support."""

from .base import OntologyPack, OntologyPackInfo, OntologyPackRegistry, StyleConfig, get_registry
from .filesystem_pack import FilesystemOntologyPack
from .schema import OntologySchema, EntityType, RelationType, Property
from .ttl_loader import TTLOntologyLoader
from .markdown_loader import MarkdownOntologyLoader

__all__ = [
    'OntologyPack',
    'OntologyPackInfo',
    'OntologyPackRegistry',
    'StyleConfig',
    'FilesystemOntologyPack',
    'OntologySchema',
    'EntityType',
    'RelationType',
    'Property',
    'TTLOntologyLoader',
    'MarkdownOntologyLoader',
    'get_registry',
]