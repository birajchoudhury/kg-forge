"""
Tests for LLM error handling and retry logic.
"""

from unittest.mock import Mock, patch
from kg_forge.llm.client import BaseLLMExtractor, ExtractionResult
from kg_forge.llm.exceptions import LLMError, ParseError, ValidationError, ExtractionAbortError


class MockLLMExtractor(BaseLLMExtractor):
    """Mock LLM extractor for testing error handling."""
    
    def __init__(self, responses=None, fail_count=0):
        super().__init__()
        self.responses = responses or []
        self.fail_count = fail_count
        self.call_count = 0
    
    def _call_llm(self, prompt: str) -> str:
        """Mock LLM call that can simulate failures."""
        self.call_count += 1
        
        if self.call_count <= self.fail_count:
            raise LLMError(f"Simulated failure {self.call_count}")
        
        if self.responses:
            return self.responses[min(self.call_count - 1, len(self.responses) - 1)]
        
        # Default successful response
        return '{"entities": [{"type_id": "product", "name": "Test", "confidence": 0.9}]}'


class TestErrorHandling:
    """Tests for error handling and retry logic."""
    
    def test_successful_extraction_resets_failure_count(self):
        """Test that successful extraction resets consecutive failure counter."""
        extractor = MockLLMExtractor()
        
        # Simulate some failures first
        extractor.consecutive_failures = 5
        
        # Successful call should reset counter
        result = extractor.extract_entities("test prompt")
        
        assert isinstance(result, ExtractionResult)
        assert extractor.consecutive_failures == 0
    
    def test_single_failure_with_retry_success(self):
        """Test single failure followed by retry success."""
        # Fail once, then succeed
        extractor = MockLLMExtractor(fail_count=1)
        
        result = extractor.extract_entities("test prompt")
        
        assert isinstance(result, ExtractionResult)
        assert extractor.call_count == 2  # Failed once, then succeeded
        assert extractor.consecutive_failures == 0
    
    def test_double_failure_raises_exception(self):
        """Test that two failures in a row raise the exception."""
        # Fail twice (both initial call and retry)
        extractor = MockLLMExtractor(fail_count=2)
        
        try:
            extractor.extract_entities("test prompt")
            assert False, "Expected LLMError to be raised"
        except LLMError as e:
            assert "Simulated failure 2" in str(e)
            assert extractor.call_count == 2
            assert extractor.consecutive_failures == 2
    
    def test_consecutive_failure_counter_increment(self):
        """Test that consecutive failure counter increments correctly."""
        extractor = MockLLMExtractor(fail_count=10)  # Fail many times
        
        # Make several failed calls
        for i in range(5):
            try:
                extractor.extract_entities(f"test prompt {i}")
            except LLMError:
                pass  # Expected
        
        assert extractor.consecutive_failures == 10  # 5 calls * 2 attempts each
    
    def test_abort_after_max_consecutive_failures(self):
        """Test abort after exceeding max consecutive failures."""
        extractor = MockLLMExtractor(fail_count=100)  # Always fail
        extractor.max_consecutive_failures = 3  # Lower threshold for testing
        
        # Set initial failure count to 2, so next failures will reach and exceed threshold
        extractor.consecutive_failures = 2
        
        # Make calls until abort
        with_abort = False
        try:
            # This call will increment consecutive_failures to 3, then to 4 (exceeding threshold)
            extractor.extract_entities("test prompt")
        except ExtractionAbortError as e:
            with_abort = True
            assert "Exceeded maximum consecutive failures (3)" in str(e)
        
        assert with_abort, "Expected ExtractionAbortError to be raised"
    
    @patch('kg_forge.llm.parser.ResponseParser')
    def test_parse_error_handling(self, mock_parser_class):
        """Test handling of parse errors with retry."""
        # Setup mock parser to fail first, then succeed
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # First call fails with ParseError, second succeeds
        mock_parser.parse_extraction_result.side_effect = [
            ParseError("Invalid JSON"),
            ExtractionResult(entities=[])
        ]
        
        extractor = MockLLMExtractor(responses=["invalid json", "valid json"])
        
        # Should succeed after retry
        result = extractor.extract_entities("test prompt")
        
        assert isinstance(result, ExtractionResult)
        assert extractor.call_count == 2  # Called twice due to retry
        assert mock_parser.parse_extraction_result.call_count == 2
    
    @patch('kg_forge.llm.parser.ResponseParser')
    def test_validation_error_handling(self, mock_parser_class):
        """Test handling of validation errors with retry."""
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # Both calls fail with ValidationError
        mock_parser.parse_extraction_result.side_effect = [
            ValidationError("Missing entities field"),
            ValidationError("Missing entities field")
        ]
        
        extractor = MockLLMExtractor()
        
        try:
            extractor.extract_entities("test prompt")
            assert False, "Expected ValidationError to be raised"
        except ValidationError as e:
            assert "Missing entities field" in str(e)
            assert extractor.call_count == 2  # Tried twice
            assert extractor.consecutive_failures == 2
    
    def test_unexpected_exception_handling(self):
        """Test handling of unexpected exceptions."""
        extractor = MockLLMExtractor()
        
        # Mock _call_llm to raise unexpected exception
        def raise_unexpected(prompt):
            raise RuntimeError("Unexpected error")
        
        extractor._call_llm = raise_unexpected
        
        try:
            extractor.extract_entities("test prompt")
            assert False, "Expected RuntimeError to be raised"
        except RuntimeError as e:
            assert "Unexpected error" in str(e)
            assert extractor.consecutive_failures == 2  # Tried twice


class TestRetryLogic:
    """Tests specifically for retry logic."""
    
    def test_retry_exactly_once(self):
        """Test that retry happens exactly once."""
        extractor = MockLLMExtractor(fail_count=1)  # Fail first call, succeed second
        
        result = extractor.extract_entities("test prompt")
        
        assert isinstance(result, ExtractionResult)
        assert extractor.call_count == 2  # Original + 1 retry
    
    def test_no_retry_on_success(self):
        """Test that no retry happens when first call succeeds."""
        extractor = MockLLMExtractor(fail_count=0)  # Never fail
        
        result = extractor.extract_entities("test prompt")
        
        assert isinstance(result, ExtractionResult)
        assert extractor.call_count == 1  # Only original call
    
    def test_retry_preserves_prompt(self):
        """Test that retry uses the same prompt."""
        class PromptCapturingExtractor(BaseLLMExtractor):
            def __init__(self):
                super().__init__()
                self.captured_prompts = []
                self.call_count = 0
            
            def _call_llm(self, prompt: str) -> str:
                self.captured_prompts.append(prompt)
                self.call_count += 1
                
                if self.call_count == 1:
                    raise LLMError("First call failed")
                
                return '{"entities": []}'
        
        extractor = PromptCapturingExtractor()
        test_prompt = "Extract entities from this test document."
        
        extractor.extract_entities(test_prompt)
        
        # Both calls should have used same prompt
        assert len(extractor.captured_prompts) == 2
        assert extractor.captured_prompts[0] == test_prompt
        assert extractor.captured_prompts[1] == test_prompt