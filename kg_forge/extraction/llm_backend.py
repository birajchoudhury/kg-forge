"""
LLM-based extraction backend using AWS Bedrock with schema-driven approach.

Implements entity and relation extraction using large language models.
"""
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.ontology.schema import OntologySchema
from kg_forge.extraction.interface import BaseExtractionBackend
from kg_forge.extraction.exceptions import (
    ExtractionError, 
    BackendNotAvailableError,
    ConsecutiveFailureError,
    ExtractionTimeoutError
)
from kg_forge.extraction.schema_driven_extractor import extract_entities_from_document

logger = logging.getLogger(__name__)


class BedrockLLMClientAdapter:
    """Adapter to make BedrockClient compatible with schema-driven extractor interface."""
    
    def __init__(self, bedrock_client):
        """Initialize adapter with BedrockClient instance."""
        self.bedrock_client = bedrock_client
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate LLM response from system and user prompts.
        
        Args:
            system_prompt: System instructions
            user_prompt: User content with document and config
        
        Returns:
            LLM response text
        """
        # Combine prompts for Bedrock client
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Call Bedrock client
        if hasattr(self.bedrock_client, 'generate'):
            # New interface
            return self.bedrock_client.generate(system_prompt, user_prompt)
        else:
            # Legacy interface - call_model expects full prompt
            response = self.bedrock_client.call_model(combined_prompt)
            return response.get("response_text", response) if isinstance(response, dict) else response


class LLMExtractionBackend(BaseExtractionBackend):
    """LLM-based extraction backend using schema-driven approach.
    
    Extracts entities and relations using a generic, ontology-driven method that works
    with any domain. Automatically converts the ontology into a schema for the LLM.
    """
    
    def __init__(self, 
                 model_name: str = "anthropic.claude-3-haiku-20240307-v1:0",
                 region: str = "us-east-1",
                 max_tokens: int = 4000,
                 temperature: float = 0.1,
                 timeout: int = 30,
                 max_retries: int = 3,
                 consecutive_failure_threshold: int = 10,
                 fake_mode: bool = False,
                 save_debug: bool = True):
        """Initialize LLM extraction backend.
        
        Args:
            model_name: Bedrock model identifier
            region: AWS region
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            timeout: Request timeout in seconds
            max_retries: Maximum retries per document
            consecutive_failure_threshold: Max consecutive failures before aborting
            fake_mode: Use fake client instead of real Bedrock
            save_debug: Save debug files for each extraction
        """
        super().__init__("llm")
        
        self.model_name = model_name
        self.region = region
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.consecutive_failure_threshold = consecutive_failure_threshold
        self.fake_mode = fake_mode
        self.save_debug = save_debug
        
        # State tracking
        self.consecutive_failures = 0
        self.total_calls = 0
        self.total_failures = 0
        
        # Initialize components
        self.bedrock_client = None
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize backend components."""
        # Import here to avoid circular dependency
        from kg_forge.llm.bedrock_client import BedrockClient, FakeBedrockClient
        
        try:
            # Initialize Bedrock client
            if self.fake_mode:
                logger.info("Initializing fake Bedrock client for testing")
                self.bedrock_client = FakeBedrockClient(
                    model_name=self.model_name,
                    region=self.region
                )
            else:
                self.bedrock_client = BedrockClient(
                    model_name=self.model_name,
                    region=self.region,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=self.timeout
                )
            
            logger.info(f"LLM extraction backend initialized (schema-driven)", extra={
                "model": self.model_name,
                "region": self.region,
                "fake_mode": self.fake_mode
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM backend: {e}")
            raise BackendNotAvailableError(f"LLM backend initialization failed: {e}")
    
    def _do_extract(self, content: str, ontology: OntologySchema, doc_id: str, namespace: str = None) -> LexicalGraph:
        """Perform schema-driven LLM extraction.
        
        Args:
            content: Curated document content
            ontology: Normalized ontology schema
            doc_id: Document identifier
            namespace: Optional namespace for organizing debug output
        
        Returns:
            LexicalGraph with extracted mentions and relations
        
        Raises:
            ExtractionError: If extraction fails
            ConsecutiveFailureError: If too many consecutive failures
        """
        # Check consecutive failure threshold
        if self.consecutive_failures >= self.consecutive_failure_threshold:
            raise ConsecutiveFailureError(
                self.consecutive_failures, 
                self.consecutive_failure_threshold,
                f"Aborting extraction after {self.consecutive_failures} consecutive failures"
            )
        
        start_time = time.time()
        
        # Check if content is too short for meaningful extraction
        content_words = len(content.split()) if content else 0
        if content_words < 20:
            logger.warning(f"Content too short for extraction", extra={
                "doc_id": doc_id,
                "content_length": len(content) if content else 0,
                "word_count": content_words
            })
            # Return empty graph for very short content
            return LexicalGraph(
                mentions=[],
                relations=[],
                metadata={
                    "backend": "llm",
                    "model_name": self.model_name,
                    "extraction_time": 0,
                    "skip_reason": "content_too_short",
                    "word_count": content_words
                }
            )
        
        try:
            # Convert ontology to entity config for schema-driven extraction
            entity_config = ontology.to_entity_config()
            
            logger.debug(f"Converted ontology to entity config", extra={
                "doc_id": doc_id,
                "core_entities": len([e for e in entity_config.get('entities', []) if not e.get('is_occurrence_entity')]),
                "occurrence_entities": len([e for e in entity_config.get('entities', []) if e.get('is_occurrence_entity')])
            })
            
            # Use schema-driven extraction
            result = extract_entities_from_document(
                entity_config=entity_config,
                doc_id=doc_id,
                doc_title=doc_id,  # Use doc_id as title if not available
                doc_text=content,
                llm_client=BedrockLLMClientAdapter(self.bedrock_client)
            )
            
            # Save extraction debug files
            if self.save_debug:
                self._save_extraction_debug(
                    doc_id=doc_id,
                    entity_config=entity_config,
                    content=content,
                    result=result,
                    namespace=namespace
                )
            
            # Convert schema-driven result to LexicalGraph
            graph = self._convert_to_lexical_graph(result, doc_id, content)
            
            # Update success metrics
            extraction_time = time.time() - start_time
            self.consecutive_failures = 0  # Reset on success
            self.total_calls += 1
            
            # Add timing and model info to metadata
            graph.metadata.update({
                "model_name": self.model_name,
                "extraction_time": extraction_time,
                "fake_mode": self.fake_mode,
                "extraction_approach": "schema_driven",
                "core_entities_count": len(result.get("core_entities", [])),
                "occurrence_entities_count": len(result.get("occurrence_entities", []))
            })
            
            logger.info(f"Schema-driven LLM extraction completed", extra={
                "doc_id": doc_id,
                "mentions": len(graph.mentions),
                "relations": len(graph.relations),
                "extraction_time": extraction_time,
                "consecutive_failures": self.consecutive_failures
            })
            
            return graph
            
        except Exception as e:
            # Update failure metrics
            self.consecutive_failures += 1
            self.total_failures += 1
            extraction_time = time.time() - start_time
            
            logger.error(f"Schema-driven LLM extraction failed", extra={
                "doc_id": doc_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "consecutive_failures": self.consecutive_failures,
                "extraction_time": extraction_time
            })
            
            # Re-raise specific exceptions or wrap in ExtractionError
            if isinstance(e, (ConsecutiveFailureError, ExtractionTimeoutError)):
                raise
            else:
                raise ExtractionError(f"Schema-driven LLM extraction failed for {doc_id}: {e}")
    
    def _convert_to_lexical_graph(self, result: Dict[str, Any], doc_id: str, content: str) -> LexicalGraph:
        """Convert schema-driven extraction result to LexicalGraph.
        
        Args:
            result: Schema-driven extraction result with core_entities and occurrence_entities
            doc_id: Document identifier
            content: Original document content
        
        Returns:
            LexicalGraph with mentions and relations
        """
        mentions = []
        relations = []
        
        # Track entity_id to name mapping for relations
        entity_map = {}
        
        # Process core entities
        for entity in result.get("core_entities", []):
            mention = self._entity_to_mention(entity, doc_id, is_occurrence=False)
            if mention:
                mentions.append(mention)
                entity_map[entity.get("entity_id")] = mention.text
        
        # Process occurrence entities and their relations
        for entity in result.get("occurrence_entities", []):
            mention = self._entity_to_mention(entity, doc_id, is_occurrence=True)
            if mention:
                mentions.append(mention)
                entity_map[entity.get("entity_id")] = mention.text
                
                # Extract relations from links
                for link in entity.get("links", []):
                    relation = LexicalRelation(
                        source_mention=mention.text,
                        target_mention=entity_map.get(link.get("entity_id"), link.get("entity_id")),
                        relation_type=link.get("relation_type", "RELATED_TO"),
                        confidence=1.0,
                        metadata={
                            "from_occurrence_entity": True,
                            "dependency": link.get("dependency", ""),
                            "source_entity_type": entity.get("type"),
                            "source_entity_id": entity.get("entity_id")
                        }
                    )
                    relations.append(relation)
        
        # Create graph
        graph = LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={
                "backend": "llm",
                "core_entities": len(result.get("core_entities", [])),
                "occurrence_entities": len(result.get("occurrence_entities", [])),
                "total_mentions": len(mentions),
                "total_relations": len(relations)
            }
        )
        
        return graph
    
    def _entity_to_mention(self, entity: Dict[str, Any], doc_id: str, is_occurrence: bool = False) -> Optional[LexicalMention]:
        """Convert entity dict to LexicalMention.
        
        Args:
            entity: Entity dictionary from schema-driven extraction
            doc_id: Document identifier
            is_occurrence: Whether this is an occurrence entity
        
        Returns:
            LexicalMention or None if entity is invalid
        """
        try:
            # Extract properties
            entity_type = entity.get("type")
            properties = entity.get("properties", {})
            
            # Get the primary property value as text
            # For occurrence entities, prefer "value" property
            # For core entities, prefer "name" or first non-empty property
            text = None
            if is_occurrence:
                text = properties.get("value") or properties.get("name")
            else:
                text = properties.get("name")
            
            # Fallback to first non-empty property
            if not text:
                for key, value in properties.items():
                    if value:
                        text = str(value)
                        break
            
            # Last resort: use entity_id
            if not text:
                text = entity.get("entity_id", "UNKNOWN")
            
            # Get span information
            span_info = entity.get("span", {})
            start_offset = span_info.get("start_offset", 0)
            end_offset = span_info.get("end_offset", start_offset + len(text))
            
            # Create mention
            mention = LexicalMention(
                text=text,
                entity_type=entity_type,
                start_offset=start_offset,
                end_offset=end_offset,
                confidence=1.0,
                features=properties,
                metadata={
                    "entity_id": entity.get("entity_id"),
                    "is_occurrence_entity": is_occurrence,
                    "doc_id": doc_id
                }
            )
            
            return mention
            
        except Exception as e:
            logger.warning(f"Failed to convert entity to mention: {e}", extra={
                "entity": entity,
                "doc_id": doc_id
            })
            return None
    
    def _save_extraction_debug(self, doc_id: str, entity_config: Dict, content: str, 
                              result: Dict[str, Any], namespace: str = None):
        """Save schema-driven extraction debug files.
        
        Args:
            doc_id: Document identifier
            entity_config: Entity configuration sent to LLM
            content: Original curated content
            result: Extraction result with core_entities and occurrence_entities
            namespace: Optional namespace (defaults to 'default')
        """
        try:
            # Use provided namespace or default
            if not namespace:
                namespace = "default"
            
            # Create extraction output directory
            output_dir = Path("output") / "markdowns" / namespace / "extractions"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize doc_id for filename
            safe_doc_id = doc_id.replace("/", "_").replace("\\", "_").replace(":", "_")
            
            # Save files
            base_path = output_dir / safe_doc_id
            
            # 1. Save entity config
            config_file = base_path.with_suffix(".entity_config.json")
            config_file.write_text(json.dumps(entity_config, indent=2), encoding='utf-8')
            
            # 2. Save original content
            content_file = base_path.with_suffix(".content.txt")
            content_file.write_text(content, encoding='utf-8')
            
            # 3. Save extraction result
            result_file = base_path.with_suffix(".result.json")
            result_file.write_text(json.dumps(result, indent=2), encoding='utf-8')
            
            # 4. Save metadata
            metadata = {
                "doc_id": doc_id,
                "namespace": namespace,
                "model": self.model_name,
                "backend": "llm_schema_driven",
                "content_length": len(content),
                "core_entities_count": len(result.get("core_entities", [])),
                "occurrence_entities_count": len(result.get("occurrence_entities", [])),
                "entity_types_in_config": len(entity_config.get("entities", [])),
                "files": {
                    "entity_config": str(config_file),
                    "content": str(content_file),
                    "result": str(result_file)
                }
            }
            metadata_file = base_path.with_suffix(".metadata.json")
            metadata_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            
            logger.debug(f"Saved schema-driven extraction debug files", extra={
                "doc_id": doc_id,
                "output_dir": str(output_dir),
                "files_saved": 4
            })
            
        except Exception as e:
            # Don't fail extraction if debug save fails
            logger.warning(f"Failed to save schema-driven extraction debug files: {e}", extra={
                "doc_id": doc_id
            })
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get detailed backend information."""
        info = super().get_backend_info()
        
        info.update({
            "model_name": self.model_name,
            "region": self.region,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "consecutive_failure_threshold": self.consecutive_failure_threshold,
            "fake_mode": self.fake_mode,
            "save_debug": self.save_debug,
            "consecutive_failures": self.consecutive_failures,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "success_rate": (self.total_calls - self.total_failures) / max(self.total_calls, 1),
            "extraction_approach": "schema_driven"
        })
        
        # Add client info if available
        if self.bedrock_client:
            client_info = self.bedrock_client.get_client_info()
            info["client_info"] = client_info
        
        return info
    
    def validate_configuration(self) -> bool:
        """Validate backend configuration and connectivity.
        
        Returns:
            True if backend is properly configured and ready
        """
        try:
            # Check if client is initialized
            if not self.bedrock_client:
                logger.warning("Bedrock client not initialized")
                return False
            
            # Test connectivity (only in non-fake mode)
            if not self.fake_mode:
                if not self.bedrock_client.validate_connection():
                    logger.warning("Bedrock connectivity test failed")
                    return False
            
            # Check consecutive failures
            if self.consecutive_failures >= self.consecutive_failure_threshold:
                logger.warning(f"Too many consecutive failures: {self.consecutive_failures}")
                return False
            
            logger.info("LLM backend configuration validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"LLM backend validation failed: {e}")
            return False
    
    def reset_failure_count(self):
        """Reset consecutive failure counter.
        
        Useful for manual recovery or when switching to different content.
        """
        logger.info(f"Resetting consecutive failure count from {self.consecutive_failures} to 0")
        self.consecutive_failures = 0
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics.
        
        Returns:
            Dictionary with extraction performance metrics
        """
        return {
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": (self.total_calls - self.total_failures) / max(self.total_calls, 1),
            "failure_rate": self.total_failures / max(self.total_calls, 1),
            "at_failure_threshold": self.consecutive_failures >= self.consecutive_failure_threshold
        }
