"""TTL ontology loader using rdflib.

This module implements loading of TTL (Turtle) ontology files and converting
them to the normalized OntologySchema representation.
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging

try:
    from rdflib import Graph, Namespace, RDF, RDFS, OWL
    from rdflib.term import URIRef
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    Graph = None
    Namespace = None
    RDF = None
    RDFS = None
    OWL = None
    URIRef = None

from .schema import OntologySchema, EntityType, RelationType, Property

logger = logging.getLogger(__name__)


class TTLOntologyLoader:
    """Load ontologies from TTL (Turtle) files using rdflib."""
    
    def __init__(self):
        """Initialize the TTL loader."""
        if not RDFLIB_AVAILABLE:
            raise ImportError(
                "rdflib is required for TTL ontology support. "
                "Install it with: pip install rdflib"
            )
        self.graph = Graph()
    
    def load_from_file(self, ttl_path: Path) -> OntologySchema:
        """Load ontology from a single TTL file.
        
        Args:
            ttl_path: Path to TTL file
            
        Returns:
            Normalized OntologySchema
        """
        logger.info(f"Loading TTL ontology from {ttl_path}")
        
        # Parse TTL file
        self.graph.parse(ttl_path, format='turtle')
        
        return self._build_ontology_schema()
    
    def load_from_directory(self, ttl_dir: Path) -> OntologySchema:
        """Load ontology from all TTL files in a directory.
        
        Args:
            ttl_dir: Directory containing .ttl files
            
        Returns:
            Merged OntologySchema from all TTL files
        """
        logger.info(f"Loading TTL ontologies from directory {ttl_dir}")
        
        ttl_files = list(ttl_dir.glob("*.ttl"))
        if not ttl_files:
            raise ValueError(f"No .ttl files found in {ttl_dir}")
        
        # Parse all TTL files into single graph
        for ttl_file in ttl_files:
            logger.debug(f"Parsing {ttl_file}")
            self.graph.parse(ttl_file, format='turtle')
        
        return self._build_ontology_schema()
    
    def _build_ontology_schema(self) -> OntologySchema:
        """Build OntologySchema from parsed RDF graph."""
        entities = self._extract_entities()
        relations = self._extract_relations()
        metadata = self._extract_metadata()
        
        logger.info(f"Loaded {len(entities)} entity types and {len(relations)} relation types from TTL")
        
        return OntologySchema(
            entities=entities,
            relations=relations,
            metadata=metadata
        )
    
    def _extract_entities(self) -> Dict[str, EntityType]:
        """Extract entity types from RDF graph.
        
        Looks for rdfs:Class or owl:Class instances with labels and descriptions.
        """
        entities = {}
        
        # Query for all classes (both OWL and RDFS)
        for class_uri in self.graph.subjects(RDF.type, OWL.Class):
            entity = self._parse_entity_class(class_uri)
            if entity:
                entities[entity.name] = entity
        
        for class_uri in self.graph.subjects(RDF.type, RDFS.Class):
            if class_uri not in [e.iri for e in entities.values()]:  # Avoid duplicates
                entity = self._parse_entity_class(class_uri)
                if entity:
                    entities[entity.name] = entity
        
        return entities
    
    def _parse_entity_class(self, class_uri: URIRef) -> Optional[EntityType]:
        """Parse a single entity class from RDF graph.
        
        Args:
            class_uri: URI of the class
            
        Returns:
            EntityType or None if parsing fails
        """
        # Extract label (required)
        label = self._get_label(class_uri)
        if not label:
            logger.warning(f"Skipping class without label: {class_uri}")
            return None
        
        # Extract description (from rdfs:comment or skos:definition)
        description = self._get_description(class_uri)
        if not description:
            description = f"Entity type: {label}"  # Default description
        
        # Extract properties (data properties)
        properties = self._extract_properties_for_class(class_uri)
        
        return EntityType(
            name=label,
            iri=str(class_uri),
            description=description,
            properties=properties,
            examples=[]  # TTL files don't typically include examples
        )
    
    def _extract_relations(self) -> Dict[str, RelationType]:
        """Extract relation types from RDF graph.
        
        Looks for owl:ObjectProperty instances with domain/range constraints.
        """
        relations = {}
        
        for prop_uri in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            relation = self._parse_relation_property(prop_uri)
            if relation:
                relations[relation.name] = relation
        
        # Also check for rdf:Property
        for prop_uri in self.graph.subjects(RDF.type, RDF.Property):
            if prop_uri not in [r.iri for r in relations.values()]:  # Avoid duplicates
                relation = self._parse_relation_property(prop_uri)
                if relation:
                    relations[relation.name] = relation
        
        return relations
    
    def _parse_relation_property(self, prop_uri: URIRef) -> Optional[RelationType]:
        """Parse a single relation property from RDF graph.
        
        Args:
            prop_uri: URI of the property
            
        Returns:
            RelationType or None if parsing fails
        """
        # Extract label (required)
        label = self._get_label(prop_uri)
        if not label:
            logger.warning(f"Skipping property without label: {prop_uri}")
            return None
        
        # Convert label to uppercase relation name (e.g., "works on" -> "WORKS_ON")
        relation_name = label.upper().replace(" ", "_")
        
        # Extract description
        description = self._get_description(prop_uri)
        if not description:
            description = f"Relation: {label}"
        
        # Extract domain (head types)
        head_types = self._get_domain_types(prop_uri)
        
        # Extract range (tail types)
        tail_types = self._get_range_types(prop_uri)
        
        # If no domain/range specified, allow any entity type
        if not head_types:
            head_types = ["*"]  # Wildcard
        if not tail_types:
            tail_types = ["*"]  # Wildcard
        
        return RelationType(
            name=relation_name,
            iri=str(prop_uri),
            head_types=head_types,
            tail_types=tail_types,
            description=description,
            properties=[]
        )
    
    def _extract_properties_for_class(self, class_uri: URIRef) -> List[Property]:
        """Extract datatype properties for a class."""
        properties = []
        
        # Find all datatype properties with this class as domain
        for prop_uri in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            domains = list(self.graph.objects(prop_uri, RDFS.domain))
            if class_uri in domains:
                label = self._get_label(prop_uri)
                description = self._get_description(prop_uri)
                
                # Get datatype if specified
                datatype = None
                ranges = list(self.graph.objects(prop_uri, RDFS.range))
                if ranges:
                    datatype = str(ranges[0]).split('#')[-1]  # Extract type name
                
                if label:
                    properties.append(Property(
                        name=label,
                        description=description,
                        datatype=datatype
                    ))
        
        return properties
    
    def _get_label(self, uri: URIRef) -> Optional[str]:
        """Get rdfs:label for a URI."""
        labels = list(self.graph.objects(uri, RDFS.label))
        if labels:
            return str(labels[0])
        
        # Fallback: use last part of URI
        uri_str = str(uri)
        if '#' in uri_str:
            return uri_str.split('#')[-1]
        elif '/' in uri_str:
            return uri_str.split('/')[-1]
        
        return None
    
    def _get_description(self, uri: URIRef) -> Optional[str]:
        """Get description from rdfs:comment or skos:definition."""
        # Try rdfs:comment first
        comments = list(self.graph.objects(uri, RDFS.comment))
        if comments:
            return str(comments[0])
        
        # Try skos:definition
        SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
        definitions = list(self.graph.objects(uri, SKOS.definition))
        if definitions:
            return str(definitions[0])
        
        return None
    
    def _get_domain_types(self, prop_uri: URIRef) -> List[str]:
        """Get domain (head) entity types for a property."""
        types = []
        for domain_uri in self.graph.objects(prop_uri, RDFS.domain):
            label = self._get_label(domain_uri)
            if label:
                types.append(label)
        return types
    
    def _get_range_types(self, prop_uri: URIRef) -> List[str]:
        """Get range (tail) entity types for a property."""
        types = []
        for range_uri in self.graph.objects(prop_uri, RDFS.range):
            label = self._get_label(range_uri)
            if label:
                types.append(label)
        return types
    
    def _extract_metadata(self) -> Dict[str, any]:
        """Extract ontology metadata."""
        metadata = {
            "format": "ttl",
            "triple_count": len(self.graph)
        }
        
        # Try to extract ontology metadata from owl:Ontology
        for ont_uri in self.graph.subjects(RDF.type, OWL.Ontology):
            # Version
            versions = list(self.graph.objects(ont_uri, OWL.versionInfo))
            if versions:
                metadata["version"] = str(versions[0])
            
            # Description
            description = self._get_description(ont_uri)
            if description:
                metadata["description"] = description
            
            # Label/title
            label = self._get_label(ont_uri)
            if label:
                metadata["title"] = label
        
        return metadata
