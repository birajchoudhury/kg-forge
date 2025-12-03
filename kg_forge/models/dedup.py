"""
Data models for entity deduplication pipeline.

Extends the lexical models from Step 6 to support canonical entity clustering
and deduplicated graph representations after entity resolution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class CanonicalLexicalEntity:
    """
    Represents a cluster of mentions believed to refer to the same real-world entity.
    
    Output of deduplication backends (Splink/Zingg/none) after processing LexicalGraph.
    """
    id: str                           # Stable within namespace/batch
    entity_type: str                  # Same space as LexicalMention.entity_type  
    canonical_name: str               # Chosen surface form
    aliases: List[str] = field(default_factory=list)  # All observed surface forms
    mention_ids: List[str] = field(default_factory=list)  # LexicalMention.id values in cluster
    features: Dict[str, Any] = field(default_factory=dict)  # Aggregated dedup backend features
    
    def __post_init__(self):
        """Validate canonical entity properties."""
        if not self.id:
            raise ValueError("CanonicalLexicalEntity.id cannot be empty")
        if not self.entity_type:
            raise ValueError("CanonicalLexicalEntity.entity_type cannot be empty")
        if not self.canonical_name:
            raise ValueError("CanonicalLexicalEntity.canonical_name cannot be empty")
        if not self.mention_ids:
            raise ValueError("CanonicalLexicalEntity must reference at least one mention")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "mention_ids": self.mention_ids,
            "features": self.features
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalLexicalEntity":
        """Create instance from dictionary."""
        return cls(
            id=data["id"],
            entity_type=data["entity_type"],
            canonical_name=data["canonical_name"],
            aliases=data.get("aliases", []),
            mention_ids=data.get("mention_ids", []),
            features=data.get("features", {})
        )


@dataclass
class CanonicalRelation:
    """
    Relation between canonical entities after deduplication.
    
    Aggregates information from underlying LexicalRelations between mentions
    that were clustered into the same canonical entities.
    """
    id: str                          # Unique relation identifier
    type: str                        # e.g., "WORKS_ON", "USES", "PART_OF"
    src_entity_id: str               # CanonicalLexicalEntity.id
    dst_entity_id: str               # CanonicalLexicalEntity.id
    features: Dict[str, Any] = field(default_factory=dict)  # Aggregated from LexicalRelations
    
    def __post_init__(self):
        """Validate canonical relation properties."""
        if not self.id:
            raise ValueError("CanonicalRelation.id cannot be empty")
        if not self.type:
            raise ValueError("CanonicalRelation.type cannot be empty")
        if not self.src_entity_id:
            raise ValueError("CanonicalRelation.src_entity_id cannot be empty")
        if not self.dst_entity_id:
            raise ValueError("CanonicalRelation.dst_entity_id cannot be empty")
        if self.src_entity_id == self.dst_entity_id:
            raise ValueError("CanonicalRelation cannot have same source and destination")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "src_entity_id": self.src_entity_id,
            "dst_entity_id": self.dst_entity_id,
            "features": self.features
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalRelation":
        """Create instance from dictionary."""
        return cls(
            id=data["id"],
            type=data["type"],
            src_entity_id=data["src_entity_id"],
            dst_entity_id=data["dst_entity_id"],
            features=data.get("features", {})
        )


@dataclass
class DedupedLexicalGraph:
    """
    Lexical graph after deduplication processing.
    
    Contains canonical entities (clusters) and relations between them,
    along with metadata about the deduplication process.
    """
    canonical_entities: List[CanonicalLexicalEntity] = field(default_factory=list)
    relations: List[CanonicalRelation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate deduplicated graph structure."""
        # Check for duplicate canonical entity IDs
        entity_ids = {entity.id for entity in self.canonical_entities}
        if len(entity_ids) != len(self.canonical_entities):
            raise ValueError("DedupedLexicalGraph contains duplicate canonical entity IDs")
        
        # Check for duplicate relation IDs
        relation_ids = {relation.id for relation in self.relations}
        if len(relation_ids) != len(self.relations):
            raise ValueError("DedupedLexicalGraph contains duplicate relation IDs")
        
        # Validate relation references
        for relation in self.relations:
            if relation.src_entity_id not in entity_ids:
                raise ValueError(f"Relation {relation.id} references unknown src_entity_id: {relation.src_entity_id}")
            if relation.dst_entity_id not in entity_ids:
                raise ValueError(f"Relation {relation.id} references unknown dst_entity_id: {relation.dst_entity_id}")
    
    def get_entity_by_id(self, entity_id: str) -> Optional[CanonicalLexicalEntity]:
        """Get canonical entity by ID."""
        for entity in self.canonical_entities:
            if entity.id == entity_id:
                return entity
        return None
    
    def get_relations_for_entity(self, entity_id: str) -> List[CanonicalRelation]:
        """Get all relations where entity is source or destination."""
        return [
            relation for relation in self.relations
            if relation.src_entity_id == entity_id or relation.dst_entity_id == entity_id
        ]
    
    def get_entity_count_by_type(self) -> Dict[str, int]:
        """Get count of canonical entities by type."""
        counts = {}
        for entity in self.canonical_entities:
            counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
        return counts
    
    def get_relation_count_by_type(self) -> Dict[str, int]:
        """Get count of relations by type."""
        counts = {}
        for relation in self.relations:
            counts[relation.type] = counts.get(relation.type, 0) + 1
        return counts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "canonical_entities": [entity.to_dict() for entity in self.canonical_entities],
            "relations": [relation.to_dict() for relation in self.relations],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DedupedLexicalGraph":
        """Create instance from dictionary."""
        return cls(
            canonical_entities=[
                CanonicalLexicalEntity.from_dict(entity_data) 
                for entity_data in data.get("canonical_entities", [])
            ],
            relations=[
                CanonicalRelation.from_dict(relation_data)
                for relation_data in data.get("relations", [])
            ],
            metadata=data.get("metadata", {})
        )
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "DedupedLexicalGraph":
        """Create instance from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass 
class LinkResult:
    """
    Result of linking a canonical entity to existing KG entities.
    
    Produced by EntityLinkerBackend to indicate whether a canonical entity
    should be linked to an existing KG entity or created as new.
    """
    canonical_entity: "CanonicalLexicalEntity"  # The canonical entity being linked
    linked_entity: Optional["KGEntity"] = None   # Existing KG entity if linked
    confidence: float = 0.0                     # Linking confidence (0.0-1.0)
    candidates: List["KGCandidate"] = field(default_factory=list)  # All candidates considered
    action: str = "skip"                        # Action: "link_existing", "create_new", "skip"
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional backend-specific data
    
    def __post_init__(self):
        """Validate link result properties."""
        if not self.canonical_entity:
            raise ValueError("LinkResult.canonical_entity cannot be None")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("LinkResult.confidence must be between 0.0 and 1.0")
        valid_actions = {"link_existing", "create_new", "skip"}
        if self.action not in valid_actions:
            raise ValueError(f"LinkResult.action must be one of {valid_actions}")
    
    def is_new_entity(self) -> bool:
        """Check if this result creates a new entity."""
        return self.action == "create_new"
    
    def is_linked_entity(self) -> bool:
        """Check if this result links to existing entity."""
        return self.action == "link_existing"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "canonical_entity": self.canonical_entity.to_dict(),
            "linked_entity": self.linked_entity.to_dict() if self.linked_entity else None,
            "confidence": self.confidence,
            "candidates": [c.to_dict() for c in self.candidates],
            "action": self.action,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinkResult":
        """Create instance from dictionary."""
        return cls(
            canonical_entity_id=data["canonical_entity_id"],
            existing_entity_id=data.get("existing_entity_id"),
            new_entity_payload=data.get("new_entity_payload"),
            confidence=data.get("confidence", 0.0),
            explanation=data.get("explanation", "")
        )


# Helper data classes for entity linking

@dataclass
class KGEntity:
    """
    Existing entity from Neo4j knowledge graph.
    
    Used by EntityLinkerBackend to represent candidate entities
    for linking against canonical entities.
    """
    id: str                    # Neo4j entity identifier  
    name: str                  # Display name
    normalized_name: str       # Normalized for matching
    aliases: List[str] = field(default_factory=list)  # Known aliases
    confidence: float = 1.0    # Entity confidence score
    
    def __post_init__(self):
        """Validate KG entity properties."""
        if not self.id:
            raise ValueError("KGEntity.id cannot be empty")
        if not self.name:
            raise ValueError("KGEntity.name cannot be empty")
        if not self.normalized_name:
            raise ValueError("KGEntity.normalized_name cannot be empty")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("KGEntity.confidence must be between 0.0 and 1.0")


@dataclass
class KGCandidate:
    """
    Candidate entity for linking with match score.
    
    Represents a potential match between a canonical entity
    and an existing KG entity with similarity scoring.
    """
    kg_id: str                # Neo4j entity identifier (renamed from entity_id)
    name: str                 # Entity name
    entity_type: str          # Entity type
    namespace: str            # Entity namespace
    description: Optional[str] = None  # Entity description (may be None)
    properties: Optional[Dict] = None  # Entity properties (may be None)
    score: float = 1.0        # Similarity/match score (0.0-1.0)
    match_reason: str = "unknown"  # Explanation of why this is a candidate
    
    def __post_init__(self):
        """Validate KG candidate properties."""
        if not self.kg_id:
            raise ValueError("KGCandidate.kg_id cannot be empty")
        if not self.name:
            raise ValueError("KGCandidate.name cannot be empty")
        if not self.entity_type:
            raise ValueError("KGCandidate.entity_type cannot be empty")
        if not self.namespace:
            raise ValueError("KGCandidate.namespace cannot be empty")
        if self.score < 0.0 or self.score > 1.0:
            raise ValueError("KGCandidate.score must be between 0.0 and 1.0")
        if not self.match_reason:
            raise ValueError("KGCandidate.match_reason cannot be empty")