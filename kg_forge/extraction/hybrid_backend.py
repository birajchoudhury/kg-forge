"""
Hybrid GLiNER + LLM extraction backend.

Combines GLiNER's ontology-aware entity detection with LLM for property 
extraction and relationship detection.

Phase 1: GLiNER detects entities using ontology types
Phase 2: LLM enriches with properties and extracts relations
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
    ModelLoadingError,
    ConsecutiveFailureError
)
from kg_forge.nlp.gliner_wrapper import GLiNERWrapper, FakeGLiNERWrapper, GLINER_AVAILABLE
from kg_forge.llm.bedrock_client import BedrockClient, FakeBedrockClient

logger = logging.getLogger(__name__)


class HybridExtractionBackend(BaseExtractionBackend):
    """Hybrid GLiNER + LLM extraction backend.
    
    Two-phase extraction:
    - Phase 1: GLiNER for ontology-guided entity detection
    - Phase 2: LLM for property extraction and relationship detection
    
    This combines the ontology-awareness and speed of GLiNER with the flexibility
    and contextual understanding of LLM-based property and relation extraction.
    """
    
    def __init__(self,
                 gliner_model: str = "urchade/gliner_base",
                 device: str = "cpu",
                 llm_model_name: str = "anthropic.claude-3-haiku-20240307-v1:0",
                 llm_region: str = "us-east-1",
                 max_tokens: int = 4000,
                 temperature: float = 0.1,
                 timeout: int = 30,
                 max_retries: int = 3,
                 consecutive_failure_threshold: int = 10,
                 entity_confidence_threshold: float = 0.5,
                 fake_mode: bool = False):
        """Initialize hybrid extraction backend.
        
        Args:
            gliner_model: GLiNER model name for ontology-guided entity detection
            device: Device to run GLiNER on ("cpu" or "cuda")
            llm_model_name: Bedrock model identifier for property/relation extraction
            llm_region: AWS region for Bedrock
            max_tokens: Maximum tokens in LLM response
            temperature: LLM sampling temperature
            timeout: LLM request timeout in seconds
            max_retries: Maximum retries per LLM call
            consecutive_failure_threshold: Max consecutive LLM failures before aborting
            entity_confidence_threshold: Minimum confidence for GLiNER entities
            fake_mode: Use fake models for testing
        """
        super().__init__("hybrid")
        
        # GLiNER configuration
        self.gliner_model = gliner_model
        self.device = device
        self.entity_confidence_threshold = entity_confidence_threshold
        
        # LLM configuration
        self.llm_model_name = llm_model_name
        self.llm_region = llm_region
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.consecutive_failure_threshold = consecutive_failure_threshold
        self.fake_mode = fake_mode
        
        # Components
        self.gliner_wrapper = None
        self.bedrock_client = None
        
        # Statistics
        self.total_extractions = 0
        self.total_entities_detected = 0
        self.total_entities_enriched = 0
        self.total_relations = 0
        self.consecutive_llm_failures = 0
        self.total_llm_calls = 0
        self.total_llm_failures = 0
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize GLiNER and LLM components."""
        try:
            if self.fake_mode:
                logger.info("Initializing fake hybrid backend for testing")
                self.gliner_wrapper = FakeGLiNERWrapper(self.gliner_model, self.device, self.entity_confidence_threshold)
                self.bedrock_client = FakeBedrockClient(
                    model_name=self.llm_model_name,
                    region=self.llm_region
                )
            else:
                # Initialize GLiNER wrapper
                if not GLINER_AVAILABLE:
                    raise BackendNotAvailableError("GLiNER not available")
                
                logger.info(f"Loading GLiNER model: {self.gliner_model}")
                self.gliner_wrapper = GLiNERWrapper(
                    model_name=self.gliner_model,
                    device=self.device,
                    threshold=self.entity_confidence_threshold
                )
                
                # Initialize Bedrock client
                logger.info(f"Initializing Bedrock client: {self.llm_model_name}")
                self.bedrock_client = BedrockClient(
                    model_name=self.llm_model_name,
                    region=self.llm_region,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=self.timeout
                )
            
            logger.info("Hybrid extraction backend initialized", extra={
                "gliner_model": self.gliner_model,
                "device": self.device,
                "llm_model": self.llm_model_name,
                "fake_mode": self.fake_mode
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid backend: {e}")
            raise BackendNotAvailableError(f"Hybrid backend initialization failed: {e}")
    
    def extract(self, content: str, ontology: OntologySchema, doc_id: str) -> LexicalGraph:
        """Extract entities and relations using hybrid approach.
        
        Phase 1: Use GLiNER to detect entities (ontology-aware)
        Phase 2: Use LLM to extract properties and relations
        
        Args:
            content: Curated text content
            ontology: Normalized ontology schema
            doc_id: Document identifier
        
        Returns:
            LexicalGraph with entities and relations
        """
        start_time = time.time()
        self.total_extractions += 1
        
        try:
            # Phase 1: GLiNER for ontology-aware entity detection
            logger.info(f"Phase 1: Detecting entities with GLiNER", extra={"doc_id": doc_id})
            detected_entities = self._detect_entities_with_gliner(content, ontology)
            self.total_entities_detected += len(detected_entities)
            
            logger.info(f"Detected {len(detected_entities)} entities with GLiNER", extra={
                "doc_id": doc_id,
                "entity_count": len(detected_entities)
            })
            
            # Phase 2: LLM for properties and relations
            logger.info(f"Phase 2: Enriching with LLM properties and relations", extra={"doc_id": doc_id})
            lexical_graph = self._enrich_with_llm(
                content=content,
                detected_entities=detected_entities,
                ontology=ontology,
                doc_id=doc_id
            )
            
            self.total_entities_enriched += len(lexical_graph.mentions)
            self.total_relations += len(lexical_graph.relations)
            
            elapsed = time.time() - start_time
            
            logger.info(f"Hybrid extraction completed", extra={
                "doc_id": doc_id,
                "entities": len(lexical_graph.mentions),
                "relations": len(lexical_graph.relations),
                "elapsed_seconds": round(elapsed, 2)
            })
            
            return lexical_graph
            
        except Exception as e:
            logger.error(f"Hybrid extraction failed for {doc_id}: {e}")
            raise ExtractionError(f"Hybrid extraction failed: {e}")
    
    def _detect_entities_with_gliner(self, content: str, ontology: OntologySchema) -> List[Dict[str, Any]]:
        """Detect entities using GLiNER with ontology types.
        
        Args:
            content: Text content
            ontology: Normalized ontology schema
        
        Returns:
            List of detected entities with metadata
        """
        try:
            # Use OntologySchema.to_gliner_config() helper
            gliner_config = ontology.to_gliner_config()
            entity_types = list(gliner_config.keys())
            
            if not entity_types:
                logger.warning("No entity types defined in ontology")
                return []
            
            logger.debug(f"Using ontology entity types: {entity_types}")
            
            # Extract entities with GLiNER
            gliner_entities = self.gliner_wrapper.extract_entities(content, entity_types)
            
            logger.info(f"GLiNER detected {len(gliner_entities)} entities")
            
            # Normalize GLiNER format to match expected format
            normalized_entities = []
            for ent in gliner_entities:
                normalized_entities.append({
                    "text": ent["text"],
                    "entity_type": ent["label"],  # GLiNER uses "label" 
                    "start_offset": ent["start"],  # GLiNER uses "start"
                    "end_offset": ent["end"],      # GLiNER uses "end"
                    "confidence": ent.get("score", 0.5)  # GLiNER uses "score"
                })
            
            return normalized_entities
            
        except Exception as e:
            logger.error(f"GLiNER entity detection failed: {e}")
            return []  # Return empty list on failure, LLM might still extract some
    

    
    def _enrich_with_llm(self, 
                        content: str, 
                        detected_entities: List[Dict[str, Any]],
                        ontology: OntologySchema,
                        doc_id: str) -> LexicalGraph:
        """Use LLM to extract properties and relations.
        
        Args:
            content: Original text content
            detected_entities: Entities detected by GLiNER
            ontology: Ontology pack
            doc_id: Document identifier
        
        Returns:
            Complete LexicalGraph with enriched entities and relations
        """
        # Build specialized prompt for property and relation extraction
        prompt = self._build_hybrid_prompt(content, detected_entities, ontology)
        
        # Call LLM with retries
        for attempt in range(self.max_retries):
            try:
                self.total_llm_calls += 1
                
                logger.debug(f"Calling LLM for enrichment (attempt {attempt + 1}/{self.max_retries})")
                
                response_dict = self.bedrock_client.call_model(prompt)
                response_text = response_dict.get("response_text", "")
                
                # Parse LLM response for hybrid mode - extract only relations
                relations = self._parse_hybrid_llm_response(
                    response_text=response_text,
                    detected_entities=detected_entities,
                    doc_id=doc_id
                )
                
                # Reset consecutive failures on success
                self.consecutive_llm_failures = 0
                
                # Create merged graph with GLiNER entities and LLM relations
                merged_graph = self._create_hybrid_graph(
                    detected_entities=detected_entities,
                    relations=relations,
                    doc_id=doc_id
                )
                
                return merged_graph
                
            except Exception as e:
                self.total_llm_failures += 1
                self.consecutive_llm_failures += 1
                
                logger.warning(f"LLM enrichment attempt {attempt + 1} failed: {e}")
                
                if self.consecutive_llm_failures >= self.consecutive_failure_threshold:
                    raise ConsecutiveFailureError(
                        failure_count=self.consecutive_llm_failures,
                        threshold=self.consecutive_failure_threshold,
                        message=f"LLM failed {self.consecutive_llm_failures} consecutive times"
                    )
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # On final failure, return graph with just GLiNER entities (no relations)
                    logger.warning(f"LLM enrichment failed after {self.max_retries} attempts, returning entities only")
                    return self._create_graph_from_gliner_only(detected_entities, doc_id)
    
    def _build_hybrid_prompt(self, 
                            content: str,
                            detected_entities: List[Dict[str, Any]],
                            ontology: OntologySchema) -> str:
        """Build specialized prompt for hybrid extraction.
        
        Args:
            content: Document content
            detected_entities: Entities already detected by GLiNER
            ontology: Normalized ontology schema
        
        Returns:
            Complete prompt for LLM
        """
        # Format detected entities for prompt
        entity_list = "\n".join([
            f"- {ent['text']} (type: {ent['entity_type']}, offset: {ent['start_offset']}-{ent['end_offset']})"
            for ent in detected_entities
        ])
        
        # Use OntologySchema helper method to generate ontology JSON
        ontology_json = ontology.to_llm_prompt_snippet()
        
        prompt = f"""You are an expert entity and relationship analysis system. 

TASK: Given a document and a list of detected entities, extract:
1. Additional properties for each detected entity based on the ontology
2. Relationships between the detected entities based on the ontology schema

**CRITICAL: You must respond with ONLY valid JSON. Do not include any explanatory text, markdown formatting, or commentary.**

**DETECTED ENTITIES:**
{entity_list}

**ONTOLOGY DEFINITIONS:**
{ontology_json}

**DOCUMENT CONTENT:**
{content}

**INSTRUCTIONS:**
1. For each detected entity, extract any additional properties mentioned in the document
2. Identify relationships between the detected entities based on the ontology schema
3. Only create relationships that are defined in the ontology for the entity types
4. Include confidence scores (0.0-1.0) for each relationship
5. Include context text that supports each relationship

**REQUIRED OUTPUT FORMAT (return ONLY this JSON):**

{{
  "entity_properties": [
    {{
      "entity_text": "exact text from detected entities",
      "entity_type": "type from detected entities",
      "properties": {{
        "property_name": "property_value"
      }}
    }}
  ],
  "relations": [
    {{
      "source_entity": "exact text from detected entities",
      "target_entity": "exact text from detected entities",
      "relation_type": "RELATION_TYPE from ontology",
      "confidence": 0.9,
      "context": "text showing the relationship"
    }}
  ]
}}"""
        
        return prompt
    
    def _parse_hybrid_llm_response(self,
                                  response_text: str,
                                  detected_entities: List[Dict[str, Any]],
                                  doc_id: str) -> List[LexicalRelation]:
        """Parse LLM response to extract only relations for hybrid mode.
        
        Args:
            response_text: Raw LLM response
            detected_entities: GLiNER-detected entities
            doc_id: Document identifier
        
        Returns:
            List of LexicalRelation objects
        """
        import json
        import re
        
        relations = []
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                logger.warning(f"No JSON found in LLM response", extra={"doc_id": doc_id})
                return relations
            
            json_data = json.loads(json_match.group(0))
            
            # Build entity text to ID mapping
            entity_text_to_id = {}
            for idx, entity in enumerate(detected_entities):
                mention_id = f"{doc_id}_mention_{idx}"
                # Normalize for matching
                entity_text_to_id[entity["text"].strip().lower()] = mention_id
            
            # Extract relations
            relations_data = json_data.get("relations", [])
            for i, rel_data in enumerate(relations_data):
                source_text = rel_data.get("source_entity", "").strip()
                target_text = rel_data.get("target_entity", "").strip()
                relation_type = rel_data.get("relation_type", "").strip()
                
                if not all([source_text, target_text, relation_type]):
                    continue
                
                # Map entity text to mention IDs (case-insensitive)
                src_id = entity_text_to_id.get(source_text.lower())
                dst_id = entity_text_to_id.get(target_text.lower())
                
                if src_id and dst_id:
                    relation_id = f"{doc_id}_relation_{i}"
                    relation = LexicalRelation(
                        id=relation_id,
                        type=relation_type,
                        src_mention_id=src_id,
                        dst_mention_id=dst_id,
                        features={
                            "backend": "hybrid_llm",
                            "confidence": rel_data.get("confidence", 1.0),
                            "context": rel_data.get("context", ""),
                            "extraction_method": "llm_hybrid"
                        }
                    )
                    relations.append(relation)
                else:
                    logger.warning(f"Could not map LLM relation to GLiNER mentions: {source_text} -> {target_text}",
                                 extra={"doc_id": doc_id})
            
            logger.info(f"Parsed {len(relations)} relations from LLM response", extra={"doc_id": doc_id})
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in LLM response: {e}", extra={"doc_id": doc_id})
        except Exception as e:
            logger.error(f"Error parsing hybrid LLM response: {e}", extra={"doc_id": doc_id})
        
        return relations
    
    def _create_hybrid_graph(self,
                           detected_entities: List[Dict[str, Any]],
                           relations: List[LexicalRelation],
                           doc_id: str) -> LexicalGraph:
        """Create final graph from GLiNER entities and LLM relations.
        
        Args:
            detected_entities: Entities from GLiNER
            relations: Relations from LLM
            doc_id: Document identifier
        
        Returns:
            Complete LexicalGraph
        """
        # Create mentions from GLiNER entities
        mentions = []
        for idx, entity in enumerate(detected_entities):
            mention_id = f"{doc_id}_mention_{idx}"
            
            mention = LexicalMention(
                id=mention_id,
                doc_id=doc_id,
                entity_type=entity["entity_type"],
                surface=entity["text"],
                start_offset=entity["start_offset"],
                end_offset=entity["end_offset"],
                features={
                    "confidence": entity.get("confidence", 0.9),
                    "detection_method": "gliner"
                }
            )
            mentions.append(mention)
        
        # Create graph
        graph = LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={
                "backend": "hybrid",
                "gliner_model": self.gliner_model,
                "llm_model": self.llm_model_name,
                "total_entities": len(mentions),
                "total_relations": len(relations),
                "detection_method": "gliner",
                "enrichment_method": "llm"
            }
        )
        
        return graph
    
    def _create_graph_from_gliner_only(self, 
                                     detected_entities: List[Dict[str, Any]],
                                     doc_id: str) -> LexicalGraph:
        """Create graph from GLiNER entities only (LLM failed).
        
        Args:
            detected_entities: Entities from GLiNER
            doc_id: Document identifier
        
        Returns:
            LexicalGraph with entities only (no relations)
        """
        mentions = []
        
        for idx, entity in enumerate(detected_entities):
            mention_id = f"{doc_id}_mention_{idx}"
            
            mention = LexicalMention(
                id=mention_id,
                doc_id=doc_id,
                entity_type=entity["entity_type"],
                surface=entity["text"],
                start_offset=entity["start_offset"],
                end_offset=entity["end_offset"],
                features={
                    "confidence": entity.get("confidence", 0.9),
                    "detection_method": "gliner",
                    "note": "LLM enrichment failed, relations not extracted"
                }
            )
            
            mentions.append(mention)
        
        return LexicalGraph(
            mentions=mentions,
            relations=[],
            metadata={
                "backend": "hybrid",
                "gliner_model": self.gliner_model,
                "total_entities": len(mentions),
                "total_relations": 0,
                "detection_method": "gliner",
                "enrichment_method": "failed",
                "note": "LLM enrichment failed, returning entities only"
            }
        )
    
    def get_backend_info(self) -> dict:
        """Get detailed backend information.
        
        Returns:
            Dictionary with backend metadata
        """
        return {
            "name": "hybrid",
            "description": "Hybrid GLiNER + LLM extraction",
            "gliner_model": self.gliner_model,
            "device": self.device,
            "llm_model": self.llm_model_name,
            "llm_region": self.llm_region,
            "entity_confidence_threshold": self.entity_confidence_threshold,
            "statistics": {
                "total_extractions": self.total_extractions,
                "total_entities_detected": self.total_entities_detected,
                "total_entities_enriched": self.total_entities_enriched,
                "total_relations": self.total_relations,
                "total_llm_calls": self.total_llm_calls,
                "total_llm_failures": self.total_llm_failures,
                "consecutive_llm_failures": self.consecutive_llm_failures
            }
        }
