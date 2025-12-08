"""
spaCy-based extraction backend using GLiNER and GLiREL.

Implements entity and relation extraction using spaCy + GLiNER + GLiREL pipeline.
"""
import time
from typing import Dict, Any, List, Optional, Set
import logging

from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.ontology.schema import OntologySchema
from kg_forge.extraction.interface import BaseExtractionBackend
from kg_forge.extraction.exceptions import (
    ExtractionError,
    BackendNotAvailableError, 
    ModelLoadingError
)
from kg_forge.nlp.spacy_pipeline import SpacyPipeline, FakeSpacyPipeline, SPACY_AVAILABLE
from kg_forge.nlp.gliner_wrapper import GLiNERWrapper, FakeGLiNERWrapper, GLINER_AVAILABLE
from kg_forge.nlp.glirel_wrapper import GLiRELWrapper, FakeGLiRELWrapper, GLIREL_AVAILABLE

logger = logging.getLogger(__name__)


class SpacyLexicalBackend(BaseExtractionBackend):
    """spaCy-based lexical extraction backend.
    
    Uses spaCy for text processing, GLiNER for entity recognition,
    and GLiREL for relation extraction.
    """
    
    def __init__(self,
                 spacy_model: str = "en_core_web_sm",
                 gliner_model: str = "urchade/gliner_base", 
                 glirel_model: str = "jackboyla/glirel-large-v0",
                 device: str = "cpu",
                 entity_threshold: float = 0.5,
                 relation_threshold: float = 0.5,
                 max_relation_distance: int = 50,
                 fake_mode: bool = False):
        """Initialize spaCy extraction backend.
        
        Args:
            spacy_model: spaCy model name
            gliner_model: GLiNER model name
            glirel_model: GLiREL model name
            device: Device to run models on ("cpu" or "cuda")
            entity_threshold: Confidence threshold for entities
            relation_threshold: Confidence threshold for relations
            max_relation_distance: Maximum token distance for relations
            fake_mode: Use fake models for testing
        """
        super().__init__("spacy")
        
        self.spacy_model = spacy_model
        self.gliner_model = gliner_model
        self.glirel_model = glirel_model
        self.device = device
        self.entity_threshold = entity_threshold
        self.relation_threshold = relation_threshold
        self.max_relation_distance = max_relation_distance
        self.fake_mode = fake_mode
        
        # Initialize components
        self.spacy_pipeline = None
        self.gliner_wrapper = None
        self.glirel_wrapper = None
        
        # Statistics
        self.total_extractions = 0
        self.total_entities = 0
        self.total_relations = 0
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize all backend components."""
        try:
            if self.fake_mode:
                logger.info("Initializing fake spaCy backend for testing")
                self.spacy_pipeline = FakeSpacyPipeline(self.spacy_model)
                self.gliner_wrapper = FakeGLiNERWrapper(self.gliner_model, self.device, self.entity_threshold)
                self.glirel_wrapper = FakeGLiRELWrapper(self.glirel_model, self.device, self.relation_threshold)
            else:
                # Initialize spaCy pipeline
                if not SPACY_AVAILABLE:
                    raise BackendNotAvailableError("spaCy not available")
                
                self.spacy_pipeline = SpacyPipeline(
                    model_name=self.spacy_model,
                    disable_components=["ner", "parser"]  # We'll use GLiNER for NER
                )
                
                # Initialize GLiNER wrapper
                if not GLINER_AVAILABLE:
                    raise BackendNotAvailableError("GLiNER not available")
                
                self.gliner_wrapper = GLiNERWrapper(
                    model_name=self.gliner_model,
                    device=self.device,
                    threshold=self.entity_threshold
                )
                
                # Initialize GLiREL wrapper (real models only)
                if not GLIREL_AVAILABLE:
                    raise BackendNotAvailableError("GLiREL not available")
                
                self.glirel_wrapper = GLiRELWrapper(
                    model_name=self.glirel_model,
                    device=self.device,
                    threshold=self.relation_threshold
                )
            
            logger.info(f"spaCy extraction backend initialized", extra={
                "spacy_model": self.spacy_model,
                "gliner_model": self.gliner_model,
                "glirel_model": self.glirel_model,
                "device": self.device,
                "fake_mode": self.fake_mode
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize spaCy backend: {e}")
            raise BackendNotAvailableError(f"spaCy backend initialization failed: {e}")
    
    def _do_extract(self, content: str, ontology: OntologySchema, doc_id: str) -> LexicalGraph:
        """Perform spaCy-based extraction.
        
        Args:
            content: Curated document content
            ontology: Normalized ontology schema
            doc_id: Document identifier
        
        Returns:
            LexicalGraph with extracted mentions and relations
        
        Raises:
            ExtractionError: If extraction fails
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting spaCy extraction", extra={
                "doc_id": doc_id,
                "content_length": len(content)
            })
            
            # Step 1: Process text with spaCy
            spacy_doc = self.spacy_pipeline.process(content)
            
            # Step 2: Extract entity types from ontology
            entity_types = self._get_entity_types_from_ontology(ontology)
            
            # Step 3: Extract entities with GLiNER
            gliner_entities = self.gliner_wrapper.extract_entities(content, entity_types)
            
            # Step 4: Convert to LexicalMentions
            mentions = self._convert_entities_to_mentions(gliner_entities, spacy_doc, doc_id)
            
            # Step 5: Extract relation types from ontology
            relation_types = self._get_relation_types_from_ontology(ontology)
            
            # Step 6: Extract relations with GLiREL
            logger.debug(f"About to call GLiREL with relation_types: {relation_types}, type: {type(relation_types)}")
            glirel_relations = self.glirel_wrapper.extract_relations(content, gliner_entities, relation_types)
            
            # Step 7: Filter relations by distance
            filtered_relations = self.glirel_wrapper.filter_relations_by_distance(
                glirel_relations, self.max_relation_distance
            )
            
            # Step 8: Convert to LexicalRelations
            relations = self._convert_relations_to_lexical_relations(filtered_relations, mentions, doc_id)
            
            # Step 9: Build metadata
            extraction_time = time.time() - start_time
            metadata = {
                "backend": "spacy",
                "spacy_model": self.spacy_model,
                "gliner_model": self.gliner_model,
                "glirel_model": self.glirel_model,
                "extraction_time": extraction_time,
                "content_length": len(content),
                "spacy_tokens": len(spacy_doc) if hasattr(spacy_doc, '__len__') else 0,
                "gliner_entities": len(gliner_entities),
                "glirel_relations": len(glirel_relations),
                "filtered_relations": len(filtered_relations),
                "entity_threshold": self.entity_threshold,
                "relation_threshold": self.relation_threshold,
                "fake_mode": self.fake_mode
            }
            
            # Step 10: Create LexicalGraph
            graph = LexicalGraph(
                mentions=mentions,
                relations=relations,
                metadata=metadata
            )
            
            # Update statistics
            self.total_extractions += 1
            self.total_entities += len(mentions)
            self.total_relations += len(relations)
            
            logger.info(f"spaCy extraction completed", extra={
                "doc_id": doc_id,
                "mentions": len(mentions),
                "relations": len(relations),
                "extraction_time": extraction_time
            })
            
            return graph
            
        except Exception as e:
            extraction_time = time.time() - start_time
            
            logger.error(f"spaCy extraction failed", extra={
                "doc_id": doc_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "extraction_time": extraction_time
            })
            
            raise ExtractionError(f"spaCy extraction failed for {doc_id}: {e}")
    
    def _get_entity_types_from_ontology(self, ontology: OntologySchema) -> List[str]:
        """Extract entity type labels for GLiNER using ontology helper.
        
        Args:
            ontology: Normalized ontology schema
        
        Returns:
            List of entity type strings for GLiNER
        """
        # Use OntologySchema.to_gliner_config() helper method
        gliner_config = ontology.to_gliner_config()
        entity_types = list(gliner_config.keys())
        
        logger.debug(f"Extracted entity types for GLiNER", extra={
            "entity_types": entity_types,
            "count": len(entity_types)
        })
        
        return entity_types
    
    def _get_relation_types_from_ontology(self, ontology: OntologySchema) -> List[str]:
        """Extract relation type labels for GLiREL using ontology helper.
        
        Args:
            ontology: Normalized ontology schema
        
        Returns:
            List of relation type strings for GLiREL
        """
        # Use OntologySchema.to_glirel_config() helper method
        glirel_config = ontology.to_glirel_config()
        relation_list = list(glirel_config.keys())
        
        logger.debug(f"Extracted relation types for GLiREL", extra={
            "relation_types": relation_list,
            "count": len(relation_list)
        })
        
        return relation_list
    
    def _convert_entities_to_mentions(self, gliner_entities: List[Dict[str, Any]], 
                                    spacy_doc: Any, doc_id: str) -> List[LexicalMention]:
        """Convert GLiNER entities to LexicalMention objects.
        
        Args:
            gliner_entities: Entities from GLiNER
            spacy_doc: Processed spaCy document
            doc_id: Document identifier
        
        Returns:
            List of LexicalMention objects
        """
        mentions = []
        
        for entity in gliner_entities:
            # Convert GLiNER label back to ontology entity type
            entity_type = self._normalize_entity_type(entity["label"])
            
            # Get context information from spaCy
            context_info = self.spacy_pipeline.get_context_around_span(
                spacy_doc, entity["start"], entity["end"], context_words=5
            )
            
            # Build features
            features = {
                "backend": "spacy",
                "gliner_confidence": entity["score"],
                "gliner_label": entity["label"],
                "before_context": context_info.get("before_context", ""),
                "after_context": context_info.get("after_context", ""),
                "sentence_text": context_info.get("sentence_text", ""),
                "sentence_index": context_info.get("sentence_index", -1)
            }
            
            # Create mention
            mention = LexicalMention(
                id=self._generate_mention_id(doc_id),
                doc_id=doc_id,
                entity_type=entity_type,
                surface=entity["text"],
                start_offset=entity["start"],
                end_offset=entity["end"],
                features=features
            )
            mentions.append(mention)
        
        return mentions
    
    def _convert_relations_to_lexical_relations(self, glirel_relations: List[Dict[str, Any]],
                                              mentions: List[LexicalMention], 
                                              doc_id: str) -> List[LexicalRelation]:
        """Convert GLiREL relations to LexicalRelation objects.
        
        Args:
            glirel_relations: Relations from GLiREL
            mentions: Available LexicalMention objects
            doc_id: Document identifier
        
        Returns:
            List of LexicalRelation objects
        """
        relations = []
        
        # Build lookup from entity position to mention ID
        position_to_mention_id = {}
        for mention in mentions:
            # Use start position as key (assumes unique positions)
            position_to_mention_id[mention.start_offset] = mention.id
        
        for relation in glirel_relations:
            try:
                # Get head and tail entities
                head_entity = relation["head_entity"]
                tail_entity = relation["tail_entity"]
                
                # Find corresponding mentions
                head_mention_id = position_to_mention_id.get(head_entity.get("start"))
                tail_mention_id = position_to_mention_id.get(tail_entity.get("start"))
                
                if not head_mention_id or not tail_mention_id:
                    logger.warning(f"Could not find mentions for relation", extra={
                        "doc_id": doc_id,
                        "head_entity": head_entity.get("text", ""),
                        "tail_entity": tail_entity.get("text", "")
                    })
                    continue
                
                # Convert GLiREL relation type back to ontology relation type
                relation_type = self._normalize_relation_type(relation["relation"])
                
                # Build features
                features = {
                    "backend": "spacy",
                    "glirel_confidence": relation["score"],
                    "glirel_relation": relation["relation"],
                    "token_distance": relation.get("token_distance", -1),
                    "context": relation.get("context", "")
                }
                
                # Create relation
                lexical_relation = LexicalRelation(
                    id=self._generate_relation_id(doc_id),
                    type=relation_type,
                    src_mention_id=head_mention_id,
                    dst_mention_id=tail_mention_id,
                    features=features
                )
                relations.append(lexical_relation)
                
            except (KeyError, TypeError) as e:
                logger.warning(f"Error converting relation", extra={
                    "doc_id": doc_id,
                    "error": str(e),
                    "relation": relation
                })
                continue
        
        return relations
    
    def _normalize_entity_type(self, gliner_label: str) -> str:
        """Convert GLiNER label back to ontology entity type.
        
        Args:
            gliner_label: Label from GLiNER (lowercase, spaces)
        
        Returns:
            Normalized entity type for ontology
        """
        # Convert back: "ai ml domain" -> "AiMlDomain"
        words = gliner_label.split()
        normalized = "".join(word.capitalize() for word in words)
        return normalized
    
    def _normalize_relation_type(self, glirel_label: str) -> str:
        """Convert GLiREL label back to ontology relation type.
        
        Args:
            glirel_label: Label from GLiREL (lowercase, spaces)
        
        Returns:
            Normalized relation type for ontology
        """
        # Convert back: "works on" -> "WORKS_ON"
        normalized = glirel_label.upper().replace(" ", "_")
        return normalized
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get detailed backend information."""
        info = super().get_backend_info()
        
        info.update({
            "spacy_model": self.spacy_model,
            "gliner_model": self.gliner_model,
            "glirel_model": self.glirel_model,
            "device": self.device,
            "entity_threshold": self.entity_threshold,
            "relation_threshold": self.relation_threshold,
            "max_relation_distance": self.max_relation_distance,
            "fake_mode": self.fake_mode,
            "total_extractions": self.total_extractions,
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "spacy_available": SPACY_AVAILABLE,
            "gliner_available": GLINER_AVAILABLE,
            "glirel_available": GLIREL_AVAILABLE
        })
        
        # Add component info if available
        if self.spacy_pipeline:
            info["spacy_info"] = self.spacy_pipeline.get_pipeline_info()
        if self.gliner_wrapper:
            info["gliner_info"] = self.gliner_wrapper.get_model_info()
        if self.glirel_wrapper:
            info["glirel_info"] = self.glirel_wrapper.get_model_info()
        
        return info
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration and model loading.
        
        Returns:
            True if backend is properly configured and ready
        """
        try:
            # Validate spaCy pipeline
            if not self.spacy_pipeline or not self.spacy_pipeline.validate_model():
                logger.warning("spaCy pipeline validation failed")
                return False
            
            # Validate GLiNER wrapper
            if not self.gliner_wrapper or not self.gliner_wrapper.validate_model():
                logger.warning("GLiNER wrapper validation failed")
                return False
            
            # Validate GLiREL wrapper
            if not self.glirel_wrapper or not self.glirel_wrapper.validate_model():
                logger.warning("GLiREL wrapper validation failed")
                return False
            
            logger.info("spaCy backend configuration validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"spaCy backend validation failed: {e}")
            return False
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics.
        
        Returns:
            Dictionary with extraction performance metrics
        """
        return {
            "total_extractions": self.total_extractions,
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "avg_entities_per_doc": self.total_entities / max(self.total_extractions, 1),
            "avg_relations_per_doc": self.total_relations / max(self.total_extractions, 1),
            "entity_threshold": self.entity_threshold,
            "relation_threshold": self.relation_threshold
        }