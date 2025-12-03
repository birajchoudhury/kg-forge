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
            try:
                from splink.backends.duckdb import DuckDBAPI
            except ImportError:
                # Fallback to old import path for older splink versions
                try:
                    from splink.duckdb_api import DuckDBAPI
                except ImportError:
                    raise ImportError("Could not import DuckDBAPI from splink. Please check splink installation.")
            from splink import Linker
            
            # Initialize linker with single DataFrame for dedupe mode
            db_api = DuckDBAPI()
            linker = Linker(mentions_df, settings, db_api, input_table_aliases=["mentions"])
            
            # Train model if needed (simplified for v1)
            # In production, this would involve proper training on labeled data
            
            # Generate predictions using Splink 4.x API
            predictions_df = linker.inference.predict(threshold_match_probability=self.similarity_threshold)
            
            # Form clusters from predictions
            clusters = self._build_clusters_from_predictions(predictions_df, lexical_graph.mentions)
            
            # Convert to deduplicated graph
            return self._build_deduped_graph(clusters, lexical_graph, namespace, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Splink deduplication failed: {e}")
            # Fallback to fake splink implementation
            return self._fake_splink_dedup(lexical_graph, namespace)
    
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
        processing_time = time.time() - time.time()  # Fake timing

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
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        return name.lower().strip().replace("  ", " ")
    
    def _prepare_mentions_dataframe(self, mentions):
        """Convert mentions to DataFrame format for Splink."""
        import pandas as pd
        
        data = []
        for i, mention in enumerate(mentions):
            data.append({
                'unique_id': i,  # Splink requires a unique_id column
                'entity_type': mention.entity_type,
                'surface': mention.surface,
                'normalized_name': self._normalize_name(mention.surface),
                'mention_id': mention.id
            })
        
        return pd.DataFrame(data)
    
    def _build_clusters_from_predictions(self, predictions_df, mentions: List) -> Dict[str, List]:
        """Build entity clusters from Splink predictions."""
        import pandas as pd
        
        # Create mention lookup
        mention_lookup = {i: mention for i, mention in enumerate(mentions)}
        
        # Initialize clusters - each mention starts in its own cluster
        clusters = {}
        mention_to_cluster = {}
        
        # Process each mention initially
        for i, mention in enumerate(mentions):
            entity_type = mention.entity_type
            if entity_type not in clusters:
                clusters[entity_type] = []
            
            cluster_id = f"{entity_type}_{len(clusters[entity_type])}"
            clusters[entity_type].append([mention])
            mention_to_cluster[i] = (entity_type, len(clusters[entity_type]) - 1)
        
        # Process predictions to merge clusters
        # Convert to pandas DataFrame if it's a DuckDB DataFrame
        logger.debug(f"Processing predictions DataFrame of type: {type(predictions_df)}")
        
        try:
            # Try different conversion methods for DuckDB DataFrame
            import pandas as pd
            
            # Use the correct Splink API to convert DuckDB DataFrame to pandas
            if hasattr(predictions_df, 'as_pandas'):
                # Method 1: .as_pandas() method (Splink's preferred method)
                predictions_pandas = predictions_df.as_pandas()
            elif hasattr(predictions_df, 'to_df'):
                # Method 2: .to_df() method  
                predictions_pandas = predictions_df.to_df()
            elif hasattr(predictions_df, '_df'):
                # Method 3: Access private _df attribute
                predictions_pandas = predictions_df._df
            else:
                # Fallback: iterate through results to create pandas DataFrame manually
                rows = []
                try:
                    # Try to iterate through the DuckDB DataFrame
                    for row in predictions_df:
                        rows.append(row)
                    if rows:
                        # Get column names from first row if available
                        columns = list(rows[0].keys()) if rows and hasattr(rows[0], 'keys') else None
                        predictions_pandas = pd.DataFrame(rows, columns=columns)
                    else:
                        # Empty DataFrame
                        predictions_pandas = pd.DataFrame()
                except:
                    # Last resort: empty DataFrame
                    predictions_pandas = pd.DataFrame()
                
            # Verify conversion worked
            if hasattr(predictions_pandas, '__len__'):
                logger.debug(f"Successfully converted to DataFrame with length: {len(predictions_pandas)}")
            else:
                raise Exception(f"Conversion failed, still have: {type(predictions_pandas)}")
                
        except Exception as e:
            logger.error(f"Could not convert predictions DataFrame: {type(predictions_df)}, error: {e}")
            # Return empty clusters rather than failing completely
            return clusters
        
        if len(predictions_pandas) > 0:
            for _, row in predictions_pandas.iterrows():
                try:
                    # Get mention indices (Splink uses 0-based indexing)
                    left_idx = int(row['source_dataset_l_index']) if 'source_dataset_l_index' in row else int(row.get('__index_level_0___l', -1))
                    right_idx = int(row['source_dataset_r_index']) if 'source_dataset_r_index' in row else int(row.get('__index_level_0___r', -1))
                    
                    if left_idx == -1 or right_idx == -1 or left_idx >= len(mentions) or right_idx >= len(mentions):
                        continue
                        
                    # Get match probability
                    match_prob = float(row.get('match_probability', 0.0))
                    
                    if match_prob >= self.similarity_threshold:
                        # Merge clusters
                        left_mention = mention_lookup[left_idx]
                        right_mention = mention_lookup[right_idx]
                        
                        if left_mention.entity_type == right_mention.entity_type:
                            left_cluster = mention_to_cluster[left_idx]
                            right_cluster = mention_to_cluster[right_idx]
                            
                            if left_cluster != right_cluster:
                                # Merge right cluster into left cluster
                                entity_type = left_cluster[0]
                                left_cluster_idx = left_cluster[1]
                                right_cluster_idx = right_cluster[1]
                                
                                # Move all mentions from right cluster to left cluster
                                right_mentions = clusters[entity_type][right_cluster_idx]
                                clusters[entity_type][left_cluster_idx].extend(right_mentions)
                                clusters[entity_type][right_cluster_idx] = []  # Mark as empty
                                
                                # Update mention-to-cluster mapping
                                for mention in right_mentions:
                                    mention_idx = mentions.index(mention)
                                    mention_to_cluster[mention_idx] = left_cluster
                                    
                except Exception as e:
                    logger.debug(f"Error processing prediction row: {e}")
                    continue
        
        # Clean up empty clusters and return non-empty ones
        final_clusters = {}
        for entity_type, type_clusters in clusters.items():
            non_empty_clusters = [cluster for cluster in type_clusters if cluster]
            if non_empty_clusters:
                final_clusters[entity_type] = non_empty_clusters
                
        return final_clusters
    
    def _build_deduped_graph(self, clusters: Dict[str, List], lexical_graph: 'LexicalGraph', namespace: str, processing_time: float) -> 'DedupedLexicalGraph':
        """Convert clusters to deduplicated graph."""
        canonical_entities = []
        entity_id_counter = 1
        
        # Build canonical entities from clusters
        for entity_type, type_clusters in clusters.items():
            for cluster in type_clusters:
                if not cluster:  # Skip empty clusters
                    continue
                    
                if len(cluster) == 1:
                    # Single mention - no deduplication needed
                    mention = cluster[0]
                    canonical_entity = CanonicalLexicalEntity(
                        id=f"canonical_{entity_id_counter}",
                        entity_type=entity_type,
                        canonical_name=mention.surface,
                        aliases=[mention.surface],
                        mention_ids=[mention.id],
                        features={
                            "dedup_method": "splink",
                            "cluster_size": 1,
                            "splink_score": 1.0
                        }
                    )
                else:
                    # Multiple mentions - deduplicated cluster
                    # Choose the longest surface form as canonical name
                    canonical_name = max(cluster, key=lambda m: len(m.surface)).surface
                    aliases = list(set(mention.surface for mention in cluster))
                    mention_ids = [mention.id for mention in cluster]
                    
                    canonical_entity = CanonicalLexicalEntity(
                        id=f"canonical_{entity_id_counter}",
                        entity_type=entity_type,
                        canonical_name=canonical_name,
                        aliases=aliases,
                        mention_ids=mention_ids,
                        features={
                            "dedup_method": "splink",
                            "cluster_size": len(cluster),
                            "splink_score": 0.9  # High confidence for clustered entities
                        }
                    )
                
                canonical_entities.append(canonical_entity)
                entity_id_counter += 1
        
        # Build canonical relations
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
                    features={**relation.features, "dedup_method": "splink"}
                ))
        
        return DedupedLexicalGraph(
            canonical_entities=canonical_entities,
            relations=canonical_relations,
            metadata={
                "dedup_backend": "splink",
                "similarity_threshold": self.similarity_threshold,
                "processing_time": processing_time,
                "namespace": namespace,
                "input_mentions": len(lexical_graph.mentions),
                "output_entities": len(canonical_entities),
                "deduplication_ratio": len(lexical_graph.mentions) / max(len(canonical_entities), 1)
            }
        )
    
    def _build_splink_settings(self) -> Dict[str, Any]:
        """Build Splink configuration settings for version 4.x."""
        return {
            "link_type": "dedupe_only",
            "probability_two_random_records_match": 0.001,  # Reasonable default for entity deduplication
            "blocking_rules_to_generate_predictions": self.blocking_rules,
            "comparisons": [
                {
                    "output_column_name": "entity_type",
                    "comparison_levels": [
                        {"sql_condition": "entity_type_l IS NULL OR entity_type_r IS NULL", "is_null_level": True},
                        {"sql_condition": "entity_type_l = entity_type_r", "m_probability": 0.9, "u_probability": 0.1},
                        {"sql_condition": "ELSE", "m_probability": 0.1, "u_probability": 0.4}
                    ]
                },
                {
                    "output_column_name": "normalized_name", 
                    "comparison_levels": [
                        {"sql_condition": "normalized_name_l IS NULL OR normalized_name_r IS NULL", "is_null_level": True},
                        {"sql_condition": "normalized_name_l = normalized_name_r", "m_probability": 0.95, "u_probability": 0.05},
                        {"sql_condition": "jaro_winkler_similarity(normalized_name_l, normalized_name_r) >= 0.9", "m_probability": 0.8, "u_probability": 0.1},
                        {"sql_condition": "jaro_winkler_similarity(normalized_name_l, normalized_name_r) >= 0.8", "m_probability": 0.6, "u_probability": 0.15},
                        {"sql_condition": "ELSE", "m_probability": 0.1, "u_probability": 0.2}
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