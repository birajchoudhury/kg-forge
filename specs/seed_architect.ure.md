# Architecture Seed – KG Forge CLI & Knowledge Graph

This document describes the **technical architecture** for a CLI tool that:

- **ingests** unstructured content,
- **extracts entities/topics** via one of three extraction pipelines:
  - an **LLM-based pipeline** (full LLM extraction),
  - **spaCy + GLiNER + GLiREL lexical graph pipeline** (zero-shot NER + relation extraction), or
  - **Hybrid GLiNER + LLM pipeline** (ontology-aware NER + LLM properties/relations),
- runs **deduplication** on extracted entities using **Splink/Zingg**,
- performs **entity linking** to an ontology-backed **Neo4j Knowledge Graph**,
- **queries** entities and related chunks,
- **renders** the graph for exploration.

The system is designed as an **experimental playground** to learn:

- how to extract meaningful entities/topics from content,
- how to store/merge/prune a KG,
- how to design and iterate on a useful ontology.

---

## 1. Goals & Scope

### 1.1 What We Want to Build

A **Python CLI tool** with three primary subcommands:

- `ingest`
  - curate content from multiple document formats (HTML, PDF, etc.) using a configurable curation backend,
  - **run one of three extraction pipelines** to form a lexical graph from the extracted entities and relations:
    - **LLM-based** (full LLM extraction),
    - **spaCy + GLiNER + GLiREL** (zero-shot lexical graph), or
    - **Hybrid** (GLiNER ontology-aware NER + LLM for properties and relations),
  - run **deduplication** on the lexical/entity layer using Splink/Zingg,
  - run **entity linking** against an ontology-backed KB,
  - populate/update a Neo4j-based Knowledge Graph.
- `query`
  - get entities associated with a chunk (Doc),
  - find related chunks via graph traversal.
- `render`
  - render the graph to HTML,
  - provide a way to navigate the graph visually.

The main goal is to help us **figure out how to build a Knowledge Graph from existing unstructured data** (starting from a Confluence HTML export), and to iterate quickly on ontology + extraction strategies.

### 1.2 Scope of Experimentation

The system should provide a **simple end-to-end pipeline** so we can focus on:

- **KG creation & usage**, not infrastructure plumbing.

For this project:

- `ingest` source = **filesystem** with folders containing various document formats  
  (e.g. HTML from **Confluence site export**, PDFs, etc.).

The user can choose the curation and extraction modes at runtime:

--curator [docling|hyland_ke] (default docling)
--extractor [llm|spacy|hybrid] (default llm)

For the first step, we want **basic implementations** with minimal external dependencies:

- curate text: simple HTML → curated text extraction,
- extract entities and relationships between entities using one of three methods and build a **lexical graph**: 
  - REST call to **Bedrock** (via LlamaIndex client) using a configurable prompt template,
  - via **spaCy + GLiNER + GLiREL** (zero-shot NER + relation extraction), or
  - via **Hybrid pipeline** (spaCy transformer NER + LLM for properties/relations),
- run **deduplication** on the lexical/entity layer using **Splink/Zingg**,
- perform **entity linking** from deduped mentions to canonical entities (ontology),
- populate/update the Neo4j Knowledge Graph.

The primary focus areas:

- storing/updating the graph,
- pruning/merging entities,
- iterating on ontology.

In the long term, we may:

- use a **KnowledgeEnrichment SaaS API** to run the full orchestrated pipeline as another extraction backend,
- use a **Content Lake** as the storage system.

The architecture must therefore be **modular**, with clear boundaries so that:

- extraction backends (LLM vs spacy pipeline vs hybrid vs KE API),
- deduplication backends (Splink vs Zingg vs none),
- knowledge graph (Neo4j vs DGraph vs AWS Neptune)
- and storage backends (filesystem vs Content Lake, etc.)

 can be swapped independently.

---

## 2. Technology & Dependencies

### 2.1 Languages & Tools

- **Language:** Python
- **Environment:**
  - Use `venv` for virtual environments.
  - Use `pip` and a `requirements.txt` to manage dependencies.
- **Testing:**
  - Use `pytest` as the test framework.
  - Generate test data under `tests/data` as needed.
  - Aim for good test coverage, especially around:
    - HTML curation,
    - entity-definition loading,
    - extraction backends (LLM + spacy pipeline) using fakes,
    - deduplication integration (Splink/Zingg mocks),
    - graph schema operations.

### 2.2 Core Libraries

- **CLI:** `click`
- **Graph DB:** Neo4j (official Python driver)
- **Graph Visualization:** `vis.js` (via generated HTML)
- **Ontology Processing:**
  - **rdflib** (TTL/RDF parsing and SPARQL queries for ontology ingestion)
- **Document Curation:**
  - **Docling** (multi-format document processing and conversion to markdown),
  - **Hyland KE** (future: curated content API integration).
- **LLM & KG Integration:** **LlamaIndex**
  - Use LlamaIndex **KnowledgeGraphIndex** plugged into Neo4j where helpful.
  - Use LlamaIndex **Bedrock client** for LLM calls.
- **NLP / Lexical Graph Pipeline**:
  - **spaCy** (tokenization, sentences, Doc/Span objects, KB & EntityLinker API),
  - **GLiNER** for NER (via its Python API or spaCy wrapper),
  - **GLiREL** for relation extraction.
- **Deduplication/ Entity Resolution**:
  - **Splink** (probabilistic, Python, good for tabular features),
  - **Zingg** (ML-based ER at larger scale; may be optional/advanced).
- **Environment Configuration:**
  - Use `.env` for configuration (e.g., via `python-dotenv` or similar).

### 2.3 Configuration

Parameters such as:

- Bedrock credentials (access keys / region),
- Neo4j location & credentials,
- Bedrock model name,
- **Curator backend** (docling or hyland_ke),
- **Extractor mode** (llm, spacy, or hybrid),
- **Dedup backend** (none, splink, zingg, both/ensemble),
are provided via a `.env` file.

- Provide `.env.example` as a template.
- The CLI must read configuration from `.env` (and can allow overrides via flags where relevant).

---

## 3. High-Level Architecture

### 3.1 Pipeline Overview

1. **Ingestion Source**
   - Read from a folder of documents (HTML, PDF, etc.) and subfolders.
   - Automatically detect file format based on extension and content.

2. **Curation (Document → Markdown → Curated Text)**
   - Use a configurable **CurationBackend** (`--curator` flag):
     - **Docling** (default): Multi-format document processor
       - Converts documents (HTML, PDF, DOCX, etc.) to markdown
       - Extracts clean text with structure preservation
       - Saves markdown to `output/markdowns/<namespace>/<doc_id>.md`
     - **hyland_ke** (future): Curated content API integration
   - Output:
     - **Markdown file**: Saved to disk for provenance and review
     - **Curated text**: Clean text string used by extraction backends
   - **Chunking**:
     - Start with **one file = one chunk** (one `Doc` node per document file).

3. **Ontology Ingestion & Normalization**
   - Load ontology from **TTL files** (.ttl) or **Markdown files** (.md) for backward compatibility
   - Parse TTL using `rdflib` to extract entities (rdfs:Class/owl:Class) and relations (rdf:Property/owl:ObjectProperty)
   - Parse Markdown from `entities_extract/*.md` (legacy format - see §4)
   - Normalize into `OntologySchema` with entities and relations
   - **Raw TTL/Markdown never passed to extraction backends**

4. **LLM / SpaCy Pipeline / Hybrid / KE-based Extraction (Configurable)**
  In v1, `--extractor` supports `llm`, `spacy`, and `hybrid`. A `KE` (KnowledgeEnrichment SaaS)
  backend is planned but not yet implemented.

  Depending on --extractor:
  - **LLM-based pipeline (llm)**
   - Build a prompt from:
     - `entities_extract/prompt_template.md`, and
     - concatenated entity-type definitions.
   - Call Bedrock via LlamaIndex client.
   - Parse output into a JSON-like metadata structure:
     {
       "entities": [
         {
           "type": "Product",
           "name": "Knowledge Discovery",
           "confidence": 0.92
         },
         {
           "type": "EngineeringTeam",
           "name": "Platform Engineering",
           "confidence": 0.89
         }
       ]
     }
   - Treat this as a **logical lexical graph** (mentions + optional relations).

 - **spaCy lexical graph pipeline (spacy)**
   - Run spacy → tokens, sentences (Doc).
   - Run GLiNER → entity mentions (with ontology-aligned labels).
   - Run GLiREL → relations between mentions.
   - Build an explicit lexical graph representation:
     - Mention nodes (with spans, types, features),
     - Edges (relations/co-occurrence).

5. **Deduplication (Splink/Zingg)**
 - Convert extracted mentions/entities (from either pipeline) into feature tables per entity type.
 - Run **entity resolution** using:
 - Splink and/or Zingg (configurable),
 - focusing on:
    - misspellings,
    - phonetic variants,
    - abbreviations/synonyms,
    - partial names, nicknames, etc.
 - Produce:
    - **mention clusters** (local duplicates within documents/corpus),
    - **canonical entity candidate records** (one row per deduped entity).

- The deduplicated structure is a **deduplicated lexical graph**:
    - Nodes = canonical lexical entities (clusters),
    - Edges = relations between those clusters.

6. **Entity Linking (spaCy KB or custom linker)**
 - Use a **KnowledgeBase** representation (spacy KB or equivalent) populated from the ontology and existing KG.
 - For each canonical lexical entity (cluster), run a **linker** that:
    - generates candidates from KB,
    - scores them using:
      - strings, identifiers, context relations from lexical graph,
      - ontology constraints, and
      - (optionally) Entity Resolution signals from Splink/Zingg.
 - Decide:
    - **link to existing KG entity**, or
    - **Create a new canonical entity** in KG.

7. **Extensibility Hooks (Optional Transform & Cleanup)**
  - `process_before_store(content, deduped_graph, kg_client)`:
    - called after deduplication and entity linking decisions, before KG write.
  - `process_after_batch(created_entities, kg_client, interactive_session)`:
    - batch cleanup / dedup / pruning after ingest completes.

8. **Graph Storage (Neo4j)**

 - Persist into Neo4j using a **simple property graph schema**:
    - :Doc and :Entity nodes (canonical),
    - :MENTIONS and typed :RELATION relationships between canonical entities,
    - all scoped by namespace.
 - The lexical graph itself may be:
    - held in memory for scoring, or
    - partially persisted (e.g., :Mention nodes) if we want full provenance.
 - Optionally expose this to LlamaIndex KnowledgeGraphIndex.

9. **Query & Render**
  - `query` CLI:
     - list entity types, entities, docs, related docs.
  - `render` CLI:
     - export a subgraph to HTML & visualize with vis.js.

  - A future render-lexical variant could visualize a local lexical graph for debugging.

10. **Experimentation & Iteration**

  - Adjust entity definitions, prompts, hooks.
  - Re-ingest with `--dry-run` or new `--namespace`.
  - Compare extraction strategies:
     --extractor llm vs --extractor spacy vs --extractor hybrid.
  - Compare dedup strategies:
  --dedup none/splink/zingg/both.
   - Observe impact in Neo4j & rendered graph.

## 3.2 Curation and Extraction as Pluggable Backends

### 3.2.0 Ontology Ingestion & Normalization

**TTL (.ttl) files are the new standard ontology format**, with backward compatibility for the legacy markdown-based format.

#### Architecture Flow:

```
TTL (.ttl files) ──┐
                   ├──> Ontology Ingestion ──> OntologySchema (normalized)
Markdown (.md)  ──┘                                   │
                                                       ├──> GLiNER config (labels + descriptions)
                                                       ├──> GLiREL config (relations + constraints)
                                                       └──> LLM prompt snippets (JSON)
```

**Key Principle**: Raw TTL files are **never passed directly** to spaCy, GLiNER, GLiREL, or LLMs. All downstream components consume the normalized `OntologySchema`.

#### OntologySchema (Internal Representation)

Normalized ontology structure used throughout the system:

```python
@dataclass
class EntityType:
    name: str                    # e.g., "Product", "Team"
    iri: str                     # e.g., "http://example.org/ont#Product"
    description: str             # Natural language description
    properties: List[Property]   # Entity-specific properties
    
@dataclass
class RelationType:
    name: str                    # e.g., "WORKS_ON"
    iri: str                     # e.g., "http://example.org/ont#worksOn"
    head_types: List[str]        # Allowed source entity types
    tail_types: List[str]        # Allowed target entity types
    description: str             # Natural language description
    properties: List[Property]   # Relation-specific properties

@dataclass
class OntologySchema:
    entities: Dict[str, EntityType]
    relations: Dict[str, RelationType]
    metadata: Dict[str, Any]     # Version, author, provenance, etc.
    
    def to_gliner_config(self) -> Dict[str, str]:
        """Generate GLiNER label config with natural language descriptions."""
        
    def to_glirel_config(self) -> Dict[str, RelationConstraints]:
        """Generate GLiREL relation config with type constraints."""
        
    def to_entity_config(self) -> Dict[str, Any]:
        """Generate entity configuration for schema-driven LLM extraction."""
```

#### Ontology Ingestion Backends

**TTLOntologyLoader** (primary, new):
- Parses .ttl files using `rdflib`
- Extracts entities (rdfs:Class or owl:Class)
- Extracts relations (rdf:Property, owl:ObjectProperty)
- Builds OntologySchema with IRIs preserved

**MarkdownOntologyLoader** (legacy, backward compatible):
- Parses entities_extract/*.md files
- Generates synthetic IRIs (e.g., `urn:kg-forge:entity:Product`)
- Builds OntologySchema for compatibility

Both loaders produce the same `OntologySchema` output.

### 3.2.1 CurationBackend

We treat document curation as a pluggable backend behind a common interface.

Conceptually:

```python
class CurationBackend(Protocol):
    def curate(self, file_path: str, namespace: str, chunking_enabled: bool = False) -> CurationResult:
        """Process a document file and return markdown + curated text + optional chunks.
        
        Args:
            file_path: Path to source document
            namespace: Current namespace for organizing outputs
            chunking_enabled: Whether to produce document chunks
            
        Returns:
            CurationResult with:
                - curated_text: Clean text for extraction (full or first chunk)
                - markdown_content: Full markdown representation
                - markdown_path: Where markdown was saved
                - chunks: List of DocumentChunk (if chunking_enabled)
                - chunks_path: Path to chunks.json file (if chunking_enabled)
                - metadata: Format, page count, chunking info, etc.
        """
```

Implementations:

- **DoclingCurationBackend**: Uses Docling library for multi-format processing (HTML, PDF, DOCX, etc.)
- **hyland_ke_CurationBackend** (future): Integration with Hyland curated content API

### 3.2.2 ExtractionBackend

We treat the extraction + lexical graph building as backends behind a common interface.
A separate DedupBackend (Splink/Zingg) receives the LexicalGraph and returns a DedupedLexicalGraph.

**All extraction backends receive `OntologySchema` (not raw TTL or markdown).**

Conceptually:

```python
class ExtractionBackend(Protocol):
    def extract(self, content: str, ontology: OntologySchema) -> LexicalGraph:
        """Produce a LexicalGraph (mentions + relations) from curated text.
        
        Args:
            content: Curated document text
            ontology: Normalized OntologySchema (from TTL or markdown)
            
        Returns:
            LexicalGraph with mentions and relations
        """
```

Implementations:

- **LLMExtractionBackend**: 
  - Uses `ontology.to_entity_config()` to generate entity configuration
  - Schema-driven extraction: generic prompts that adapt to any ontology
  - Separates core entities (global) from occurrence entities (document-specific)
  - Full LLM-based extraction (entities + properties + relations)
  
- **SpacyLexicalBackend**: 
  - Uses `ontology.to_gliner_config()` for entity labels
  - Uses `ontology.to_glirel_config()` for relation constraints
  - spaCy + GLiNER + GLiREL (zero-shot NER + relation extraction)
  
- **HybridExtractionBackend**: 
  - Phase 1: Uses `ontology.to_gliner_config()` for entity detection
  - Phase 2: Uses `ontology.to_entity_config()` for property and relation extraction
  - GLiNER + LLM (ontology-aware entity detection + LLM property/relation extraction)

A separate DedupBackend (Splink/Zingg) receives the LexicalGraph and returns a DedupedLexicalGraph.

### 3.2.3 Hybrid Extraction Backend

The **HybridExtractionBackend** combines the strengths of both approaches:

**Phase 1: Ontology-Aware Entity Detection with GLiNER**
- Uses GLiNER (Generalist and Lightweight model for Named Entity Recognition)
- **Ontology-guided**: Receives entity types directly from the active ontology pack
- Performs zero-shot NER for custom domain-specific entity types
- Detects entities that match the ontology schema (e.g., "Content Lake", "HXPR", "Workstream")
- Produces entity mentions with confidence scores and precise character offsets

**Phase 2: Property and Relation Extraction with LLM**
- Takes GLiNER-detected entities as input context
- Uses LLM to extract:
  - Additional properties for each entity based on ontology definitions
  - Relationships between detected entities based on ontology schema
- Constructs specialized prompts that reference the detected entities
- Validates relations against ontology-defined relationship types

**Benefits:**
- **Ontology alignment**: Both phases use the ontology (GLiNER for detection, LLM for enrichment)
- **Domain awareness**: GLiNER can detect custom entities that spaCy's pre-trained models miss
- **Efficiency**: Only calls LLM for complex property/relation extraction, not basic NER
- **Flexibility**: GLiNER adapts to any ontology without retraining
- **Fallback resilience**: If LLM fails, still returns graph with GLiNER-detected entities

**Configuration:**
```python
extraction_config = {
    'gliner_model': 'urchade/gliner_base',  # Zero-shot NER model
    'device': 'cpu',  # or 'cuda' for GPU
    'llm_model_name': 'anthropic.claude-3-haiku-20240307-v1:0',
    'llm_region': 'us-east-1',
    'entity_confidence_threshold': 0.5,  # GLiNER threshold
    'fake_mode': False
}
```

**Output:**
- `LexicalGraph` with:
  - Mentions from GLiNER (with `detection_method: "gliner"`)
  - Relations from LLM (with `extraction_method: "llm_hybrid"`)
  - Metadata indicating both gliner_model and llm_model used

A separate DedupBackend (Splink/Zingg) receives the LexicalGraph and returns a DedupedLexicalGraph.

## 3.3 Core In-Memory Data Models

These types are used by the curation, extraction, deduplication, and linking steps. They are in-memory models; only some of their information is ultimately persisted to Neo4j.

### 3.3.0 `CurationResult`

The output of a `CurationBackend` for a single document.

- `curated_text`: string (clean text suitable for extraction backends)
- `markdown_content`: string (full markdown representation of document)
- `markdown_path`: string (absolute path where markdown was saved)
- `chunks`: list of `DocumentChunk` or None (when chunking is disabled)
- `chunks_path`: string or None (absolute path where chunks.json was saved, when chunking enabled)
- `metadata`: dict  
  Examples: source_format ("html", "pdf", etc.), page_count, curation_backend, timestamp, file_size, chunking_enabled, chunk_count.

### 3.3.0a `DocumentChunk`

Represents a chunk of a document when chunking is enabled.

- `chunk_id`: string (unique identifier for this chunk, e.g., "<doc_id>_chunk_001")
- `doc_id`: string (parent document ID)
- `page`: int or None (page number if available from source document)
- `section`: string or None (section/heading name if available)
- `start_offset`: int (character offset in the full markdown where chunk starts)
- `end_offset`: int (character offset in the full markdown where chunk ends)
- `text`: string (the actual chunk text content)
- `metadata`: dict (optional additional metadata like chunk_index, heading_level, etc.)

### 3.3.1 `LexicalMention`

A single mention of an entity in curated text.

- `id`: string (unique within a document or batch)
- `doc_id`: string (links back to the `:Doc` node)
- `entity_type`: string (e.g., `"Product"`, `"Team"`, `"Topic"`)
- `surface`: string (exact text span)
- `start_offset`: int (character offset in curated text)
- `end_offset`: int (character offset in curated text)
- `features`: dict  
  Examples: normalized surface, token list, sentence index, surrounding sentence text, section, etc.

### 3.3.2 `LexicalRelation`

A relation between two lexical mentions, typically produced by GLiREL or inferred by the LLM.

- `id`: string
- `type`: string (e.g., `"WORKS_ON"`, `"USES"`, `"PART_OF"`)
- `src_mention_id`: string (ID of source `LexicalMention`)
- `dst_mention_id`: string (ID of destination `LexicalMention`)
- `features`: dict  
  Examples: confidence score, pattern that fired, sentence index, etc.

### 3.3.3 `LexicalGraph`

The lexical graph produced by an `ExtractionBackend`.

- `mentions`: list of `LexicalMention`
- `relations`: list of `LexicalRelation`
- `metadata`: dict  
  Examples: backend name (`"llm"`/`"spacy"`), model version, runtime stats.



### 3.3.4 `CanonicalLexicalEntity`

Represents a cluster of mentions that are believed to refer to the same real-world entity (output of deduplication).

- `id`: string (stable within a namespace/batch)
- `entity_type`: string (same space as `LexicalMention.entity_type`)
- `canonical_name`: string (chosen surface form)
- `aliases`: list of strings (all observed surface forms)
- `mention_ids`: list of `LexicalMention.id` values in this cluster
- `features`: dict  
  Examples: aggregated Splink/Zingg scores, count of mentions, source docs.

### 3.3.5 DedupedLexicalGraph

Lexical graph after deduplication.

- `canonical_entities`: list of `CanonicalLexicalEntity`
- `relations`: list of `CanonicalRelation`
- `metadata`: dict  
  Examples: dedup backend used (`"splink"`/`"zingg"`/`"none"`), thresholds, timestamp.

### 3.3.6 `LinkResult`

The result of linking a canonical lexical entity to the Neo4j KG.

- `canonical_entity_id`: string (ID of `CanonicalLexicalEntity`)
- `existing_entity_id`: string or `null`  
  Neo4j internal ID or business ID of an existing `:Entity`, if matched.
- `new_entity_payload`: dict or `null`  
  Properties to use when creating a new `:Entity` (if no existing entity matched).
- `confidence`: float (0.0–1.0)
- `explanation`: string (optional, for debugging / interactive review)

### 3.3.7 `CanonicalRelation`

- `id`: string
- `type`: string
- `src_entity_id`: string (CanonicalLexicalEntity.id)
- `dst_entity_id`: string (CanonicalLexicalEntity.id)
- `features`: dict (aggregated from underlying LexicalRelations)

---

## 4. Ontology Sources – TTL (Standard) & Markdown (Legacy)

This section defines how ontologies are represented and ingested into the system.

---

### 4.1 TTL Ontology Format (Standard)

**TTL (Turtle) is the standard ontology format.** Ontologies are defined using RDF/OWL vocabularies.

#### 4.1.1 Structure

A TTL ontology file contains:

1. **Entity Types** (rdfs:Class or owl:Class):
   - Class IRI (e.g., `<http://example.org/ont#Product>`)
   - `rdfs:label` for display name
   - `rdfs:comment` or `skos:definition` for description
   - Optional properties (datatype and object properties)

2. **Relation Types** (rdf:Property or owl:ObjectProperty):
   - Property IRI (e.g., `<http://example.org/ont#worksOn>`)
   - `rdfs:domain` (allowed head entity types)
   - `rdfs:range` (allowed tail entity types)
   - `rdfs:label` and `rdfs:comment` for documentation

Example TTL snippet:

```turtle
@prefix : <http://example.org/ont#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2001/XMLSchema#> .

:Product a owl:Class ;
    rdfs:label "Product" ;
    rdfs:comment "A software product or service offering" .

:Team a owl:Class ;
    rdfs:label "Team" ;
    rdfs:comment "An engineering team or organizational unit" .

:worksOn a owl:ObjectProperty ;
    rdfs:label "works on" ;
    rdfs:domain :Team ;
    rdfs:range :Product ;
    rdfs:comment "Indicates that a team works on a product" .
```

#### 4.1.2 Ingestion Process

1. **Parse TTL** with `rdflib`:
   - Load .ttl file(s) into an RDF graph
   - Query for classes (entities): `?class a owl:Class`
   - Query for properties (relations): `?prop a owl:ObjectProperty`
   
2. **Extract metadata**:
   - IRIs, labels, comments/descriptions
   - Domain/range constraints for relations
   
3. **Build OntologySchema**:
   - Normalize into internal representation
   - Generate configs for downstream components

#### 4.1.3 Multiple TTL Files

An ontology pack can include multiple .ttl files:
- Core ontology (domain concepts)
- Application-specific extensions
- Third-party vocabularies (FOAF, Dublin Core, etc.)

All files are merged into a single `OntologySchema`.

---

### 4.2 Markdown Ontology Format (Legacy - Backward Compatible)

**Markdown format is supported for backward compatibility only.** New ontologies should use TTL.

Entities and topics are defined as **markdown files** in a dedicated folder:

entities_extract/
  product.md
  component.md
  workstream.md
  team.md
  engineer.md
  domain.md
  concern.md
  topic.md
  ...

For backward compatibility:

- We treat **entities and topics the same way** in the pipeline.
  - **Entities** are often explicitly named in text (e.g., product names, team names).
  - **Topics** may not appear verbatim and are usually inferred from context.
- In the graph, both are stored as `:Entity` nodes; the distinction is via `entity_type` (e.g., `"Product"`, `"Topic"`).

- An ontology pack is represented on disk as a folder like `entities_extract/` containing:
  - one `.md` file per entity type,
  - a `prompt_template.md` file.

Typical entity types (not exhaustive):

- Software product  
- Service / component  
- Technology  
- Engineering team  
- Engineer  
- Engineering domain (Architecture, Platform Eng, CI/CD, QA, …)  
- Engineering concern (Security, AI Safety, Scalability, Robustness, …)  
- AI/ML domain (RAG, LLMs, fine-tuning, evaluation, observability, …)  
- Topic (generic concept)


---

### 4.2 Entity Definition File Structure

Each markdown file in `entities_extract/` describes **one entity type** and provides example values and relations.

Canonical structure:

# ID: <unique_type_identifier>
## Name: <Label for the entity type>
## Description: <Text description provided to LLM for extraction>
## Relations
  - <linked_entity_type_1> : <to_label> : <from_label>
  - <linked_entity_type_2> : <to_label> : <from_label>
## Examples:

### <example 1>
<additional description>

### <example 2>
<additional description>

Semantics:

- `ID`  
  - Becomes the `entity_type` value in the graph (e.g. "Product", "EngineeringTeam").
- `Name`  
  - Human-friendly label for the type (used in prompts/docs).
- `Description`  
  - Text fed to the LLM to explain what this entity type is and how to recognize it.
- `Relations`  
  - Defines **schema-level relations** between this entity type and others.
  - Format:  
    OtherType : TO_LABEL : FROM_LABEL
  - Example in `team.md`:
    Product : WORKS_ON : WORKED_ON_BY
    means the canonical graph relation is:
    (Team)-[:WORKS_ON]->(Product)
- `Examples`  
  - Realistic examples to anchor the LLM’s understanding.

---

### 4.3 Prompt Template & ENTITY_TYPE_DEFINITIONS

We maintain a prompt template:

entities_extract/prompt_template.md

This file contains the **base prompt** used for LLM extraction, including a placeholder:

... prompt text ...

You must strictly follow these definitions:

{{ENTITY_TYPE_DEFINITIONS}}

At runtime:

- The system:
  - Loads all `entities_extract/*.md` files (excluding `prompt_template.md`),
  - Concatenates their markdown content into a single string,
  - Replaces `{{ENTITY_TYPE_DEFINITIONS}}` in `prompt_template.md` with that string.
- The resulting prompt is what we send to the LLM (along with the curated document text) via the extraction backend.

This ensures the LLM always sees **the current ontology** as markdown text.

---

### 4.4 Validation & Tolerance

We intentionally keep validation **lightweight** to support fast iteration.

Rules:

- **Required field**
  - Only `ID` is strictly required.
  - If `ID` is missing, it should **default to the filename** (without extension).
- **Optional fields**
  - `Name`, `Description`, `Relations`, `Examples` are optional.
  - If present, they are included in the concatenated definitions.
  - If absent, the file is still valid; it just contributes less guidance.
- **No hard schema enforcement**
  - We do not block ingestion if a definition file is “imperfect”.
  - The system should:
    - log parsing problems at debug level,
    - skip only the broken parts, not the entire pipeline.

This design lets us rapidly tweak definitions without constantly fighting validation.

---

### 4.5 Round-trip: Graph → Markdown (export-entities)

As ingestion runs, we will **discover new entities** from content that are not yet curated in `entities_extract/`.

To support iterative ontology improvement:

- Provide an `export-entities` CLI command that:
  - Reads entities from Neo4j (`:Entity` nodes),
  - Groups them by `entity_type`,
  - Generates / updates markdown files under `entities_extract/` for each type.

Expected behaviour:

- For each `entity_type`, e.g. "Product":
  - Create or update `entities_extract/product.md`.
  - Append newly discovered `name` values as additional examples (or in a dedicated "Discovered" section).

This enables a virtuous loop:

1. Define initial types and examples in markdown.
2. Ingest content, discover more entities.
3. Export entities back to markdown.
4. Curate and refine those definitions.
5. Re-ingest with improved ontology.

This round-trip is critical for the **“experiment, observe, refine”** workflow that this CLI is designed to support.

### 4.6 OntologyPack

An `OntologyPack` is an in-memory wrapper around the active ontology, backed on disk
by either **TTL files** or **Markdown files** (legacy).

#### Structure:

```python
class OntologyPack:
    def __init__(self, pack_path: Path):
        """Initialize from TTL or Markdown ontology pack."""
        
    def load_ontology_schema(self) -> OntologySchema:
        """Load and normalize ontology into OntologySchema.
        
        - If .ttl files present: Use TTLOntologyLoader
        - Else: Use MarkdownOntologyLoader (legacy)
        
        Returns normalized OntologySchema.
        """
```

#### What it contains:

- **For TTL packs**: `.ttl` files with RDF/OWL ontology definitions
- **For Markdown packs** (legacy): 
  - Parsed entity-type definitions from `entities_extract/*.md`
  - Relation schema (allowed relations per type)
  - Reference to `prompt_template.md`

#### Key principle:

- `OntologyPack` loads and normalizes the ontology into `OntologySchema`
- **All extraction backends receive `OntologySchema`** (never raw TTL or markdown)
- Extraction backends call helper methods:
  - `ontology.to_gliner_config()` → GLiNER labels
  - `ontology.to_glirel_config()` → GLiREL relation constraints  
  - `ontology.to_entity_config()` → Entity configuration for schema-driven LLM extraction

---

## 5. LLM Call & KE Abstraction

### 5.1 Abstraction Layer

We reuse the `ExtractionBackend` abstraction introduced in §3.2. All concrete backends (LLM, spaCy pipeline, future KE SaaS) must:

- accept curated document text and the active ontology, and
- return a `LexicalGraph` (see §3.3) for that document.

See ExtractionBackend definition in §3.2.


### 5.2 LlamaIndex + Bedrock (Initial Backend)

- Use LlamaIndex **Bedrock client** to:
  - construct a prompt from `prompt_template.md` + concatenated entity definitions,
  - call the Bedrock model specified via configuration / --model flag,
  - parse the raw model output into a `LexicalGraph`:
      - build `LexicalMention`s for extracted entities,
      - optionally infer `LexicalRelation`s if the prompt asks for relations.

### 5.3 Error Handling Strategy

If the LLM output **cannot be parsed** into the expected JSON:

- Log the error.
- Retry once (with the same prompt).
- Track consecutive failures; if **more than 10 calls fail in a row**:
  - Abort the ingest with a **non-zero exit code**.
- If a single document fails but we have not crossed the threshold:
  - Skip that document,
  - Continue with the rest of the batch.

### 5.4 Call Strategy

- Start with **one LLM call per document**:
  - Ask the model to extract **all entities** in one shot.
- Later iterations can:
  - move to more granular strategies (e.g. per entity-type call),
  - or use multi-pass extraction.

---

## 6. Extensibility Hooks & Human-in-the-Loop

To support experimentation and custom logic, we expose **hooks**.

### 6.1 Hook Registration

- For v1, this can be simple:
  - a Python module containing a list of hook functions (no dynamic plugin system needed).
- Hooks are imported statically and called at well-defined points in the pipeline.

### 6.2 process_before_store

Called  after extraction + dedup + linking and ontology parsing, **before** writing to the KG.

Signature:

def process_before_store(
    content: str,
    deduped_graph: DedupedLexicalGraph,
    kg_client,
) -> DedupedLexicalGraph:
    """
    content: curated text of the document
    deduped_graph: DedupedLexicalGraph produced by the selected DedupBackend
    kg_client: client to query/update the KG if needed
    returns: modified DedupedLexicalGraph
    """



Use cases:

- custom filtering / normalization,
- adding derived attributes,
- pre-merge tweaks before graph persistence.

### 6.3 process_after_batch

Called **at the end of an import batch**.

Signature:

def process_after_batch(
    created_entities: list[dict],
    kg_client,
    interactive_session
) -> None:
    """
    created_entities: list of KG entity payloads (e.g. Neo4j :Entity properties)
    interactive_session: optional handle for interactive use (e.g. to prompt a human reviewer
in a REPL or notebook). In non-interactive runs it may be None.

    """


Responsibilities:
- Cleanup / prune the KG.
---

## 7. Knowledge Graph Schema & Storage

We use a **simple property graph schema** with two primary node types and a few relationships.

### 7.1 Node Types

#### 7.1.1 :Doc

Represents an ingested document. In v1, one document file = one Doc.

Label

- :Doc

Required properties

- namespace – string, experiment/environment name (e.g. "default").
- doc_id – string, stable ID including format (e.g. "platform/kd/intro.html", "platform/kd/intro.pdf").
- source_path – string, relative file path (e.g. "platform/kd/intro.html").
- source_format – string, document format (e.g. "html", "pdf", "docx").
- content_hash – string, MD5 of curated text (used to skip unchanged docs).

Optional properties

- markdown_path – string, path to saved markdown representation.
- page_count – int, number of pages (for paginated formats like PDF).

Merge key

- (namespace, doc_id)

Note: doc_id includes the file extension to allow same logical document in different formats to coexist.

#### 7.1.2 :Entity

Represents both **entities and topics**.

Label

- Always :Entity.
- Optionally additional label per type (e.g. :Entity:Product, :Entity:Topic).

Required properties

- namespace – string, experiment/environment name.
- entity_type – string, one of the types defined in entities_extract/*.md
  (e.g. "Product", "Team", "Topic").
- name – string, canonical name (e.g. "Knowledge Discovery").
- normalized_name – string, normalized name for matching.

Optional properties

- aliases – list of strings (all observed surface forms).
- mention_count – int (aggregated number of lexical mentions).
- dedup_features – map (backend-specific scores or cluster metadata).

Normalization:

- lowercase,
- trim whitespace,
- collapse multiple spaces,
- remove punctuation except alphanumeric characters.

Merge key

- (namespace, entity_type, normalized_name)

Topics

- Topics are simply entities with entity_type = "Topic" (and optionally label :Topic).

### 7.2 Relationships

#### 7.2.1 Markdown & Orientation

Canonical direction rule:

- The entity whose .md file defines the relation is the source.

Example from team.md:

Product : WORKS_ON : WORKED_ON_BY
means:

(Team)-[:WORKS_ON]->(Product)

#### 7.2.2 (:Doc)-[:MENTIONS]->(:Entity)

Links a document to the entities (including topics) mentioned in it.

Required properties

- namespace – string, same namespace as the connected nodes.

Other properties (e.g. confidence) are optional and can be added later.

For v1, we create one `(:Doc)-[:MENTIONS]->(:Entity)` edge per (doc_id, entity) pair,
aggregating lexical-level signals into optional properties such as:
- mention_count,
- max_confidence,
- first_seen_offset.

#### 7.2.3 (:Entity)-[:<RELATION>]->(:Entity)

Domain / ontology relationships between entities (e.g. team works on product, product uses technology).

- Relation type names (e.g. WORKS_ON, USES, etc.) are derived from the Relations section in entity definition markdown.
- Direction is defined by the schema (as described above).
- For v1, always use a **single canonical direction** per relation.

Required properties

- namespace – string, same namespace as the connected nodes.

### 7.3 Namespace

All commands accept --namespace (default "default"), and **always operate only** on nodes and relationships with that namespace.

- namespace is used to:
  - keep different experiments isolated in the same Neo4j database,
  - allow re-ingestion with changed ontology/prompts without clobbering other experiments.

Rules:

- Ingest commands **must set namespace** on all created nodes and relationships.
- Query and render commands **must filter** by the given namespace.

---

## 8. CLI Design & Commands

We use Click to implement a robust, discoverable CLI.

### 8.1 Global Structure

Top-level command exposes subcommands:

- ingest
- query
- render
- render-ontology
- neo4j (subcommands: init-schema, clear-database, status)
- export-entities

Common options:

- --namespace (default "default").

### 8.2 ingest Command

Responsibilities:

- Read document files from a folder (HTML, PDF, etc.),
- Curate documents to markdown and text using selected curation backend,
- Run extraction via selected backend (llm or spacy; KE backend planned for later),
- Run deduplication (if configured),
- Run entity linking,
- Call hooks (process_before_store, process_after_batch),
- Write graph to Neo4j.

Options:

- --source PATH (required)
  - Folder containing document files (HTML, PDF, DOCX, etc.).
- --namespace TEXT (default "default")
- --curator [docling|hyland_ke] (default docling)
  - Selects curation backend for document processing.
- --chunking [on|off] (default off)
  - Controls whether documents are split into chunks.
  - When on: produces <doc_id>.md + <doc_id>.chunks.json
  - When off: produces only <doc_id>.md (full document extraction)
- --refresh (flag)
  - If not set:
    - skip re-import when content_hash is unchanged.
- --dry-run (flag)
  - Run curation and extraction but **do not write** to the graph.
  - Useful for ontology/prompt tweaks.
- --prompt-template PATH
  - Override default entities_extract/prompt_template.md.
- --model TEXT
  - Override default Bedrock model name from config.
- --extractor [llm|spacy|hybrid] (default llm)
  - Selects extraction backend.
- --dedup-backend [none|splink|zingg|both] (default splink)  
      - In v1, `both` behaves like `splink`. A true ensemble mode will be added later.
  - Controls dedup engine.

Behaviour:

- For each document file under --source:
  - Detect file format (based on extension: .html, .pdf, .docx, etc.).
  - Compute doc_id as:
    - sub-path + filename with extension, lower case.
    - Example: "platform/kd/intro.html" or "platform/kd/intro.pdf"
  - Run selected CurationBackend:
    - Process document → markdown + curated text (+ optional chunks if --chunking=on).
    - Save markdown to `output/markdowns/<namespace>/<doc_id>.md`.
    - If --chunking=on: Save chunks to `output/markdowns/<namespace>/<doc_id>.chunks.json`.
    - On curation failure:
      - Log error with file path and reason.
      - Skip document and continue with next file.
  - Compute MD5 content_hash on curated text.
  - If a :Doc already exists with same (namespace, doc_id, content_hash):
    - and --refresh is not provided → skip.
  - Otherwise:
    - **Extraction (chunk-aware)**:
      - If --chunking=off: run extraction backend on full curated_text → LexicalGraph
      - If --chunking=on:
        - For each chunk in chunks:
          - Run extraction backend on chunk.text → LexicalGraph
          - Annotate each LexicalMention with chunk metadata (chunk_id, page, section)
        - Merge all chunk-level LexicalGraphs into document-level LexicalGraph
    - Run DedupBackend (if not none) → DedupedLexicalGraph.
    - Run EntityLinkerBackend → mapping of canonical lexical entities → KG entities.
    - call process_before_store,
    - Create/merge :Doc, :Entity, :MENTIONS, and :RELATION edges in Neo4j.
    - Include source_format, markdown_path, chunks_path (if --chunking=on) in :Doc properties.
    - collect entities for batch summary.

- After all docs:
  - call process_after_batch with list of entities, kg_client
  - Log summary including: total files, processed, skipped (unchanged), failed (curation errors)

### 8.3 query Command

Subcommands:

- list-types
  - list distinct entity_type values in the namespace.
- list-entities --type Product
  - list entities for a given type.
- list-docs
  - list Docs in the namespace (with optional pagination / filters).
- show-doc --id <chunk-id>
  - show curated text and metadata for a Doc by doc_id.
- find-related --entity "<value>" --type Product
  - find Docs and/or Entities related to a given entity name and type.

Common options:

- --namespace TEXT (default "default")
- --max-results INT (default 10)
- --format TEXT (json | text)

Behaviour:

- All subcommands must:
  - respect --namespace,
  - limit results to --max-results,
  - format output according to --format.

### 8.4 render Command

For rendering, we:

- generate an HTML page that uses vis.js to display the graph.

Options:

- --namespace TEXT (default "default")
- --out PATH
  - output HTML file (e.g. graph.html).
- --depth INT (default 2)
  - max hop distance from seed nodes.
- --max-nodes INT (default 100, allow larger caps e.g. up to 200).

Behaviour:

- Extract a subgraph from Neo4j (respecting namespace, depth, and node limit).
- Emit HTML + embedded JS that:
  - uses vis.js,
  - connects to Neo4j or uses a pre-fetched dataset,
  - visualizes :Doc and :Entity nodes and relationships.

### 8.4.1 render-ontology Command

For rendering ontology structure visualization:

Options:

- --ontology-pack TEXT
  - ontology pack to visualize (default: active or auto-detected).
- --out PATH
  - output HTML file (default: ontology.html).
- --layout [force-directed|hierarchical|circular|grid]
  - graph layout algorithm (default: force-directed).
- --include-examples
  - include entity examples as additional nodes.
- --theme [light|dark]
  - visualization theme (default: light).

Behaviour:

- Load entity definitions from active ontology pack.
- Build graph data showing entity types and their relationships.
- Generate self-contained HTML file using Cytoscape.js for visualization.
- Support interactive exploration with tooltips, zooming, and layout controls.

### 8.5 Additional Commands

- neo4j-start / neo4j-stop
  - Wrap starting/stopping a local Neo4j process,
  - Helpful for local dev & tests.

- neo4j clear-database
  - Purge the knowledge graph (delete all nodes and relationships).
  - Options:
    - --namespace TEXT (default: all namespaces)
      - Scope deletion to specific namespace only.
    - --yes (flag)
      - Skip confirmation prompt (for scripting).
    - --output [table|json|raw] (default: table)
      - Output format.
  - Behaviour:
    - If namespace is provided:
      - Delete only nodes/relationships with matching namespace property.
    - If namespace is not provided:
      - Delete ALL nodes and relationships in the database.
    - Requires confirmation unless --yes is provided.
    - Reports count of deleted nodes.

- export-entities
  - Read entities from Neo4j,
  - Generate entities_extract/*.md from KG content,
  - Used to sync discovered entities back into ontology files.

---

## 9. Ingestion & Curation Details

### 9.1 Multi-Format Document Processing

#### 9.1.1 Docling Backend (Default)

Docling processes multiple document formats:

- **Supported formats**: HTML, PDF, DOCX, PPTX, and more
- **Processing**:
  - Automatic format detection
  - Structure-aware conversion to markdown:
    - Preserves headings, lists, tables
    - Extracts text with minimal noise
    - Handles multi-column layouts, footnotes, etc.
  - Generates clean curated text for extraction

- **Output**:
  - Markdown file saved to `output/markdowns/<namespace>/<doc_id>.md`
  - Curated text string (cleaned, ready for extraction backends)
  - Metadata (format, page count, processing stats)

- **Error handling**:
  - Log failures with file path and error reason
  - Skip failed documents and continue processing
  - Track failure count in batch summary

#### 9.1.2 hyland_ke Backend (Future)

Integration with Hyland curated content API:

- API-based document processing
- Enterprise-grade curation with advanced features
- Same output contract as Docling backend

### 9.2 Document ID Generation

- **Format**: `<relative_path_with_extension_lowercase>`
- **Examples**:
  - `docs/platform/intro.html`
  - `docs/platform/intro.pdf`
  - `reports/q4/summary.docx`

- **Rationale**:
  - Including extension allows same logical document in different formats to coexist
  - Different formats may have different content/curation results
  - Clear provenance of source format

### 9.3 Chunking

#### 9.3.1 Overview

Chunking is an **optional feature** controlled by the `--chunking` CLI flag during ingestion.

**Why Chunking?**

- **LLM context limitations**: Large documents may exceed token limits or degrade extraction quality
- **Better extraction precision**: Processing focused segments improves entity/relation detection
- **Fine-grained provenance**: Track which page/section entities came from

#### 9.3.2 CLI Control

```bash
kg-forge ingest <path> --chunking=on   # Enable chunking
kg-forge ingest <path> --chunking=off  # Disable (default)
```

Future: `--chunking=semantic`, `--chunking=fixed-size` for advanced modes.

#### 9.3.3 Behavior When Chunking is OFF (Default)

- **One file = one document = one extraction unit**
- CurationBackend produces:
  - Full markdown file: `output/markdowns/<namespace>/<doc_id>.md`
  - Curated text (full document)
- ExtractionBackend processes entire document text in one pass
- Graph contains one `:Doc` node per file

#### 9.3.4 Behavior When Chunking is ON

**Curation Phase:**

CurationBackend produces **two artifacts** per document:

1. **`<doc_id>.md`** – Full markdown representation (unchanged from chunking=off)
2. **`<doc_id>.chunks.json`** – JSON array of DocumentChunk objects

Example `chunks.json`:
```json
[
  {
    "chunk_id": "doc123_chunk_001",
    "doc_id": "doc123",
    "page": 1,
    "section": "Introduction",
    "start_offset": 0,
    "end_offset": 512,
    "text": "# Introduction\n\nThis document describes..."
  },
  {
    "chunk_id": "doc123_chunk_002",
    "doc_id": "doc123",
    "page": 1,
    "section": "Architecture Overview",
    "start_offset": 512,
    "end_offset": 1024,
    "text": "## Architecture Overview\n\nThe system consists of..."
  }
]
```

**Extraction Phase:**

- ExtractionBackend receives the list of chunks (not full text)
- Processes **each chunk independently**:
  - For LLM backend: Send chunk.text + ontology to LLM
  - For spaCy backend: Run GLiNER + GLiREL on chunk.text
- Produces one `LexicalGraph` per chunk
- Each `LexicalMention` includes:
  - `chunk_id` in features/metadata
  - `page` and `section` from chunk metadata
  - Offsets are relative to chunk (or can be adjusted to full-doc offsets)
- Merge all chunk-level `LexicalGraph` instances into one document-level `LexicalGraph`

**Note on Cross-Chunk Entities and Relations:**

When chunking is enabled, each chunk is extracted independently. This design choice has important implications:

- **Same entity in multiple chunks** → Creates separate `LexicalMention` instances
  - Example: "RAG system" mentioned in chunk 1, chunk 3, and chunk 5 produces 3 distinct mentions
- **Relations between chunks** → Not detected at extraction time
  - Example: Entity A (chunk 1) relates to Entity B (chunk 3) - this relation won't appear in lexical graphs

**Why this design?**

✅ **Pros:**
- Maintains focused LLM context per chunk (500-1000 tokens)
- Enables parallel processing of chunks
- Provides fault tolerance (one chunk fails, others succeed)
- Better extraction quality on focused text segments

❌ **Trade-off:**
- Higher mention count (same entity = multiple mentions)
- Missing cross-chunk relations at lexical level
- Increased deduplication workload

**How cross-chunk issues are resolved:**

The deduplication and canonical graph construction phases address these limitations:

1. **Entity Resolution (Deduplication Phase):**
   - Mentions "John Smith" (chunk 1), "J. Smith" (chunk 3), "John Smith" (chunk 5) → clustered into one `CanonicalLexicalEntity`
   - Same entity across chunks is recognized and merged

2. **Cross-Chunk Relations (Canonical Graph):**
   - After entity linking to Neo4j, relations form between canonical entities
   - Example:
     - Chunk 1: "KD team works on Knowledge Discovery"
     - Chunk 2: "Knowledge Discovery uses RAG system"  
     - Chunk 3: "RAG system uses AWS Bedrock"
     - Chunk 5: "Platform Engineering maintains AWS Bedrock"
   - In the canonical graph: `(KD team)-[:WORKS_ON]->()-[:USES*]->(AWS Bedrock)<-[:MAINTAINS]-(Platform Engineering)`
   - The cross-chunk relation between "KD team" and "AWS Bedrock" **emerges through graph traversal**, not direct extraction

**Bottom line:** We accept chunk-local extraction (narrow view) in exchange for better per-chunk quality. The canonical graph (wide view) recovers cross-chunk relationships through deduplication and graph connectivity.

**Deduplication Phase:**

- Receives merged LexicalGraph from all chunks
- Deduplication works across all chunks (same as before)
- Canonical entities may reference mentions from multiple chunks
- Cross-chunk entity merging happens here

**Graph Storage:**

- One `:Doc` node per document (not per chunk)
- `:Entity` nodes linked to `:Doc` via `:MENTIONS`
- Optional: Store chunk-level provenance in `:MENTIONS` relationship properties:
  - `chunk_id`, `page`, `section`, `offset_in_chunk`

#### 9.3.5 Chunking Strategy (v1)

For v1, use **simple size/structure-based chunking**:

- Split on section boundaries (headings) when available
- Target chunk size: ~500-1000 tokens (configurable)
- Preserve context: Include section heading in each chunk
- Avoid splitting mid-sentence or mid-paragraph when possible

Future iterations may support:
- Semantic chunking (embedding-based similarity)
- Sliding window with overlap
- Custom chunking strategies per document type

---

## 10. Neo4j & LlamaIndex Integration

### 10.1 Neo4j Layer

Implement a kg_client (e.g. Neo4jClient) wrapping the official Neo4j driver:

- Methods:
  - create/merge :Doc,
  - create/merge :Entity,
  - create/merge :MENTIONS,
  - create/merge :RELATION edges,
  - query for types, entities, docs, related nodes.

Ensure:

- proper indexes/constraints on:
  - (:Doc {namespace, doc_id}),
  - (:Entity {namespace, entity_type, normalized_name}).

### 10.2 LlamaIndex KnowledgeGraphIndex

Use LlamaIndex’s KnowledgeGraphIndex to:

- plug into Neo4j,
- optionally:
  - run experiments on KG building,
  - expose KG to LLMs for higher-level graph queries.

The underlying schema in Neo4j must remain consistent with:

- :Doc,
- :Entity,
- :MENTIONS,
- typed :RELATION edges.

---

## 11. Implementation Plan (Steps 0–8)

We decompose the work into steps that allow us to test, verify, and adjust the spec.

Each step will have its own detailed spec (docs/specs/*.md), tests, and code.

### Step 0 – CLI Skeleton

- Implement the CLI logic:
  - command parsing,
  - help,
  - config loading from .env,
  - top-level subcommands (ingest, query, render, neo4j-start, neo4j-stop, export-entities).
- Add basic unit tests for CLI.
- Add a README.
- No actual processing or LLM calls yet.

### Step 1 – Ontology Management & TTL Ingestion

- Implement ontology pack system supporting **TTL (standard)** and **Markdown (legacy)**:
  - **TTL Ingestion**:
    - Use `rdflib` to parse .ttl files
    - Extract entities (rdfs:Class, owl:Class) with IRIs, labels, descriptions
    - Extract relations (rdf:Property, owl:ObjectProperty) with domain/range constraints
    - Build normalized `OntologySchema` from RDF graph
  - **Markdown Ingestion** (backward compatible):
    - Parse entities_extract/*.md files
    - Generate synthetic IRIs (e.g., `urn:kg-forge:entity:Product`)
    - Build `OntologySchema` for compatibility
  - **OntologySchema Helpers**:
    - `to_gliner_config()`: Generate entity labels + descriptions for GLiNER
    - `to_glirel_config()`: Generate relation constraints for GLiREL
    - `to_entity_config()`: Generate entity configuration for schema-driven LLM extraction
  - Dynamic loading and activation of ontology packs
  - Validation framework for ontology definitions
  - CLI commands for ontology inspection and management
  - Extensible architecture for custom ontology formats
- **Key Principle**: Raw TTL/Markdown never passed to extraction backends; only `OntologySchema`
- Add comprehensive test coverage:
  - TTL parsing and normalization
  - Markdown parsing (legacy compatibility)
  - Config generation for GLiNER, GLiREL, LLM
  - Round-trip TTL → OntologySchema → configs

### Step 2 – Ontology Visualization

- Implement ontology structure visualization using Cytoscape.js:
  - Interactive HTML generation showing entity types and relationships.
  - Multiple layout algorithms (force-directed, hierarchical, circular, grid).
  - Theme support (light/dark) and entity examples integration.
  - CLI render-ontology command with comprehensive options.
- Add comprehensive test coverage:
  - test functions covering all functionality.
  - HTML generation, layout options, theme support, and error handling.
- Self-contained HTML output with no external dependencies.

### Step 3 – Data Curation

- Implement CurationBackend interface and protocol.
- Implement DoclingCurationBackend:
  - Multi-format document processing (HTML, PDF, DOCX, etc.)
  - Automatic format detection based on file extension
  - Markdown generation and storage to `output/markdowns/<namespace>/<doc_id>.md`
  - Curated text extraction for downstream processing
  - Error handling: log and skip failed documents
- Add Docling dependency to requirements.txt.
- Generate test documents in tests/data:
  - HTML files (Confluence-style)
  - PDF files (multi-page, various layouts)
  - DOCX files (structured documents)
- Add comprehensive tests:
  - Format detection accuracy
  - Markdown generation quality
  - Curated text extraction (text is clean, structure preserved)
  - Error handling (corrupted files, unsupported formats)
  - Namespace-based markdown organization
  - CurationResult model validation
- Add CLI flag --curator to select backend (default: docling).
- Add CLI flag --chunking to control chunking (default: off, options: on|off).
- When --chunking=on:
  - CurationBackend must produce chunks array and save chunks.json
  - Each chunk includes: chunk_id, doc_id, page, section, start_offset, end_offset, text
- Stub hyland_ke_CurationBackend for future implementation.

### Step 4 – Load Entity Definitions (Integrated with Step 1)

**Note**: This step is now integrated into Step 1 (Ontology Management & TTL Ingestion).

- TTL ontology loading replaces direct entity definition loading
- Markdown loading preserved for backward compatibility
- All entity definitions normalized into `OntologySchema`
- CLI commands for ontology inspection show both TTL and Markdown sources

### Step 5 – Neo4j Bootstrap

- Implement connection to Neo4j.
- Initialize schema:
  - :Doc and :Entity node definitions,
  - indexes/constraints on merge keys.
- Implement CLI command to:
  - create DB structures,
  - initialize graph with loaded entity types (if needed).
- Add unit/integration tests:
  - using Docker-based Neo4j fixture in pytest.
  - implement initial CLI query behaviours (e.g. list-types).

### Step 6a – Plug Extraction through LLM backend 

- Implement LLMExtractionBackend:
   - **Receives `OntologySchema` (not raw TTL or markdown)**
   - Uses schema-driven extraction approach:
       - `ontology.to_entity_config()` → entity configuration with core/occurrence entities
       - Generic system and user prompts that adapt to any ontology
       - Automatic validation and normalization of extraction results
   - Call Bedrock via BedrockClient
   - Parse model output into LexicalGraph:
       - LexicalMentions with entity_type, surface, spans (if provided)
       - LexicalRelations
   - Implement parsing logic that:
       - validates JSON shape (core_entities and occurrence_entities),
       - validates entity properties against schema,
       - logs and skips malformed items,
       - gracefully handles partial failures.
   - Generate test data:
       - fake LLM responses for unit tests (no real Bedrock),
       - test edge-cases: empty entities, unknown types.
   - Add CLI command to:
       - test model calling with sample data (e.g. test-llm),
       - print parsed LexicalGraph.

### Step 6b – Plug Extraction through  GLiNER + GLiREL Lexical Backend

   - Implement SpacyLexicalBackend:
      - **Receives `OntologySchema` (not raw TTL or markdown)**
      - Load spacy model (nlp)
      - Configure GLiNER with `ontology.to_gliner_config()`:
        - Entity labels (e.g., "Product", "Team")
        - Natural language descriptions for zero-shot NER
      - Configure GLiREL with `ontology.to_glirel_config()`:
        - Relation names (e.g., "WORKS_ON")
        - Head/tail type constraints (e.g., Team → Product)
   - Pipeline:
      - Run nlp on curated text to get tokens and sentences
      - Run GLiNER to get entity spans and types (using ontology config)
      - Map GLiNER spans back to spacy spans
      - Build LexicalMentions with context and features
      - Run GLiREL on text + entity spans to get relations (respecting ontology constraints)
      - Build LexicalRelations
      - Return LexicalGraph
    - Tests:
      - Use small fixtures with known entities/relations
      - Verify LexicalGraph contains expected mentions and relations
      - Ensure ontology labels are respected (no unknown types)
      - Test TTL → OntologySchema → GLiNER/GLiREL config pipeline
   - Config:
      - Support model names/paths via .env or CLI flags

### Step 6c – Plug Extraction through Hybrid Backend

   - Implement HybridExtractionBackend:
      - **Receives `OntologySchema` (not raw TTL or markdown)**
      - Configure GLiNER with `ontology.to_gliner_config()` for entity detection
      - Initialize Bedrock client for LLM calls
   - Two-phase pipeline:
      - **Phase 1 (GLiNER)**:
        - Run GLiNER on curated text using `ontology.to_gliner_config()`
        - Detect entities with zero-shot NER (ontology-guided, no label mapping needed)
        - Build initial LexicalMentions with entity_type, surface, spans, confidence
      - **Phase 2 (LLM)**:
        - Build specialized prompt:
          - Include detected entities from Phase 1
          - Include `ontology.to_entity_config()` for property and relation extraction
        - Call LLM to extract properties and relationships
        - Merge GLiNER entities with LLM-extracted relations
   - Graceful fallback:
      - If LLM enrichment fails after retries, return entities-only graph
      - Log LLM failures and track statistics
   - Tests:
      - Verify two-phase extraction works correctly
      - Verify ontology types are used for GLiNER detection (from OntologySchema)
      - Verify LLM enrichment with mocked responses
      - Test fallback behavior when LLM fails
      - Ensure output LexicalGraph contains both entities and relations
      - Test TTL → OntologySchema → Hybrid extraction pipeline
   - Config:
      - Support gliner_model name, device, and LLM parameters via .env or CLI flags

### Step 7a – Plug Dedup Backend using Splink and Zingg
  Input: a `LexicalGraph` produced by Step 6 (LLM, spacy, or hybrid backend).  
  Output: a `DedupedLexicalGraph` and a set of `CanonicalLexicalEntity` objects.

   -   Implement DedupBackend interface and concrete implementations:
      -   Splink DedupBackend for local / smaller-scale, Python-only workflows,
      -   Zingg DedupBackend for larger / Spark-based or distributed environments. 
   -   Feature engineering and data preparation:
      -   transform LexicalGraph.mentions into per-entity-type tabular data (Pandas/Spark),
      -   compute normalized names (lowercased, de-punctuated strings),
      -   generate phonetic keys (e.g. Soundex/Metaphone) for name fields,
      -   build character n-grams / token n-grams for fuzzy matching,
      -   attach context features (e.g. co-occurring entities, document section),
      -   include strong identifiers where available (email, ID, URL, etc.).      
   -   Matching logic:
      -   for Splink:
          -   define comparison rules per field (exact, Jaro-Winkler, n-gram similarity, phonetic),
          -   configure blocking rules for scalability (e.g. same initial, same domain),
          -   train or configure match weights and thresholds for match / possible-match / non-match, 
     -   for Zingg:
          -   configure match/merge rules per entity type using its DSL or config, 
          -   leverage ML-based classification for match vs non-match,
          -   support active learning / label collection in later iterations. 
     -   Cluster formation:
          -   run the chosen backend(s) to produce clusters of mentions that likely refer to the same real-world entity,
          -   assign a canonical ID for each cluster,
          -   choose a canonical name (e.g. highest-quality or most frequent surface form),
          -   collect all surface forms as aliases and merge feature dictionaries.
      -   Build DedupedLexicalGraph:
      -   construct CanonicalLexicalEntity objects for each cluster:
          -   id, entity_type, canonical\_name, aliases, merged features,
      -   aggregate LexicalRelations into CanonicalRelations using the mention→canonical mapping, so that DedupedLexicalGraph.relations is a list of CanonicalRelation.
      -   ensure that singletons (no duplicates) still become canonical entities.
        
    -   Tests:
      -   create small synthetic datasets with known duplicate patterns:
        -   misspellings,
        -   phonetic variants,
        -   abbreviations,
        -   partial names,
      -   verify that obvious duplicates are clustered together,
      -   verify that clearly distinct entities are not merged,
      -   add regression tests for tricky borderline cases (e.g. “James Jones” vs “James Earl Jones”).
      
    -   Config:
      -   support selecting backend via CLI / config:
        -   \--dedup-backend \[none|splink|zingg|both\],   
      -   read tuning parameters (thresholds, blocking rules, comparison fields) from a config file or .env,
      -   allow per-entity-type overrides so different schemas can use different dedup strategies.

### Step 7b – Entity Linking Backend

    Input: `CanonicalLexicalEntity` instances and the `DedupedLexicalGraph` from Step 7a.  
    Output: `LinkResult` objects consumed by the Neo4j write layer in Step 7c.

    -   Implement `EntityLinkerBackend`:
      -   interface and a concrete implementation (e.g. `DefaultEntityLinkerBackend`). 
    -   Build or load a candidate KB from Neo4j:
      -   index `:Entity` nodes by `(namespace, entity_type, normalized_name)`,
      -   optionally pre-compute embeddings or extra features.
    -   For each `CanonicalLexicalEntity`:
      -   generate candidate entities from KB using:
        -   exact/normalized name,  
        -   phonetic variants,  
        -   strong identifiers (emails, IDs) from features.
      -   score candidates using:
        -   string similarity,
        -   context overlap / relation patterns,
        -   ontology constraints (what relations are allowed).
      -   decide:
        -   link to an existing KG entity, or
        -   create a new KG entity.
    -   Return `LinkResult`s to the KG layer:
      -   `existing_entity_id` vs `new_entity_payload`,
      -   confidence scores and reasons (for debugging).
  -   Tests:
      -   local KB with a few entities,
      -   verify linking behaviour for:
          -   clear matches,  
          -   clear non-matches, 
          -   borderline cases.


### Step 7c – Ingest Pipeline Wiring (Three Pipelines + Dedup + Linking)

    -   Implement full pipeline:
      -   read HTML → curate text → load ontology
      -   run **selected** `ExtractionBackend` (llm, spacy, or hybrid) → `LexicalGraph`
      -   run **selected** `DedupBackend` → `DedupedLexicalGraph`
      -   run `EntityLinkerBackend` → link decisions
      - run `process_before_store` hook → possibly modified `DedupedLexicalGraph`
      -   write to Neo4j:
          -   `:Doc`,
          -   `:Entity`,
          -   `:MENTIONS`,
          -   domain `:RELATION` edges
      -   collect canonical entities for batch.
    -   Implement flags:
        -   `--dry-run` (no writes, just log pipeline output),
        -   `--refresh` (skip unchanged docs by `content_hash`),
        -   `--namespace`, 
        -   `--extractor [llm|spacy|hybrid]` (default `llm`),
        -   `--dedup-backend [none|splink|zingg|both]` (default `splink`)
    - Implement process_after_batch invocation.
    -   Add end-to-end tests:
        -   use fake extractors/dedup/linkers,
        -   verify Neo4j content for `llm`, `spacy`, and `hybrid` modes matches expectations.


### Step 8 – Graph Rendering

- Implement render command:
  - subgraph extraction based on namespace, depth, and max_nodes.
  - HTML/JS generation using vis.js.
- Test:
  - HTML is generated,
  - configuration options are respected.

### Further Iterations

- Update this plan as we learn:
  - more granular LLM strategies,
  - better dedup and merging,
  - integration with KE SaaS and Content Lake,
  - advanced graph queries and GraphRAG integrations.
  - expanded ontology visualization features and layouts.

For each step:

- we will write a **detailed spec**,
- implement code + tests,
- only move to the next step when the current one is accepted.
