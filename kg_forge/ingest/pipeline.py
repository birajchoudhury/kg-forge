"""
Core ingest pipeline orchestrating HTML processing, LLM extraction, and Neo4j storage.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

from kg_forge.config.settings import Settings, get_settings
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.llm.exceptions import LLMError, ParseError, ValidationError, ExtractionAbortError
from kg_forge.models.document import ParsedDocument
from kg_forge.parsers.document_loader import DocumentLoader
from kg_forge.utils.hashing import compute_content_hash
from kg_forge.utils.interactive import InteractiveSession
from kg_forge.ontology_manager import get_ontology_manager
from kg_forge.dedup.interface import create_dedup_backend
from kg_forge.linking.interface import create_entity_linker
from kg_forge.extraction.interface import create_extraction_backend

from .filesystem import FileDiscovery
from .hooks import HookRegistry, EntityRecord, get_global_registry
from .metrics import IngestMetrics


logger = logging.getLogger(__name__)


class IngestPipeline:
    """
    End-to-end ingest pipeline that orchestrates:
    1. HTML file discovery and parsing (Step 3)
    2. Configurable entity extraction (Step 6: LLM or spaCy backend)
    3. Entity deduplication (Step 7a: Splink/Zingg/none)
    4. Entity linking (Step 7b: Map to existing KG entities)
    5. Neo4j storage and relationship creation (Step 5)
    6. Hook execution for custom processing
    """
    
    def __init__(self, 
                 source_path: Path,
                 namespace: Optional[str] = None,
                 dry_run: bool = False,
                 refresh: bool = False,
                 interactive: bool = False,
                 prompt_template: Optional[Path] = None,
                 model: Optional[str] = None,
                 max_docs: Optional[int] = None,
                 extractor: Optional[str] = None,
                 dedup_backend: Optional[str] = None,
                 fake_llm: bool = False,
                 config: Optional[Settings] = None,
                 hook_registry: Optional[HookRegistry] = None):
        """
        Initialize ingest pipeline.
        
        Args:
            source_path: Root directory containing HTML files
            namespace: Namespace for this ingest run
            dry_run: Run without writing to Neo4j
            refresh: Reprocess all documents ignoring content hash
            interactive: Enable interactive mode for hooks
            prompt_template: Override prompt template file
            model: Override LLM model name
            max_docs: Limit number of documents processed
            extractor: Extraction backend (llm|spacy, default from config)
            dedup_backend: Deduplication backend (none|splink|zingg|both, default from config)
            fake_llm: Use fake LLM for testing
            config: Application configuration (uses default if None)
            hook_registry: Hook registry (uses global if None)
        """
        self.source_path = Path(source_path).resolve()
        self.dry_run = dry_run
        self.refresh = refresh
        self.interactive_mode = interactive
        self.max_docs = max_docs
        self.fake_llm = fake_llm
        
        # Load configuration
        self.config = config or get_settings()
        self.namespace = namespace or self.config.app.default_namespace
        
        # Backend selection
        self.extractor = extractor or self.config.app.default_extractor
        self.dedup_backend = dedup_backend or self.config.app.default_dedup_backend
        
        # Initialize components
        self.file_discovery = FileDiscovery(self.source_path)
        self.document_loader = DocumentLoader()
        
        # Initialize ontology manager and set active pack
        self.ontology_manager = get_ontology_manager()
        if self.config.app.ontology_pack:
            try:
                self.ontology_manager.set_active_ontology(self.config.app.ontology_pack)
                logger.info(f"Using ontology pack: {self.config.app.ontology_pack}")
            except Exception as e:
                logger.warning(f"Failed to activate configured ontology pack '{self.config.app.ontology_pack}': {e}")
        
        # Set up ontology for extraction
        active_pack = self.ontology_manager.get_active_ontology()
        if self.config.app.ontology_pack:
            try:
                self.ontology_manager.set_active_ontology(self.config.app.ontology_pack)
                active_pack = self.ontology_manager.get_active_ontology()
                logger.info(f"Using ontology pack: {self.config.app.ontology_pack}")
            except Exception as e:
                logger.warning(f"Failed to activate configured ontology pack '{self.config.app.ontology_pack}': {e}")
        
        ontology_id = active_pack.info.id if active_pack else None
        
        # Initialize Neo4j client
        self.neo4j_client = Neo4jClient(self.config)
        
        # Initialize extraction backend with backend-specific config
        if self.extractor == "llm":
            extraction_config = {
                'model_name': model or self.config.aws.bedrock_model_name,
                'fake_mode': fake_llm,
                'region': self.config.aws.default_region,
                'max_tokens': self.config.aws.bedrock_max_tokens,
                'temperature': self.config.aws.bedrock_temperature
            }
        elif self.extractor == "spacy":
            extraction_config = {
                'fake_mode': fake_llm,
                'spacy_model': "en_core_web_sm"
            }
        else:  # fake backend
            extraction_config = {
                'fake_mode': True
            }
        self.extraction_backend = create_extraction_backend(self.extractor, extraction_config)
        self.active_ontology = active_pack
        
        # Initialize deduplication backend
        dedup_config = {
            'similarity_threshold': getattr(self.config.app, 'dedup_similarity_threshold', 0.8),
            'max_clusters': getattr(self.config.app, 'dedup_max_clusters', 1000)
        }
        self.dedup_backend = create_dedup_backend(self.dedup_backend, dedup_config)
        
        # Initialize entity linking backend
        linking_config = {
            'similarity_threshold': getattr(self.config.app, 'linking_similarity_threshold', 0.8),
            'max_candidates': getattr(self.config.app, 'linking_max_candidates', 5),
            'create_missing': getattr(self.config.app, 'linking_create_missing', True)
        }
        self.entity_linker = create_entity_linker('default', self.neo4j_client, linking_config)
        
        # Set up hooks and session
        self.hook_registry = hook_registry or get_global_registry()
        self.interactive_session = InteractiveSession(enabled=interactive) if interactive else None
        
        # Initialize metrics and state
        self.metrics = IngestMetrics()
        self.processed_entities: List[EntityRecord] = []
        
        logger.info(f"Initialized IngestPipeline: source={source_path}, namespace={self.namespace}, "
                   f"dry_run={dry_run}, refresh={refresh}, fake_llm={fake_llm}")
    
    def run(self) -> IngestMetrics:
        """
        Execute the complete ingest pipeline.
        
        Returns:
            IngestMetrics object with processing statistics
            
        Raises:
            ExtractionAbortError: If consecutive failure threshold exceeded
            Exception: For critical configuration or connection errors
        """
        logger.info("Starting ingest pipeline")
        
        try:
            # Validate configuration and connections
            self._validate_setup()
            
            # Discover files
            html_files = list(self.file_discovery.discover_html_files())
            self.metrics.files_discovered = len(html_files)
            
            if self.max_docs:
                html_files = html_files[:self.max_docs]
                logger.info(f"Limited processing to {len(html_files)} documents")
            
            logger.info(f"Discovered {len(html_files)} HTML files to process")
            
            if not html_files:
                logger.warning("No HTML files found in source directory")
                self.metrics.finalize()
                return self.metrics
            
            # Process each document
            for i, file_path in enumerate(html_files, 1):
                logger.info(f"Processing document {i}/{len(html_files)}: {file_path.name}")
                
                try:
                    self._process_document(file_path)
                    
                    # Check for consecutive failure abort
                    if self.metrics.has_consecutive_failures:
                        raise ExtractionAbortError(
                            f"Exceeded maximum consecutive failures ({self.metrics.consecutive_failures})"
                        )
                        
                except ExtractionAbortError:
                    raise  # Re-raise abort errors
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    self.metrics.record_doc_failed(str(e))
            
            # Execute batch completion hooks
            if self.processed_entities:
                logger.info(f"Executing batch completion hooks for {len(self.processed_entities)} entities")
                self.hook_registry.execute_after_batch(
                    self.processed_entities, 
                    self.neo4j_client, 
                    self.interactive_session
                )
            
            self.metrics.finalize()
            logger.info(f"Ingest pipeline completed: {self.metrics}")
            
            return self.metrics
            
        except Exception as e:
            self.metrics.finalize()
            logger.error(f"Ingest pipeline failed: {e}")
            raise
    
    def _validate_setup(self) -> None:
        """Validate configuration and connections."""
        # Check source path
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {self.source_path}")
        
        # Test Neo4j connection (unless dry run)
        if not self.dry_run:
            try:
                with self.neo4j_client:
                    self.neo4j_client.test_connection()
            except Exception as e:
                raise ConnectionError(f"Neo4j connection failed: {e}")
        
        # Load entity definitions
        entities_dir = Path(self.config.app.entities_extract_dir)
        if not entities_dir.exists():
            raise FileNotFoundError(f"Entity definitions directory not found: {entities_dir}")
    
    def _process_document(self, file_path: Path) -> None:
        """Process a single HTML document through the complete pipeline."""
        doc_id = self.file_discovery.get_doc_id(file_path)
        
        try:
            # Parse HTML to curated document
            start_time = time.time()
            curated_doc = self._parse_html_document(file_path, doc_id)
            
            # Check if document needs processing (content hash comparison)
            content_hash = compute_content_hash(curated_doc)
            
            if not self.refresh and self._should_skip_document(doc_id, content_hash):
                logger.info(f"Skipping {doc_id} (unchanged content hash)")
                self.metrics.record_doc_skipped("unchanged content hash")
                return
            
            # Phase 1: Extract entities using configured backend
            extraction_start = time.time()
            lexical_graph = self._extract_entities(curated_doc)
            self.metrics.add_llm_time(time.time() - extraction_start)
            
            # Phase 2: Apply deduplication
            dedup_start = time.time()
            deduplicated_graph = self._apply_deduplication(lexical_graph)
            dedup_time = time.time() - dedup_start
            
            # Phase 3: Apply entity linking
            linking_start = time.time()
            link_results = self._apply_entity_linking(deduplicated_graph)
            linking_time = time.time() - linking_start
            
            # Prepare metadata for hooks
            metadata = {
                'extraction_result': lexical_graph,
                'deduplicated_graph': deduplicated_graph,
                'link_results': link_results,
                'timing': {
                    'extraction_time': time.time() - extraction_start,
                    'dedup_time': dedup_time,
                    'linking_time': linking_time
                },
                'doc_id': doc_id,
                'namespace': self.namespace
            }
            
            processed_metadata = self.hook_registry.execute_before_store(
                curated_doc, metadata, self.neo4j_client
            )
            
            # Store in Neo4j
            if not self.dry_run:
                neo4j_start = time.time()
                self._store_document_and_entities(
                    curated_doc, doc_id, content_hash, deduplicated_graph, link_results, processed_metadata
                )
                self.metrics.add_neo4j_time(time.time() - neo4j_start)
            else:
                entity_count = len(deduplicated_graph.canonical_entities)
                logger.info(f"DRY RUN: Would store document {doc_id} with {entity_count} canonical entities")
            
            # Record successful processing
            self.metrics.record_doc_processed()
            
            # Track canonical entities for batch hooks
            for canonical_entity in deduplicated_graph.canonical_entities:
                entity_record = EntityRecord(
                    entity_type=canonical_entity.entity_type,
                    name=canonical_entity.canonical_name,
                    confidence=1.0,  # Canonical entities have high confidence
                    doc_id=doc_id,
                    namespace=self.namespace
                )
                entity_record.created_at = datetime.utcnow()
                self.processed_entities.append(entity_record)
            
            entity_count = len(deduplicated_graph.canonical_entities)
            relation_count = len(deduplicated_graph.relations)
            logger.info(f"Successfully processed {doc_id}: {entity_count} canonical entities, {relation_count} relations")
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def _parse_html_document(self, file_path: Path, doc_id: str) -> ParsedDocument:
        """Parse HTML file into CuratedDocument."""
        try:
            documents = self.document_loader.load_files([file_path])
            
            if not documents:
                raise ValueError(f"No documents could be loaded from {file_path}")
            
            # Use first document (1 file = 1 document in v1)
            return documents[0]
            
        except Exception as e:
            raise ValueError(f"Failed to parse HTML document {file_path}: {e}")
    
    def _should_skip_document(self, doc_id: str, content_hash: str) -> bool:
        """Check if document should be skipped based on content hash."""
        if self.dry_run:
            return False  # Don't skip in dry run mode
        
        try:
            with self.neo4j_client:
                # Query for existing document
                query = """
                MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
                RETURN d.content_hash as content_hash
                """
                
                result = self.neo4j_client.execute_query(
                    query, 
                    {
                        "namespace": self.namespace, 
                        "doc_id": doc_id
                    }
                )
                
                if result and result[0] and result[0]['content_hash'] == content_hash:
                    return True  # Skip - content unchanged
                
        except Exception as e:
            logger.warning(f"Failed to check existing document {doc_id}: {e}")
            # Continue processing on error
        
        return False
    
    def _extract_entities(self, curated_doc: ParsedDocument):
        """Extract entities from document using configured backend."""
        try:
            # Get document ID for mention generation
            doc_id = self.file_discovery.get_doc_id(Path(curated_doc.source_path)) if hasattr(curated_doc, 'source_path') else 'unknown'
            
            # Use extraction backend to get lexical graph
            lexical_graph = self.extraction_backend.extract(
                content=curated_doc.text,
                ontology=self.active_ontology,
                doc_id=doc_id
            )
            
            logger.debug(f"Extracted {len(lexical_graph.mentions)} mentions, {len(lexical_graph.relations)} relations")
            return lexical_graph
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            raise
    
    def _apply_deduplication(self, lexical_graph):
        """Apply deduplication to group entity mentions into canonical entities."""
        try:
            if self.dedup_backend == 'none':
                logger.debug("Skipping deduplication (none backend selected)")
                # Convert to deduplicated format without actual deduplication
                from kg_forge.models.dedup import DedupedLexicalGraph, CanonicalLexicalEntity, CanonicalRelation
                
                # Create canonical entities (1:1 mapping from mentions)
                canonical_entities = []
                for mention in lexical_graph.mentions:
                    canonical_entity = CanonicalLexicalEntity(
                        id=f"canonical_{mention.id}",
                        entity_type=mention.entity_type,
                        canonical_name=mention.surface_form,
                        aliases=[mention.surface_form],
                        mention_ids=[mention.id],
                        features={'confidence': mention.confidence},
                        namespace=self.namespace
                    )
                    canonical_entities.append(canonical_entity)
                
                # Create canonical relations
                canonical_relations = []
                for relation in lexical_graph.relations:
                    # Map to canonical entity IDs
                    src_canonical_id = f"canonical_{relation.src_mention_id}"
                    dst_canonical_id = f"canonical_{relation.dst_mention_id}"
                    
                    canonical_relation = CanonicalRelation(
                        id=f"canonical_rel_{relation.id}",
                        type=relation.relation_type,
                        src_entity_id=src_canonical_id,
                        dst_entity_id=dst_canonical_id,
                        features={'confidence': relation.confidence}
                    )
                    canonical_relations.append(canonical_relation)
                
                return DedupedLexicalGraph(
                    canonical_entities=canonical_entities,
                    relations=canonical_relations,
                    metadata={'dedup_backend': 'none', 'clusters_formed': len(canonical_entities)}
                )
            else:
                # Use configured deduplication backend
                deduplicated_graph = self.dedup_backend.deduplicate(lexical_graph, self.namespace)
                logger.debug(f"Deduplication created {len(deduplicated_graph.canonical_entities)} canonical entities")
                return deduplicated_graph
                
        except Exception as e:
            logger.error(f"Deduplication failed: {e}")
            raise
    
    def _apply_entity_linking(self, deduplicated_graph):
        """Apply entity linking to map canonical entities to existing KG entities."""
        try:
            link_results = self.entity_linker.link_entities(
                deduplicated_graph.canonical_entities, 
                self.namespace
            )
            
            # Count linking actions
            linked_count = sum(1 for r in link_results if r.action == 'link_existing')
            create_count = sum(1 for r in link_results if r.action == 'create_new')
            skip_count = sum(1 for r in link_results if r.action == 'skip')
            
            logger.debug(f"Entity linking: {linked_count} linked, {create_count} to create, {skip_count} skipped")
            return link_results
            
        except Exception as e:
            logger.error(f"Entity linking failed: {e}")
            raise
    
    def _store_document_and_entities(self, curated_doc: ParsedDocument, doc_id: str, 
                                   content_hash: str, deduplicated_graph, link_results, metadata: Dict[str, Any]) -> None:
        """Store document and deduplicated entities in Neo4j."""
        try:
            with self.neo4j_client:
                with self.neo4j_client.session() as session:
                    with session.begin_transaction() as tx:
                        # Store document node
                        self._create_document_node(tx, curated_doc, doc_id, content_hash)
                        
                        # Process canonical entities and link results
                        entity_map = {}  # canonical_id -> neo4j_entity_id
                        entities_created = 0
                        entities_updated = 0
                        
                        for canonical_entity in deduplicated_graph.canonical_entities:
                            # Find corresponding link result
                            link_result = next(
                                (lr for lr in link_results if lr.canonical_entity.id == canonical_entity.id),
                                None
                            )
                            
                            if link_result:
                                if link_result.action == 'link_existing' and link_result.linked_entity:
                                    # Use existing entity
                                    entity_map[canonical_entity.id] = link_result.linked_entity.kg_id
                                    entities_updated += 1
                                elif link_result.action == 'create_new':
                                    # Create new entity
                                    entity_id = self._create_canonical_entity_node(tx, canonical_entity)
                                    entity_map[canonical_entity.id] = entity_id
                                    entities_created += 1
                                # Skip entities with action == 'skip'
                            else:
                                # Fallback: create new entity
                                entity_id = self._create_canonical_entity_node(tx, canonical_entity)
                                entity_map[canonical_entity.id] = entity_id
                                entities_created += 1
                            
                            # Create MENTIONS relationships for all entity mentions
                            if canonical_entity.id in entity_map:
                                neo4j_entity_id = entity_map[canonical_entity.id]
                                self._create_mentions_relationship(tx, doc_id, neo4j_entity_id, 1.0)
                        
                        # Create canonical relationships
                        relations_created = 0
                        for relation in deduplicated_graph.relations:
                            src_entity_id = entity_map.get(relation.src_entity_id)
                            dst_entity_id = entity_map.get(relation.dst_entity_id)
                            
                            if src_entity_id and dst_entity_id:
                                self._create_canonical_relationship(tx, src_entity_id, dst_entity_id, relation)
                                relations_created += 1
                        
                        tx.commit()
                        
                        # Update metrics
                        self.metrics.record_entity_created(entities_created)
                        self.metrics.record_entity_updated(entities_updated)
                        self.metrics.record_mentions_created(len(deduplicated_graph.canonical_entities))
                        self.metrics.record_relations_created(relations_created)
                        
        except Exception as e:
            logger.error(f"Failed to store document {doc_id} in Neo4j: {e}")
            raise
    
    def _create_document_node(self, tx, curated_doc: ParsedDocument, doc_id: str, content_hash: str) -> None:
        """Create or update document node in Neo4j."""
        query = """
        MERGE (d:Doc {namespace: $namespace, doc_id: $doc_id})
        SET d.title = $title,
            d.content = $content,
            d.content_hash = $content_hash,
            d.source_path = $source_path,
            d.last_processed_at = datetime()
        RETURN d
        """
        
        tx.run(query,
               namespace=self.namespace,
               doc_id=doc_id,
               title=curated_doc.title or "",
               content=curated_doc.text or "",
               content_hash=content_hash,
               source_path=str(self.source_path))
    
    def _create_canonical_entity_node(self, tx, canonical_entity) -> str:
        """Create or update canonical entity node in Neo4j."""
        # Use canonical name for normalization
        normalized_name = canonical_entity.canonical_name.lower().strip()
        
        # Flatten features into Neo4j-compatible properties
        features = canonical_entity.features or {}
        dedup_method = features.get("dedup_method", "unknown")
        original_mention_id = features.get("original_mention_id", "unknown")
        confidence = float(features.get("confidence", 1.0))
        
        # Create or merge entity node
        query = """
        MERGE (e:Entity {namespace: $namespace, entity_type: $entity_type, normalized_name: $normalized_name})
        SET e.name = $name,
            e.aliases = $aliases,
            e.mention_count = $mention_count,
            e.dedup_method = $dedup_method,
            e.original_mention_id = $original_mention_id,
            e.confidence = $confidence,
            e.last_seen_at = datetime(),
            e.kg_id = CASE WHEN e.kg_id IS NULL THEN randomUUID() ELSE e.kg_id END
        RETURN e.kg_id as kg_id
        """
        
        result = tx.run(query,
                       namespace=self.namespace,
                       entity_type=canonical_entity.entity_type,
                       normalized_name=normalized_name,
                       name=canonical_entity.canonical_name,
                       aliases=canonical_entity.aliases,
                       mention_count=len(canonical_entity.mention_ids),
                       dedup_method=dedup_method,
                       original_mention_id=original_mention_id,
                       confidence=confidence)
        
        # Get the kg_id for use in relationships
        record = result.single()
        return record['kg_id'] if record else f"{self.namespace}:{canonical_entity.entity_type}:{normalized_name}"
    
    def _create_mentions_relationship(self, tx, doc_id: str, entity_kg_id: str, confidence: float) -> None:
        """Create MENTIONS relationship between document and entity."""
        query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
        MATCH (e:Entity {kg_id: $entity_kg_id})
        MERGE (d)-[:MENTIONS {confidence: $confidence, created_at: datetime()}]->(e)
        """
        
        tx.run(query,
               namespace=self.namespace,
               doc_id=doc_id,
               entity_kg_id=entity_kg_id,
               confidence=confidence)
    
    def _create_canonical_relationship(self, tx, src_entity_kg_id: str, dst_entity_kg_id: str, relation) -> None:
        """Create relationship between canonical entities."""
        # Extract and flatten features
        features = relation.features or {}
        confidence = float(features.get('confidence', 0.5))
        extraction_method = features.get('extraction_method', 'unknown')
        
        query = """
        MATCH (src:Entity {kg_id: $src_kg_id})
        MATCH (dst:Entity {kg_id: $dst_kg_id})
        MERGE (src)-[r:RELATION {type: $relation_type}]->(dst)
        SET r.confidence = $confidence,
            r.extraction_method = $extraction_method,
            r.created_at = CASE WHEN r.created_at IS NULL THEN datetime() ELSE r.created_at END,
            r.last_seen_at = datetime()
        """
        
        tx.run(query,
               src_kg_id=src_entity_kg_id,
               dst_kg_id=dst_entity_kg_id,
               relation_type=relation.type,
               confidence=confidence,
               extraction_method=extraction_method)