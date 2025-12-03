"""
Fake extraction backend for testing and development.

Returns deterministic, predictable results without external dependencies.
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation
from kg_forge.ontology.base import OntologyPack
from kg_forge.extraction.interface import BaseExtractionBackend
from kg_forge.extraction.exceptions import ExtractionError, ValidationError


class FakeExtractionBackend(BaseExtractionBackend):
    """Mock extraction backend for testing.
    
    Returns deterministic results based on content hash or test data files.
    Supports injecting malformed data for negative testing scenarios.
    """
    
    def __init__(self, test_data_dir: Optional[Path] = None, 
                 malformed_mode: bool = False,
                 failure_mode: bool = False):
        """Initialize fake extraction backend.
        
        Args:
            test_data_dir: Directory containing test data files
            malformed_mode: If True, return malformed/invalid data
            failure_mode: If True, raise exceptions during extraction
        """
        super().__init__("fake")
        self.test_data_dir = test_data_dir
        self.malformed_mode = malformed_mode
        self.failure_mode = failure_mode
        self._test_data_cache: Dict[str, Dict] = {}
        
        if test_data_dir:
            self._load_test_data()
    
    def _load_test_data(self):
        """Load test data files from test_data_dir."""
        if not self.test_data_dir or not self.test_data_dir.exists():
            return
        
        for json_file in self.test_data_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Use filename (without extension) as key
                    key = json_file.stem
                    self._test_data_cache[key] = data
            except (json.JSONDecodeError, IOError) as e:
                # Skip invalid test data files
                pass
    
    def _do_extract(self, content: str, ontology: OntologyPack, doc_id: str) -> LexicalGraph:
        """Perform fake extraction."""
        if self.failure_mode:
            raise ExtractionError("Fake backend configured to fail")
        
        if self.malformed_mode:
            return self._generate_malformed_data(content, doc_id)
        
        # Try to find specific test data for this content/doc_id
        test_data = self._get_test_data_for_content(content, doc_id)
        if test_data:
            return self._build_graph_from_test_data(test_data, doc_id)
        
        # Generate deterministic fake data based on content
        return self._generate_deterministic_data(content, ontology, doc_id)
    
    def _get_test_data_for_content(self, content: str, doc_id: str) -> Optional[Dict]:
        """Get test data for specific content or doc_id."""
        # First try exact doc_id match
        if doc_id in self._test_data_cache:
            return self._test_data_cache[doc_id]
        
        # Try content hash match
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        if content_hash in self._test_data_cache:
            return self._test_data_cache[content_hash]
        
        # Try generic test data
        if "default" in self._test_data_cache:
            return self._test_data_cache["default"]
        
        return None
    
    def _build_graph_from_test_data(self, test_data: Dict, doc_id: str) -> LexicalGraph:
        """Build LexicalGraph from test data file format."""
        mentions = []
        relations = []
        
        # Process mentions
        for mention_data in test_data.get("mentions", []):
            mention = LexicalMention(
                id=self._generate_mention_id(doc_id),
                doc_id=doc_id,
                entity_type=mention_data.get("entity_type", "Topic"),
                surface=mention_data.get("surface", "unknown"),
                start_offset=mention_data.get("start_offset", 0),
                end_offset=mention_data.get("end_offset", 1),
                features=mention_data.get("features", {
                    "backend": "fake",
                    "test_data": True
                })
            )
            mentions.append(mention)
        
        # Process relations
        if len(mentions) >= 2:  # Need at least 2 mentions for relations
            for relation_data in test_data.get("relations", []):
                # Map relation to available mentions
                src_idx = relation_data.get("src_index", 0) % len(mentions)
                dst_idx = relation_data.get("dst_index", 1) % len(mentions)
                
                if src_idx != dst_idx:  # Avoid self-relations
                    relation = LexicalRelation(
                        id=self._generate_relation_id(doc_id),
                        type=relation_data.get("type", "RELATED_TO"),
                        src_mention_id=mentions[src_idx].id,
                        dst_mention_id=mentions[dst_idx].id,
                        features=relation_data.get("features", {
                            "backend": "fake",
                            "test_data": True
                        })
                    )
                    relations.append(relation)
        
        return LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={
                "backend": "fake",
                "test_data": True,
                "doc_id": doc_id
            }
        )
    
    def _generate_deterministic_data(self, content: str, ontology: OntologyPack, 
                                   doc_id: str) -> LexicalGraph:
        """Generate deterministic fake data based on content hash."""
        # Use content hash to make results reproducible
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        hash_int = int(content_hash[:8], 16)
        
        # Get available entity types from ontology
        entity_definitions = ontology.get_entity_definitions()
        entity_types = [defn.id for defn in entity_definitions]
        if not entity_types:
            entity_types = ["Topic"]  # Fallback
        
        mentions = []
        relations = []
        
        # Generate deterministic number of mentions (1-5 based on hash)
        num_mentions = (hash_int % 5) + 1
        
        # Split content into words for mention generation
        words = content.split()[:50]  # Limit to first 50 words
        if not words:
            words = ["placeholder"]
        
        # Generate mentions
        for i in range(num_mentions):
            if i < len(words):
                word_idx = (hash_int + i) % len(words)
                surface = words[word_idx]
                
                # Deterministic entity type selection
                entity_type = entity_types[(hash_int + i) % len(entity_types)]
                
                # Calculate fake offsets
                start_offset = sum(len(w) + 1 for w in words[:word_idx])  # +1 for spaces
                end_offset = start_offset + len(surface)
                
                mention = LexicalMention(
                    id=self._generate_mention_id(doc_id),
                    doc_id=doc_id,
                    entity_type=entity_type,
                    surface=surface,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    features={
                        "backend": "fake",
                        "confidence": 0.8 + (i * 0.05),  # Varying confidence
                        "deterministic": True,
                        "hash_seed": content_hash
                    }
                )
                mentions.append(mention)
        
        # Generate relations between mentions
        if len(mentions) >= 2:
            num_relations = min(len(mentions) - 1, 3)  # At most 3 relations
            
            for i in range(num_relations):
                src_idx = i
                dst_idx = (i + 1) % len(mentions)
                
                # Get possible relations for these entity types
                src_entity_type = mentions[src_idx].entity_type
                dst_entity_type = mentions[dst_idx].entity_type
                
                # Find valid relation from ontology
                relation_type = "RELATED_TO"  # Default fallback
                src_defn = next((d for d in entity_definitions if d.id == src_entity_type), None)
                if src_defn and src_defn.relations:
                    for rel in src_defn.relations:
                        if rel.target_type == dst_entity_type:
                            relation_type = rel.to_label
                            break
                
                relation = LexicalRelation(
                    id=self._generate_relation_id(doc_id),
                    type=relation_type,
                    src_mention_id=mentions[src_idx].id,
                    dst_mention_id=mentions[dst_idx].id,
                    features={
                        "backend": "fake",
                        "confidence": 0.7,
                        "deterministic": True,
                        "hash_seed": content_hash
                    }
                )
                relations.append(relation)
        
        return LexicalGraph(
            mentions=mentions,
            relations=relations,
            metadata={
                "backend": "fake",
                "content_hash": content_hash,
                "num_words": len(words),
                "doc_id": doc_id,
                "deterministic": True
            }
        )
    
    def _generate_malformed_data(self, content: str, doc_id: str) -> LexicalGraph:
        """Generate malformed data for negative testing."""
        # Create deliberately invalid mentions
        malformed_mention = LexicalMention(
            id=self._generate_mention_id(doc_id),
            doc_id=doc_id,
            entity_type="",  # Invalid: empty type
            surface="test",
            start_offset=0,
            end_offset=4,
            features={"malformed": True}
        )
        
        try:
            # This should trigger validation error in LexicalGraph
            return LexicalGraph(
                mentions=[malformed_mention],
                relations=[],
                metadata={"backend": "fake", "malformed": True}
            )
        except Exception as e:
            # If validation catches it, raise our own error
            raise ValidationError(f"Malformed data generated: {e}")
    
    def get_backend_info(self) -> dict:
        """Get fake backend information."""
        info = super().get_backend_info()
        info.update({
            "test_data_dir": str(self.test_data_dir) if self.test_data_dir else None,
            "malformed_mode": self.malformed_mode,
            "failure_mode": self.failure_mode,
            "cached_test_files": list(self._test_data_cache.keys()),
            "dependencies": "none",
            "deterministic": True
        })
        return info
    
    def validate_configuration(self) -> bool:
        """Validate fake backend configuration."""
        if self.failure_mode:
            return False  # Configured to fail validation
        return True


def create_fake_backend_with_test_data() -> FakeExtractionBackend:
    """Create a fake backend with built-in test data."""
    # Create minimal test data in memory
    backend = FakeExtractionBackend()
    
    # Inject some test data directly
    backend._test_data_cache = {
        "technical_doc": {
            "mentions": [
                {
                    "entity_type": "Product",
                    "surface": "Knowledge Discovery",
                    "start_offset": 0,
                    "end_offset": 19,
                    "features": {"confidence": 0.9}
                },
                {
                    "entity_type": "Technology",
                    "surface": "Neo4j",
                    "start_offset": 50,
                    "end_offset": 55,
                    "features": {"confidence": 0.95}
                }
            ],
            "relations": [
                {
                    "type": "USES",
                    "src_index": 0,
                    "dst_index": 1,
                    "features": {"confidence": 0.8}
                }
            ]
        }
    }
    
    return backend