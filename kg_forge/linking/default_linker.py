"""
Default entity linking backend implementation.

Provides a baseline entity linking approach using Neo4j KG queries
to find matching entities based on names and types, with fallback
to creating new entities when no matches are found.
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
import hashlib
from kg_forge.models.dedup import CanonicalLexicalEntity, LinkResult, KGEntity, KGCandidate
from kg_forge.graph.exceptions import GraphDatabaseError


logger = logging.getLogger(__name__)


class DefaultEntityLinker:
    """
    Default entity linking backend using Neo4j KG queries.
    
    Maps canonical entities to existing KG entities using:
    - Exact name matching within same type/namespace
    - Fuzzy name similarity for near matches
    - Type compatibility checking
    - Confidence scoring for ranking candidates
    """
    
    def __init__(self, neo4j_client, similarity_threshold: float = 0.8, 
                 max_candidates: int = 5, create_missing: bool = True):
        """
        Initialize default entity linker.
        
        Args:
            neo4j_client: Neo4j client for KG access
            similarity_threshold: Minimum similarity for candidate matching (0.0-1.0)
            max_candidates: Maximum number of candidates to consider per entity
            create_missing: Whether to mark unmatched entities for creation
        """
        self.neo4j_client = neo4j_client
        self.similarity_threshold = similarity_threshold
        self.max_candidates = max_candidates
        self.create_missing = create_missing
        
        if not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        if max_candidates < 1:
            raise ValueError("max_candidates must be at least 1")
    
    def link_entities(self, canonical_entities: List[CanonicalLexicalEntity], 
                     namespace: str) -> List[LinkResult]:
        """
        Link canonical entities to existing KG entities.
        
        Args:
            canonical_entities: Deduplicated entities to link
            namespace: Current processing namespace
            
        Returns:
            List of LinkResult objects with linking decisions
        """
        if not canonical_entities:
            return []
        
        logger.info(f"Linking {len(canonical_entities)} canonical entities in namespace '{namespace}'")
        
        results = []
        
        for canonical_entity in canonical_entities:
            try:
                # Find candidate KG entities
                candidates = self._find_candidates(canonical_entity, namespace)
                
                # Score and rank candidates
                scored_candidates = self._score_candidates(canonical_entity, candidates, namespace)
                
                # Make linking decision
                link_result = self._make_linking_decision(canonical_entity, scored_candidates)
                results.append(link_result)
                
            except Exception as e:
                logger.error(f"Error linking entity {canonical_entity.id}: {e}")
                # Create fallback result
                fallback_result = LinkResult(
                    canonical_entity=canonical_entity,
                    linked_entity=None,
                    confidence=0.0,
                    candidates=[],
                    action="create_new" if self.create_missing else "skip",
                    metadata={"error": str(e), "backend": "default"}
                )
                results.append(fallback_result)
        
        logger.info(f"Completed entity linking: {len(results)} results generated")
        return results
    
    def _find_candidates(self, canonical_entity: CanonicalLexicalEntity, 
                        namespace: str) -> List[KGCandidate]:
        """
        Find candidate KG entities for linking.
        
        Args:
            canonical_entity: Entity to find candidates for
            namespace: Processing namespace
            
        Returns:
            List of KG candidate entities
        """
        candidates = []
        
        try:
            # Query 1: Exact name match within same type and namespace
            exact_matches = self._query_exact_matches(canonical_entity, namespace)
            candidates.extend(exact_matches)
            
            # Query 2: Fuzzy name matches if no exact matches found
            if not exact_matches:
                fuzzy_matches = self._query_fuzzy_matches(canonical_entity, namespace)
                candidates.extend(fuzzy_matches)
            
            # Query 3: Type-compatible entities with similar names
            if len(candidates) < self.max_candidates:
                type_matches = self._query_type_compatible(canonical_entity, namespace)
                candidates.extend(type_matches)
            
            # Deduplicate and limit candidates
            unique_candidates = self._deduplicate_candidates(candidates)
            return unique_candidates[:self.max_candidates]
            
        except GraphDatabaseError as e:
            logger.error(f"Neo4j error finding candidates for {canonical_entity.canonical_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error finding candidates: {e}")
            return []
    
    def _query_exact_matches(self, canonical_entity: CanonicalLexicalEntity, 
                            namespace: str) -> List[KGCandidate]:
        """Query for exact name matches within same type and namespace."""
        query = """
        MATCH (e:Entity)
        WHERE e.name = $name 
        AND e.entity_type = $entity_type 
        AND e.namespace = $namespace
        RETURN e.kg_id as kg_id, e.name as name, e.entity_type as entity_type,
               e.namespace as namespace
        """
        
        try:
            results = self.neo4j_client.execute_query(
                query,
                parameters={
                    "name": canonical_entity.canonical_name,
                    "entity_type": canonical_entity.entity_type,
                    "namespace": namespace
                }
            )
            
            candidates = []
            for record in results:
                candidate = KGCandidate(
                    kg_id=record["kg_id"],
                    name=record["name"],
                    entity_type=record["entity_type"],
                    namespace=record["namespace"],
                    score=1.0,  # Exact match
                    match_reason="exact_name_match"
                )
                candidates.append(candidate)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in exact match query: {e}")
            return []
    
    def _query_fuzzy_matches(self, canonical_entity: CanonicalLexicalEntity,
                            namespace: str) -> List[KGCandidate]:
        """Query for fuzzy name matches using text similarity."""
        # Use Neo4j's fulltext search or similarity functions if available
        query = """
        MATCH (e:Entity)
        WHERE e.entity_type = $entity_type 
        AND e.namespace = $namespace
        AND e.name <> $name
        RETURN e.kg_id as kg_id, e.name as name, e.entity_type as entity_type,
               e.namespace as namespace
        LIMIT 20
        """
        
        try:
            results = self.neo4j_client.execute_query(
                query,
                parameters={
                    "entity_type": canonical_entity.entity_type,
                    "namespace": namespace,
                    "name": canonical_entity.canonical_name
                }
            )
            
            candidates = []
            for record in results:
                # Calculate similarity score
                similarity = self._calculate_name_similarity(
                    canonical_entity.canonical_name,
                    record["name"]
                )
                
                if similarity >= self.similarity_threshold:
                    candidate = KGCandidate(
                        kg_id=record["kg_id"],
                        name=record["name"],
                        entity_type=record["entity_type"],
                        namespace=record["namespace"],
                        score=similarity,
                        match_reason="type_similarity_match"
                    )
                    candidates.append(candidate)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in fuzzy match query: {e}")
            return []
    
    def _query_type_compatible(self, canonical_entity: CanonicalLexicalEntity,
                              namespace: str) -> List[KGCandidate]:
        """Query for type-compatible entities with similar names."""
        # Define type compatibility rules (can be extended)
        compatible_types = self._get_compatible_types(canonical_entity.entity_type)
        
        if not compatible_types:
            return []
        
        query = """
        MATCH (e:Entity)
        WHERE e.entity_type IN $compatible_types
        AND e.namespace = $namespace
        AND e.name <> $name
        RETURN e.kg_id as kg_id, e.name as name, e.entity_type as entity_type,
               e.namespace as namespace
        LIMIT 10
        """
        
        try:
            results = self.neo4j_client.execute_query(
                query,
                parameters={
                    "compatible_types": compatible_types,
                    "namespace": namespace,
                    "name": canonical_entity.canonical_name
                }
            )
            
            candidates = []
            for record in results:
                similarity = self._calculate_name_similarity(
                    canonical_entity.canonical_name,
                    record["name"]
                )
                
                if similarity >= self.similarity_threshold:
                    candidate = KGCandidate(
                        kg_id=record["kg_id"],
                        name=record["name"],
                        entity_type=record["entity_type"],
                        namespace=record["namespace"],
                        score=similarity,
                        match_reason="type_compatible_match"
                    )
                    candidates.append(candidate)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in type compatible query: {e}")
            return []
    
    def _get_compatible_types(self, entity_type: str) -> List[str]:
        """Get list of entity types compatible with the given type."""
        # Basic type compatibility rules - can be made configurable
        compatibility_map = {
            "Person": ["Person", "Author", "Contributor"],
            "Organization": ["Organization", "Company", "Institution"],
            "Technology": ["Technology", "Tool", "Framework", "Library"],
            "Concept": ["Concept", "Topic", "Domain"],
            "Document": ["Document", "Article", "Page"],
        }
        
        return compatibility_map.get(entity_type, [entity_type])
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two entity names.
        
        Uses a simple character-based similarity for now.
        Can be enhanced with more sophisticated NLP methods.
        """
        if not name1 or not name2:
            return 0.0
        
        # Normalize names
        norm1 = name1.lower().strip()
        norm2 = name2.lower().strip()
        
        if norm1 == norm2:
            return 1.0
        
        # Simple Jaccard similarity on character n-grams
        ngrams1 = set(self._get_character_ngrams(norm1, n=3))
        ngrams2 = set(self._get_character_ngrams(norm2, n=3))
        
        if not ngrams1 and not ngrams2:
            return 1.0
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1.intersection(ngrams2))
        union = len(ngrams1.union(ngrams2))
        
        return intersection / union if union > 0 else 0.0
    
    def _get_character_ngrams(self, text: str, n: int = 3) -> List[str]:
        """Generate character n-grams from text."""
        if len(text) < n:
            return [text]
        return [text[i:i+n] for i in range(len(text) - n + 1)]
    
    def _deduplicate_candidates(self, candidates: List[KGCandidate]) -> List[KGCandidate]:
        """Remove duplicate candidates based on kg_id."""
        seen_ids = set()
        unique_candidates = []
        
        for candidate in candidates:
            if candidate.kg_id not in seen_ids:
                unique_candidates.append(candidate)
                seen_ids.add(candidate.kg_id)
        
        return unique_candidates
    
    def _score_candidates(self, canonical_entity: CanonicalLexicalEntity,
                         candidates: List[KGCandidate], namespace: str) -> List[Tuple[KGCandidate, float]]:
        """
        Score and rank candidates for the canonical entity.
        
        Returns:
            List of (candidate, confidence_score) tuples, sorted by score descending
        """
        scored_candidates = []
        
        for candidate in candidates:
            confidence = self._calculate_confidence(canonical_entity, candidate, namespace)
            scored_candidates.append((candidate, confidence))
        
        # Sort by confidence descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        return scored_candidates
    
    def _calculate_confidence(self, canonical_entity: CanonicalLexicalEntity,
                             candidate: KGCandidate, namespace: str) -> float:
        """
        Calculate confidence score for a candidate match.
        
        Combines multiple factors:
        - Name similarity
        - Type exactness
        - Namespace match
        - Entity mention frequency
        """
        confidence = 0.0
        
        # Name similarity (40% weight)
        name_sim = candidate.score
        confidence += 0.4 * name_sim
        
        # Type exactness (30% weight)
        type_score = 1.0 if canonical_entity.entity_type == candidate.entity_type else 0.5
        confidence += 0.3 * type_score
        
        # Namespace match (20% weight)
        namespace_score = 1.0 if namespace == candidate.namespace else 0.8
        confidence += 0.2 * namespace_score
        
        # Mention frequency boost (10% weight)
        mention_boost = min(1.0, len(canonical_entity.mention_ids) / 10.0)
        confidence += 0.1 * mention_boost
        
        return min(1.0, confidence)
    
    def _make_linking_decision(self, canonical_entity: CanonicalLexicalEntity,
                              scored_candidates: List[Tuple[KGCandidate, float]]) -> LinkResult:
        """
        Make final linking decision based on scored candidates.
        
        Args:
            canonical_entity: Entity to link
            scored_candidates: List of (candidate, confidence) tuples
            
        Returns:
            LinkResult with linking decision
        """
        if not scored_candidates:
            # No candidates found
            action = "create_new" if self.create_missing else "skip"
            return LinkResult(
                canonical_entity=canonical_entity,
                linked_entity=None,
                confidence=0.0,
                candidates=[],
                action=action,
                metadata={"reason": "no_candidates", "backend": "default"}
            )
        
        best_candidate, best_confidence = scored_candidates[0]
        
        if best_confidence >= self.similarity_threshold:
            # Link to best candidate
            linked_entity = KGEntity(
                id=best_candidate.kg_id,
                name=best_candidate.name,
                normalized_name=best_candidate.name.lower().replace(' ', '_'),
                aliases=[best_candidate.name],
                confidence=best_candidate.score
            )
            
            return LinkResult(
                canonical_entity=canonical_entity,
                linked_entity=linked_entity,
                confidence=best_confidence,
                candidates=[cand for cand, _ in scored_candidates],
                action="link_existing",
                metadata={
                    "best_similarity": best_candidate.score,
                    "backend": "default"
                }
            )
        else:
            # Confidence too low, create new or skip
            action = "create_new" if self.create_missing else "skip"
            return LinkResult(
                canonical_entity=canonical_entity,
                linked_entity=None,
                confidence=best_confidence,
                candidates=[cand for cand, _ in scored_candidates],
                action=action,
                metadata={
                    "reason": "low_confidence",
                    "best_confidence": best_confidence,
                    "threshold": self.similarity_threshold,
                    "backend": "default"
                }
            )
    
    def get_backend_name(self) -> str:
        """Get the name of this entity linking backend."""
        return "default"
    
    def get_backend_info(self) -> dict:
        """Get detailed information about this backend."""
        return {
            "name": "default",
            "version": "1.0.0",
            "description": "Default entity linking using Neo4j KG queries",
            "parameters": {
                "similarity_threshold": self.similarity_threshold,
                "max_candidates": self.max_candidates,
                "create_missing": self.create_missing
            },
            "capabilities": [
                "exact_name_matching",
                "fuzzy_name_matching", 
                "type_compatibility",
                "confidence_scoring"
            ]
        }
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration and dependencies."""
        try:
            # Check Neo4j client is available
            if not self.neo4j_client:
                return False
            
            # Test basic Neo4j connectivity
            test_query = "RETURN 1 as test"
            self.neo4j_client.execute_query(test_query)
            
            return True
            
        except Exception as e:
            logger.error(f"Default entity linker validation failed: {e}")
            return False