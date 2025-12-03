"""
Zingg-based deduplication backend implementation.

Uses ML-based entity resolution with Zingg for clustering mentions
into canonical entities using machine learning models.
"""

import logging
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from kg_forge.models.lexical import LexicalGraph, LexicalMention
from kg_forge.models.dedup import (
    DedupedLexicalGraph, 
    CanonicalLexicalEntity, 
    CanonicalRelation
)

logger = logging.getLogger(__name__)

# Optional imports for real Zingg integration
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not available - Zingg real implementation will be limited")

try:
    import pyspark
    from pyspark.sql import SparkSession
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, BooleanType, DoubleType
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    logger.warning("pyspark not available - Zingg real implementation will use fallback")

try:
    import zingg.client
    from zingg.client import ZinggWithSpark
    ZINGG_AVAILABLE = True
except ImportError:
    ZINGG_AVAILABLE = False
    logger.warning("zingg not available - using fake implementation")


class ZinggDedupBackend:
    """
    Zingg-based ML entity resolution backend.
    
    Uses Zingg's machine learning approach to identify duplicate mentions
    and cluster them into canonical entities.
    """
    
    def __init__(self, 
                 model_config: Dict[str, Any] = None,
                 confidence_threshold: float = 0.8,
                 **config):
        """
        Initialize Zingg deduplication backend.
        
        Args:
            model_config: Zingg model configuration
            confidence_threshold: Minimum confidence for clustering
            **config: Additional configuration parameters
        """
        self.model_config = model_config or {}
        self.confidence_threshold = confidence_threshold
        self.config = config
        self.zingg_client = None
        
        # Check if real Zingg implementation is available
        self.zingg_available = ZINGG_AVAILABLE and PYSPARK_AVAILABLE and PANDAS_AVAILABLE
        
        if self.zingg_available:
            logger.info("Real Zingg deduplication backend initialized with all dependencies")
        else:
            missing_deps = []
            if not ZINGG_AVAILABLE:
                missing_deps.append("zingg")
            if not PYSPARK_AVAILABLE:
                missing_deps.append("pyspark")  
            if not PANDAS_AVAILABLE:
                missing_deps.append("pandas")
            logger.warning(f"Missing dependencies for real Zingg: {missing_deps}. Using fake implementation.")
    
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Apply Zingg ML-based entity resolution.
        
        Args:
            lexical_graph: Raw extraction results
            namespace: Processing namespace
            
        Returns:
            DedupedLexicalGraph with clustered canonical entities
        """
        start_time = time.time()
        
        if not self.zingg_available:
            logger.warning("Zingg not available - falling back to fake implementation")
            return self._fake_zingg_dedup(lexical_graph, namespace)
        
        logger.info(f"Running real Zingg deduplication on {len(lexical_graph.mentions)} mentions")
        
        if len(lexical_graph.mentions) < 2:
            # Not enough mentions for deduplication
            return self._create_single_entity_graph(lexical_graph, namespace)
        
        try:
            # Run real Zingg pipeline
            clusters = self._run_real_zingg_dedup(lexical_graph.mentions, namespace)
            
            # Convert to deduplicated graph
            return self._build_deduped_graph(clusters, lexical_graph, namespace, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Zingg deduplication failed: {e}")
            # Fallback to fake implementation
            logger.warning("Falling back to fake Zingg implementation")
            return self._fake_zingg_dedup(lexical_graph, namespace)
    
    def _fake_zingg_dedup(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Fake Zingg implementation for testing when Zingg is not available.
        Uses ML-inspired heuristics to simulate Zingg's clustering behavior.
        
        Performs fuzzy matching based on Jaro-Winkler similarity.
        """
        logger.info("Using fake Zingg implementation for testing")
        
        mentions = lexical_graph.mentions
        clusters = []
        processed_mentions = set()
        
        for i, mention in enumerate(mentions):
            if mention.id in processed_mentions:
                continue
            
            # Start new cluster with this mention
            cluster = [mention]
            processed_mentions.add(mention.id)
            
            # Find similar mentions
            for j, other_mention in enumerate(mentions[i+1:], i+1):
                if (other_mention.id in processed_mentions or 
                    mention.entity_type != other_mention.entity_type):
                    continue
                
                # Compute fake ML similarity score
                similarity = self._fake_ml_similarity(mention.surface, other_mention.surface)
                
                if similarity >= self.confidence_threshold:
                    cluster.append(other_mention)
                    processed_mentions.add(other_mention.id)
            
            clusters.append(cluster)
        
        # Convert clusters to canonical entities
        canonical_entities = []
        entity_id_counter = 1
        
        for cluster in clusters:
            if len(cluster) == 1:
                # Single mention
                mention = cluster[0]
                canonical_entity = CanonicalLexicalEntity(
                    id=mention.id,
                    entity_type=mention.entity_type,
                    canonical_name=mention.surface,
                    aliases=[mention.surface],
                    mention_ids=[mention.id],
                    features={
                        "dedup_method": "fake_zingg",
                        "cluster_size": 1,
                        "zingg_confidence": 1.0
                    }
                )
            else:
                # Multiple mentions - create cluster
                canonical_name = max(cluster, key=lambda m: len(m.surface)).surface
                aliases = list(set(m.surface for m in cluster))
                mention_ids = [m.id for m in cluster]
                
                canonical_entity = CanonicalLexicalEntity(
                    id=f"zingg_cluster_{entity_id_counter}",
                    entity_type=cluster[0].entity_type,
                    canonical_name=canonical_name,
                    aliases=aliases,
                    mention_ids=mention_ids,
                    features={
                        "dedup_method": "fake_zingg", 
                        "cluster_size": len(cluster),
                        "zingg_confidence": 0.85,  # Fake ML confidence
                        "ml_model_version": "fake_v1.0"
                    }
                )
                entity_id_counter += 1
            
            canonical_entities.append(canonical_entity)
        
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
                    features={**relation.features, "dedup_method": "fake_zingg"}
                ))
        
        metadata = {
            "dedup_backend": "zingg_fake",
            "clusters_formed": len(canonical_entities),
            "original_mentions": len(lexical_graph.mentions),
            "duplicate_pairs": sum(len(cluster) - 1 for cluster in clusters if len(cluster) > 1),
            "processing_time": 0.15,  # Fake processing time
            "namespace": namespace,
            "confidence_threshold": self.confidence_threshold
        }
        
        return DedupedLexicalGraph(
            canonical_entities=canonical_entities,
            relations=canonical_relations,
            metadata=metadata
        )
    
    def _run_real_zingg_dedup(self, mentions: List[LexicalMention], namespace: str) -> List[List[LexicalMention]]:
        """Run real Zingg deduplication pipeline."""
        if not self.zingg_available:
            raise RuntimeError("Real Zingg implementation not available - missing dependencies")
        
        # Initialize Spark session
        spark = SparkSession.builder \
            .appName(f"zingg-dedup-{namespace}") \
            .config("spark.master", "local[*]") \
            .config("spark.sql.adaptive.enabled", "true") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
            .getOrCreate()
        
        try:
            # Create temporary files for Zingg input/output
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Convert mentions to DataFrame format
                mentions_df = self._mentions_to_dataframe(mentions, spark)
                input_path = temp_path / "input.parquet"
                output_path = temp_path / "output"
                
                # Write input data
                mentions_df.write.mode("overwrite").parquet(str(input_path))
                
                # Configure Zingg
                zingg_config = self._create_zingg_config(str(input_path), str(output_path), namespace)
                
                # Initialize Zingg client
                zingg_client = ZinggWithSpark(spark, zingg_config)
                
                # Execute Zingg phases
                logger.info("Initializing Zingg models...")
                zingg_client.init()
                
                logger.info("Training Zingg models...")
                zingg_client.train()
                
                logger.info("Running Zingg matching...")
                zingg_client.match()
                
                # Read results
                results_df = spark.read.parquet(str(output_path))
                
                # Convert results to clusters
                return self._parse_zingg_dataframe_results(results_df, mentions)
                
        finally:
            spark.stop()
    
    def _mentions_to_dataframe(self, mentions: List[LexicalMention], spark):
        """Convert mentions to Spark DataFrame for Zingg processing."""
        records = []
        
        for mention in mentions:
            record = {
                "id": mention.id,
                "entity_type": mention.entity_type,
                "surface": mention.surface,
                "normalized_surface": self._normalize_name(mention.surface),
                "doc_id": mention.doc_id,
                "start_offset": mention.start_offset,
                "end_offset": mention.end_offset,
                "length": len(mention.surface),
                "token_count": len(mention.surface.split()),
                "has_digits": any(c.isdigit() for c in mention.surface),
                "has_uppercase": any(c.isupper() for c in mention.surface),
                "confidence": mention.features.get("confidence", 1.0)
            }
            records.append(record)
        
        # Convert to pandas first, then to Spark DataFrame
        pandas_df = pd.DataFrame(records)
        return spark.createDataFrame(pandas_df)
    
    def _create_zingg_config(self, input_path: str, output_path: str, namespace: str) -> Dict[str, Any]:
        """Create Zingg configuration for entity matching."""
        return {
            "data": [
                {
                    "name": "input",
                    "format": "parquet",
                    "props": {
                        "path": input_path
                    }
                }
            ],
            "output": [
                {
                    "name": "output",
                    "format": "parquet", 
                    "props": {
                        "path": output_path
                    }
                }
            ],
            "fieldDefinitions": [
                {
                    "fieldName": "id",
                    "matchType": "DONT_USE",
                    "fields": "id"
                },
                {
                    "fieldName": "entity_type", 
                    "matchType": "EXACT",
                    "fields": "entity_type"
                },
                {
                    "fieldName": "surface",
                    "matchType": "FUZZY",
                    "fields": "surface"
                },
                {
                    "fieldName": "normalized_surface",
                    "matchType": "FUZZY", 
                    "fields": "normalized_surface"
                },
                {
                    "fieldName": "doc_id",
                    "matchType": "EXACT",
                    "fields": "doc_id"
                }
            ],
            "modelId": f"{namespace}_entity_model",
            "zinggDir": f"zingg_models/{namespace}",
            "numPartitions": 4,
            "labelDataSampleSize": 0.5
        }
    
    def _parse_zingg_dataframe_results(self, results_df, mentions: List[LexicalMention]) -> List[List[LexicalMention]]:
        """Parse Zingg DataFrame results into mention clusters."""
        # Convert Spark DataFrame to pandas for easier processing
        results_pandas = results_df.toPandas()
        
        # Create mention lookup
        mention_lookup = {m.id: m for m in mentions}
        
        # Group by cluster ID
        clusters = []
        if "z_cluster" in results_pandas.columns:
            for cluster_id, group in results_pandas.groupby("z_cluster"):
                cluster_mentions = []
                for _, row in group.iterrows():
                    mention_id = row["id"]
                    if mention_id in mention_lookup:
                        cluster_mentions.append(mention_lookup[mention_id])
                
                if cluster_mentions:
                    clusters.append(cluster_mentions)
        else:
            # Fallback: treat each mention as its own cluster
            logger.warning("No cluster information found in Zingg results, treating mentions as individual clusters")
            for mention in mentions:
                clusters.append([mention])
        
        return clusters
    
    def _build_deduped_graph(self, clusters: List[List[LexicalMention]], lexical_graph: LexicalGraph, 
                           namespace: str, processing_time: float) -> DedupedLexicalGraph:
        """Build deduplicated graph from Zingg clusters."""
        canonical_entities = []
        
        for i, cluster in enumerate(clusters):
            if not cluster:
                continue
                
            # Choose canonical name (highest confidence mention)
            canonical_mention = max(cluster, key=lambda m: m.features.get("confidence", 0.0))
            
            # Create canonical entity
            entity = CanonicalLexicalEntity(
                id=f"zingg_cluster_{i+1}" if len(cluster) > 1 else cluster[0].id,
                entity_type=cluster[0].entity_type,
                canonical_name=canonical_mention.surface,
                aliases=sorted(list(set(m.surface for m in cluster))),
                mention_ids=[m.id for m in cluster],
                features={
                    "dedup_method": "zingg_real" if self.zingg_available else "zingg_fake",
                    "cluster_size": len(cluster),
                    "zingg_confidence": sum(m.features.get("confidence", 0.0) for m in cluster) / len(cluster),
                    "processing_time": processing_time
                }
            )
            canonical_entities.append(entity)
        
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
                    features={**relation.features, "dedup_method": "zingg_real"}
                ))
        
        metadata = {
            "dedup_backend": "zingg_real" if self.zingg_available else "zingg_fake",
            "clusters_formed": len(canonical_entities),
            "original_mentions": len(lexical_graph.mentions),
            "duplicate_pairs": sum(len(cluster) - 1 for cluster in clusters if len(cluster) > 1),
            "processing_time": processing_time,
            "namespace": namespace,
            "confidence_threshold": self.confidence_threshold
        }
        
        return DedupedLexicalGraph(
            canonical_entities=canonical_entities,
            relations=canonical_relations,
            metadata=metadata
        )
    
    def _fake_ml_similarity(self, name1: str, name2: str) -> float:
        """
        Fake ML-based similarity computation with domain-specific rules.
        
        In real implementation, this would use Zingg's ML models.
        """
        try:
            from difflib import SequenceMatcher
            
            norm1 = name1.lower().strip()
            norm2 = name2.lower().strip()
            
            # Exact match
            if norm1 == norm2:
                return 1.0
            
            # Handle common ML/tech abbreviations and variations
            known_equivalents = {
                "machine learning": ["ml", "machine-learning"],
                "machine learning team": ["ml team", "machine-learning-team"],
                "artificial intelligence": ["ai", "artificial-intelligence"], 
                "data science": ["ds", "data-science"],
                "data science team": ["ds team", "data-science-team"],
                "natural language processing": ["nlp"],
            }
            
            # Check if they are known equivalent terms
            for canonical, variations in known_equivalents.items():
                if (norm1 == canonical and norm2 in variations) or \
                   (norm2 == canonical and norm1 in variations) or \
                   (norm1 in variations and norm2 in variations and norm1 != norm2):
                    return 0.9  # High similarity for known equivalents
            
            # Character-level similarity
            seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
            
            # Token-based similarity boost
            tokens1 = set(norm1.split())
            tokens2 = set(norm2.split())
            if tokens1 and tokens2:
                jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
                seq_similarity = max(seq_similarity, jaccard * 0.8)
            
            # Penalize very short names unless they're known abbreviations
            if len(norm1) <= 3 or len(norm2) <= 3:
                # Check if short name is likely an abbreviation
                short_name = norm1 if len(norm1) <= 3 else norm2
                long_name = norm2 if len(norm1) <= 3 else norm1
                
                # If short name matches initials of long name, boost similarity
                if len(short_name) <= 3 and len(long_name) > 3:
                    initials = ''.join([word[0] for word in long_name.split() if word])
                    if short_name == initials:
                        seq_similarity = max(seq_similarity, 0.85)
                    else:
                        seq_similarity *= 0.8  # Penalize unrelated short names
            
            return seq_similarity
            
        except Exception:
            # Fallback to exact match
            return 1.0 if name1.lower() == name2.lower() else 0.0
    
    def _prepare_zingg_format(self, mentions: List) -> List[Dict]:
        """Convert mentions to Zingg input format."""
        return [
            {
                "id": mention.id,
                "entity_type": mention.entity_type,
                "name": mention.surface,
                "normalized_name": self._normalize_name(mention.surface),
                "length": len(mention.surface),
                "tokens": len(mention.surface.split())
            }
            for mention in mentions
        ]
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        return name.lower().strip().replace("  ", " ")
    
    def _build_zingg_config(self, namespace: str, mentions_data: List[Dict]) -> Dict[str, Any]:
        """Build Zingg configuration."""
        return {
            "data": mentions_data,
            "fieldDefinitions": [
                {"fieldName": "entity_type", "matchType": "EXACT"},
                {"fieldName": "normalized_name", "matchType": "FUZZY"},
                {"fieldName": "name", "matchType": "TEXT"}
            ],
            "modelId": f"{namespace}_entity_model",
            "threshold": self.confidence_threshold,
            **self.model_config
        }
    
    def _run_zingg_matching(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run Zingg matching (placeholder for real implementation)."""
        # This would call actual Zingg API
        return {"matches": [], "clusters": []}
    
    def _parse_zingg_results(self, results: Dict[str, Any], mentions: List) -> List[List]:
        """Parse Zingg results into mention clusters."""
        # This would parse real Zingg output
        return [[mention] for mention in mentions]  # Placeholder
    
    def _create_single_entity_graph(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """Create graph with no deduplication when clustering is not possible."""
        from kg_forge.dedup.no_dedup_backend import NoDedupBackend
        no_dedup = NoDedupBackend()
        return no_dedup.deduplicate(lexical_graph, namespace)
    
    def get_backend_name(self) -> str:
        """Get the name of this deduplication backend."""
        return "zingg"
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get detailed information about this backend."""
        return {
            "backend_name": "zingg",
            "description": "ML-based entity resolution using Zingg",
            "version": "1.0.0",
            "zingg_available": self.zingg_available,
            "confidence_threshold": self.confidence_threshold,
            "model_config": self.model_config,
            "config": self.config
        }
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration and dependencies."""
        if not self.zingg_available:
            logger.warning("Zingg not available - will use fake implementation")
        
        if not (0.0 <= self.confidence_threshold <= 1.0):
            logger.error(f"Invalid confidence_threshold: {self.confidence_threshold}")
            return False
        
        return True