"""
No-deduplication backend implementation.

Pass-through implementation that converts LexicalGraph to DedupedLexicalGraph
without any actual deduplication. Each mention becomes its own canonical entity.
"""

import logging
from typing import Dict, Any
from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.models.dedup import (
    DedupedLexicalGraph, 
    CanonicalLexicalEntity, 
    CanonicalRelation
)

logger = logging.getLogger(__name__)


class NoDedupBackend:
    """
    No-deduplication backend that treats each mention as a separate entity.
    
    Useful for scenarios where deduplication is not desired or as a baseline
    for comparing against actual deduplication backends.
    """
    
    def __init__(self, **config):
        """
        Initialize no-dedup backend.
        
        Args:
            **config: Configuration parameters (ignored for this backend)
        """
        self.config = config
    
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Convert LexicalGraph to DedupedLexicalGraph without deduplication.
        
        Each mention becomes its own canonical entity with identical ID.
        Relations are converted directly with mention IDs as entity IDs.
        
        Args:
            lexical_graph: Raw extraction results
            namespace: Processing namespace (used for logging)
            
        Returns:
            DedupedLexicalGraph with one canonical entity per mention
        """
        logger.debug(f"Running no-dedup backend on {len(lexical_graph.mentions)} mentions")
        
        # Convert each mention to canonical entity
        canonical_entities = []
        for mention in lexical_graph.mentions:
            canonical_entity = CanonicalLexicalEntity(
                id=mention.id,  # Use same ID as mention
                entity_type=mention.entity_type,
                canonical_name=mention.surface,
                aliases=[mention.surface],  # Only surface form is alias
                mention_ids=[mention.id],   # Single mention in cluster
                features={
                    "dedup_method": "none",
                    "original_mention_id": mention.id,
                    "confidence": mention.features.get("confidence", 1.0)
                }
            )
            canonical_entities.append(canonical_entity)
        
        # Convert relations to canonical format
        canonical_relations = []
        for relation in lexical_graph.relations:
            # Verify both mentions exist in the graph
            src_mention = lexical_graph.get_mention_by_id(relation.src_mention_id)
            dst_mention = lexical_graph.get_mention_by_id(relation.dst_mention_id)
            
            if src_mention and dst_mention:
                canonical_relation = CanonicalRelation(
                    id=relation.id,
                    type=relation.type,
                    src_entity_id=relation.src_mention_id,  # Same as mention ID
                    dst_entity_id=relation.dst_mention_id,  # Same as mention ID
                    features={
                        **relation.features,
                        "dedup_method": "none",
                        "source_relations": [relation.id]
                    }
                )
                canonical_relations.append(canonical_relation)
            else:
                logger.warning(
                    f"Skipping relation {relation.id}: referenced mention not found "
                    f"(src: {relation.src_mention_id}, dst: {relation.dst_mention_id})"
                )
        
        # Build metadata
        metadata = {
            "dedup_backend": "none",
            "clusters_formed": len(canonical_entities),
            "original_mentions": len(lexical_graph.mentions),
            "duplicate_pairs": 0,  # No deduplication performed
            "processing_time": 0.0,  # Minimal processing time
            "namespace": namespace
        }
        
        deduplicated_graph = DedupedLexicalGraph(
            canonical_entities=canonical_entities,
            relations=canonical_relations,
            metadata=metadata
        )
        
        logger.info(
            f"No-dedup completed: {len(canonical_entities)} canonical entities, "
            f"{len(canonical_relations)} relations"
        )
        
        return deduplicated_graph
    
    def get_backend_name(self) -> str:
        """Get the name of this deduplication backend."""
        return "none"
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get detailed information about this backend."""
        return {
            "backend_name": "none",
            "description": "Pass-through deduplication that treats each mention as separate entity",
            "version": "1.0.0",
            "capabilities": ["fast_processing", "deterministic"],
            "dependencies": "none",
            "config": self.config
        }
    
    def validate_configuration(self) -> bool:
        """
        Validate backend configuration and dependencies.
        
        Always returns True since no-dedup has no dependencies.
        """
        return True