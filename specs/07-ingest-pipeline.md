# Step 7: Ingest Pipeline

## Overview

Step 7 implements the end-to-end ingest pipeline that orchestrates all previous components into a complete workflow with multi-format document support, dual extraction, and deduplication capabilities. The pipeline discovers document files (HTML, PDF, DOCX, etc.) under a source folder, runs curation via configurable CurationBackend from Step 3 to produce markdown and curated text, uses configurable extraction backends from Step 6 (LLM or spaCy), applies entity resolution via configurable deduplication backends (Splink/Zingg), performs entity linking to existing KG entities, and writes `:Doc` and `:Entity` nodes and relationships into Neo4j according to the schema (Step 5). This is the first step that runs the full path from filesystem → curation → extraction → deduplication → linking → graph, focusing on correctness, configurability, and hooks integration (`process_before_store`, `process_after_batch`). Step 7 does NOT handle graph visualization (that's Step 8).

## Scope

### In Scope

- Implement the ingestion pipeline that:
  - Walks the `--source` directory to discover document files (HTML, PDF, DOCX, etc.)
  - Uses configurable CurationBackend (Step 3) to process documents into markdown and curated text
  - Saves markdown files to `output/markdowns/<namespace>/<doc_id>.md`
  - For each curated document, runs configurable extraction backend (Step 6) to produce LexicalGraph
  - Applies configurable deduplication backend (Splink/Zingg/none) to produce DedupedLexicalGraph
  - Runs entity linking to map canonical entities to existing KG entities
  - Applies `process_before_store` hooks to the processed data
  - Upserts `:Doc` and `:Entity` nodes in Neo4j and creates:
    - `(:Doc)-[:MENTIONS]->(:Entity)` relationships
    - Ontology-driven `(:Entity)-[:RELATION]->(:Entity)` relationships
  - Includes `source_format`, `markdown_path`, `page_count` in `:Doc` node properties
  - Applies `process_after_batch` hook at the end of a batch or ingest run
- Implement full semantics for `kg-forge ingest` options:
  - `--source`, `--namespace`, `--dry-run`, `--refresh`
  - `--curator` (docling|hyland_ke) - selects document curation backend
  - `--prompt-template`, `--model` (for LLM backend)
  - `--extractor` (llm|spacy), `--dedup-backend` (none|splink|zingg|both)
- Implement **content hashing** and **idempotent ingest**:
  - Compute MD5 of curated text per document
  - Skip re-import if hash unchanged (unless `--refresh` is set)
- Handle curation failures gracefully:
  - Log curation errors with file path and reason
  - Skip failed documents and continue processing
  - Track curation failure count in batch summary
- Integrate extraction error-handling rules from Step 6 into batch ingest:
  - Per-document failures are skipped with logging
  - Backend-specific consecutive failure tracking and abort logic
- Implement comprehensive ingest metrics (docs curated, docs processed, entities extracted/deduplicated/linked, curation failures)
- End-to-end tests using:
  - Fake curation backends from Step 3
  - Fake extraction backends from Step 6
  - Mock deduplication backends
  - Docker-based Neo4j fixture from Step 5

### Out of Scope

- Graph visualization and rendering (Step 8)
- Advanced Splink/Zingg configuration tuning or model training
- Custom deduplication backend implementations beyond Splink/Zingg integration
- Complex ontology-inferred relationship creation beyond direct entity-to-entity relations
- KE SaaS pipeline integration (future step)
- Multi-tenant orchestration or multi-namespace migrations (beyond using `--namespace`)
- Performance optimizations like parallel processing or bulk import strategies
- Advanced chunking strategies beyond 1 page = 1 chunk
- Real-time or streaming ingest capabilities

## Step Integration

### Inputs from Step 3 (Document Curation)

Step 7 depends on Step 3 providing:
- **CurationBackend**: Pluggable backend interface (Docling or hyland_ke)
- **CurationResult**: Output model with curated_text, markdown_content, markdown_path, metadata
- **Multi-Format Support**: Ability to process HTML, PDF, DOCX, and other formats
- **Format Detection**: Automatic detection of document format from file extension
- **Markdown Storage**: Organized storage in `output/markdowns/<namespace>/`
- **Error Handling**: Graceful handling of curation failures

### Inputs from Step 5 (Neo4j Bootstrap)

Step 7 depends on Step 5 providing:
- **Neo4jClient**: Configured database connection with proper credentials and URI
- **Database Schema**: Initialized `:Doc` and `:Entity` node types with constraints and indexes
- **Updated :Doc Schema**: Support for `source_format`, `markdown_path`, `page_count` properties
- **Merge Key Constraints**: 
  - `:Doc` nodes: `(namespace, doc_id)` uniqueness constraint (doc_id includes extension)
  - `:Entity` nodes: `(namespace, entity_type, normalized_name)` uniqueness constraint
- **Graph Database**: Empty or existing Neo4j database ready for content ingestion
- **Test Infrastructure**: Docker-based Neo4j fixture for testing

### Outputs to Step 7 Sub-Components

This specification implements Step 7c (Pipeline Wiring) which orchestrates:

**Step 7a (Deduplication Backend) - Implemented in this spec:**
- Input: `LexicalGraph` from Step 6 extraction backends
- Output: `DedupedLexicalGraph` with `CanonicalLexicalEntity` instances
- Backends: Splink, Zingg, or no-dedup pass-through

**Step 7b (Entity Linking Backend) - Implemented in this spec:**
- Input: `CanonicalLexicalEntity` instances from Step 7a
- Output: `LinkResult` objects with linking decisions (existing vs new entities)
- Process: Matches canonical entities against existing Neo4j KG entities

**Step 7c (Pipeline Wiring) - This specification:**
- Input: All outputs from Steps 3 (curation), 5 (Neo4j), and 6 (extraction)
- Output: Fully populated Neo4j Knowledge Graph ready for Step 8 visualization
- Process: End-to-end orchestration from multi-format documents → curation → extraction → deduplication → linking → storage

## Pipeline Design

The ingest pipeline follows this sequence:

1. **Configuration Resolution**: Load settings from Step 0 and merge CLI options with precedence
2. **Backend Initialization**: 
   - Initialize curation backend (`--curator`: docling or hyland_ke)
   - Initialize extraction backend (`--extractor`: llm or spacy)
   - Initialize dedup backend (`--dedup-backend`: none, splink, zingg, or both)
3. **File Discovery**: Walk `--source` directory recursively, discovering all supported document files with stable ordering
   - Support multiple formats: `.html`, `.pdf`, `.docx`, `.pptx`, etc.
   - Filter based on file extension
4. **Per-Document Processing**: For each document file:
   - Detect file format based on extension
   - Derive `doc_id` from relative path **including extension** (e.g., "platform/intro.html", "platform/intro.pdf")
   - Extract `source_path`, apply `namespace` from config/CLI
   - **Curation Phase**: Call configured CurationBackend:
     - Process document \u2192 markdown + curated text
     - Save markdown to `output/markdowns/<namespace>/<doc_id>.md`
     - On curation failure:
       - Log error with file path and reason
       - Skip document and continue with next file
       - Increment curation failure counter
   - Compute `content_hash` (MD5) over curated text content
   - Check Neo4j for existing `:Doc` with same `(namespace, doc_id, content_hash)`:
     - If found and `--refresh` is NOT set \u2192 skip document (log as "unchanged")
     - If not found or `--refresh` is set \u2192 continue processing
   - **Extraction Phase**: Call configured ExtractionBackend with:
     - Curated text content (format-agnostic)
     - Ontology pack from Step 4
   - Receive `LexicalGraph` (mentions + relations) or handle failures:
     - Apply backend-specific retry & failure counter logic from Step 6
     - Skip individual failing documents while continuing batch
   - **Deduplication Phase** (if `--dedup-backend` ≠ none):
     - Pass `LexicalGraph` to configured DedupBackend (Splink/Zingg)
     - Receive `DedupedLexicalGraph` with canonical entities
   - **Entity Linking Phase**:
     - Pass canonical entities to EntityLinkerBackend
     - Receive `LinkResult` objects mapping to existing KG entities
   - Run `process_before_store` hook with:
     - Original curated content (CurationResult)
     - LexicalGraph or DedupedLexicalGraph
     - Neo4j client instance
   - Write to Neo4j (if not `--dry-run`):
     - Upsert `:Doc` node with:
       - content_hash, source_format, markdown_path, page_count (from CurationResult metadata)
       - Standard properties: namespace, doc_id, source_path
     - Create/merge `:Entity` nodes for canonical entities
     - Create `(:Doc)-[:MENTIONS]->(:Entity)` relationships
     - Create typed entity-entity relationships from relations
   - Accumulate metrics and entity records for batch processing
5. **Batch Completion**: After processing all documents:
   - Call `process_after_batch` hook with:
     - List of all entities created/updated in this run
     - Neo4j client instance
   - Log comprehensive metrics summary with pipeline stage breakdowns:
     - Total files discovered
     - Curation: successful, failed, skipped (unchanged)
     - Extraction: successful, failed
     - Documents written to Neo4j
     - Entities created/updated

### Batching Strategy

- **Transaction Boundaries**: Each document is processed in its own Neo4j transaction
- **Rollback Behavior**: Failed document writes are rolled back individually, processing continues
- **Batch Size**: No artificial batching - process documents as discovered (single-threaded in v1)
- **Memory Management**: Process documents sequentially to avoid loading all content into memory

## Hook Integration

Hooks are implemented in `kg_forge/hooks.py` with a registry pattern:

### Hook Registry

```python
class HookRegistry:
    def __init__(self):
        self._before_store_hooks: list[Callable] = []
        self._after_batch_hooks: list[Callable] = []
    
    def register_before_store(self, func: Callable):
        """Register process_before_store hook"""
        
    def register_after_batch(self, func: Callable):
        """Register process_after_batch hook"""
```

### Hook Signatures

- **process_before_store**:
  ```python
  def process_before_store(content: CuratedDocument, metadata: dict, kg_client: Neo4jClient) -> dict:
      """Modify metadata before storing in graph. Return modified metadata dict."""
  ```

- **process_after_batch**:
  ```python
  def process_after_batch(entities: list[EntityRecord], kg_client: Neo4jClient, interactive: InteractiveSession | None) -> None:
      """Process all entities after batch completion. No return value."""
  ```

### Hook Behavior

- **Optional Execution**: Hooks are optional - default implementations do nothing
- **Error Handling**: Hook exceptions are logged as warnings and do not abort the pipeline
- **Hook Discovery**: Hooks are auto-registered by importing modules in `kg_forge/hooks/` directory
- **Interactive Mode**: `InteractiveSession` is only available when `--interactive/--biraj` flag is set

## Deduplication Data Models

### CanonicalLexicalEntity

Represents a cluster of mentions believed to refer to the same real-world entity.

```python
@dataclass
class CanonicalLexicalEntity:
    id: str                           # Stable within namespace/batch
    entity_type: str                  # Same space as LexicalMention.entity_type
    canonical_name: str               # Chosen surface form
    aliases: List[str]                # All observed surface forms
    mention_ids: List[str]            # LexicalMention.id values in this cluster
    features: Dict[str, Any]          # Aggregated features from dedup backend
    
    # Common features examples:
    # - splink_score: probabilistic linkage score
    # - zingg_confidence: ML model confidence
    # - mention_count: number of mentions in cluster
    # - source_docs: set of documents where entity appears
```

### DedupedLexicalGraph

Lexical graph after deduplication processing.

```python
@dataclass
class DedupedLexicalGraph:
    canonical_entities: List[CanonicalLexicalEntity]
    relations: List[CanonicalRelation]
    metadata: Dict[str, Any]
    
    # Metadata examples:
    # - dedup_backend: "splink" | "zingg" | "none"
    # - processing_time: dedup operation duration
    # - clusters_formed: number of entity clusters created
    # - duplicate_pairs: number of duplicate pairs identified
```

### CanonicalRelation

Relation between canonical entities after deduplication.

```python
@dataclass
class CanonicalRelation:
    id: str                          # Unique relation identifier
    type: str                        # e.g., "WORKS_ON", "USES", "PART_OF"
    src_entity_id: str               # CanonicalLexicalEntity.id
    dst_entity_id: str               # CanonicalLexicalEntity.id
    features: Dict[str, Any]         # Aggregated from underlying LexicalRelations
    
    # Common features examples:
    # - confidence: aggregated confidence score
    # - source_relations: list of original LexicalRelation.id values
    # - evidence_count: number of supporting mentions
```

### LinkResult

Result of linking canonical entities to existing KG entities.

```python
@dataclass
class LinkResult:
    canonical_entity_id: str         # CanonicalLexicalEntity.id
    existing_entity_id: Optional[str] # Neo4j entity ID if matched
    new_entity_payload: Optional[Dict] # Properties for new entity creation
    confidence: float                 # Linking confidence (0.0-1.0)
    explanation: str                 # Human-readable linking rationale
```

## Deduplication Backend Interface

### DedupBackend Protocol

Common interface for all deduplication implementations.

```python
from typing import Protocol

class DedupBackend(Protocol):
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Apply entity resolution to group mentions into canonical entities.
        
        Args:
            lexical_graph: Raw extraction results with mentions and relations
            namespace: Current processing namespace for context
            
        Returns:
            DedupedLexicalGraph with canonical entities and updated relations
        """
        ...
```

### SpLinkDedupBackend

Probabilistic entity resolution using Splink.

```python
class SpLinkDedupBackend:
    def __init__(self, similarity_threshold: float = 0.8, blocking_rules: List[str] = None):
        self.similarity_threshold = similarity_threshold
        self.blocking_rules = blocking_rules or [
            "l.entity_type = r.entity_type",
            "substr(l.normalized_name, 1, 3) = substr(r.normalized_name, 1, 3)"
        ]
        
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Use Splink for probabilistic entity resolution.
        - Convert mentions to DataFrame with features
        - Apply blocking rules for efficiency
        - Train/apply probabilistic model
        - Form clusters based on similarity threshold
        """
        mentions_df = self._prepare_mentions_dataframe(lexical_graph.mentions)
        
        # Configure Splink model with comparison features
        settings = {
            "link_type": "dedupe_only",
            "blocking_rules_to_generate_predictions": self.blocking_rules,
            "comparisons": [
                cl.exact_match("entity_type"),
                cl.jaro_winkler_at_thresholds("normalized_name", [0.9, 0.8]),
                cl.jaccard_at_thresholds("surface_tokens", [0.8, 0.6])
            ]
        }
        
        linker = Linker(mentions_df, settings)
        clusters = linker.predict(threshold_match_probability=self.similarity_threshold)
        
        return self._build_deduped_graph(clusters, lexical_graph)
```

### ZinggDedupBackend

ML-based entity resolution using Zingg.

```python
class ZinggDedupBackend:
    def __init__(self, model_config: Dict[str, Any]):
        self.model_config = model_config
        self.zingg_client = None
        
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Use Zingg for ML-based entity resolution.
        - Convert mentions to Zingg input format
        - Apply pre-trained ML model for matching
        - Form clusters based on ML predictions
        """
        mentions_data = self._prepare_zingg_format(lexical_graph.mentions)
        
        # Configure Zingg pipeline
        zingg_config = {
            "data": mentions_data,
            "fieldDefinitions": [
                {"fieldName": "entity_type", "matchType": "EXACT"},
                {"fieldName": "normalized_name", "matchType": "FUZZY"},
                {"fieldName": "surface_text", "matchType": "TEXT"}
            ],
            "modelId": f"{namespace}_entity_model"
        }
        
        results = self.zingg_client.match(zingg_config)
        clusters = self._parse_zingg_results(results)
        
        return self._build_deduped_graph(clusters, lexical_graph)
```

### NoDedupBackend

Pass-through implementation that performs no deduplication.

```python
class NoDedupBackend:
    def deduplicate(self, lexical_graph: LexicalGraph, namespace: str) -> DedupedLexicalGraph:
        """
        Convert LexicalGraph to DedupedLexicalGraph without deduplication.
        Each mention becomes its own canonical entity.
        """
        canonical_entities = [
            CanonicalLexicalEntity(
                id=mention.id,
                entity_type=mention.entity_type,
                canonical_name=mention.surface,
                aliases=[mention.surface],
                mention_ids=[mention.id],
                features={"dedup_method": "none"}
            )
            for mention in lexical_graph.mentions
        ]
        
        # Convert relations to canonical format
        canonical_relations = [
            CanonicalRelation(
                id=rel.id,
                type=rel.type,
                src_entity_id=rel.src_mention_id,
                dst_entity_id=rel.dst_mention_id,
                features=rel.features
            )
            for rel in lexical_graph.relations
        ]
        
        return DedupedLexicalGraph(
            canonical_entities=canonical_entities,
            relations=canonical_relations,
            metadata={"dedup_backend": "none", "clusters_formed": len(canonical_entities)}
        )
```

## Entity Linking Backend Interface

### EntityLinkerBackend Protocol

Common interface for mapping canonical entities to existing KG entities.

```python
from typing import Protocol, List

class EntityLinkerBackend(Protocol):
    def link_entities(self, canonical_entities: List[CanonicalLexicalEntity], namespace: str) -> List[LinkResult]:
        """
        Link canonical entities to existing KG entities or mark for creation.
        
        Args:
            canonical_entities: Deduplicated entities to link
            namespace: Current processing namespace for scoping
            
        Returns:
            List of LinkResult objects with linking decisions
        """
        ...
```

### DefaultEntityLinker

Production entity linking implementation using Neo4j KG matching.

```python
class DefaultEntityLinker:
    def __init__(self, neo4j_client, similarity_threshold: float = 0.8):
        self.neo4j_client = neo4j_client
        self.similarity_threshold = similarity_threshold
        self.kg_builder = KGCandidateBuilder(neo4j_client)
        self.matcher = SimilarityMatcher()
        
    def link_entities(self, canonical_entities: List[CanonicalLexicalEntity], namespace: str) -> List[LinkResult]:
        """
        Link each canonical entity to existing KG entities or mark for creation.
        """
        results = []
        
        # Build candidate KB from Neo4j for this namespace and entity types
        entity_types = {entity.entity_type for entity in canonical_entities}
        candidate_kb = self.kg_builder.build_candidate_kb(namespace, entity_types)
        
        for canonical_entity in canonical_entities:
            # Generate candidates from KB
            candidates = self._generate_candidates(canonical_entity, candidate_kb)
            
            if not candidates:
                # No candidates - create new entity
                results.append(LinkResult(
                    canonical_entity_id=canonical_entity.id,
                    existing_entity_id=None,
                    new_entity_payload={
                        "namespace": namespace,
                        "entity_type": canonical_entity.entity_type,
                        "name": canonical_entity.canonical_name,
                        "normalized_name": self._normalize_name(canonical_entity.canonical_name),
                        "aliases": canonical_entity.aliases,
                        "confidence": 1.0
                    },
                    confidence=1.0,
                    explanation=f"No existing candidates found for {canonical_entity.canonical_name}"
                ))
                continue
            
            # Score candidates and select best match
            best_candidate = self.matcher.find_best_match(canonical_entity, candidates)
            
            if best_candidate and best_candidate.score >= self.similarity_threshold:
                # Link to existing entity
                results.append(LinkResult(
                    canonical_entity_id=canonical_entity.id,
                    existing_entity_id=best_candidate.entity_id,
                    new_entity_payload=None,
                    confidence=best_candidate.score,
                    explanation=f"Linked to existing entity via {best_candidate.match_reason}"
                ))
            else:
                # Create new entity - no good matches
                results.append(LinkResult(
                    canonical_entity_id=canonical_entity.id,
                    existing_entity_id=None,
                    new_entity_payload={
                        "namespace": namespace,
                        "entity_type": canonical_entity.entity_type,
                        "name": canonical_entity.canonical_name,
                        "normalized_name": self._normalize_name(canonical_entity.canonical_name),
                        "aliases": canonical_entity.aliases,
                        "confidence": 1.0
                    },
                    confidence=1.0,
                    explanation=f"No matches above threshold {self.similarity_threshold}"
                ))
        
        return results
        
    def _generate_candidates(self, canonical_entity: CanonicalLexicalEntity, candidate_kb: Dict) -> List[KGCandidate]:
        """Generate candidate entities from KB using multiple strategies."""
        candidates = []
        entity_type_kb = candidate_kb.get(canonical_entity.entity_type, [])
        
        for kb_entity in entity_type_kb:
            # Exact normalized name match
            if self._normalize_name(canonical_entity.canonical_name) == kb_entity.normalized_name:
                candidates.append(KGCandidate(
                    entity_id=kb_entity.id,
                    name=kb_entity.name,
                    score=1.0,
                    match_reason="exact_normalized_name"
                ))
                continue
            
            # Check aliases for exact matches
            canonical_aliases = {self._normalize_name(alias) for alias in canonical_entity.aliases}
            if canonical_aliases.intersection({kb_entity.normalized_name}):
                candidates.append(KGCandidate(
                    entity_id=kb_entity.id,
                    name=kb_entity.name,
                    score=0.95,
                    match_reason="alias_exact_match"
                ))
                continue
            
            # Fuzzy name similarity
            name_similarity = self.matcher.compute_name_similarity(
                canonical_entity.canonical_name, 
                kb_entity.name
            )
            if name_similarity >= 0.7:
                candidates.append(KGCandidate(
                    entity_id=kb_entity.id,
                    name=kb_entity.name,
                    score=name_similarity,
                    match_reason=f"name_similarity_{name_similarity:.2f}"
                ))
        
        return sorted(candidates, key=lambda c: c.score, reverse=True)
```

### KGCandidateBuilder

Builds candidate entity index from Neo4j for efficient matching.

```python
class KGCandidateBuilder:
    def __init__(self, neo4j_client):
        self.neo4j_client = neo4j_client
        
    def build_candidate_kb(self, namespace: str, entity_types: Set[str]) -> Dict[str, List[KGEntity]]:
        """
        Build candidate KB indexed by entity type from existing Neo4j entities.
        """
        candidate_kb = {}
        
        for entity_type in entity_types:
            # Query existing entities of this type in namespace
            query = """
            MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type})
            RETURN e.id as entity_id, e.name as name, e.normalized_name as normalized_name,
                   e.aliases as aliases, e.confidence as confidence
            LIMIT 1000
            """
            
            results = self.neo4j_client.run(query, namespace=namespace, entity_type=entity_type)
            
            kb_entities = []
            for record in results:
                kb_entities.append(KGEntity(
                    id=record["entity_id"],
                    name=record["name"],
                    normalized_name=record["normalized_name"],
                    aliases=record["aliases"] or [],
                    confidence=record["confidence"] or 1.0
                ))
            
            candidate_kb[entity_type] = kb_entities
            
        return candidate_kb
```

### SimilarityMatcher

Computes similarity scores between canonical entities and KG candidates.

```python
class SimilarityMatcher:
    def __init__(self):
        self.name_matcher = NameMatcher()
        self.phonetic_matcher = PhoneticMatcher()
        
    def find_best_match(self, canonical_entity: CanonicalLexicalEntity, candidates: List[KGCandidate]) -> Optional[KGCandidate]:
        """Find the best matching candidate with combined scoring."""
        if not candidates:
            return None
            
        # Candidates are already sorted by individual scores
        best_candidate = candidates[0]
        
        # Apply additional context-based scoring if available
        context_boost = self._compute_context_similarity(canonical_entity, best_candidate)
        best_candidate.score = min(1.0, best_candidate.score + context_boost)
        
        return best_candidate
        
    def compute_name_similarity(self, name1: str, name2: str) -> float:
        """Compute string similarity between two entity names."""
        # Combine multiple similarity metrics
        jaro_score = self.name_matcher.jaro_winkler(name1, name2)
        phonetic_score = self.phonetic_matcher.soundex_similarity(name1, name2)
        
        # Weighted combination
        return (jaro_score * 0.7) + (phonetic_score * 0.3)
        
    def _compute_context_similarity(self, canonical_entity: CanonicalLexicalEntity, candidate: KGCandidate) -> float:
        """Boost score based on contextual features (future enhancement)."""
        # Could consider:
        # - Co-occurring entities in same documents
        # - Similar relationship patterns
        # - Document/section context overlap
        return 0.0  # Placeholder for future context-aware matching
```

### Entity Linking Data Models

```python
@dataclass
class KGEntity:
    """Existing entity from Neo4j knowledge graph."""
    id: str                    # Neo4j entity identifier  
    name: str                  # Display name
    normalized_name: str       # Normalized for matching
    aliases: List[str]         # Known aliases
    confidence: float          # Entity confidence score

@dataclass  
class KGCandidate:
    """Candidate entity for linking with match score."""
    entity_id: str            # Neo4j entity identifier
    name: str                 # Entity name
    score: float              # Similarity/match score (0.0-1.0)
    match_reason: str         # Explanation of why this is a candidate
```

## Neo4j Write Behaviour

Step 7 uses the Neo4j client and schema from Step 5 with these semantics:

### Node Creation and Merging

- **`:Doc` nodes**:
  - Merge key: `(namespace, doc_id)`
  - Always update: `content_hash`, `source_path`, `last_processed_at`
  - Create if not exists, update properties if exists

- **`:Entity` nodes**:
  - Merge key: `(namespace, entity_type, normalized_name)`
  - Update properties: `name`, `last_seen_at`, `confidence` (if higher)
  - Create if not exists, update properties if exists

### Relationship Creation

- **`:MENTIONS` relationships**:
  - Link `(:Doc)-[:MENTIONS]->(:Entity)` for each extracted entity
  - Properties: `confidence` (from LLM extraction result)
  - Create new relationship for each ingest (no deduplication)

- **Entity-entity relationships**:
  - Derived from entity definitions' `Relations` section where both entities exist
  - Create relationships like `(:Entity)-[:COLLABORATES_WITH]->(:Entity)` based on definitions
  - Only create if both source and target entities were extracted in current or previous runs

### Flag Semantics

- **Dry Run (`--dry-run`)**:
  - Run full pipeline including LLM calls and hook execution
  - Skip all Neo4j write operations (create, update, relationship creation)
  - Log what writes would have occurred at INFO level
  - Useful for testing pipeline without affecting database

- **Refresh (`--refresh`)**:
  - Ignore content hash comparison - always reprocess documents
  - Useful when entity definitions, prompt templates, or LLM model changes
  - Does not delete existing data - only updates/creates

### Transaction Strategy

- **Per-Document Transactions**: Each document is processed in its own transaction
- **Rollback on Failure**: Database errors cause transaction rollback for that document only
- **Continue on Failure**: Failed document writes are logged, processing continues with next document
- **Batch Hooks**: `process_after_batch` runs in separate transaction after all documents processed

## CLI Behaviour (`kg-forge ingest`)

The `kg-forge ingest` command implements the complete ingest pipeline:

```bash
kg-forge ingest --source <path> [options]
```

### Arguments and Options

- `--source PATH` (required): Root directory containing HTML files to process
- `--namespace TEXT` (optional): Namespace for this ingest run (default from config)
- `--dry-run` (flag): Run pipeline without writing to Neo4j
- `--refresh` (flag): Reprocess all documents ignoring content hash
- `--interactive` / `--biraj` (flag): Enable interactive mode for hooks
- `--prompt-template PATH` (optional): Override default prompt template file
- `--model TEXT` (optional): Override LLM model name from config
- `--extractor [llm|spacy]` (optional): Override extraction backend from config
- `--dedup-backend [none|splink|zingg|both]` (optional): Override deduplication backend from config
- `--max-docs INTEGER` (optional): Limit number of documents processed (for debugging)

### Command Behavior

**Progress and Logging**:
- Display file discovery progress with total count
- Show per-document processing status (processed/skipped/failed)
- Log LLM extraction results and Neo4j write operations
- Display final metrics summary:
  - Total files discovered
  - Documents processed, skipped (unchanged), failed
  - Entities created, updated
  - Total processing time

**Configuration Precedence**:
- Follow Step 1 precedence: YAML config < environment variables < CLI arguments
- Validate required configuration (Neo4j connection, entity definitions path)
- Support `--fake-llm` flag from Step 5 for testing

**Exit Codes**:
- `0`: Success (even if some documents skipped due to unchanged content hash)
- `1`: Configuration or validation errors
- `2`: LLM consecutive failure threshold exceeded (>10 failures)
- `3`: Critical Neo4j connection or schema errors

### Example Usage

```bash
# Basic ingest with default configuration (Docling curator, LLM extractor)
kg-forge ingest --source ./documents

# Ingest PDF documents using Docling
kg-forge ingest --source ./pdfs --curator docling

# Dry run to test without database writes
kg-forge ingest --source ./test_data --dry-run --fake-llm

# Refresh all documents with custom model and spaCy extractor
kg-forge ingest --source ./docs --refresh --extractor spacy

# Multi-format ingest with custom namespace
kg-forge ingest --source ./export --namespace "team_docs" --curator docling

# Debug mode with document limit
kg-forge ingest --source ./large_export --max-docs 10 --dry-run
```

## Project Structure

```
kg_forge/
├── ingest/
│   ├── __init__.py
│   ├── pipeline.py           # Core IngestPipeline class and orchestration
│   ├── hooks.py             # Hook registry and default implementations
│   ├── metrics.py           # IngestMetrics class for tracking statistics
│   └── filesystem.py        # File discovery and path utilities
├── dedup/
│   ├── __init__.py
│   ├── interface.py          # DedupBackend protocol
│   ├── splink_backend.py     # Splink implementation
│   ├── zingg_backend.py      # Zingg implementation  
│   ├── no_dedup_backend.py   # Pass-through implementation
│   └── ensemble_backend.py   # Combined Splink + Zingg backend
├── linking/
│   ├── __init__.py
│   ├── interface.py          # EntityLinkerBackend protocol
│   ├── default_linker.py     # Default entity linking implementation
│   ├── kg_candidate_builder.py  # Neo4j KB candidate generation
│   └── similarity_matcher.py    # String/context similarity scoring
├── cli/
│   ├── ingest.py            # CLI command implementation
│   └── main.py             # Updated to include ingest command
├── hooks/
│   ├── __init__.py
│   └── examples/
│       ├── __init__.py
│       ├── metadata_enricher.py  # Example process_before_store hook
│       └── batch_reporter.py     # Example process_after_batch hook
└── utils/
    ├── hashing.py           # Content hash utilities
    └── interactive.py       # InteractiveSession class for --biraj mode

tests/
├── test_ingest/
│   ├── __init__.py
│   ├── test_ingest_single_doc.py    # Single document processing
│   ├── test_ingest_multi_format.py  # Multi-format document processing (HTML, PDF, DOCX)
│   ├── test_ingest_curation.py      # Curation backend integration
│   ├── test_ingest_idempotency.py   # Hash-based skipping behavior
│   ├── test_ingest_dry_run.py       # Dry run mode validation
│   ├── test_ingest_error_handling.py # Curation/extraction failures and recovery
│   ├── test_ingest_hooks.py         # Hook integration testing
│   ├── test_ingest_metrics.py       # Metrics collection and reporting
│   └── test_filesystem.py          # File discovery utilities
├── test_cli/
│   └── test_ingest_cli.py           # End-to-end CLI command testing
└── data/
    └── documents/
        ├── sample_space/
        │   ├── page1.html           # Simple HTML document
        │   ├── report.pdf           # PDF document
        │   ├── doc.docx            # Word document
        │   └── nested/
        │       └── page3.html       # Nested directory structure
        └── malformed/
            ├── broken.html          # Invalid HTML for error testing
            └── corrupted.pdf        # Corrupted PDF for curation error testing
```

## Dependencies

Step 7 reuses existing dependencies without introducing new runtime requirements:

### Existing Dependencies

- **Document Curation**: `docling>=1.0.0` from Step 3
- **Neo4j Integration**: `neo4j>=5.0.0` from Step 5  
- **Extraction Backends**: `llama-index-llms-bedrock`, `boto3`, `spacy` from Step 6
- **Configuration**: `pyyaml`, `python-dotenv` from Step 0
- **CLI Framework**: `click`, `rich` from Step 0

### New Deduplication Dependencies

- **Splink**: `splink>=3.0.0` for probabilistic entity resolution
- **Zingg**: `zingg` for ML-based entity resolution (optional)
- **Pandas**: `pandas>=1.5.0` for data processing (required by Splink)
- **DuckDB**: `duckdb` as Splink backend (lightweight, no external database required)

### Standard Library Usage

- `hashlib` for MD5 content hashing
- `pathlib` for filesystem operations
- `os.walk()` for directory traversal
- `json` for metadata serialization

### Test Dependencies

- **Docker Integration**: Reuse existing Neo4j test fixtures from Step 4
- **File Fixtures**: Sample HTML files stored in `tests/data/html/`
- **Mock Objects**: Use existing patterns from Steps 2-5 for component isolation

No heavy new dependencies are introduced - Step 6 focuses on orchestration of existing components.

## Implementation Details

### Filesystem Traversal

**File Discovery Algorithm**:
- Use `os.walk()` for recursive directory traversal
- Filter files by `.html` extension (case-insensitive)
- Sort files alphabetically for reproducible processing order
- Generate `doc_id` from relative path: remove extension, normalize separators, lowercase

**Path Handling**:
```python
def derive_doc_id(file_path: Path, source_root: Path) -> str:
    """Convert file path to doc_id: relative/path/file -> relative_path_file"""
    relative_path = file_path.relative_to(source_root)
    return str(relative_path.with_suffix('')).replace(os.sep, '_').lower()
```

### Content Hashing Strategy

**Hash Computation**:
- Generate MD5 hash of curated text content (not raw HTML)
- Include metadata like title, extracted text, but exclude timestamps
- Store hash in `:Doc` node `content_hash` property for comparison

**Idempotency Logic**:
```python
def should_process_document(doc_id: str, content_hash: str, namespace: str, refresh: bool) -> bool:
    """Check if document needs processing based on content hash"""
    if refresh:
        return True
    
    existing = neo4j_client.get_document(namespace, doc_id)
    return existing is None or existing.content_hash != content_hash
```

### Chunking Strategy

**Initial Implementation**:
- 1 HTML file = 1 document = 1 chunk (as per architecture seeds)
- Future evolution point for larger documents or section-based chunking
- Document model from Step 2 supports multiple chunks per document

### Metrics Collection

**IngestMetrics Class**:
```python
@dataclass
class IngestMetrics:
    files_discovered: int = 0
    docs_processed: int = 0  
    docs_skipped: int = 0    # Due to unchanged content hash
    docs_failed: int = 0     # Due to LLM or Neo4j errors
    entities_created: int = 0
    entities_updated: int = 0
    processing_time: float = 0.0
```

**Logging Strategy**:
- INFO: Progress updates, successful operations, final metrics, deduplication results
- WARNING: Skipped documents, recoverable failures, dedup threshold warnings
- ERROR: Extraction failures, Neo4j write errors, deduplication backend failures
- DEBUG: Detailed pipeline steps, hook execution, dedup cluster details

### Deduplication Configuration

**Splink Configuration**:
```python
@dataclass
class SpLinkConfig:
    similarity_threshold: float = 0.8    # Minimum probability for match
    blocking_rules: List[str] = field(default_factory=lambda: [
        "l.entity_type = r.entity_type",
        "substr(l.normalized_name, 1, 3) = substr(r.normalized_name, 1, 3)"
    ])
    comparison_features: List[str] = field(default_factory=lambda: [
        "exact_match_entity_type",
        "jaro_winkler_normalized_name",
        "jaccard_surface_tokens"
    ])
    training_sample_size: int = 10000
```

**Zingg Configuration**:
```python
@dataclass
class ZinggConfig:
    model_type: str = "ml"               # ML model type
    match_threshold: float = 0.75        # Minimum confidence for match
    field_definitions: List[Dict] = field(default_factory=lambda: [
        {"fieldName": "entity_type", "matchType": "EXACT"},
        {"fieldName": "normalized_name", "matchType": "FUZZY"},
        {"fieldName": "surface_text", "matchType": "TEXT"}
    ])
    training_enabled: bool = True
```

**Backend Selection Logic**:
- `none`: Use NoDedupBackend (each mention = separate entity)
- `splink`: Use SpLinkDedupBackend with probabilistic matching
- `zingg`: Use ZinggDedupBackend with ML-based matching
- `both`: Run both backends, use ensemble scoring (Splink score * 0.6 + Zingg score * 0.4)

### Interactive Mode

**InteractiveSession**:
- Available only when `--interactive/--biraj` flag is set
- Passed to `process_after_batch` hook for user interaction
- Supports simple terminal-based prompts and confirmations
- Example use cases: manual entity validation, batch approval

**Implementation Assumptions**:
- Ingest pipeline is single-threaded in v1 for simplicity
- LLM calls are sequential (no parallel processing)
- Neo4j writes use individual transactions per document
- Hook execution is synchronous and blocking

## Testing Strategy

### End-to-End Test Infrastructure

**Test Environment Setup**:
- Docker-based Neo4j fixture from Step 4 (isolated test database)
- Fake LLM implementation from Step 5 (deterministic responses)
- Sample HTML files in `tests/data/html/` (realistic Confluence exports)
- Temporary directories for source path testing

### Core Test Scenarios

**Happy Path Testing** (`test_ingest_single_doc.py`):
- Process single HTML file through complete pipeline
- Verify `:Doc` node creation with correct properties
- Verify `:Entity` node creation for extracted entities
- Verify `:MENTIONS` relationships with confidence scores
- Assert metrics tracking (1 processed, 0 skipped, N entities created)

**Idempotency Testing** (`test_ingest_idempotency.py`):
- Run ingest twice on identical HTML content
- First run: creates nodes and relationships
- Second run without `--refresh`: skips processing (0 processed, 1 skipped)
- Verify no duplicate nodes or relationships created
- Test `--refresh` flag forces reprocessing despite unchanged content

**Dry Run Testing** (`test_ingest_dry_run.py`):
- Run complete pipeline with `--dry-run` flag
- Verify LLM calls are made and hooks are executed
- Assert zero writes to Neo4j database
- Verify logging shows "would create" messages for intended operations

**Error Handling Testing** (`test_ingest_error_handling.py`):
- Simulate LLM parse failures using fake LLM malformed responses
- Verify individual document failures are logged and skipped
- Test consecutive failure counter and abort behavior (>10 failures)
- Verify Neo4j write failures cause transaction rollback but continue processing

**Hook Integration Testing** (`test_ingest_hooks.py`):
- Register test hooks that modify metadata and track batch entities
- Verify `process_before_store` can alter entity extraction results
- Verify `process_after_batch` receives complete entity list
- Test hook exception handling (logged but doesn't abort pipeline)

**Deduplication Testing** (`test_ingest_deduplication.py`):
- Test each deduplication backend (none, splink, zingg) with known duplicate entities
- Verify canonical entity formation and alias preservation
- Test deduplication metrics tracking (clusters formed, duplicates merged)
- Test error handling for deduplication backend failures
- Mock Splink/Zingg for deterministic test results

**Entity Linking Testing** (`test_ingest_entity_linking.py`):
- Test linking with existing KG entities using exact and fuzzy name matches
- Test creation of new entities when no good candidates exist
- Verify LinkResult generation and confidence scoring
- Test entity linking with various similarity thresholds
- Mock Neo4j candidate KB for deterministic test scenarios

### Test Isolation and CI

**Database Isolation**:
- Each test uses unique namespace (e.g., `test_namespace_12345`)
- Test fixtures clean up created nodes after test completion
- No shared state between test runs

**CI Configuration**:
- All tests use fake LLM only (no real Bedrock API calls)
- Docker Neo4j containers managed by test fixtures
- Environment variable `KG_FORGE_TEST_MODE=true` enables test-specific behaviors
- Coverage target: >90% for ingest module components

**Performance Testing**:
- Measure processing time for batches of 10, 50, 100 documents
- Memory usage monitoring for large document sets
- Baseline metrics for regression detection

## Success Criteria

Step 6 is considered complete when:

- [ ] `kg-forge ingest --source tests/data/html --fake-llm` with Docker Neo4j:
  - Discovers and processes all HTML files in test data
  - Creates appropriate `:Doc` and `:Entity` nodes according to schema
  - Establishes `:MENTIONS` relationships with confidence scores
  - Logs processing metrics and exits with code 0
- [ ] **Idempotent behavior**: Re-running ingest on unchanged files skips processing (verified by metrics: 0 processed, N skipped)
- [ ] **Refresh semantics**: `--refresh` flag forces reprocessing despite unchanged content hash
- [ ] **Dry run functionality**: `--dry-run` executes full pipeline without Neo4j writes, logs intended operations
- [ ] **Hook integration**: Custom `process_before_store` and `process_after_batch` hooks are called at correct pipeline points
- [ ] **Error resilience**: LLM failures skip individual documents, >10 consecutive failures abort with non-zero exit code
- [ ] **Configuration integration**: CLI options override config file values following Step 1 precedence rules
- [ ] **Metrics accuracy**: Processing statistics (docs processed/skipped/failed, entities created/deduplicated) are correctly tracked and reported
- [ ] **Deduplication backends**: All backends (none, splink, zingg) process test data and produce expected canonical entities
- [ ] **Entity linking**: Canonical entities are correctly linked to existing KG entities or marked for creation
- [ ] **Backend configuration**: CLI flags `--extractor` and `--dedup-backend` override configuration values correctly
- [ ] **No API changes**: Steps 0-6 components integrate without modification (composition, not modification)
- [ ] **Test coverage**: Ingest and dedup modules achieve >90% test coverage with comprehensive end-to-end scenarios
- [ ] **CLI usability**: Command help text, error messages, and progress logging provide clear user experience

## Next Steps

Step 7 provides the fully-populated Knowledge Graph based on Confluence HTML exports by orchestrating the HTML parsing (Step 3), entity extraction (Step 6), and Neo4j storage infrastructure (Step 5) into a complete ingest workflow. 

**Outputs to Step 8 (Graph Rendering):**
- **Populated Neo4j Database**: Complete knowledge graph with `:Doc` and `:Entity` nodes
- **Rich Entity Relationships**: Both `(:Doc)-[:MENTIONS]->(:Entity)` and typed `(:Entity)-[:RELATION]->(:Entity)` relationships
- **Namespace Support**: All entities properly namespaced for multi-tenant visualization
- **Deduplication Metadata**: Canonical entities with aliases and confidence scores for enhanced rendering
- **Entity Linking Results**: Connections between extracted entities and existing KG entities
- **Content Hash Tracking**: Ability to identify recently updated vs stable content for visualization prioritization

**Outputs to Enhanced Query Operations:**
- **Traversal-Ready Graph**: Relationships enable graph traversal for finding related documents and entities
- **Confidence Scoring**: Entity and relationship confidence metadata for result ranking
- **Rich Metadata**: Document source paths, processing timestamps, and extraction metadata for debugging
- **Canonical Entity Names**: Deduplicated entity names and aliases for improved search and matching

The robust ingest pipeline established in Step 7 ensures that the graph contains high-quality, structured data ready for visualization and complex querying operations in subsequent steps.