"""
Ensemble deduplication backend implementation.

Combines Splink and Zingg backends to provide more robust entity resolution
by leveraging both probabilistic and ML-based approaches.
"""

import logging
from typing import Dict, Any
import time
from kg_forge.models.lexical import LexicalGraph
from kg_forge.models.dedup import DedupedLexicalGraph
from kg_forge.dedup.splink_backend import SpLinkDedupBackend
from kg_forge.dedup.zingg_backend import ZinggDedupBackend

logger = logging.getLogger(__name__)


class EnsembleDedupBackend:
    """
    Ensemble deduplication backend combining Splink and Zingg.
    
    Runs both backends and combines their results using a voting mechanism
    or confidence-weighted averaging to produce final clusters.
    """
    
    def __init__(self, 
                 splink_config: Dict[str, Any] = None,
                 zingg_config: Dict[str, Any] = None,
                 combination_strategy: str = "confidence_weighted",
                 **config):
        """
        Initialize ensemble deduplication backend.
        
        Args:
            splink_config: Configuration for Splink backend
            zingg_config: Configuration for Zingg backend
            combination_strategy: How to combine results ("confidence_weighted", "voting", "union")
            **config: Additional configuration parameters
        """
        self.combination_strategy = combination_strategy
        self.config = config
        
        # Initialize constituent backends
        self.splink_backend = SpLinkDedupBackend(**(splink_config or {}))
        self.zingg_backend = ZinggDedupBackend(**(zingg_config or {}))
        
        logger.info(f"Ensemble deduplication backend initialized with strategy: {combination_strategy}")
    
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Apply ensemble entity resolution using both Splink and Zingg.
        
        Args:
            lexical_graph: Raw extraction results
            namespace: Processing namespace
            
        Returns:
            DedupedLexicalGraph with ensemble-clustered canonical entities
        """
        start_time = time.time()
        
        logger.info(f"Running ensemble deduplication on {len(lexical_graph.mentions)} mentions")
        
        try:
            # Run both backends
            logger.debug("Running Splink backend...")
            splink_result = self.splink_backend.deduplicate(lexical_graph, namespace)
            
            logger.debug("Running Zingg backend...")
            zingg_result = self.zingg_backend.deduplicate(lexical_graph, namespace)
            
            # Combine results based on strategy
            if self.combination_strategy == "confidence_weighted":
                combined_result = self._combine_confidence_weighted(splink_result, zingg_result, lexical_graph)
            elif self.combination_strategy == "voting":
                combined_result = self._combine_voting(splink_result, zingg_result, lexical_graph)
            elif self.combination_strategy == "union":
                combined_result = self._combine_union(splink_result, zingg_result, lexical_graph)
            else:
                logger.error(f"Unknown combination strategy: {self.combination_strategy}")
                # Fallback to Splink result
                combined_result = splink_result
            
            # Update metadata
            combined_result.metadata.update({
                "dedup_backend": "ensemble",
                "combination_strategy": self.combination_strategy,
                "ensemble_processing_time": time.time() - start_time,
                "splink_clusters": len(splink_result.canonical_entities),
                "zingg_clusters": len(zingg_result.canonical_entities),
                "final_clusters": len(combined_result.canonical_entities)
            })
            
            logger.info(
                f"Ensemble deduplication completed: {len(combined_result.canonical_entities)} "
                f"canonical entities from {len(lexical_graph.mentions)} mentions"
            )
            
            return combined_result
            
        except Exception as e:
            logger.error(f"Ensemble deduplication failed: {e}")
            # Fallback to single backend
            logger.info("Falling back to Splink backend only")
            return self.splink_backend.deduplicate(lexical_graph, namespace)
    
    def _combine_confidence_weighted(self, splink_result: DedupedLexicalGraph, 
                                   zingg_result: DedupedLexicalGraph,
                                   lexical_graph: LexicalGraph) -> DedupedLexicalGraph:
        """
        Combine results using confidence-weighted approach.
        
        Higher confidence clusters from either backend are preferred.
        """
        logger.debug("Combining results using confidence weighting")
        
        # For simplicity in v1, choose the result with higher average confidence
        splink_avg_confidence = self._compute_average_confidence(splink_result)
        zingg_avg_confidence = self._compute_average_confidence(zingg_result)
        
        if splink_avg_confidence >= zingg_avg_confidence:
            logger.debug(f"Using Splink result (confidence: {splink_avg_confidence:.3f})")
            return splink_result
        else:
            logger.debug(f"Using Zingg result (confidence: {zingg_avg_confidence:.3f})")
            return zingg_result
    
    def _combine_voting(self, splink_result: DedupedLexicalGraph,
                       zingg_result: DedupedLexicalGraph,
                       lexical_graph: LexicalGraph) -> DedupedLexicalGraph:
        """
        Combine results using voting mechanism.
        
        Clusters are formed when both backends agree on grouping.
        """
        logger.debug("Combining results using voting mechanism")
        
        # For v1 implementation, use the result with fewer clusters (more aggressive clustering)
        # This assumes that agreement between methods indicates higher confidence
        if len(splink_result.canonical_entities) <= len(zingg_result.canonical_entities):
            logger.debug("Using Splink result (more aggressive clustering)")
            return splink_result
        else:
            logger.debug("Using Zingg result (more aggressive clustering)")
            return zingg_result
    
    def _combine_union(self, splink_result: DedupedLexicalGraph,
                      zingg_result: DedupedLexicalGraph,
                      lexical_graph: LexicalGraph) -> DedupedLexicalGraph:
        """
        Combine results using union approach.
        
        Take the union of clusters from both backends (conservative approach).
        """
        logger.debug("Combining results using union approach")
        
        # For v1, use the result with more clusters (less aggressive clustering)
        # This is more conservative and avoids false positive merges
        if len(splink_result.canonical_entities) >= len(zingg_result.canonical_entities):
            logger.debug("Using Splink result (more conservative clustering)")
            return splink_result
        else:
            logger.debug("Using Zingg result (more conservative clustering)")
            return zingg_result
    
    def _compute_average_confidence(self, result: DedupedLexicalGraph) -> float:
        """Compute average confidence score for a dedup result."""
        if not result.canonical_entities:
            return 0.0
        
        total_confidence = 0.0
        count = 0
        
        for entity in result.canonical_entities:
            # Extract confidence from features if available
            confidence = entity.features.get("splink_score", entity.features.get("zingg_confidence", 1.0))
            total_confidence += confidence
            count += 1
        
        return total_confidence / count if count > 0 else 0.0
    
    def get_backend_name(self) -> str:
        """Get the name of this deduplication backend."""
        return "ensemble"
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get detailed information about this backend."""
        return {
            "backend_name": "ensemble",
            "description": "Ensemble deduplication combining Splink and Zingg",
            "version": "1.0.0",
            "combination_strategy": self.combination_strategy,
            "splink_info": self.splink_backend.get_backend_info(),
            "zingg_info": self.zingg_backend.get_backend_info(),
            "config": self.config
        }
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration and dependencies."""
        splink_valid = self.splink_backend.validate_configuration()
        zingg_valid = self.zingg_backend.validate_configuration()
        
        if not splink_valid:
            logger.warning("Splink backend configuration invalid")
        if not zingg_valid:
            logger.warning("Zingg backend configuration invalid")
        
        # At least one backend should be valid
        is_valid = splink_valid or zingg_valid
        
        if not is_valid:
            logger.error("Both Splink and Zingg backends are invalid")
        
        return is_valid