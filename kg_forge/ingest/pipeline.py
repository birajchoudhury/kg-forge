"""
Core ingest pipeline orchestrating multi-format curation, entity extraction, and Neo4j storage.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

from kg_forge.config.settings import Settings, get_settings
from kg_forge.curation import create_curation_backend, CurationError
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.llm.exceptions import LLMError, ParseError, ValidationError, ExtractionAbortError
from kg_forge.models.curation import CurationResult
from kg_forge.utils.hashing import compute_string_hash
from kg_forge.utils.interactive import InteractiveSession
from kg_forge.ontology_manager import get_ontology_manager
from kg_forge.dedup.interface import create_dedup_backend
from kg_forge.linking.interface import create_entity_linker
from kg_forge.extraction.interface import create_extraction_backend

from .filesystem import FileDiscovery, derive_doc_id
from .hooks import HookRegistry, EntityRecord, get_global_registry
from .metrics import IngestMetrics


logger = logging.getLogger(__name__)


class IngestPipeline:
    """
    End-to-end ingest pipeline that orchestrates:
    1. Multi-format document discovery and curation (Step 3)
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
                 curator: Optional[str] = None,
                 extractor: Optional[str] = None,
                 dedup_backend: Optional[str] = None,
                 fake_llm: bool = False,
                 chunking_enabled: bool = False,
                 config: Optional[Settings] = None,
                 hook_registry: Optional[HookRegistry] = None):
        """
        Initialize ingest pipeline.
        
        Args:
            source_path: Root directory containing document files
            namespace: Namespace for this ingest run
            dry_run: Run without writing to Neo4j
            refresh: Reprocess all documents ignoring content hash
            interactive: Enable interactive mode for hooks
            prompt_template: Override prompt template file
            model: Override LLM model name
            max_docs: Limit number of documents processed
            curator: Curation backend (docling|hyland_ke, default from config)
            extractor: Extraction backend (llm|spacy, default from config)
            dedup_backend: Deduplication backend (none|splink|zingg|both, default from config)
            fake_llm: Use fake LLM for testing
            chunking_enabled: Enable document chunking for LLM context control
            config: Application configuration (uses default if None)
            hook_registry: Hook registry (uses global if None)
        """
        self.source_path = Path(source_path).resolve()
        self.dry_run = dry_run
        self.refresh = refresh
        self.interactive_mode = interactive
        self.max_docs = max_docs
        self.fake_llm = fake_llm
        self.chunking_enabled = chunking_enabled
        
        # Load configuration
        self.config = config or get_settings()
        self.namespace = namespace or self.config.app.default_namespace
        
        # Backend selection
        self.curator = curator or getattr(self.config.app, 'default_curator', 'docling')
        self.extractor = extractor or self.config.app.default_extractor
        self.dedup_backend = dedup_backend or self.config.app.default_dedup_backend
        
        # Markdown output directory
        self.markdown_base_dir = Path("output/markdowns")
        self.markdown_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.file_discovery = FileDiscovery(self.source_path)
        
        # Initialize curation backend
        curation_config = {}
        if self.curator == "hyland_ke":
            # Get credentials from hyland_ke config section
            curation_config['hyland_client_id'] = getattr(self.config.hyland_ke, 'client_id', None)
            curation_config['hyland_client_secret'] = getattr(self.config.hyland_ke, 'client_secret', None)
            curation_config['hyland_api_url'] = getattr(self.config.hyland_ke, 'api_url', None)
            curation_config['hyland_oauth_url'] = getattr(self.config.hyland_ke, 'oauth_url', None)
            # Build curation options dict from config
            curation_options = {
                'normalization': {
                    'quotations': getattr(self.config.hyland_ke, 'normalize_quotations', True),
                    'dashes': getattr(self.config.hyland_ke, 'normalize_dashes', True)
                },
                'chunking': getattr(self.config.hyland_ke, 'enable_chunking', False),
                'chunk_size': getattr(self.config.hyland_ke, 'chunk_size', 1000),
                'embeddings': getattr(self.config.hyland_ke, 'enable_embeddings', False)
            }
            curation_config['hyland_curation_options'] = curation_options
        
        self.curation_backend = create_curation_backend(
            self.curator,
            hyland_client_id=curation_config.get('hyland_client_id'),
            hyland_client_secret=curation_config.get('hyland_client_secret'),
            hyland_api_url=curation_config.get('hyland_api_url'),
            hyland_oauth_url=curation_config.get('hyland_oauth_url'),
            hyland_curation_options=curation_config.get('hyland_curation_options')
        )
        
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
        elif self.extractor == "hybrid":
            extraction_config = {
                'gliner_model': "urchade/gliner_base",
                'device': "cpu",
                'llm_model_name': model or self.config.aws.bedrock_model_name,
                'llm_region': self.config.aws.default_region,
                'max_tokens': self.config.aws.bedrock_max_tokens,
                'temperature': self.config.aws.bedrock_temperature,
                'entity_confidence_threshold': 0.5,
                'fake_mode': fake_llm
            }
        else:  # fake backend
            extraction_config = {
                'fake_mode': True
            }
        self.extraction_backend = create_extraction_backend(self.extractor, extraction_config)
        
        # Load normalized OntologySchema from the active pack
        # Extraction backends expect OntologySchema, not OntologyPack
        self.active_ontology = active_pack.load_ontology_schema() if active_pack else None
        
        if not self.active_ontology:
            logger.warning("No ontology schema loaded - extraction may fail")
        
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
                   f"curator={self.curator}, extractor={self.extractor}, "
                   f"dry_run={dry_run}, refresh={refresh}, fake_llm={fake_llm}")
    
    def run(self) -> IngestMetrics:
        """
        Execute the complete ingest pipeline with multi-format support.
        
        Returns:
            IngestMetrics object with processing statistics
            
        Raises:
            ExtractionAbortError: If consecutive failure threshold exceeded
            Exception: For critical configuration or connection errors
        """
        logger.info("Starting ingest pipeline with multi-format curation")
        
        try:
            # Validate configuration and connections
            self._validate_setup()
            
            # Discover document files (multi-format)
            document_files = list(self.file_discovery.discover_documents())
            self.metrics.files_discovered = len(document_files)
            
            if self.max_docs:
                document_files = document_files[:self.max_docs]
                logger.info(f"Limited processing to {len(document_files)} documents")
            
            logger.info(f"Discovered {len(document_files)} document files to process")
            
            if not document_files:
                logger.warning("No supported document files found in source directory")
                self.metrics.finalize()
                return self.metrics
            
            # Process each document
            for i, file_path in enumerate(document_files, 1):
                logger.info(f"Processing document {i}/{len(document_files)}: {file_path.name}")
                
                try:
                    self._process_document(file_path)
                    
                    # Check for consecutive failure abort
                    if self.metrics.has_consecutive_failures:
                        raise ExtractionAbortError(
                            f"Exceeded maximum consecutive failures ({self.metrics.consecutive_failures})"
                        )
                        
                except ExtractionAbortError:
                    raise  # Re-raise abort errors
                except CurationError as e:
                    logger.error(f"Curation failed for {file_path}: {e}")
                    self.metrics.record_curation_failed(str(e))
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
        
        # Validate ontology pack is available
        try:
            self.ontology_manager.get_active_ontology()
            logger.debug("Ontology pack validated successfully")
        except Exception as e:
            raise RuntimeError(f"Ontology pack validation failed: {e}")
    
    def _process_document(self, file_path: Path) -> None:
        """Process a single document through the complete pipeline."""
        doc_id = derive_doc_id(file_path, self.source_path)
        
        try:
            # Curate document using configured curation backend
            start_time = time.time()
            curation_result = self._curate_document(file_path, doc_id)
            self.metrics.add_curation_time(time.time() - start_time)
            self.metrics.record_doc_curated()
            
            # Check if document needs processing (content hash comparison)
            content_hash = compute_string_hash(curation_result.curated_text)
            
            if not self.refresh and self._should_skip_document(doc_id, content_hash):
                logger.info(f"Skipping {doc_id} (unchanged content hash)")
                self.metrics.record_doc_skipped("unchanged content hash")
                return
            
            # Phase 1: Extract entities using configured backend
            extraction_start = time.time()
            lexical_graph = self._extract_entities(curation_result, doc_id)
            self.metrics.add_llm_time(time.time() - extraction_start)
            self.metrics.record_entities_extracted(len(lexical_graph.mentions))
            
            # Phase 2: Apply deduplication
            dedup_start = time.time()
            deduplicated_graph = self._apply_deduplication(lexical_graph)
            dedup_time = time.time() - dedup_start
            self.metrics.record_entities_deduped(len(deduplicated_graph.canonical_entities))
            
            # Phase 3: Apply entity linking
            linking_start = time.time()
            link_results = self._apply_entity_linking(deduplicated_graph)
            linking_time = time.time() - linking_start
            self.metrics.record_entities_linked(sum(1 for r in link_results if r.is_linked_entity()))
            
            # Prepare metadata for hooks
            metadata = {
                'curation_result': curation_result,
                'extraction_result': lexical_graph,
                'deduplicated_graph': deduplicated_graph,
                'link_results': link_results,
                'timing': {
                    'curation_time': time.time() - start_time,
                    'extraction_time': time.time() - extraction_start,
                    'dedup_time': dedup_time,
                    'linking_time': linking_time
                },
                'doc_id': doc_id,
                'namespace': self.namespace
            }
            
            processed_metadata = self.hook_registry.execute_before_store(
                curation_result.curated_text, metadata, self.neo4j_client
            )
            
            # Store in Neo4j
            if not self.dry_run:
                neo4j_start = time.time()
                self._store_document_and_entities(
                    curation_result, doc_id, content_hash, deduplicated_graph, link_results, processed_metadata
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
            
        except CurationError as e:
            logger.error(f"Curation failed for {file_path}: {e}")
            self.metrics.record_curation_failed(str(e))
            raise
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def _curate_document(self, file_path: Path, doc_id: str) -> CurationResult:
        """
        Curate document using configured curation backend.
        
        Args:
            file_path: Path to document file
            doc_id: Document ID (includes extension)
            
        Returns:
            CurationResult with curated text and metadata
            
        Raises:
            CurationError: If curation fails
        """
        try:
            logger.debug(f"Curating document: {file_path} (doc_id={doc_id})")
            
            # Curate document using backend
            curation_result = self.curation_backend.curate(
                source_path=file_path,
                namespace=self.namespace,
                markdown_base_dir=self.markdown_base_dir,
                chunking_enabled=self.chunking_enabled
            )
            
            chunk_info = f", chunks={len(curation_result.chunks)}" if curation_result.chunks else ""
            logger.info(f"Curated {doc_id}: {len(curation_result.curated_text)} chars, "
                       f"format={curation_result.metadata.source_format}, pages={curation_result.metadata.page_count}{chunk_info}")
            
            return curation_result
            
        except CurationError:
            raise  # Re-raise curation errors as-is
        except Exception as e:
            raise CurationError(f"Failed to curate document {file_path}: {e}")
    
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
    
    def _extract_entities(self, curation_result: CurationResult, doc_id: str):
        """
        Extract entities from curated content.
        
        If chunking is enabled and chunks are present, performs chunk-by-chunk extraction
        and merges the results into a single document-level LexicalGraph.
        
        Args:
            curation_result: CurationResult from curation backend
            doc_id: Document ID for this document
            
        Returns:
            LexicalGraph with extracted entities and relations
        """
        try:
            # Check if we have chunks to process
            if self.chunking_enabled and curation_result.chunks:
                logger.info(f"Processing {len(curation_result.chunks)} chunks for {doc_id}")
                
                # Extract from each chunk and merge
                merged_graph = None
                for idx, chunk in enumerate(curation_result.chunks):
                    logger.debug(f"Extracting from chunk {idx+1}/{len(curation_result.chunks)}: {chunk.chunk_id}")
                    
                    # Extract entities from this chunk
                    chunk_graph = self.extraction_backend.extract(
                        content=chunk.text,
                        ontology=self.active_ontology,
                        doc_id=chunk.chunk_id  # Use chunk_id for unique mention IDs
                    )
                    
                    # Add chunk metadata to all mentions
                    for mention in chunk_graph.mentions:
                        mention.features['chunk_id'] = chunk.chunk_id
                        if chunk.page is not None:
                            mention.features['page'] = chunk.page
                        if chunk.section:
                            mention.features['section'] = chunk.section
                    
                    # Update doc_id to reference the document, not the chunk
                    for mention in chunk_graph.mentions:
                        mention.doc_id = doc_id
                    
                    # Merge into accumulated graph
                    if merged_graph is None:
                        merged_graph = chunk_graph
                    else:
                        merged_graph = merged_graph.merge(chunk_graph)
                    
                    logger.debug(f"Chunk {chunk.chunk_id}: {len(chunk_graph.mentions)} mentions, {len(chunk_graph.relations)} relations")
                
                logger.info(f"Merged extraction: {len(merged_graph.mentions)} total mentions, {len(merged_graph.relations)} total relations")
                return merged_graph
            
            else:
                # Normal extraction from full document
                lexical_graph = self.extraction_backend.extract(
                    content=curation_result.curated_text,
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
    
    def _store_document_and_entities(self, curation_result: CurationResult, doc_id: str, 
                                   content_hash: str, deduplicated_graph, link_results, metadata: Dict[str, Any]) -> None:
        """
        Store document and deduplicated entities in Neo4j.
        
        Args:
            curation_result: CurationResult from curation backend
            doc_id: Document ID (includes extension)
            content_hash: Content hash of curated text
            deduplicated_graph: DedupedLexicalGraph with canonical entities
            link_results: List of EntityLinkResult objects
            metadata: Additional metadata from hooks
        """
        try:
            with self.neo4j_client:
                with self.neo4j_client.session() as session:
                    with session.begin_transaction() as tx:
                        # Store document node
                        self._create_document_node(tx, curation_result, doc_id, content_hash)
                        
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
                                    entity_map[canonical_entity.id] = link_result.linked_entity.id
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
    
    def _create_document_node(self, tx, curation_result: CurationResult, doc_id: str, content_hash: str) -> None:
        """
        Create or update document node in Neo4j.
        
        Args:
            tx: Neo4j transaction
            curation_result: CurationResult with document data
            doc_id: Document ID (includes extension)
            content_hash: Content hash of curated text
        """
        query = """
        MERGE (d:Doc {namespace: $namespace, doc_id: $doc_id})
        SET d.title = $title,
            d.content = $content,
            d.content_hash = $content_hash,
            d.source_path = $source_path,
            d.source_format = $source_format,
            d.markdown_path = $markdown_path,
            d.page_count = $page_count,
            d.last_processed_at = datetime()
        RETURN d
        """
        
        tx.run(query,
               namespace=self.namespace,
               doc_id=doc_id,
               title=curation_result.metadata.title or "",
               content=curation_result.curated_text or "",
               content_hash=content_hash,
               source_path=doc_id,  # Use doc_id as source_path
               source_format=curation_result.metadata.source_format,
               markdown_path=str(curation_result.markdown_path) if curation_result.markdown_path else None,
               page_count=curation_result.metadata.page_count or 0)
    
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