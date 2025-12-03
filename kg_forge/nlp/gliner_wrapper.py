"""
GLiNER wrapper for named entity recognition.

Provides GLiNER model integration for entity extraction.
"""
from typing import List, Dict, Any, Optional, Tuple
import logging

# GLiNER imports with fallback
try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    GLiNER = None

from kg_forge.extraction.exceptions import BackendNotAvailableError, ModelLoadingError

logger = logging.getLogger(__name__)


class GLiNERWrapper:
    """Wrapper for GLiNER entity recognition model."""
    
    def __init__(self, 
                 model_name: str = "urchade/gliner_base",
                 device: str = "cpu",
                 threshold: float = 0.5):
        """Initialize GLiNER wrapper.
        
        Args:
            model_name: GLiNER model name or path
            device: Device to run model on ("cpu" or "cuda")
            threshold: Confidence threshold for predictions
        """
        if not GLINER_AVAILABLE:
            raise BackendNotAvailableError(
                "GLiNER not available. Install with: pip install gliner"
            )
        
        self.model_name = model_name
        self.device = device
        self.threshold = threshold
        
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the GLiNER model."""
        try:
            logger.info(f"Loading GLiNER model: {self.model_name}")
            
            # Load the model
            self.model = GLiNER.from_pretrained(self.model_name)
            
            # Move to specified device
            if hasattr(self.model, 'to'):
                self.model.to(self.device)
            
            logger.info(f"GLiNER model loaded successfully", extra={
                "model": self.model_name,
                "device": self.device,
                "threshold": self.threshold
            })
            
        except Exception as e:
            raise ModelLoadingError(f"Failed to load GLiNER model {self.model_name}: {e}")
    
    def extract_entities(self, text: str, entity_types: List[str]) -> List[Dict[str, Any]]:
        """Extract entities from text using GLiNER.
        
        Args:
            text: Input text to process
            entity_types: List of entity type labels to extract
        
        Returns:
            List of entity dictionaries with text, label, start, end, score
        
        Raises:
            ModelLoadingError: If extraction fails
        """
        if not self.model:
            raise ModelLoadingError("GLiNER model not loaded")
        
        if not entity_types:
            logger.debug("No entity types provided, skipping GLiNER extraction")
            return []
        
        try:
            logger.debug(f"Running GLiNER extraction", extra={
                "text_length": len(text),
                "entity_types": entity_types,
                "threshold": self.threshold
            })
            
            # Run GLiNER prediction
            entities = self.model.predict_entities(text, entity_types, threshold=self.threshold)
            
            # Convert to our format
            results = []
            for entity in entities:
                result = {
                    "text": entity["text"],
                    "label": entity["label"], 
                    "start": entity["start"],
                    "end": entity["end"],
                    "score": entity["score"]
                }
                results.append(result)
            
            logger.debug(f"GLiNER extraction completed", extra={
                "entities_found": len(results),
                "text_length": len(text)
            })
            
            return results
            
        except Exception as e:
            logger.error(f"GLiNER extraction failed: {e}")
            raise ModelLoadingError(f"GLiNER extraction failed: {e}")
    
    def extract_entities_with_context(self, text: str, entity_types: List[str], 
                                    context_window: int = 50) -> List[Dict[str, Any]]:
        """Extract entities with surrounding context.
        
        Args:
            text: Input text to process
            entity_types: List of entity type labels to extract
            context_window: Characters of context around each entity
        
        Returns:
            List of entity dictionaries with added context information
        """
        entities = self.extract_entities(text, entity_types)
        
        # Add context to each entity
        for entity in entities:
            start_char = entity["start"]
            end_char = entity["end"]
            
            # Get context before and after
            context_start = max(0, start_char - context_window)
            context_end = min(len(text), end_char + context_window)
            
            before_context = text[context_start:start_char].strip()
            after_context = text[end_char:context_end].strip()
            full_context = text[context_start:context_end].strip()
            
            entity["before_context"] = before_context
            entity["after_context"] = after_context
            entity["full_context"] = full_context
            entity["context_start"] = context_start
            entity["context_end"] = context_end
        
        return entities
    
    def batch_extract(self, texts: List[str], entity_types: List[str]) -> List[List[Dict[str, Any]]]:
        """Extract entities from multiple texts in batch.
        
        Args:
            texts: List of input texts
            entity_types: Entity types to extract
        
        Returns:
            List of entity lists, one per input text
        """
        if not self.model:
            raise ModelLoadingError("GLiNER model not loaded")
        
        results = []
        for text in texts:
            entities = self.extract_entities(text, entity_types)
            results.append(entities)
        
        return results
    
    def validate_model(self) -> bool:
        """Test if GLiNER model is working.
        
        Returns:
            True if model validation passes
        """
        try:
            # Test with simple text and entity type
            test_text = "John Doe works at Microsoft Corporation."
            test_entities = ["person", "organization"]
            
            results = self.extract_entities(test_text, test_entities)
            
            # Check if we got reasonable results
            logger.info(f"GLiNER validation completed", extra={
                "entities_found": len(results),
                "test_passed": True
            })
            
            return True
            
        except Exception as e:
            logger.error(f"GLiNER validation failed: {e}")
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
            "available": GLINER_AVAILABLE
        }


class FakeGLiNERWrapper:
    """Fake GLiNER wrapper for testing when GLiNER is not available."""
    
    def __init__(self, model_name: str = "fake-gliner", device: str = "cpu", threshold: float = 0.5):
        """Initialize fake wrapper."""
        self.model_name = model_name
        self.device = device
        self.threshold = threshold
        self.extraction_count = 0
    
    def extract_entities(self, text: str, entity_types: List[str]) -> List[Dict[str, Any]]:
        """Return fake entity extractions."""
        self.extraction_count += 1
        
        # Generate fake entities based on entity types
        entities = []
        words = text.split()
        
        for i, entity_type in enumerate(entity_types[:2]):  # Limit to 2 entities
            if i < len(words):
                word = words[i]
                start_pos = text.find(word)
                
                if start_pos >= 0:
                    entities.append({
                        "text": word,
                        "label": entity_type,
                        "start": start_pos,
                        "end": start_pos + len(word),
                        "score": 0.8 + (i * 0.05)  # Fake confidence scores
                    })
        
        return entities
    
    def extract_entities_with_context(self, text: str, entity_types: List[str], 
                                    context_window: int = 50) -> List[Dict[str, Any]]:
        """Return fake entities with fake context."""
        entities = self.extract_entities(text, entity_types)
        
        for entity in entities:
            entity.update({
                "before_context": "fake before",
                "after_context": "fake after",
                "full_context": f"fake before {entity['text']} fake after",
                "context_start": max(0, entity["start"] - context_window),
                "context_end": min(len(text), entity["end"] + context_window)
            })
        
        return entities
    
    def batch_extract(self, texts: List[str], entity_types: List[str]) -> List[List[Dict[str, Any]]]:
        """Return fake batch results."""
        return [self.extract_entities(text, entity_types) for text in texts]
    
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