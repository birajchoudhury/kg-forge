"""
GLiREL wrapper for relation extraction.

Provides GLiREL model integration for relation extraction between entities.
"""
from typing import List, Dict, Any, Optional, Tuple
import logging

# GLiREL imports with fallback
try:
    from glirel import GLiREL
    GLIREL_AVAILABLE = True
except ImportError:
    GLIREL_AVAILABLE = False
    GLiREL = None

from kg_forge.extraction.exceptions import BackendNotAvailableError, ModelLoadingError

logger = logging.getLogger(__name__)


class GLiRELWrapper:
    """Wrapper for GLiREL relation extraction model."""
    
    def __init__(self, 
                 model_name: str = "urchade/glirel_base",
                 device: str = "cpu",
                 threshold: float = 0.5):
        """Initialize GLiREL wrapper.
        
        Args:
            model_name: GLiREL model name or path
            device: Device to run model on ("cpu" or "cuda")
            threshold: Confidence threshold for predictions
        """
        if not GLIREL_AVAILABLE:
            raise BackendNotAvailableError(
                "GLiREL not available. Install with: pip install glirel"
            )
        
        self.model_name = model_name
        self.device = device
        self.threshold = threshold
        
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the GLiREL model."""
        try:
            logger.info(f"Loading GLiREL model: {self.model_name}")
            
            # Load the model
            self.model = GLiREL.from_pretrained(self.model_name)
            
            # Move to specified device
            if hasattr(self.model, 'to'):
                self.model.to(self.device)
            
            logger.info(f"GLiREL model loaded successfully", extra={
                "model": self.model_name,
                "device": self.device,
                "threshold": self.threshold
            })
            
        except Exception as e:
            raise ModelLoadingError(f"Failed to load GLiREL model {self.model_name}: {e}")
    
    def extract_relations(self, text: str, entities: List[Dict[str, Any]], 
                         relation_types: List[str]) -> List[Dict[str, Any]]:
        """Extract relations between entities using GLiREL.
        
        Args:
            text: Input text containing the entities
            entities: List of entity dictionaries with 'text', 'start', 'end', 'label'
            relation_types: List of relation type labels to extract
        
        Returns:
            List of relation dictionaries with head, tail, relation, score
        
        Raises:
            ModelLoadingError: If extraction fails
        """
        if not self.model:
            raise ModelLoadingError("GLiREL model not loaded")
        
        if not entities or not relation_types:
            logger.debug("No entities or relation types provided, skipping GLiREL extraction")
            return []
        
        try:
            logger.debug(f"Running GLiREL relation extraction", extra={
                "text_length": len(text),
                "entities_count": len(entities),
                "relation_types": relation_types,
                "relation_types_type": str(type(relation_types)),
                "threshold": self.threshold
            })
            
            # Debug: Check each relation type
            for i, rel_type in enumerate(relation_types):
                logger.debug(f"Relation type {i}: '{rel_type}' (type: {type(rel_type)})")
            
            # Convert entities to GLiREL format - expects tuples (start, end, label)
            glirel_entities = []
            for entity in entities:
                glirel_entity = (entity["start"], entity["end"], entity["label"])
                glirel_entities.append(glirel_entity)
            
            # Run GLiREL prediction
            # Based on API signature: predict_relations(text, labels, flat_ner=True, threshold=0.5, ner=None, ...)
            # We need to pass relation_types as labels and entities as ner parameter
            relations = self.model.predict_relations(
                text, 
                relation_types,
                threshold=self.threshold,
                ner=glirel_entities
            )
            
            # Convert results to our format
            results = []
            for relation in relations:
                result = {
                    "head_entity_id": relation.get("head", {}).get("id", -1),
                    "tail_entity_id": relation.get("tail", {}).get("id", -1),
                    "head_entity": relation.get("head", {}),
                    "tail_entity": relation.get("tail", {}),
                    "relation": relation["relation"],
                    "score": relation["score"],
                    "text": text[relation.get("start", 0):relation.get("end", len(text))] if "start" in relation else ""
                }
                results.append(result)
            
            logger.debug(f"GLiREL relation extraction completed", extra={
                "relations_found": len(results),
                "entities_processed": len(entities)
            })
            
            return results
            
        except Exception as e:
            logger.error(f"GLiREL relation extraction failed: {e}")
            raise ModelLoadingError(f"GLiREL relation extraction failed: {e}")
    
    def extract_relations_with_context(self, text: str, entities: List[Dict[str, Any]], 
                                     relation_types: List[str], 
                                     context_window: int = 100) -> List[Dict[str, Any]]:
        """Extract relations with surrounding context.
        
        Args:
            text: Input text containing the entities
            entities: List of entity dictionaries
            relation_types: List of relation type labels to extract
            context_window: Characters of context around each relation
        
        Returns:
            List of relation dictionaries with added context information
        """
        relations = self.extract_relations(text, entities, relation_types)
        
        # Add context to each relation
        for relation in relations:
            # Get the span between head and tail entities
            head_entity = relation["head_entity"]
            tail_entity = relation["tail_entity"]
            
            if "start" in head_entity and "start" in tail_entity:
                relation_start = min(head_entity["start"], tail_entity["start"])
                relation_end = max(head_entity["end"], tail_entity["end"])
                
                # Get context around the relation
                context_start = max(0, relation_start - context_window)
                context_end = min(len(text), relation_end + context_window)
                
                relation["context"] = text[context_start:context_end].strip()
                relation["context_start"] = context_start
                relation["context_end"] = context_end
                relation["relation_span_start"] = relation_start
                relation["relation_span_end"] = relation_end
        
        return relations
    
    def filter_relations_by_distance(self, relations: List[Dict[str, Any]], 
                                   max_token_distance: int = 50) -> List[Dict[str, Any]]:
        """Filter relations by token distance between entities.
        
        Args:
            relations: List of relations to filter
            max_token_distance: Maximum token distance allowed
        
        Returns:
            Filtered list of relations
        """
        filtered_relations = []
        
        for relation in relations:
            head_entity = relation["head_entity"]
            tail_entity = relation["tail_entity"]
            
            if "start" in head_entity and "start" in tail_entity:
                # Calculate character distance (approximate for tokens)
                distance = abs(head_entity["start"] - tail_entity["start"])
                
                # Rough approximation: 5 characters per token
                token_distance = distance // 5
                
                if token_distance <= max_token_distance:
                    relation["token_distance"] = token_distance
                    filtered_relations.append(relation)
                else:
                    logger.debug(f"Filtered out relation due to distance: {token_distance} > {max_token_distance}")
        
        return filtered_relations
    
    def group_relations_by_type(self, relations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group relations by their type.
        
        Args:
            relations: List of relations to group
        
        Returns:
            Dictionary mapping relation types to lists of relations
        """
        grouped = {}
        
        for relation in relations:
            relation_type = relation["relation"]
            if relation_type not in grouped:
                grouped[relation_type] = []
            grouped[relation_type].append(relation)
        
        return grouped
    
    def validate_model(self) -> bool:
        """Test if GLiREL model is working.
        
        Returns:
            True if model validation passes
        """
        try:
            # Test with simple entities and relation types
            test_text = "John Doe works at Microsoft Corporation in Seattle."
            test_entities = [
                {"text": "John Doe", "start": 0, "end": 8, "label": "person"},
                {"text": "Microsoft Corporation", "start": 18, "end": 39, "label": "organization"}
            ]
            test_relations = ["works_at", "employed_by"]
            
            results = self.extract_relations(test_text, test_entities, test_relations)
            
            logger.info(f"GLiREL validation completed", extra={
                "relations_found": len(results),
                "test_passed": True
            })
            
            return True
            
        except Exception as e:
            logger.error(f"GLiREL validation failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model.
        
        Returns:
            Dictionary with model details
        """
        if not self.model:
            return {"loaded": False, "error": "Model not loaded"}
        
        return {
            "loaded": True,
            "model_name": self.model_name,
            "device": self.device,
            "threshold": self.threshold,
            "available": GLIREL_AVAILABLE
        }


class FakeGLiRELWrapper:
    """Fake GLiREL wrapper for testing when GLiREL is not available."""
    
    def __init__(self, model_name: str = "fake-glirel", device: str = "cpu", threshold: float = 0.5):
        """Initialize fake wrapper."""
        self.model_name = model_name
        self.device = device
        self.threshold = threshold
        self.extraction_count = 0
    
    def extract_relations(self, text: str, entities: List[Dict[str, Any]], 
                         relation_types: List[str]) -> List[Dict[str, Any]]:
        """Return fake relation extractions."""
        self.extraction_count += 1
        
        relations = []
        
        # Generate fake relations between first pairs of entities
        if len(entities) >= 2 and relation_types:
            for i in range(0, len(entities) - 1, 2):
                if i + 1 < len(entities):
                    head_entity = entities[i]
                    tail_entity = entities[i + 1]
                    
                    # Pick a relation type
                    relation_type = relation_types[i % len(relation_types)]
                    
                    relation = {
                        "head_entity_id": i,
                        "tail_entity_id": i + 1,
                        "head_entity": head_entity,
                        "tail_entity": tail_entity,
                        "relation": relation_type,
                        "score": 0.7 + (i * 0.05),
                        "text": f"{head_entity['text']} {relation_type} {tail_entity['text']}"
                    }
                    relations.append(relation)
        
        return relations
    
    def extract_relations_with_context(self, text: str, entities: List[Dict[str, Any]], 
                                     relation_types: List[str], 
                                     context_window: int = 100) -> List[Dict[str, Any]]:
        """Return fake relations with fake context."""
        relations = self.extract_relations(text, entities, relation_types)
        
        for relation in relations:
            relation.update({
                "context": "fake context around relation",
                "context_start": 0,
                "context_end": len(text),
                "relation_span_start": 0,
                "relation_span_end": len(text)
            })
        
        return relations
    
    def filter_relations_by_distance(self, relations: List[Dict[str, Any]], 
                                   max_token_distance: int = 50) -> List[Dict[str, Any]]:
        """Return all relations (no filtering in fake mode)."""
        for relation in relations:
            relation["token_distance"] = 10  # Fake distance
        return relations
    
    def group_relations_by_type(self, relations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group fake relations."""
        grouped = {}
        for relation in relations:
            relation_type = relation["relation"]
            if relation_type not in grouped:
                grouped[relation_type] = []
            grouped[relation_type].append(relation)
        return grouped
    
    def validate_model(self) -> bool:
        """Fake validation always passes."""
        return True
    
    def get_model_info(self) -> Dict[str, Any]:
        """Return fake model info."""
        return {
            "loaded": True,
            "model_name": self.model_name,
            "device": self.device,
            "threshold": self.threshold,
            "available": True,
            "fake": True,
            "extraction_count": self.extraction_count
        }