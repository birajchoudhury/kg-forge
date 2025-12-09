"""
Schema-driven entity extraction using LLM.

This module implements a generic extraction pipeline that:
- Takes an entity configuration derived from an ontology
- Builds system and user prompts for the LLM
- Parses and validates the LLM's JSON response
- Returns structured entities with properties and links
"""
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """Abstract interface for LLM clients."""
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response from the LLM.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User message with task details
            
        Returns:
            LLM response as string
        """
        raise NotImplementedError("Subclasses must implement generate()")


def build_system_prompt() -> str:
    """Build the system prompt for schema-driven extraction.
    
    Returns:
        System prompt string instructing the LLM how to extract entities
    """
    return """You are an entity and relationship extraction engine.

You receive:
- An ENTITY CONFIG JSON that defines allowed entities:
  - each entity has: kind ("core" or "occurrence"), label, properties, relations, depends_on
- A single document's text plus simple metadata (doc_id, title)

Your task is to extract entity instances from the document according to the entity configuration.

You must:
- Extract entities and relationships from the document
- Respect the ENTITY CONFIG JSON strictly (do not invent new entity types or properties)
- Return ONLY valid JSON with this exact structure:

{
  "core_entities": [
    {
      "entity_id": "unique_string_id",
      "type": "EntityTypeName",
      "properties": {
        "propertyName": value_or_null
      },
      "span": {
        "start_offset": integer_or_null,
        "end_offset": integer_or_null
      }
    }
  ],
  "occurrence_entities": [
    {
      "entity_id": "unique_string_id",
      "type": "EntityTypeName",
      "properties": {
        "propertyName": value_or_null
      },
      "links": {
        "roleName": "entity_id_of_related_core_entity"
      },
      "span": {
        "start_offset": integer_or_null,
        "end_offset": integer_or_null
      }
    }
  ]
}

RULES:

1. Use ENTITY CONFIG as the source of truth
   - For each entity type in entity_config["entities"]:
     - Use exactly the property names given there.
     - For occurrence entities, they may inherit properties from base types like "Occurrence Entity"
       (such as "event date/time", "page number") even if defined separately.

2. Core vs occurrence entities
   - core_entities: entities with "kind": "core" that represent things that can exist independently 
     (e.g., Contract, Organization, Person, Clause Template).
   - occurrence_entities: entities with "kind": "occurrence" that represent events or instances that 
     depend on one or more core entities (e.g., Signature Event, Renewal Event, Clause Occurrence, 
     Price Increase Occurrence).
   - For each occurrence entity, you MUST:
     - Fill the "links" object according to depends_on:
       - role names come from depends_on[].role
       - values are the entity_id of the related core entity you created.
     - Attempt to populate meaningful properties whenever the document provides evidence.
     - Use "span.start_offset" and "span.end_offset" to point to the main place in the text where 
       that occurrence is expressed.

3. Populating properties (VERY IMPORTANT)
   - For each entity you output (core or occurrence):
     - For every property defined in ENTITY CONFIG for that entity type:
       - If the document clearly expresses a value, set that property to the best structured value 
         you can infer (string/number/boolean/date/datetime as appropriate).
       - If the information truly does not appear in the document, set the property to null.
   - Do NOT output entities where all properties are null and the span is null.
     - If you cannot populate at least one non-null property OR a non-null span for an occurrence 
       entity, omit that entity entirely.
   - For occurrence entities that inherit from base types (e.g., with properties like "event date/time" 
     and "page number"):
     - If you can infer an event date/time from nearby text, set "event date/time".
     - If you can infer which page the occurrence is on (from page markers or context), set "page number".
     - Otherwise, set them to null.

4. Clause Occurrence patterns (when this type exists in ENTITY CONFIG)
   - Use this when the document has clearly defined sections or clauses (e.g., headings like 
     "ARTICLE VII – TERM OF AGREEMENT AND TERMINATION").
   - Try to populate:
     - "clause type" (based on meaning: e.g., "term_termination", "confidentiality", "non_assignment", 
       "counterparts", "arbitration", etc.)
     - "section number" (e.g., "7.01")
     - "clause heading" (e.g., "TERM OF AGREEMENT AND TERMINATION")
     - "clause text" (the full text of the clause body, in a concise but faithful form)
     - "is standard clause" (true if the language looks boilerplate, false if it deviates)
     - "deviation type" and "risk label" if the clause deviates in a meaningful way; otherwise null.

5. Price Increase Occurrence patterns (when this type exists in ENTITY CONFIG)
   - Use this when the document describes price increases, escalators, fee changes, or inflation indexing.
   - Try to populate:
     - "price increase present": true if a price increase mechanism is described, otherwise false.
     - "increase type": e.g., "fixed_percent", "capped_index", "discretionary", "tiered".
     - "increase cap percent": numeric cap, if any (e.g., 3.0 for 3%).
     - "increase frequency": e.g., "annual", "biennial", "one_time".
     - "index reference": e.g., "CPI", or name of the index.
   - If no price increase is described, you may omit the entity OR set "price increase present": false 
     and keep other properties null.

6. Contract-specific property extraction
   - When extracting Contract entities, if the document contains different notice periods for each party:
     - Extract "notice period – board (days)" and "notice period – plan manager (days)" as integers 
       (e.g., 60, 90).
     - Do NOT leave these null if the information is present in the document.

7. Person + Signature Event extraction
   - If the document contains a signature block (names, titles, signature lines):
     - Create Person entities for each named signer with:
       - 'full name' from the text (e.g., 'Edward S. Wolyniec')
       - 'title' where available (e.g., 'CEO')
     - Create Signature Event entities with:
       - a link 'contract' to the relevant Contract
       - 'signer' links for each Person who signs
     - Do NOT omit Person or Signature Event if there is a visible signature block.

8. Spans and offsets
   - Offsets are character offsets in the provided document text string (0-indexed).
   - "start_offset" is the index of the first character of the main mention.
   - "end_offset" is the index just after the last character of the main mention.
   - If offsets are difficult to compute, you may set them to null, but try to set them when possible 
     for key clauses and events.

9. Relationships
   - Use the "relations" definitions in ENTITY CONFIG to guide how entities connect.
   - Primary responsibility:
     - For occurrence_entities: fill "links" using depends_on roles.
   - If you create Organization and Contract entities that are clearly parties to each other, create 
     the appropriate IS_PARTY_TO relationship if defined in ENTITY CONFIG.
   - Do not invent relations not listed in ENTITY CONFIG.

10. Output format
    - Return ONLY a JSON object with keys "core_entities" and "occurrence_entities".
    - Do not include comments, explanations, or extra keys.
    - The JSON MUST be syntactically valid.
    - No markdown code blocks, no preamble.
    - Each entity_id must be unique within the document.
    - If no entities are found, return: {"core_entities": [], "occurrence_entities": []}

EXAMPLES:

EXAMPLE 1 - Full extraction with Clause Occurrence and Price Increase:

ENTITY CONFIG (simplified):
{
  "entities": {
    "Contract": {
      "kind": "core",
      "properties": {
        "contract title": {"type": "string"},
        "effective date": {"type": "date"},
        "initial term (years)": {"type": "number"}
      }
    },
    "Clause Occurrence": {
      "kind": "occurrence",
      "properties": {
        "clause type": {"type": "string"},
        "section number": {"type": "string"},
        "clause heading": {"type": "string"},
        "clause text": {"type": "string"},
        "is standard clause": {"type": "boolean"}
      },
      "depends_on": [{"role": "contract", "entity": "Contract", "cardinality": "1"}]
    },
    "Price Increase Occurrence": {
      "kind": "occurrence",
      "properties": {
        "price increase present": {"type": "boolean"},
        "increase type": {"type": "string"},
        "increase cap percent": {"type": "number"},
        "increase frequency": {"type": "string"}
      },
      "depends_on": [{"role": "contract", "entity": "Contract", "cardinality": "1"}]
    }
  }
}

DOCUMENT TEXT:
"ADMINISTRATIVE SERVICES AGREEMENT
This Agreement is effective as of November 1, 2025.

ARTICLE VII – TERM OF AGREEMENT
Section 7.01. This Agreement shall continue for three (3) years and shall be automatically renewed 
from year to year unless terminated.

ARTICLE VI – COMPENSATION
Section 6.01. The monthly fee shall be 10,000 USD. Beginning year two, the fee shall increase by 
three percent (3%) per year, but in no event more than five percent (5%) in any year."

EXPECTED OUTPUT:
{
  "core_entities": [
    {
      "entity_id": "contract_1",
      "type": "Contract",
      "properties": {
        "contract title": "ADMINISTRATIVE SERVICES AGREEMENT",
        "effective date": "2025-11-01",
        "initial term (years)": 3
      },
      "span": {"start_offset": 0, "end_offset": 70}
    }
  ],
  "occurrence_entities": [
    {
      "entity_id": "clause_occurrence_1",
      "type": "Clause Occurrence",
      "properties": {
        "clause type": "term_termination",
        "section number": "7.01",
        "clause heading": "TERM OF AGREEMENT",
        "clause text": "This Agreement shall continue for three (3) years and shall be automatically renewed from year to year unless terminated.",
        "is standard clause": true
      },
      "links": {"contract": "contract_1"},
      "span": {"start_offset": 120, "end_offset": 250}
    },
    {
      "entity_id": "price_increase_1",
      "type": "Price Increase Occurrence",
      "properties": {
        "price increase present": true,
        "increase type": "capped_index",
        "increase cap percent": 5.0,
        "increase frequency": "annual"
      },
      "links": {"contract": "contract_1"},
      "span": {"start_offset": 300, "end_offset": 450}
    }
  ]
}

EXAMPLE 2 - No price increase mechanism:

DOCUMENT TEXT:
"ARTICLE VI – COMPENSATION
Section 6.01. The monthly fee shall be 10,000 USD. Any future changes shall be mutually agreed in writing."

EXPECTED OUTPUT:
{
  "core_entities": [...],
  "occurrence_entities": [
    {
      "entity_id": "price_increase_1",
      "type": "Price Increase Occurrence",
      "properties": {
        "price increase present": false,
        "increase type": null,
        "increase cap percent": null,
        "increase frequency": null
      },
      "links": {"contract": "contract_1"},
      "span": {"start_offset": 50, "end_offset": 120}
    }
  ]
}

Remember: Your response must be valid, parseable JSON with no additional text."""


def build_user_prompt(
    entity_config: Dict[str, Any],
    doc_id: str,
    doc_title: str,
    doc_text: str
) -> str:
    """Build the user prompt with entity config and document.
    
    Args:
        entity_config: Entity configuration dictionary
        doc_id: Document identifier
        doc_title: Document title
        doc_text: Full document text
        
    Returns:
        User prompt string
    """
    entity_config_json = json.dumps(entity_config, indent=2)
    
    return f"""ENTITY CONFIG JSON:
{entity_config_json}

DOCUMENT METADATA:
- doc_id: {doc_id}
- doc_title: {doc_title}

DOCUMENT TEXT:
{doc_text}

Now extract all core and occurrence entities according to the ENTITY CONFIG.
Remember to follow the output JSON shape specified in the system prompt
and respond with ONLY valid JSON."""


def _is_occurrence_entity(entity_type: str, entity_config: Dict[str, Any]) -> bool:
    """Return True if this entity type is defined with kind == 'occurrence'.
    
    Args:
        entity_type: The entity type name
        entity_config: Entity configuration dictionary
        
    Returns:
        True if the entity type has kind='occurrence', False otherwise
    """
    entity_types = entity_config.get("entities", {})
    type_config = entity_types.get(entity_type, {})
    return type_config.get("kind") == "occurrence"


def _has_meaningful_properties(entity: Dict[str, Any], entity_config: Dict[str, Any]) -> bool:
    """Return True if the entity has at least one non-null, non-empty property.
    
    Args:
        entity: Entity dictionary
        entity_config: Entity configuration dictionary
        
    Returns:
        True if entity has at least one meaningful property value
    """
    entity_type = entity.get("type")
    if not entity_type:
        return False
    
    entity_types = entity_config.get("entities", {})
    type_config = entity_types.get(entity_type, {})
    defined_properties = type_config.get("properties", {})
    
    # Get actual property values from the entity
    properties = entity.get("properties", {})
    
    # Check if any defined property has a meaningful value
    for prop_name in defined_properties.keys():
        value = properties.get(prop_name)
        
        # Check if value is meaningful (not None, not empty string, not empty container)
        if value is not None:
            if isinstance(value, str) and value.strip():
                return True
            elif isinstance(value, (int, float, bool)):
                return True
            elif isinstance(value, (list, dict)) and value:
                return True
    
    return False


def _validate_person_entity(entity: Dict[str, Any]) -> bool:
    """Return True if Person entity has required 'full name' property.
    
    Args:
        entity: Entity dictionary
        
    Returns:
        True if entity has non-empty 'full name'
    """
    if entity.get("type") != "Person":
        return True  # Not a Person, skip validation
    
    properties = entity.get("properties", {})
    full_name = properties.get("full name")
    
    return full_name and isinstance(full_name, str) and full_name.strip()


def _validate_signature_event(entity: Dict[str, Any]) -> bool:
    """Return True if Signature Event has required links.
    
    Args:
        entity: Entity dictionary
        
    Returns:
        True if entity has contract link and at least one signer link
    """
    if entity.get("type") != "Signature Event":
        return True  # Not a Signature Event, skip validation
    
    links = entity.get("links", {})
    
    # Must have contract link
    if "contract" not in links or not links["contract"]:
        return False
    
    # Must have at least one signer
    signer_value = links.get("signer")
    if not signer_value:
        return False
    
    # signer can be a single ID or list of IDs
    if isinstance(signer_value, list):
        return len(signer_value) > 0
    else:
        return bool(signer_value)


def _validate_contract_notice_periods(entity: Dict[str, Any], doc_id: str) -> None:
    """Log warning if Contract entity is missing notice periods.
    
    Args:
        entity: Entity dictionary
        doc_id: Document identifier for logging
    """
    if entity.get("type") != "Contract":
        return
    
    properties = entity.get("properties", {})
    board_notice = properties.get("notice period – board (days)")
    manager_notice = properties.get("notice period – plan manager (days)")
    
    if board_notice is None and manager_notice is None:
        logger.warning(
            f"Contract entity in {doc_id} is missing both notice period properties. "
            f"This may indicate the LLM failed to extract termination notice requirements."
        )


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON from LLM response, handling common formatting issues.
    
    Args:
        response_text: Raw LLM response
        
    Returns:
        Parsed JSON object
        
    Raises:
        ValueError: If JSON cannot be parsed
    """
    # Try direct parsing first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks or other text
    response_text = response_text.strip()
    
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        lines = response_text.split('\n')
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = '\n'.join(lines).strip()
    
    # Try parsing again
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Last resort: find first { and last }
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        raise ValueError(
            f"Could not find valid JSON object in response. "
            f"Response started with: {response_text[:100]}"
        )
    
    json_substring = response_text[start_idx:end_idx + 1]
    try:
        return json.loads(json_substring)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from LLM response: {e}. "
            f"Extracted substring: {json_substring[:200]}"
        )


def _normalize_entity(
    entity: Dict[str, Any],
    entity_type_config: Dict[str, Any],
    is_occurrence: bool
) -> Dict[str, Any]:
    """Normalize and validate a single entity.
    
    Args:
        entity: Raw entity dict from LLM
        entity_type_config: Configuration for this entity type
        is_occurrence: Whether this is an occurrence entity
        
    Returns:
        Normalized entity dict
        
    Raises:
        ValueError: If entity is invalid
    """
    # Validate entity_id
    if "entity_id" not in entity or not entity["entity_id"]:
        raise ValueError(f"Entity missing required 'entity_id': {entity}")
    
    # Ensure properties exists
    if "properties" not in entity:
        entity["properties"] = {}
    elif not isinstance(entity["properties"], dict):
        raise ValueError(f"Entity properties must be a dict: {entity}")
    
    # Ensure span exists
    if "span" not in entity or not isinstance(entity["span"], dict):
        entity["span"] = {"start_offset": None, "end_offset": None}
    else:
        # Ensure span has required keys
        if "start_offset" not in entity["span"]:
            entity["span"]["start_offset"] = None
        if "end_offset" not in entity["span"]:
            entity["span"]["end_offset"] = None
    
    # Filter properties to only those defined in config
    defined_properties = entity_type_config.get("properties", {})
    filtered_properties = {
        k: v for k, v in entity["properties"].items()
        if k in defined_properties
    }
    entity["properties"] = filtered_properties
    
    # For occurrence entities, validate links
    if is_occurrence:
        if "links" not in entity:
            entity["links"] = {}
        elif not isinstance(entity["links"], dict):
            raise ValueError(f"Occurrence entity links must be a dict: {entity}")
        
        # Check required dependencies
        depends_on = entity_type_config.get("depends_on", [])
        for dep in depends_on:
            role = dep["role"]
            cardinality = dep.get("cardinality", "0..1")
            
            # If cardinality requires the link, validate it exists
            if cardinality in ["1", "1..*"]:
                if role not in entity["links"] or not entity["links"][role]:
                    raise ValueError(
                        f"Occurrence entity type '{entity['type']}' requires "
                        f"link '{role}' (cardinality: {cardinality}), but it's missing "
                        f"in entity: {entity['entity_id']}"
                    )
    
    return entity


def _normalize_entities(
    entities: List[Dict[str, Any]],
    entity_config: Dict[str, Any],
    is_occurrence: bool
) -> List[Dict[str, Any]]:
    """Normalize and validate a list of entities.
    
    Args:
        entities: List of raw entity dicts from LLM
        entity_config: Full entity configuration
        is_occurrence: Whether these are occurrence entities
        
    Returns:
        List of normalized and validated entities
    """
    normalized = []
    entity_types = entity_config.get("entities", {})
    
    for entity in entities:
        # Validate type exists
        entity_type = entity.get("type")
        if not entity_type:
            logger.warning(f"Skipping entity without type: {entity}")
            continue
        
        if entity_type not in entity_types:
            logger.warning(
                f"Skipping entity with unknown type '{entity_type}'. "
                f"Available types: {list(entity_types.keys())}"
            )
            continue
        
        # Get type configuration
        type_config = entity_types[entity_type]
        
        # Skip meta-types like CoreEntity or OccurrenceEntity
        if entity_type in ["CoreEntity", "OccurrenceEntity"]:
            logger.warning(f"Skipping meta-type entity: {entity_type}")
            continue
        
        # Verify kind matches expectation
        expected_kind = "occurrence" if is_occurrence else "core"
        actual_kind = type_config.get("kind", "core")
        if actual_kind != expected_kind:
            logger.warning(
                f"Entity type '{entity_type}' has kind '{actual_kind}' but was "
                f"placed in '{expected_kind}_entities'. Moving to correct list."
            )
            # Still normalize it - caller can move it to the right list
        
        try:
            normalized_entity = _normalize_entity(entity, type_config, is_occurrence)
            normalized.append(normalized_entity)
        except ValueError as e:
            logger.error(f"Failed to normalize entity: {e}")
            # Skip invalid entities rather than failing the whole extraction
            continue
    
    return normalized


def extract_entities_from_document(
    entity_config: Dict[str, Any],
    doc_id: str,
    doc_title: str,
    doc_text: str,
    llm_client: LLMClient
) -> Dict[str, Any]:
    """Extract entities from document using LLM and entity configuration.
    
    Args:
        entity_config: Entity configuration dictionary with entity types,
            properties, and dependencies
        doc_id: Document identifier
        doc_title: Document title
        doc_text: Full document text
        llm_client: LLM client for generation
        
    Returns:
        Dictionary with 'core_entities' and 'occurrence_entities' lists
        
    Raises:
        ValueError: If LLM response cannot be parsed or validated
    """
    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(entity_config, doc_id, doc_title, doc_text)
    
    # Call LLM
    logger.debug(f"Calling LLM for entity extraction from document: {doc_id}")
    response_text = llm_client.generate(system_prompt, user_prompt)
    
    # Parse JSON response
    try:
        data = _parse_json_response(response_text)
    except ValueError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise
    
    # Validate response structure
    if not isinstance(data, dict):
        raise ValueError(f"LLM response must be a dict, got: {type(data)}")
    
    if "core_entities" not in data or "occurrence_entities" not in data:
        raise ValueError(
            f"LLM response must have 'core_entities' and 'occurrence_entities' keys. "
            f"Got keys: {list(data.keys())}"
        )
    
    if not isinstance(data["core_entities"], list):
        raise ValueError(
            f"'core_entities' must be a list, got: {type(data['core_entities'])}"
        )
    
    if not isinstance(data["occurrence_entities"], list):
        raise ValueError(
            f"'occurrence_entities' must be a list, got: {type(data['occurrence_entities'])}"
        )
    
    # Normalize and validate entities
    normalized_core = _normalize_entities(
        data["core_entities"],
        entity_config,
        is_occurrence=False
    )
    
    normalized_occurrence = _normalize_entities(
        data["occurrence_entities"],
        entity_config,
        is_occurrence=True
    )
    
    # Check if any entities were misclassified and move them
    entity_types = entity_config.get("entities", {})
    
    # Move core entities that should be occurrences
    core_to_move = []
    for entity in normalized_core:
        entity_type = entity["type"]
        if entity_types.get(entity_type, {}).get("kind") == "occurrence":
            core_to_move.append(entity)
    
    for entity in core_to_move:
        normalized_core.remove(entity)
        # Re-normalize as occurrence
        entity_type_config = entity_types[entity["type"]]
        try:
            renormalized = _normalize_entity(entity, entity_type_config, is_occurrence=True)
            normalized_occurrence.append(renormalized)
        except ValueError as e:
            logger.error(f"Failed to move misclassified entity: {e}")
    
    # Move occurrence entities that should be core
    occurrence_to_move = []
    for entity in normalized_occurrence:
        entity_type = entity["type"]
        if entity_types.get(entity_type, {}).get("kind") == "core":
            occurrence_to_move.append(entity)
    
    for entity in occurrence_to_move:
        normalized_occurrence.remove(entity)
        # Re-normalize as core (remove links)
        if "links" in entity:
            del entity["links"]
        entity_type_config = entity_types[entity["type"]]
        try:
            renormalized = _normalize_entity(entity, entity_type_config, is_occurrence=False)
            normalized_core.append(renormalized)
        except ValueError as e:
            logger.error(f"Failed to move misclassified entity: {e}")
    
    # Filter out empty occurrence entities
    filtered_occurrence = []
    for entity in normalized_occurrence:
        entity_type = entity.get("type")
        
        # For occurrence entities, check if they have meaningful properties
        if _is_occurrence_entity(entity_type, entity_config):
            if not _has_meaningful_properties(entity, entity_config):
                logger.debug(
                    f"Dropping empty occurrence entity: {entity_type} "
                    f"(ID: {entity.get('entity_id')}) - no meaningful properties"
                )
                continue
        
        # Validate Signature Event has required links
        if not _validate_signature_event(entity):
            logger.warning(
                f"Dropping Signature Event (ID: {entity.get('entity_id')}) - "
                f"missing required contract or signer links"
            )
            continue
        
        filtered_occurrence.append(entity)
    
    # Validate Person entities in core
    filtered_core = []
    for entity in normalized_core:
        # Validate Person has full name
        if not _validate_person_entity(entity):
            logger.warning(
                f"Dropping Person entity (ID: {entity.get('entity_id')}) - "
                f"missing required 'full name' property"
            )
            continue
        
        # Validate Contract notice periods (just log warnings)
        _validate_contract_notice_periods(entity, doc_id)
        
        filtered_core.append(entity)
    
    logger.info(
        f"Extracted {len(filtered_core)} core entities and "
        f"{len(filtered_occurrence)} occurrence entities from {doc_id}"
    )
    
    return {
        "core_entities": filtered_core,
        "occurrence_entities": filtered_occurrence,
    }
