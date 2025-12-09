"""TTL/OWL ontology to KG Forge entity config JSON converter.

This module converts OWL/Turtle ontologies to a JSON configuration format
that includes entity types, properties, relations, and dependencies.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, Namespace, XSD
from rdflib.term import Node
import logging
import re

logger = logging.getLogger(__name__)


def ontology_to_kgforge_config(ttl_path: str) -> Dict[str, Any]:
    """Parse a Turtle ontology file and return KG Forge entity config JSON.
    
    Args:
        ttl_path: Path to the TTL/OWL ontology file
        
    Returns:
        Dictionary with structure:
        {
            "entities": {
                "<ClassName>": {
                    "kind": "core" | "occurrence",
                    "label": "<rdfs:label or local name>",
                    "description": "<rdfs:comment>",
                    "properties": {
                        "<propertyName>": {
                            "type": "string|number|boolean|date|datetime|other",
                            "source": "datatype_property",
                            "description": "<optional>"
                        }
                    },
                    "relations": {
                        "<relationName>": {
                            "target": "<TargetClassName>",
                            "source": "object_property",
                            "description": "<optional>"
                        }
                    },
                    "depends_on": [
                        {
                            "role": "<roleName>",
                            "entity": "<TargetClassName>",
                            "cardinality": "1" | "0..1" | "1..*" | "0..*"
                        }
                    ]
                }
            }
        }
    """
    g = Graph()
    g.parse(ttl_path, format="turtle")
    
    logger.info(f"Loaded ontology from {ttl_path}")
    
    # Define custom namespace for entity kind annotation
    EX = Namespace("http://example.org/ontology#")
    
    # Collect all entity classes
    entities = {}
    
    # Step 1: Discover all classes
    classes = set(g.subjects(RDF.type, OWL.Class))
    
    for cls in classes:
        if isinstance(cls, URIRef):
            local_name = _get_local_name(cls)
            
            # Skip if this is CoreEntity or OccurrenceEntity themselves
            if local_name in ["CoreEntity", "OccurrenceEntity"]:
                continue
            
            logger.debug(f"Processing class: {local_name}")
            
            entity_config = {
                "kind": _determine_kind(g, cls, EX),
                "label": _get_label(g, cls, local_name),
                "description": _get_description(g, cls, local_name),
                "properties": {},
                "relations": {},
                "depends_on": []
            }
            
            entities[local_name] = entity_config
    
    # Step 2: Process datatype properties
    datatype_properties = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    
    for prop in datatype_properties:
        if isinstance(prop, URIRef):
            prop_name = _get_local_name(prop)
            prop_desc = _get_description(g, prop, "")
            
            # Get domains (which classes have this property)
            domains = list(g.objects(prop, RDFS.domain))
            
            # Get range (datatype)
            ranges = list(g.objects(prop, RDFS.range))
            datatype = _infer_datatype(ranges[0] if ranges else None)
            
            # Add property to each domain class
            for domain in domains:
                if isinstance(domain, URIRef):
                    domain_name = _get_local_name(domain)
                    if domain_name in entities:
                        entities[domain_name]["properties"][prop_name] = {
                            "type": datatype,
                            "source": "datatype_property"
                        }
                        if prop_desc:
                            entities[domain_name]["properties"][prop_name]["description"] = prop_desc
    
    # Step 3: Process object properties (relations)
    object_properties = set(g.subjects(RDF.type, OWL.ObjectProperty))
    
    for prop in object_properties:
        if isinstance(prop, URIRef):
            prop_name = _get_local_name(prop)
            prop_desc = _get_description(g, prop, "")
            
            # Get domains and ranges
            domains = list(g.objects(prop, RDFS.domain))
            ranges = list(g.objects(prop, RDFS.range))
            
            # Add relation to each domain class
            for domain in domains:
                if isinstance(domain, URIRef):
                    domain_name = _get_local_name(domain)
                    if domain_name in entities:
                        for range_cls in ranges:
                            if isinstance(range_cls, URIRef):
                                range_name = _get_local_name(range_cls)
                                
                                entities[domain_name]["relations"][prop_name] = {
                                    "target": range_name,
                                    "source": "object_property"
                                }
                                if prop_desc:
                                    entities[domain_name]["relations"][prop_name]["description"] = prop_desc
    
    # Step 4: Process dependencies (OWL restrictions on occurrence entities)
    for entity_name, entity_config in entities.items():
        if entity_config["kind"] == "occurrence":
            # Find the class URI
            cls_uri = _find_class_uri(g, entity_name)
            if cls_uri:
                dependencies = _extract_dependencies(g, cls_uri)
                entity_config["depends_on"] = dependencies
    
    return {"entities": entities}


def _get_local_name(uri: URIRef) -> str:
    """Extract local name from URI.
    
    Args:
        uri: RDF URI reference
        
    Returns:
        Local name (e.g., "Product" from "http://example.org/ont#Product")
    """
    uri_str = str(uri)
    
    # Split on # first
    if '#' in uri_str:
        return uri_str.split('#')[-1]
    # Fall back to splitting on /
    elif '/' in uri_str:
        return uri_str.split('/')[-1]
    
    return uri_str


def _determine_kind(g: Graph, cls: URIRef, ex_namespace: Namespace) -> str:
    """Determine if entity is 'core' or 'occurrence'.
    
    Args:
        g: RDF graph
        cls: Class URI
        ex_namespace: Custom namespace for annotations
        
    Returns:
        "core" or "occurrence"
    """
    # Check for explicit annotation
    entity_kind_prop = ex_namespace.entityKind
    for kind_value in g.objects(cls, entity_kind_prop):
        if isinstance(kind_value, Literal):
            kind = str(kind_value).lower()
            if kind in ["core", "occurrence"]:
                return kind
    
    # Check inheritance from CoreEntity or OccurrenceEntity
    for parent in g.objects(cls, RDFS.subClassOf):
        if isinstance(parent, URIRef):
            parent_name = _get_local_name(parent)
            if parent_name == "CoreEntity":
                return "core"
            elif parent_name == "OccurrenceEntity":
                return "occurrence"
    
    # Default to core
    return "core"


def _get_label(g: Graph, resource: URIRef, default: str) -> str:
    """Get rdfs:label or fall back to default.
    
    Args:
        g: RDF graph
        resource: Resource URI
        default: Default label if none found
        
    Returns:
        Label string
    """
    for label in g.objects(resource, RDFS.label):
        if isinstance(label, Literal):
            return str(label)
    return default


def _get_description(g: Graph, resource: URIRef, default: str) -> str:
    """Get rdfs:comment or fall back to default.
    
    Args:
        g: RDF graph
        resource: Resource URI
        default: Default description if none found
        
    Returns:
        Description string
    """
    for comment in g.objects(resource, RDFS.comment):
        if isinstance(comment, Literal):
            return str(comment)
    return default


def _infer_datatype(range_uri: Optional[Node]) -> str:
    """Infer JSON type from XSD datatype.
    
    Args:
        range_uri: XSD datatype URI
        
    Returns:
        One of: "string", "number", "boolean", "date", "datetime", "other"
    """
    if not range_uri or not isinstance(range_uri, URIRef):
        return "string"
    
    range_str = str(range_uri)
    
    # XSD string types
    if any(t in range_str for t in ["string", "normalizedString", "token"]):
        return "string"
    
    # XSD numeric types
    if any(t in range_str for t in ["integer", "int", "long", "short", "byte",
                                     "decimal", "float", "double", "nonNegativeInteger",
                                     "positiveInteger", "nonPositiveInteger", "negativeInteger"]):
        return "number"
    
    # XSD boolean
    if "boolean" in range_str:
        return "boolean"
    
    # XSD date types
    if range_str.endswith("date"):
        return "date"
    
    if "dateTime" in range_str:
        return "datetime"
    
    return "other"


def _find_class_uri(g: Graph, class_name: str) -> Optional[URIRef]:
    """Find class URI by local name.
    
    Args:
        g: RDF graph
        class_name: Local class name
        
    Returns:
        Class URI or None
    """
    for cls in g.subjects(RDF.type, OWL.Class):
        if isinstance(cls, URIRef):
            if _get_local_name(cls) == class_name:
                return cls
    return None


def _extract_dependencies(g: Graph, cls: URIRef) -> List[Dict[str, str]]:
    """Extract dependencies from OWL restrictions.
    
    Args:
        g: RDF graph
        cls: Class URI
        
    Returns:
        List of dependency dictionaries
    """
    dependencies = []
    
    # Find all restrictions in the subClassOf chain
    for parent in g.objects(cls, RDFS.subClassOf):
        if isinstance(parent, URIRef) or hasattr(parent, 'n3'):
            # Check if this is a restriction (blank node)
            restriction_type = list(g.objects(parent, RDF.type))
            if restriction_type and OWL.Restriction in restriction_type:
                # Extract restriction details
                on_property = None
                on_class = None
                cardinality = "0..*"  # default
                
                # Get the property this restriction applies to
                for prop in g.objects(parent, OWL.onProperty):
                    on_property = prop
                
                # Get the target class
                for target in g.objects(parent, OWL.onClass):
                    on_class = target
                
                if on_property and on_class:
                    # Determine cardinality
                    cardinality = _determine_cardinality(g, parent)
                    
                    # Extract role name from property
                    role = _extract_role_name(_get_local_name(on_property))
                    
                    dependencies.append({
                        "role": role,
                        "entity": _get_local_name(on_class),
                        "cardinality": cardinality
                    })
    
    return dependencies


def _determine_cardinality(g: Graph, restriction: Node) -> str:
    """Determine cardinality from OWL restriction.
    
    Args:
        g: RDF graph
        restriction: Restriction node
        
    Returns:
        Cardinality string: "1", "0..1", "1..*", "0..*"
    """
    # Check for qualifiedCardinality (exact)
    for card in g.objects(restriction, OWL.qualifiedCardinality):
        if isinstance(card, Literal):
            n = int(card)
            return str(n)
    
    # Check for min and max cardinality
    min_card = None
    max_card = None
    
    for card in g.objects(restriction, OWL.minQualifiedCardinality):
        if isinstance(card, Literal):
            min_card = int(card)
    
    for card in g.objects(restriction, OWL.maxQualifiedCardinality):
        if isinstance(card, Literal):
            max_card = int(card)
    
    # Determine cardinality pattern
    if min_card is not None and max_card is not None:
        if min_card == 0 and max_card == 1:
            return "0..1"
        elif min_card == 1 and max_card == 1:
            return "1"
        elif min_card == 0:
            return "0..*"
        elif min_card == 1:
            return "1..*"
    elif min_card is not None:
        if min_card == 0:
            return "0..*"
        elif min_card == 1:
            return "1..*"
        else:
            return f"{min_card}..*"
    elif max_card is not None:
        if max_card == 1:
            return "0..1"
        else:
            return f"0..{max_card}"
    
    return "0..*"


def _extract_role_name(property_name: str) -> str:
    """Extract role name from property name.
    
    Converts property names like 'ofContract', 'hasTemplate', 'forProject'
    to snake_case role names like 'contract', 'template', 'project'.
    
    Args:
        property_name: Property local name
        
    Returns:
        Snake-cased role name
    """
    # Remove common prefixes with space
    name = property_name.strip()
    for prefix in ['of ', 'has ', 'for ', 'with ', 'from ', 'to ', 'in ', 'on ', 'at ']:
        if name.lower().startswith(prefix):
            name = name[len(prefix):].strip()
            break
    
    # Also handle camelCase without space (ofContract, hasTemplate)
    if name == property_name:  # No prefix with space was found
        for prefix in ['of', 'has', 'for', 'with', 'from', 'to', 'in', 'on', 'at']:
            if name.lower().startswith(prefix) and len(name) > len(prefix) and name[len(prefix)].isupper():
                name = name[len(prefix):]
                break
    
    # Convert camelCase to snake_case FIRST
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    
    # Then convert to lowercase and replace spaces with underscores
    name = name.lower().replace(' ', '_')
    
    return name
