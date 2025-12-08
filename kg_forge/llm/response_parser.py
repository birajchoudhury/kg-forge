"""
LLM response parser for entity extraction.

Parses JSON responses from LLM models into LexicalGraph objects.
"""
import json
import re
from typing import Dict, Any, List, Tuple, Optional
import logging

from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.extraction.exceptions import ParseError, ValidationError

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parses LLM responses into structured extraction results."""
    
    def __init__(self, doc_id: str, strict_parsing: bool = False):
        """Initialize response parser.
        
        Args:
            doc_id: Document ID for mention/relation ID generation
            strict_parsing: If True, fail on any parsing errors
        """
        self.doc_id = doc_id
        self.strict_parsing = strict_parsing
        self._mention_counter = 0
        self._relation_counter = 0
        self._mention_name_to_id = {}  # Maps entity names to mention IDs
    
    def parse_extraction_result(self, response_text: str, 
                              original_content: str = None) -> LexicalGraph:
        """Parse LLM response into LexicalGraph.
        
        Args:
            response_text: Raw LLM response text
            original_content: Original document content for validation
        
        Returns:
            LexicalGraph containing parsed mentions and relations
        
        Raises:
            ParseError: If response cannot be parsed
            ValidationError: If parsed data is invalid
        """
        logger.debug(f"Parsing LLM response: {len(response_text)} characters")
        
        # Reset state for new parsing
        self._mention_counter = 0
        self._relation_counter = 0
        self._mention_name_to_id = {}
        
        try:
            # Extract and parse JSON from response
            json_data = self._extract_json_from_response(response_text)
            
            # Parse entities and relations
            mentions = self._parse_entities(json_data, original_content)
            relations = self._parse_relations(json_data, mentions)
            
            # Build metadata
            metadata = {
                "backend": "llm",
                "response_length": len(response_text),
                "parsed_entities": len(mentions),
                "parsed_relations": len(relations),
                "doc_id": self.doc_id
            }
            
            # Create and validate the graph
            graph = LexicalGraph(
                mentions=mentions,
                relations=relations,
                metadata=metadata
            )
            
            logger.info(f"Successfully parsed LLM response", extra={
                "doc_id": self.doc_id,
                "mentions": len(mentions),
                "relations": len(relations)
            })
            
            return graph
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in LLM response: {e}"
            logger.error(error_msg, extra={
                "doc_id": self.doc_id, 
                "response_length": len(response_text),
                "response_preview": response_text[:500] if response_text else "EMPTY_RESPONSE",
                "response_is_empty": not response_text.strip() if response_text else True
            })
            # Return empty graph instead of raising error for invalid JSON
            logger.warning(f"Returning empty graph due to invalid JSON", extra={"doc_id": self.doc_id})
            return LexicalGraph(mentions=[], relations=[], metadata={"error": "invalid_json"})
        
        except (KeyError, TypeError, ValueError) as e:
            error_msg = f"Invalid response structure: {e}"
            logger.error(error_msg, extra={"doc_id": self.doc_id})
            if self.strict_parsing:
                raise ParseError(error_msg)
            else:
                # Return empty graph on parsing errors in non-strict mode
                return LexicalGraph(mentions=[], relations=[], metadata={"backend": "llm", "parse_error": str(e)})
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON object from potentially verbose LLM response.
        
        Args:
            response_text: Raw LLM response
        
        Returns:
            Parsed JSON object
        
        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try direct JSON parsing first
        response_text = response_text.strip()
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Look for JSON blocks in markdown-style code blocks
        json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL | re.IGNORECASE)
        for block in json_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue
        
        # Look for JSON objects anywhere in the text
        json_pattern = r'\{[^}]*"entities"[^}]*\}'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # Look for the largest JSON-like structure
        brace_level = 0
        json_start = -1
        
        for i, char in enumerate(response_text):
            if char == '{':
                if brace_level == 0:
                    json_start = i
                brace_level += 1
            elif char == '}':
                brace_level -= 1
                if brace_level == 0 and json_start >= 0:
                    # Found a complete JSON object
                    json_candidate = response_text[json_start:i+1]
                    try:
                        return json.loads(json_candidate)
                    except json.JSONDecodeError:
                        continue
        
        # If all else fails, check if response is empty or very short
        if not response_text or len(response_text.strip()) < 10:
            logger.warning(f"Empty or very short LLM response", extra={
                "doc_id": self.doc_id,
                "response_length": len(response_text) if response_text else 0
            })
            if not self.strict_parsing:
                # Return empty structure for empty responses in non-strict mode
                return {"entities": [], "relations": []}
        
        # If all else fails, raise error
        raise json.JSONDecodeError("No valid JSON found in response", response_text, 0)
    
    def _parse_entities(self, json_data: Dict[str, Any], 
                       original_content: str = None) -> List[LexicalMention]:
        """Parse entities from JSON data into LexicalMention objects.
        
        Args:
            json_data: Parsed JSON response
            original_content: Original document content for offset validation
        
        Returns:
            List of LexicalMention objects
        """
        mentions = []
        entities_data = json_data.get("entities", [])
        
        if not isinstance(entities_data, list):
            if self.strict_parsing:
                raise ValidationError("'entities' field must be an array")
            entities_data = []
        
        for i, entity_data in enumerate(entities_data):
            try:
                mention = self._parse_single_entity(entity_data, original_content)
                mentions.append(mention)
                
                # Map entity name to mention ID for relation parsing
                entity_name = entity_data.get("name", "").strip()
                if entity_name:
                    self._mention_name_to_id[entity_name] = mention.id
                    
            except (KeyError, TypeError, ValueError) as e:
                error_msg = f"Error parsing entity {i}: {e}"
                logger.warning(error_msg, extra={"doc_id": self.doc_id, "entity_data": entity_data})
                
                if self.strict_parsing:
                    raise ValidationError(error_msg)
                # Skip invalid entities in non-strict mode
        
        return mentions
    
    def _parse_single_entity(self, entity_data: Dict[str, Any], 
                           original_content: str = None) -> LexicalMention:
        """Parse a single entity into LexicalMention.
        
        Args:
            entity_data: Single entity from JSON response
            original_content: Original content for validation
        
        Returns:
            LexicalMention object
        
        Raises:
            ValidationError: If entity data is invalid
        """
        # Extract required fields
        entity_type = entity_data.get("type", "").strip()
        entity_name = entity_data.get("name", "").strip()
        
        if not entity_type:
            raise ValidationError("Entity missing required 'type' field")
        if not entity_name:
            raise ValidationError("Entity missing required 'name' field")
        
        # Extract offsets (with fallbacks)
        start_offset = entity_data.get("start_offset", 0)
        end_offset = entity_data.get("end_offset", len(entity_name))
        
        # Validate and correct offsets if we have original content
        if original_content and start_offset >= 0 and end_offset <= len(original_content):
            actual_text = original_content[start_offset:end_offset]
            if actual_text.strip() != entity_name.strip():
                # LLM-provided offsets are incorrect, find the correct ones
                corrected_offsets = self._find_entity_offsets(entity_name, original_content)
                if corrected_offsets:
                    start_offset, end_offset = corrected_offsets
                    logger.debug(f"Corrected offsets for entity '{entity_name}': "
                               f"{start_offset}-{end_offset}",
                               extra={"doc_id": self.doc_id})
                else:
                    # Could not find entity in content - use safe defaults
                    # This is expected for inferred/conceptual entities
                    logger.debug(f"Could not locate entity '{entity_name}' in content "
                                f"(LLM may have inferred conceptual entity)", 
                                extra={"doc_id": self.doc_id})
                    start_offset = 0
                    end_offset = len(entity_name)
        elif original_content:
            # Invalid offset range, try to find correct offsets
            corrected_offsets = self._find_entity_offsets(entity_name, original_content)
            if corrected_offsets:
                start_offset, end_offset = corrected_offsets
            else:
                # Use safe defaults
                start_offset = 0  
                end_offset = len(entity_name)
        
        # Build features
        features = {
            "backend": "llm",
            "confidence": entity_data.get("confidence", 1.0),
        }
        
        # Add optional context
        if "context" in entity_data:
            features["context"] = entity_data["context"]
        
        # Generate mention ID
        self._mention_counter += 1
        mention_id = f"{self.doc_id}_mention_{self._mention_counter}"
        
        return LexicalMention(
            id=mention_id,
            doc_id=self.doc_id,
            entity_type=entity_type,
            surface=entity_name,
            start_offset=start_offset,
            end_offset=end_offset,
            features=features
        )
    
    def _find_entity_offsets(self, entity_name: str, 
                           content: str) -> Optional[Tuple[int, int]]:
        """Find actual offsets of entity in content using multiple strategies.
        
        Args:
            entity_name: Entity name to find
            content: Document content to search
        
        Returns:
            Tuple of (start_offset, end_offset) or None if not found
        """
        import re
        
        # Strategy 1: Exact match
        start_idx = content.find(entity_name)
        if start_idx >= 0:
            return (start_idx, start_idx + len(entity_name))
        
        # Strategy 2: Case-insensitive exact match
        lower_content = content.lower()
        lower_name = entity_name.lower()
        start_idx = lower_content.find(lower_name)
        if start_idx >= 0:
            return (start_idx, start_idx + len(entity_name))
        
        # Strategy 3: Word boundary match (handles punctuation)
        pattern = r'\b' + re.escape(entity_name) + r'\b'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return (match.start(), match.end())
        
        # Strategy 4: Strip common markdown formatting
        stripped_name = entity_name.strip('*_`[]() ')
        if stripped_name != entity_name and len(stripped_name) > 2:
            # Try again with stripped name
            return self._find_entity_offsets(stripped_name, content)
        
        # Strategy 5: Try finding partial matches for multi-word entities
        if ' ' in entity_name:
            # Try finding the first word as a fallback
            first_word = entity_name.split()[0]
            if len(first_word) > 3:  # Only for meaningful words
                return self._find_entity_offsets(first_word, content)
        
        return None
    
    def _parse_relations(self, json_data: Dict[str, Any], 
                        mentions: List[LexicalMention]) -> List[LexicalRelation]:
        """Parse relations from JSON data into LexicalRelation objects.
        
        Args:
            json_data: Parsed JSON response
            mentions: List of parsed mentions
        
        Returns:
            List of LexicalRelation objects
        """
        relations = []
        relations_data = json_data.get("relations", [])
        
        if not isinstance(relations_data, list):
            if self.strict_parsing:
                raise ValidationError("'relations' field must be an array")
            relations_data = []
        
        for i, relation_data in enumerate(relations_data):
            try:
                relation = self._parse_single_relation(relation_data, mentions)
                if relation:  # Only add if successfully parsed
                    relations.append(relation)
                    
            except (KeyError, TypeError, ValueError) as e:
                error_msg = f"Error parsing relation {i}: {e}"
                logger.warning(error_msg, extra={"doc_id": self.doc_id, "relation_data": relation_data})
                
                if self.strict_parsing:
                    raise ValidationError(error_msg)
                # Skip invalid relations in non-strict mode
        
        return relations
    
    def _parse_single_relation(self, relation_data: Dict[str, Any], 
                             mentions: List[LexicalMention]) -> Optional[LexicalRelation]:
        """Parse a single relation into LexicalRelation.
        
        Args:
            relation_data: Single relation from JSON response
            mentions: Available mentions to link to
        
        Returns:
            LexicalRelation object or None if cannot be parsed
        """
        # Extract relation info
        source_name = relation_data.get("source_entity", "").strip()
        target_name = relation_data.get("target_entity", "").strip()
        relation_type = relation_data.get("relation_type", "").strip()
        
        if not all([source_name, target_name, relation_type]):
            logger.warning(f"Incomplete relation data", extra={"doc_id": self.doc_id})
            return None
        
        # Find corresponding mentions
        src_mention_id = self._mention_name_to_id.get(source_name)
        dst_mention_id = self._mention_name_to_id.get(target_name)
        
        if not src_mention_id or not dst_mention_id:
            # Try fuzzy matching by mention surface text
            src_mention_id = self._find_mention_by_surface(source_name, mentions)
            dst_mention_id = self._find_mention_by_surface(target_name, mentions)
        
        if not src_mention_id or not dst_mention_id:
            logger.warning(f"Could not link relation to mentions: {source_name} -> {target_name}",
                         extra={"doc_id": self.doc_id})
            return None
        
        # Skip self-loop relations (source == destination)
        if src_mention_id == dst_mention_id:
            logger.warning(f"Skipping self-loop relation: {source_name} -> {target_name}",
                         extra={"doc_id": self.doc_id})
            return None
        
        # Build features
        features = {
            "backend": "llm",
            "confidence": relation_data.get("confidence", 1.0),
        }
        
        if "context" in relation_data:
            features["context"] = relation_data["context"]
        
        # Generate relation ID
        self._relation_counter += 1
        relation_id = f"{self.doc_id}_relation_{self._relation_counter}"
        
        return LexicalRelation(
            id=relation_id,
            type=relation_type,
            src_mention_id=src_mention_id,
            dst_mention_id=dst_mention_id,
            features=features
        )
    
    def _find_mention_by_surface(self, entity_name: str, 
                               mentions: List[LexicalMention]) -> Optional[str]:
        """Find mention ID by matching surface text.
        
        Args:
            entity_name: Entity name to match
            mentions: Available mentions
        
        Returns:
            Mention ID or None if not found
        """
        # Try exact match
        for mention in mentions:
            if mention.surface == entity_name:
                return mention.id
        
        # Try case-insensitive match
        entity_lower = entity_name.lower()
        for mention in mentions:
            if mention.surface.lower() == entity_lower:
                return mention.id
        
        # Try substring match
        for mention in mentions:
            if entity_name in mention.surface or mention.surface in entity_name:
                return mention.id
        
        return None