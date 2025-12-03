"""
Data models for lexical extraction pipeline.

These models represent the output of extraction backends (LLM, spaCy) before
deduplication and linking to the canonical Knowledge Graph.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json


@dataclass
class LexicalMention:
    """A single mention of an entity in curated text.
    
    Represents one extraction result from either LLM or spaCy backend.
    Contains positional information, type classification, and backend-specific features.
    """
    
    id: str
    """Unique identifier within a document or batch"""
    
    doc_id: str
    """Links back to the :Doc node that contains this mention"""
    
    entity_type: str
    """Entity type (e.g., 'Product', 'Team', 'Topic') from ontology"""
    
    surface: str
    """Exact text span as it appears in the document"""
    
    start_offset: int
    """Character offset where mention starts in curated text"""
    
    end_offset: int
    """Character offset where mention ends in curated text"""
    
    features: Dict[str, Any] = field(default_factory=dict)
    """Backend-specific features and metadata
    
    Examples:
    - normalized_surface: normalized form of surface text
    - confidence: extraction confidence score
    - sentence_index: sentence containing this mention
    - surrounding_context: text around the mention
    - section: document section (heading, body, list)
    - tokens: tokenization information for spaCy backend
    - model_version: backend model version
    """
    
    def __post_init__(self):
        """Validate mention data after initialization."""
        if self.end_offset <= self.start_offset:
            raise ValueError(f"Invalid offsets: end_offset ({self.end_offset}) must be greater than start_offset ({self.start_offset})")
        
        if not self.surface.strip():
            raise ValueError("Surface text cannot be empty or whitespace-only")
        
        if not self.entity_type.strip():
            raise ValueError("Entity type cannot be empty or whitespace-only")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'doc_id': self.doc_id,
            'entity_type': self.entity_type,
            'surface': self.surface,
            'start_offset': self.start_offset,
            'end_offset': self.end_offset,
            'features': self.features
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LexicalMention':
        """Create instance from dictionary."""
        return cls(
            id=data['id'],
            doc_id=data['doc_id'],
            entity_type=data['entity_type'],
            surface=data['surface'],
            start_offset=data['start_offset'],
            end_offset=data['end_offset'],
            features=data.get('features', {})
        )


@dataclass
class LexicalRelation:
    """A relation between two lexical mentions.
    
    Typically produced by GLiREL or inferred by LLM backend.
    Represents relationships before deduplication and canonicalization.
    """
    
    id: str
    """Unique identifier for this relation"""
    
    type: str
    """Relation type (e.g., 'WORKS_ON', 'USES', 'PART_OF') from ontology"""
    
    src_mention_id: str
    """ID of source LexicalMention"""
    
    dst_mention_id: str
    """ID of destination LexicalMention"""
    
    features: Dict[str, Any] = field(default_factory=dict)
    """Backend-specific features and metadata
    
    Examples:
    - confidence: relation extraction confidence
    - pattern: pattern that triggered this relation (for rule-based)
    - sentence_index: sentence containing the relation
    - distance: token distance between mentions
    - context: surrounding text
    - model_version: backend model version
    """
    
    def __post_init__(self):
        """Validate relation data after initialization."""
        if not self.type.strip():
            raise ValueError("Relation type cannot be empty or whitespace-only")
        
        if self.src_mention_id == self.dst_mention_id:
            raise ValueError("Source and destination mentions cannot be the same")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'type': self.type,
            'src_mention_id': self.src_mention_id,
            'dst_mention_id': self.dst_mention_id,
            'features': self.features
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LexicalRelation':
        """Create instance from dictionary."""
        return cls(
            id=data['id'],
            type=data['type'],
            src_mention_id=data['src_mention_id'],
            dst_mention_id=data['dst_mention_id'],
            features=data.get('features', {})
        )


@dataclass
class LexicalGraph:
    """Complete lexical graph produced by an ExtractionBackend.
    
    Contains all mentions and relations extracted from a single document,
    along with metadata about the extraction process.
    """
    
    mentions: List[LexicalMention]
    """All entity mentions found in the document"""
    
    relations: List[LexicalRelation]
    """All relations found between mentions"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Extraction metadata
    
    Examples:
    - backend: extraction backend name ('llm', 'spacy')
    - model_version: specific model version used
    - extraction_time: processing duration
    - prompt_template: LLM prompt used
    - confidence_stats: aggregated confidence statistics
    - error_count: number of parsing errors encountered
    - doc_length: length of input document
    """
    
    def __post_init__(self):
        """Validate graph after initialization."""
        # Check for mention ID uniqueness
        mention_ids = [m.id for m in self.mentions]
        if len(mention_ids) != len(set(mention_ids)):
            duplicates = [mid for mid in mention_ids if mention_ids.count(mid) > 1]
            raise ValueError(f"Duplicate mention IDs found: {duplicates}")
        
        # Check that all relations reference valid mentions
        mention_id_set = set(mention_ids)
        for relation in self.relations:
            if relation.src_mention_id not in mention_id_set:
                raise ValueError(f"Relation {relation.id} references unknown source mention: {relation.src_mention_id}")
            if relation.dst_mention_id not in mention_id_set:
                raise ValueError(f"Relation {relation.id} references unknown destination mention: {relation.dst_mention_id}")
    
    def get_mention_by_id(self, mention_id: str) -> Optional[LexicalMention]:
        """Get mention by ID, or None if not found."""
        for mention in self.mentions:
            if mention.id == mention_id:
                return mention
        return None
    
    def get_mentions_by_type(self, entity_type: str) -> List[LexicalMention]:
        """Get all mentions of a specific entity type."""
        return [m for m in self.mentions if m.entity_type == entity_type]
    
    def get_relations_by_type(self, relation_type: str) -> List[LexicalRelation]:
        """Get all relations of a specific type."""
        return [r for r in self.relations if r.type == relation_type]
    
    def get_outgoing_relations(self, mention_id: str) -> List[LexicalRelation]:
        """Get all relations where the given mention is the source."""
        return [r for r in self.relations if r.src_mention_id == mention_id]
    
    def get_incoming_relations(self, mention_id: str) -> List[LexicalRelation]:
        """Get all relations where the given mention is the destination."""
        return [r for r in self.relations if r.dst_mention_id == mention_id]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'mentions': [m.to_dict() for m in self.mentions],
            'relations': [r.to_dict() for r in self.relations],
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LexicalGraph':
        """Create instance from dictionary."""
        mentions = [LexicalMention.from_dict(m) for m in data.get('mentions', [])]
        relations = [LexicalRelation.from_dict(r) for r in data.get('relations', [])]
        metadata = data.get('metadata', {})
        
        return cls(
            mentions=mentions,
            relations=relations,
            metadata=metadata
        )
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LexicalGraph':
        """Create instance from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def summary(self) -> Dict[str, Any]:
        """Get summary statistics for the graph."""
        entity_type_counts = {}
        relation_type_counts = {}
        
        for mention in self.mentions:
            entity_type_counts[mention.entity_type] = entity_type_counts.get(mention.entity_type, 0) + 1
        
        for relation in self.relations:
            relation_type_counts[relation.type] = relation_type_counts.get(relation.type, 0) + 1
        
        return {
            'total_mentions': len(self.mentions),
            'total_relations': len(self.relations),
            'entity_types': entity_type_counts,
            'relation_types': relation_type_counts,
            'backend': self.metadata.get('backend', 'unknown'),
            'extraction_time': self.metadata.get('extraction_time'),
        }


# Convenience functions for creating empty structures
def empty_lexical_graph(backend_name: str = "unknown") -> LexicalGraph:
    """Create an empty LexicalGraph with minimal metadata."""
    return LexicalGraph(
        mentions=[],
        relations=[],
        metadata={'backend': backend_name}
    )