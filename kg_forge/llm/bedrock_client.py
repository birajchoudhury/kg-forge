"""
AWS Bedrock client integration for LLM extraction.

Handles communication with AWS Bedrock API using LlamaIndex.
"""
import json
import time
from typing import Dict, Any, Optional
import logging

# We'll implement these imports when we add the dependencies
try:
    from llama_index.llms.bedrock import BedrockLLM
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False

from kg_forge.extraction.exceptions import (
    BackendNotAvailableError, 
    CredentialsError, 
    ExtractionError,
    ExtractionTimeoutError
)

logger = logging.getLogger(__name__)


class BedrockClient:
    """Client for AWS Bedrock LLM API using LlamaIndex."""
    
    def __init__(self, 
                 model_name: str = "anthropic.claude-3-haiku-20240307-v1:0",
                 region: str = "us-east-1",
                 max_tokens: int = 4000,
                 temperature: float = 0.1,
                 timeout: int = 30):
        """Initialize Bedrock client.
        
        Args:
            model_name: Bedrock model identifier
            region: AWS region
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            timeout: Request timeout in seconds
        """
        if not BEDROCK_AVAILABLE:
            raise BackendNotAvailableError(
                "Bedrock dependencies not available. Install with: pip install llama-index-llms-bedrock boto3"
            )
        
        self.model_name = model_name
        self.region = region
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        
        self._llm = None
        self._last_call_time = 0
        self._min_call_interval = 1.0  # Minimum seconds between calls
        
        # Initialize the client
        self._init_client()
    
    def _init_client(self):
        """Initialize the LlamaIndex Bedrock LLM client."""
        try:
            self._llm = BedrockLLM(
                model=self.model_name,
                region_name=self.region,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            logger.info(f"Initialized Bedrock LLM client: {self.model_name} in {self.region}")
        except NoCredentialsError:
            raise CredentialsError(
                "AWS credentials not found. Configure via AWS CLI, environment variables, or IAM role."
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'UnauthorizedOperation':
                raise CredentialsError(f"AWS credentials lack Bedrock permissions: {e}")
            else:
                raise BackendNotAvailableError(f"Failed to initialize Bedrock client: {e}")
        except Exception as e:
            raise BackendNotAvailableError(f"Unexpected error initializing Bedrock: {e}")
    
    def _rate_limit(self):
        """Implement simple rate limiting."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_call_interval:
            sleep_time = self._min_call_interval - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
    
    def call_model(self, prompt: str, doc_id: str = None) -> Dict[str, Any]:
        """Call Bedrock model with the given prompt.
        
        Args:
            prompt: Input prompt for the model
            doc_id: Optional document ID for logging
        
        Returns:
            Dictionary containing response text, metadata, and timing
        
        Raises:
            ExtractionError: If the API call fails
            ExtractionTimeoutError: If the call exceeds timeout
        """
        self._rate_limit()
        
        start_time = time.time()
        
        try:
            logger.info(f"Calling Bedrock model {self.model_name}", extra={
                "doc_id": doc_id,
                "prompt_length": len(prompt),
                "max_tokens": self.max_tokens
            })
            
            # Use LlamaIndex's complete method
            response = self._llm.complete(prompt)
            
            end_time = time.time()
            self._last_call_time = end_time
            call_duration = end_time - start_time
            
            # Extract response text
            response_text = response.text
            
            logger.info(f"Bedrock call completed", extra={
                "doc_id": doc_id,
                "response_length": len(response_text),
                "call_duration": call_duration
            })
            
            return {
                "response_text": response_text,
                "model_name": self.model_name,
                "call_duration": call_duration,
                "prompt_length": len(prompt),
                "response_length": len(response_text),
                "timestamp": start_time
            }
            
        except Exception as e:
            self._last_call_time = time.time()
            
            if "timeout" in str(e).lower():
                raise ExtractionTimeoutError(f"Bedrock call timed out after {self.timeout}s: {e}")
            elif "rate" in str(e).lower() or "throttl" in str(e).lower():
                raise ExtractionError(f"Bedrock rate limit exceeded: {e}")
            else:
                logger.error(f"Bedrock call failed", extra={
                    "doc_id": doc_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                raise ExtractionError(f"Bedrock API call failed: {e}")
    
    def validate_connection(self) -> bool:
        """Test if the Bedrock connection is working.
        
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            # Test with a minimal prompt
            test_prompt = "Say 'test' in JSON format: {\"result\": \"test\"}"
            result = self.call_model(test_prompt, doc_id="validation_test")
            
            # Check if we got a reasonable response
            response_text = result.get("response_text", "").strip()
            return len(response_text) > 0 and "test" in response_text.lower()
            
        except Exception as e:
            logger.warning(f"Bedrock validation failed: {e}")
            return False
    
    def get_client_info(self) -> Dict[str, Any]:
        """Get client configuration and status information."""
        return {
            "model_name": self.model_name,
            "region": self.region,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "available": BEDROCK_AVAILABLE,
            "last_call_time": self._last_call_time
        }


class FakeBedrockClient:
    """Fake Bedrock client for testing when real API is not available."""
    
    def __init__(self, **kwargs):
        """Initialize fake client (accepts any arguments for compatibility)."""
        self.model_name = kwargs.get("model_name", "fake-claude")
        self.region = kwargs.get("region", "fake-region")
        self.call_count = 0
    
    def call_model(self, prompt: str, doc_id: str = None) -> Dict[str, Any]:
        """Return fake model response."""
        self.call_count += 1
        
        # Generate fake response that looks like entity extraction JSON
        fake_response = {
            "entities": [
                {
                    "type": "Product",
                    "name": "Test Product",
                    "confidence": 0.9
                },
                {
                    "type": "Technology", 
                    "name": "Test Technology",
                    "confidence": 0.85
                }
            ],
            "relations": [
                {
                    "source": "Test Product",
                    "target": "Test Technology", 
                    "type": "USES",
                    "confidence": 0.8
                }
            ]
        }
        
        response_text = json.dumps(fake_response, indent=2)
        
        return {
            "response_text": response_text,
            "model_name": self.model_name,
            "call_duration": 0.5,
            "prompt_length": len(prompt),
            "response_length": len(response_text),
            "timestamp": time.time(),
            "fake": True
        }
    
    def validate_connection(self) -> bool:
        """Fake validation always succeeds."""
        return True
    
    def get_client_info(self) -> Dict[str, Any]:
        """Get fake client info."""
        return {
            "model_name": self.model_name,
            "region": self.region,
            "available": True,
            "fake": True,
            "call_count": self.call_count
        }