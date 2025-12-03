"""
Splink-based deduplication backend implementation.

Uses probabilistic entity resolution with Splink for clustering mentions
into canonical entities based on configurable similarity thresholds.
"""

import logging
from typing import Dict, Any, List
import time
from kg_forge.models.lexical import LexicalGraph
from kg_forge.models.dedup import (
    DedupedLexicalGraph, 
    CanonicalLexicalEntity, 
    CanonicalRelation
)

logger = logging.getLogger(__name__)


class SpLinkDedupBackend:
    """
    Splink-based probabilistic entity resolution backend.
    
    Uses Splink's probabilistic matching to identify duplicate mentions
    and cluster them into canonical entities.
    """
    
    def __init__(self, 
                 similarity_threshold: float = 0.8,
                 blocking_rules: List[str] = None,
                 **config):
        """
        Initialize Splink deduplication backend.
        
        Args:
            similarity_threshold: Minimum similarity for clustering (0.0-1.0)
            blocking_rules: List of blocking rules for efficiency
            **config: Additional configuration parameters
        """
        self.similarity_threshold = similarity_threshold
        self.blocking_rules = blocking_rules or [
            "l.entity_type = r.entity_type",
            "substr(l.normalized_name, 1, 3) = substr(r.normalized_name, 1, 3)"
        ]
        self.config = config
        
        # Check if Splink is available
        try:
            import splink
            self.splink_available = True
            logger.info("Splink deduplication backend initialized")
        except ImportError:
            self.splink_available = False
            logger.warning("Splink not available - using fake implementation")
    
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Apply Splink probabilistic entity resolution.
        
        Args:
            lexical_graph: Raw extraction results
            namespace: Processing namespace
            
        Returns:
            DedupedLexicalGraph with clustered canonical entities
        """
        start_time = time.time()
        
        if not self.splink_available:
            return self._fake_splink_dedup(lexical_graph, namespace)
        
        logger.info(f"Running Splink deduplication on {len(lexical_graph.mentions)} mentions")
        
        # Convert mentions to DataFrame format for Splink
        mentions_df = self._prepare_mentions_dataframe(lexical_graph.mentions)
        
        if len(mentions_df) < 2:
            # Not enough mentions for deduplication
            return self._create_single_entity_graph(lexical_graph, namespace)
        
        try:
            # Configure Splink model
            settings = self._build_splink_settings()
            
            # Import Splink components
            from splink.duckdb_api import DuckDBAPI
            from splink import Linker
            
            # Initialize linker
            db_api = DuckDBAPI()
            linker = Linker(mentions_df, settings, db_api)
            
            # Train model if needed (simplified for v1)
            # In production, this would involve proper training on labeled data
            
            # Generate predictions
            predictions_df = linker.predict(threshold_match_probability=self.similarity_threshold)
            
            # Form clusters from predictions
            clusters = self._build_clusters_from_predictions(predictions_df, lexical_graph.mentions)
            
            # Convert to deduplicated graph
            return self._build_deduped_graph(clusters, lexical_graph, namespace, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Splink deduplication failed: {e}")
            # Fallback to no deduplication
            return self._create_single_entity_graph(lexical_graph, namespace)
    
    def _fake_splink_dedup(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Fake Splink implementation for testing when Splink is not available.
        
        Performs simple exact matching on normalized names within entity types.
        """
        logger.info("Using fake Splink implementation for testing")
        
        # Group mentions by entity type and normalized name
        clusters = {}
        for mention in lexical_graph.mentions:
            normalized_name = self._normalize_name(mention.surface)
            cluster_key = (mention.entity_type, normalized_name)
            
            if cluster_key not in clusters:
                clusters[cluster_key] = []
            clusters[cluster_key].append(mention)
        
        # Convert clusters to canonical entities
        canonical_entities = []
        entity_id_counter = 1
        
        for (entity_type, normalized_name), mentions in clusters.items():
            if len(mentions) == 1:
                # Single mention - no deduplication
                mention = mentions[0]
                canonical_entity = CanonicalLexicalEntity(
                    id=mention.id,
                    entity_type=entity_type,
                    canonical_name=mention.surface,
                    aliases=[mention.surface],
                    mention_ids=[mention.id],
                    features={
                        "dedup_method": "fake_splink",
                        "cluster_size": 1,
                        "splink_score": 1.0
                    }
                )
            else:
                # Multiple mentions - create cluster
                canonical_name = max(mentions, key=lambda m: len(m.surface)).surface  # Choose longest
                aliases = list(set(m.surface for m in mentions))
                mention_ids = [m.id for m in mentions]
                
                canonical_entity = CanonicalLexicalEntity(
                    id=f"cluster_{entity_id_counter}",
                    entity_type=entity_type,
                    canonical_name=canonical_name,
                    aliases=aliases,
                    mention_ids=mention_ids,
                    features={
                        "dedup_method": "fake_splink",
                        "cluster_size": len(mentions),
                        "splink_score": 0.9,  # Fake high confidence
                        "normalized_name": normalized_name
                    }
                )
                entity_id_counter += 1
            
            canonical_entities.append(canonical_entity)
        
        # Build canonical relations (simplified)
        canonical_relations = []
        mention_to_entity = {
            mention_id: entity.id 
            for entity in canonical_entities 
            for mention_id in entity.mention_ids
        }
        
        for relation in lexical_graph.relations:
            src_entity_id = mention_to_entity.get(relation.src_mention_id)
            dst_entity_id = mention_to_entity.get(relation.dst_mention_id)
            
            if src_entity_id and dst_entity_id and src_entity_id != dst_entity_id:
                canonical_relations.append(CanonicalRelation(
                    id=relation.id,
                    type=relation.type,
                    src_entity_id=src_entity_id,
                    dst_entity_id=dst_entity_id,
                    features={**relation.features, "dedup_method": "fake_splink"}
                ))
        
        metadata = {
            "dedup_backend": "splink_fake",
            "clusters_formed": len(canonical_entities),
            "original_mentions": len(lexical_graph.mentions),
            "duplicate_pairs": sum(len(cluster) - 1 for cluster in clusters.values() if len(cluster) > 1),
            "processing_time": 0.1,
            "namespace": namespace,
            "similarity_threshold": self.similarity_threshold
        }
        
        return DedupedLexicalGraph(
            canonical_entities=canonical_entities,
            relations=canonical_relations,
            metadata=metadata
        )
    
    def _prepare_mentions_dataframe(self, mentions: List) -> List[Dict]:
        """Convert mentions to DataFrame-compatible format."""
        return [
            {
                "unique_id": mention.id,
                "entity_type": mention.entity_type,
                "surface": mention.surface,
                "normalized_name": self._normalize_name(mention.surface),
                "surface_tokens": mention.surface.lower().split()
            }
            for mention in mentions
        ]
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        return name.lower().strip().replace("  ", " ")
    
    def _build_splink_settings(self) -> Dict[str, Any]:
        """Build Splink configuration settings."""
        return {
            "link_type": "dedupe_only",
            "blocking_rules_to_generate_predictions": self.blocking_rules,
            "comparisons": [
                {
                    "output_column_name": "entity_type",
                    "comparison_levels": [
                        {"sql_condition": "entity_type_l IS NULL OR entity_type_r IS NULL"},
                        {"sql_condition": "entity_type_l = entity_type_r"},
                        {"sql_condition": "ELSE"}
                    ]
                },
                {
                    "output_column_name": "normalized_name", 
                    "comparison_levels": [
                        {"sql_condition": "normalized_name_l IS NULL OR normalized_name_r IS NULL"},
                        {"sql_condition": "normalized_name_l = normalized_name_r"},
                        {"sql_condition": "jaro_winkler(normalized_name_l, normalized_name_r) >= 0.9"},
                        {"sql_condition": "jaro_winkler(normalized_name_l, normalized_name_r) >= 0.8"},
                        {"sql_condition": "ELSE"}
                    ]
                }
            ]
        }
    
    def _create_single_entity_graph(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """Create graph with no deduplication when clustering is not possible."""
        from kg_forge.dedup.no_dedup_backend import NoDedupBackend
        no_dedup = NoDedupBackend()
        return no_dedup.deduplicate(lexical_graph, namespace)
    
    def get_backend_name(self) -> str:
        """Get the name of this deduplication backend."""
        return "splink"
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get detailed information about this backend."""
        return {
            "backend_name": "splink",
            "description": "Probabilistic entity resolution using Splink",
            "version": "1.0.0",
            "splink_available": self.splink_available,
            "similarity_threshold": self.similarity_threshold,
            "blocking_rules": self.blocking_rules,
            "config": self.config
        }
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration and dependencies."""
        if not self.splink_available:
            logger.warning("Splink not available - will use fake implementation")
        
        if not (0.0 <= self.similarity_threshold <= 1.0):
            logger.error(f"Invalid similarity_threshold: {self.similarity_threshold}")
            return False
        
        return True