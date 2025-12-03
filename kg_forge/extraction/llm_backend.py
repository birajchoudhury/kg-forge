"""
LLM-based extraction backend using AWS Bedrock.

Implements entity and relation extraction using large language models.
"""
import time
from typing import Dict, Any, Optional
import logging

from kg_forge.models.lexical import LexicalGraph
from kg_forge.ontology.base import OntologyPack
from kg_forge.extraction.interface import BaseExtractionBackend
from kg_forge.extraction.exceptions import (
    ExtractionError, 
    BackendNotAvailableError,
    ConsecutiveFailureError,
    ExtractionTimeoutError
)
from kg_forge.llm.bedrock_client import BedrockClient, FakeBedrockClient
from kg_forge.llm.prompt_builder import PromptBuilder
from kg_forge.llm.response_parser import ResponseParser

logger = logging.getLogger(__name__)


class LLMExtractionBackend(BaseExtractionBackend):
    """LLM-based extraction backend using AWS Bedrock.
    
    Extracts entities and relations by sending prompts to AWS Bedrock models
    and parsing the JSON responses.
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
                 strict_parsing: bool = True):
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
            strict_parsing: Strict JSON parsing (fail on errors)
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
        self.strict_parsing = strict_parsing
        
        # State tracking
        self.consecutive_failures = 0
        self.total_calls = 0
        self.total_failures = 0
        
        # Initialize components
        self.bedrock_client = None
        self.prompt_builder = None
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize backend components."""
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
            
            logger.info(f"LLM extraction backend initialized", extra={
                "model": self.model_name,
                "region": self.region,
                "fake_mode": self.fake_mode
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM backend: {e}")
            raise BackendNotAvailableError(f"LLM backend initialization failed: {e}")
    
    def _do_extract(self, content: str, ontology: OntologyPack, doc_id: str) -> LexicalGraph:
        """Perform LLM-based extraction.
        
        Args:
            content: Curated document content
            ontology: Active ontology pack
            doc_id: Document identifier
        
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
        
        # Initialize prompt builder with ontology
        if not self.prompt_builder:
            self.prompt_builder = PromptBuilder(ontology)
        
        start_time = time.time()
        
        try:
            # Build extraction prompt
            prompt = self.prompt_builder.build_extraction_prompt(content)
            
            logger.debug(f"Built extraction prompt", extra={
                "doc_id": doc_id,
                "prompt_length": len(prompt),
                "content_length": len(content)
            })
            
            # Call LLM with retries
            response = self._call_llm_with_retries(prompt, doc_id)
            
            # Parse response into LexicalGraph
            parser = ResponseParser(doc_id, strict_parsing=self.strict_parsing)
            graph = parser.parse_extraction_result(response["response_text"], content)
            
            # Update success metrics
            extraction_time = time.time() - start_time
            self.consecutive_failures = 0  # Reset on success
            self.total_calls += 1
            
            # Add timing and model info to metadata
            graph.metadata.update({
                "model_name": self.model_name,
                "extraction_time": extraction_time,
                "prompt_length": len(prompt),
                "response_length": len(response["response_text"]),
                "call_duration": response.get("call_duration", 0),
                "fake_mode": self.fake_mode
            })
            
            logger.info(f"LLM extraction completed", extra={
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
            
            logger.error(f"LLM extraction failed", extra={
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
                raise ExtractionError(f"LLM extraction failed for {doc_id}: {e}")
    
    def _call_llm_with_retries(self, prompt: str, doc_id: str) -> Dict[str, Any]:
        """Call LLM with retry logic.
        
        Args:
            prompt: Prompt to send to model
            doc_id: Document ID for logging
        
        Returns:
            Response dictionary from Bedrock client
        
        Raises:
            ExtractionError: If all retries are exhausted
        """
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"LLM call attempt {attempt}/{self.max_retries}", extra={
                    "doc_id": doc_id,
                    "model": self.model_name
                })
                
                response = self.bedrock_client.call_model(prompt, doc_id)
                
                logger.debug(f"LLM call succeeded on attempt {attempt}", extra={
                    "doc_id": doc_id,
                    "response_length": len(response["response_text"])
                })
                
                return response
                
            except Exception as e:
                last_error = e
                
                logger.warning(f"LLM call attempt {attempt} failed", extra={
                    "doc_id": doc_id,
                    "attempt": attempt,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                
                # Don't retry on certain error types
                if isinstance(e, ExtractionTimeoutError):
                    break
                
                # Wait before retry (exponential backoff)
                if attempt < self.max_retries:
                    wait_time = 2 ** (attempt - 1)  # 1, 2, 4 seconds
                    logger.debug(f"Waiting {wait_time}s before retry", extra={"doc_id": doc_id})
                    time.sleep(wait_time)
        
        # All retries exhausted
        raise ExtractionError(f"LLM call failed after {self.max_retries} attempts: {last_error}")
    
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
            "strict_parsing": self.strict_parsing,
            "consecutive_failures": self.consecutive_failures,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "success_rate": (self.total_calls - self.total_failures) / max(self.total_calls, 1)
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