"""
Tests for response parser functionality.
"""

from kg_forge.llm.parser import ResponseParser
from kg_forge.llm.client import ExtractedEntity, ExtractionResult
from kg_forge.llm.exceptions import ParseError, ValidationError


class TestResponseParser:
    """Tests for ResponseParser class."""
    
    def test_parse_valid_response(self):
        """Test parsing valid JSON response."""
        parser = ResponseParser()
        
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": "Knowledge Discovery",
              "confidence": 0.92
            },
            {
              "type_id": "engineering_team",
              "name": "Platform Engineering",
              "confidence": 0.89
            }
          ]
        }
        """
        
        result = parser.parse_extraction_result(response_text)
        
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 2
        
        # Check first entity
        entity1 = result.entities[0]
        assert entity1.type == "product"
        assert entity1.name == "Knowledge Discovery"
        assert entity1.confidence == 0.92
        
        # Check second entity
        entity2 = result.entities[1]
        assert entity2.type == "engineering_team"
        assert entity2.name == "Platform Engineering"
        assert entity2.confidence == 0.89
    
    def test_parse_empty_entities(self):
        """Test parsing response with empty entities list."""
        parser = ResponseParser()
        
        response_text = '{"entities": []}'
        
        result = parser.parse_extraction_result(response_text)
        
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
    
    def test_parse_entities_without_confidence(self):
        """Test parsing entities without confidence field (should default to 1.0)."""
        parser = ResponseParser()
        
        response_text = """
        {
          "entities": [
            {
              "type_id": "technology",
              "name": "Python"
            }
          ]
        }
        """
        
        result = parser.parse_extraction_result(response_text)
        
        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.type == "technology"
        assert entity.name == "Python"
        assert entity.confidence == 1.0
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        parser = ResponseParser()
        
        invalid_json = '{"entities": [{"type": "Product", "name": "Test"'  # Missing closing brackets
        
        try:
            parser.parse_extraction_result(invalid_json)
            assert False, "Expected ParseError"
        except ParseError as e:
            assert "Invalid JSON response" in str(e)
    
    def test_parse_missing_entities_field(self):
        """Test parsing JSON without entities field."""
        parser = ResponseParser()
        
        response_text = '{"wrong_field": []}'
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "missing 'entities' field" in str(e)
    
    def test_parse_non_dict_response(self):
        """Test parsing JSON that's not a dictionary."""
        parser = ResponseParser()
        
        response_text = '["not", "a", "dict"]'
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "missing 'entities' field" in str(e)
    
    def test_parse_entity_missing_required_fields(self):
        """Test parsing entity missing required fields."""
        parser = ResponseParser()
        
        # Missing 'name' field
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "confidence": 0.9
            }
          ]
        }
        """
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "missing required 'type_id' or 'name' field" in str(e)
    
    def test_parse_entity_invalid_type_field(self):
        """Test parsing entity with invalid type field."""
        parser = ResponseParser()
        
        # Empty type field
        response_text = """
        {
          "entities": [
            {
              "type_id": "",
              "name": "Valid Name"
            }
          ]
        }
        """
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "must be a non-empty string" in str(e)
    
    def test_parse_entity_invalid_name_field(self):
        """Test parsing entity with invalid name field."""
        parser = ResponseParser()
        
        # Non-string name field
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": 123
            }
          ]
        }
        """
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "must be a non-empty string" in str(e)
    
    def test_parse_entity_invalid_confidence(self):
        """Test parsing entity with invalid confidence value."""
        parser = ResponseParser()
        
        # Confidence out of range
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": "Valid Product",
              "confidence": 1.5
            }
          ]
        }
        """
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "between 0.0 and 1.0" in str(e)
    
    def test_parse_entity_non_dict(self):
        """Test parsing entity that's not a dictionary."""
        parser = ResponseParser()
        
        response_text = """
        {
          "entities": [
            "not a dict"
          ]
        }
        """
        
        try:
            parser.parse_extraction_result(response_text)
            assert False, "Expected ValidationError"
        except ValidationError as e:
            assert "must be a dictionary" in str(e)
    
    def test_parse_with_whitespace(self):
        """Test parsing response with extra whitespace."""
        parser = ResponseParser()
        
        response_text = """
        
        
        {
          "entities": [
            {
              "type_id": "  product  ",
              "name": "  Test Product  ",
              "confidence": 0.8
            }
          ]
        }
        
        
        """
        
        result = parser.parse_extraction_result(response_text)
        
        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.type == "product"  # Should be trimmed and normalized
        assert entity.name == "Test Product"  # Should be trimmed
        assert entity.confidence == 0.8
    
    def test_parse_confidence_integer(self):
        """Test parsing confidence as integer (should be converted to float)."""
        parser = ResponseParser()
        
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": "Test Product",
              "confidence": 1
            }
          ]
        }
        """
        
        result = parser.parse_extraction_result(response_text)
        
        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.confidence == 1.0
        assert isinstance(entity.confidence, float)