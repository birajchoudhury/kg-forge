# Seed – KG Forge CLI (Product Seed)

This document describes *what* we want to build and *why*, from a product perspective.  
The detailed technical design and implementation plan live in `seed_architecture.md`.

---

## 1. Problem & Context

We have a large corpus of unstructured engineering knowledge in Confluence (and similar sources).  
Today we can:

- run keyword or hybrid search over pages, and
- read individual documents in isolation,

but we **cannot see the relationships** between:

- AI/ML domains,
- products and components,
- workstreams and projects,
- teams and engineers,
- engineering domains and concerns.

We also have typical “messy text” issues:

- the same entity appears under slightly different names,
- misspellings and abbreviations are common,
- new entities keep emerging in docs but never get curated back into any ontology.

As a result:

- It is hard to answer questions like:
  - “Which teams are working on RAG-related components for Product X?”
  - “Where are we discussing reliability concerns for the platform?”
  - “Which engineers keep showing up in docs related to observability?”
- It is hard to maintain and grow an ontology of our work:
  - what products exist and how they decompose,
  - which workstreams touch which areas,
  - how concerns like “Security” or “Scalability” surface across docs,
  - how to canonicalize all of this into stable entities in a graph.

We need a **fast, experimental way** to:

- extract entities and topics from existing documentation using multiple extraction strategies,
- deduplicate messy mentions into canonical entities,
- link those entities into a **Knowledge Graph** backed by an ontology,
- iterate on the ontology itself,
- and explore the resulting graph and ontology visually.

---

## 2. Vision

Build a **CLI-based experimentation toolbox** ("KG Forge") that lets us:

1. **Ingest** unstructured content from a filesystem export.
2. **Extract entities and topics** using **pluggable extraction backends**:
   - an **LLM-based pipeline** driven by markdown definitions (full LLM extraction),
   - a **spaCy + GLiNER + GLiREL lexical graph pipeline** (zero-shot NER + relation extraction), and
   - a **Hybrid pipeline** (GLiNER ontology-aware NER + LLM for properties and relations).
3. **Deduplicate & canonicalize entities** using configurable ER backends (initially Splink, later Zingg).
4. **Link** canonical entities to an ontology-backed Knowledge Graph in Neo4j.
5. **Query** for entities, documents, and relationships within a given experiment namespace.
6. **Render**:
   - subgraphs of the KG for visual exploration, and
   - the **ontology itself** as an interactive graph.

The tool should feel like:

> “A command-line workbench for turning messy docs into a navigable, ontology-driven
> knowledge graph, where extraction backends, dedup strategies, ontology, and graph
> structure can all be tweaked and re-run quickly in isolated namespaces.”

It is **not** a production service; it is an **experiment platform** that helps us learn what a full product should eventually do (and what patterns are worth productizing).

---

## 3. Primary Users & Use Cases

### 3.1 Primary Users

- **Ontology / Knowledge Architects**
  - Define entity types and relations in markdown.
  - Iterate on schema and examples.
  - Compare how different ontologies change the resulting graph.
- **ML / AI Engineers**
  - Experiment with **LLM vs spaCy+GLiNER+GLiREL** extraction.
  - Tune prompts, labels, and thresholds.
  - Evaluate how well entities and relationships are captured.
- **Platform / Product Engineers**
  - Explore cross-cutting concerns (e.g., which docs/components touch “RAG” or “Scalability”).
  - Understand how teams, systems, and domains connect.
- **Product Managers / Tech Leads**
  - Get a structural view of workstreams, components, and teams from existing documentation.
  - Use the graph as a “map” of the engineering landscape.

### 3.2 Core Use Cases

1. **Bootstrap a knowledge graph from documents**
   - Export content as HTML, gather PDF documents, or use other document formats.
   - Run `kg-forge ingest` to extract entities, deduplicate them, and create a graph in Neo4j.
   - Use `kg-forge query` and `kg-forge render` to explore relationships.

2. **Iterate on ontology and entity definitions**
   - Edit markdown definitions for entity types (product, component, team, concern, domain, topic, etc.).
   - Re-run ingestion in a new `--namespace` to see impact on the graph without disturbing earlier runs.
   - Use `kg-forge export-entities` to push discovered entities back into markdown for curation.

3. **Compare extraction and dedup strategies**
   - Run the same corpus with:
     - `--extractor llm` vs `--extractor spacy` vs `--extractor hybrid`,
     - `--dedup-backend none` vs `--dedup-backend splink`.
   - Compare:
     - what entities are found,
     - how noisy they are,
     - extraction speed and API costs (LLM tokens),
     - and how stable canonical entities are across runs.

4. **Discover patterns and gaps**
   - Identify which products/components are heavily or sparsely documented.
   - See which workstreams and teams map to which AI/ML domains.
   - Surface recurring concerns (e.g., security) and where they appear.
   - Spot missing or inconsistent entity definitions in the ontology.

5. **Visualize and understand ontology structure**
   - Generate interactive visualizations of entity types and their relationships.
   - Explore ontology structure using different layout algorithms (force-directed, hierarchical, circular, grid) and themes.
   - Include example entities to better understand each type’s scope.

6. **Prepare for a future production-grade system**
   - Validate what ontology structures work.
   - Validate which extraction and dedup strategies are robust.
   - Produce reference graphs and ontology files that can inform a future SaaS product
     using KE APIs and a formal Content Lake.

---

## 4. Scope for v1

v1 is a **single-machine CLI tool** focused on Filesystem folder of documents and one primary graph backend (Neo4j).

### 4.1 In-Scope

- **Source**
  - Filesystem folder of documents including:
    - HTML pages (Confluence export)
    - PDF documents
    - Other document formats (extensible architecture)

- **Core Commands**
  - `ingest`
    - Read and curate text from various document formats (HTML, PDF, etc.).
    - Optionally chunk documents into smaller segments via `--chunking=on|off` (default: off).
    - Extract entities/topics (and relations) using a selected extraction backend:
      - `--extractor llm` (full LLM-based extraction),
      - `--extractor spacy` (spaCy + GLiNER + GLiREL zero-shot pipeline),
      - `--extractor hybrid` (GLiNER ontology-aware NER + LLM for properties/relations).
    - Run deduplication via a selected backend:
      - `--dedup-backend none|splink` (Zingg is planned later).
    - Link canonical entities to a Neo4j graph, backed by the ontology.
    - Respect `--namespace`, `--dry-run`, `--refresh`, `--chunking`, and basic model/prompt overrides.

  - `query`
    - List entity types, entities, and docs for a given namespace.
    - Show a doc and the entities it mentions.
    - Find docs/entities related to a given entity.
    - Support human-readable text and JSON output.

  - `render`
    - Generate an HTML file that visualizes a KG subgraph for exploration.
    - Allow controlling namespace, depth, and max node count.

  - `render-ontology`
    - Generate interactive HTML visualization of ontology structure.
    - Show entity types and their relationships using Cytoscape.js.
    - Support multiple layout algorithms and themes.
    - Optionally show examples as additional nodes or tooltips.

  - `export-entities`
    - Export entities from Neo4j back into `entities_extract/*.md` grouped by type.
    - Support round-trip ontology refinement.

  - `neo4j-start` / `neo4j-stop`
    - Convenience commands to start/stop a local Neo4j instance for experiments.

- **Ontology Management (Standard & Legacy Formats)**
  - **TTL (Turtle) ontology files** (.ttl) as the **standard format**:
    - Industry-standard RDF/OWL ontology definitions.
    - Entity types as rdfs:Class or owl:Class with IRIs, labels, and descriptions.
    - Relation types as rdf:Property or owl:ObjectProperty with domain/range constraints.
    - Parsed with rdflib and normalized to internal OntologySchema.
  - **Markdown ontology files** (.md) as **legacy format** (backward compatible):
    - Entity-type definitions + examples in `entities_extract/*.md`.
    - Relations between entity types defined in markdown.
  - **Normalized Internal Representation (OntologySchema)**:
    - Both TTL and Markdown formats normalized to same internal schema.
    - Helper methods generate backend-specific configs:
      - GLiNER config (entity labels + descriptions)
      - GLiREL config (relation constraints)
      - LLM prompt snippets (compact JSON)
  - Ontology used as:
    - input for LLM prompts (via helper methods),
    - label set / relation schema for the spaCy + GLiNER + GLiREL pipeline (via helper methods),
    - entity types for GLiNER detection in hybrid pipeline (via helper methods).
  - **Strict Separation Principle**: Raw TTL/Markdown never passed to extraction backends; only normalized OntologySchema.
  - Ability to export graph entities back into markdown for curation (TTL export planned for future).

- **Experimentation Controls**
  - **Namespaces** to isolate experiments within the same Neo4j DB.
  - **Dry-run ingestion** (run extraction + dedup + linking logic without writing to the graph).
  - **Refresh control** (skip unchanged docs via content hash, or force reprocessing).
  - Basic **configuration knobs**:
    - extraction backend (`--extractor`),
    - dedup backend (`--dedup-backend`),
    - model/prompt overrides for the LLM backend.

- **Extensibility / Hooks (v1-level)**
  - A simple hook mechanism to:
    - adjust the deduplicated graph before storage (`process_before_store`),
    - run cleanup / pruning / human-in-the-loop checks after a batch (`process_after_batch`).
  - Hooks are optional and aimed at advanced users; default behaviour should be useful without them.

### 4.2 Out of Scope (for v1)

- Multi-tenant, production-grade service.
- Real-time ingestion from live Confluence or other systems.
- UI-based ontology editor (only markdown + CLI visualizations for now).
- Advanced GraphRAG or natural language graph querying on top of the KG.
- Large-scale distributed entity resolution using Zingg (planned for later iterations).
- Managed Content Lake integration as a primary storage (filesystem-only in v1).

---

## 5. Key Concepts

### 5.1 Document & Chunking

#### Document

- One curated unit of content.
- Identified by a stable `doc_id` derived from file path.
- Represented in the graph as a `:Doc` node.
- Has relationships to entities it mentions (and optionally additional metadata).

#### Chunking (Optional)

**Why Chunking?**

For large documents, processing the entire text in a single pass can lead to:
- **LLM context limitations**: Large documents may exceed token limits or degrade extraction quality.
- **Poor extraction precision**: Entities and relationships far apart in the document may not be connected properly.
- **Difficulty in scoring**: Hard to attribute entity mentions to specific sections or track provenance.

Chunking addresses these issues by breaking documents into smaller, manageable pieces that:
- fit comfortably within LLM context windows,
- maintain section/heading context for better semantic understanding,
- enable fine-grained provenance tracking (which chunk, which page, which section).

**How to Enable/Disable Chunking**

Chunking is controlled via the `--chunking` CLI flag during ingestion:

- `--chunking=off` (default): Process entire document as one unit. Output is a single markdown file per document.
- `--chunking=on`: Enable chunking. Document is split into chunks, and two artifacts are produced per document.

Future iterations may support advanced chunking modes (e.g., `--chunking=semantic` for semantic-based splitting), but v1 focuses on simple size/structure-based chunking.

**Artifacts Produced When Chunking is ON**

When `--chunking=on` is specified, the curation/ingestion pipeline produces **two artifacts per document**:

1. **`<doc_id>.md`** – A "pure markdown" full-document representation
   - Complete markdown conversion of the original document
   - Used for reference and full-text search
   - Preserves document structure (headings, sections, formatting)

2. **`<doc_id>.chunks.json`** – A JSON file containing an array of document chunks
   - Each chunk is a JSON object with the following required fields:
     ```json
     {
       "chunk_id": "unique_chunk_identifier",
       "doc_id": "parent_document_id",
       "page": 5,                    // page number if available, null otherwise
       "section": "Architecture Overview",  // section/heading if available, null otherwise
       "start_offset": 1024,         // character offset in the full markdown
       "end_offset": 2048,           // character offset in the full markdown
       "text": "chunk content here..." // the actual chunk text
     }
     ```

**Downstream Processing with Chunks**

When chunking is enabled:
- **Entity extraction** works chunk-by-chunk, processing each chunk object independently.
- **Graph construction** links entities to both:
  - the parent `:Doc` node, and
  - optionally to chunk-level metadata (page, section) for fine-grained provenance.
- **Deduplication** still operates at the entity level across all chunks and documents.

This allows extraction backends to:
- process smaller, focused text segments,
- maintain context from section/heading information,
- provide better entity-to-location mapping for downstream analysis.

### 5.2 Entity / Topic

- An **Entity** is a named thing in our world:
  - product, component, workstream, team, engineer, technology, domain, concern, etc.
- A **Topic** represents a conceptual theme:
  - e.g., “RAG”, “Evaluation”, “Observability”.
- Both are stored as graph nodes with:
  - a type (from markdown definitions),
  - a canonical name,
  - optional aliases and dedup features,
  - and relationships to other entities and documents.

The system is responsible for:

- turning **raw mentions** in text into **canonical entities** (via deduplication),
- ensuring we can refer to “the same thing” consistently across docs.

### 5.3 Ontology

- The ontology is the set of:
  - entity types,
  - allowed relationships between them,
  - and curated examples (for markdown format).

- **Standard Format: TTL (Turtle)**
  - Industry-standard RDF/OWL ontology files (.ttl).
  - Entity types defined as rdfs:Class or owl:Class with:
    - Unique IRIs (e.g., `http://example.org/ont#Product`)
    - Labels (rdfs:label) for display names
    - Descriptions (rdfs:comment) for natural language definitions
    - Optional properties (datatype and object properties)
  - Relation types defined as rdf:Property or owl:ObjectProperty with:
    - Unique IRIs (e.g., `http://example.org/ont#worksOn`)
    - Domain constraints (rdfs:domain) for allowed source entity types
    - Range constraints (rdfs:range) for allowed target entity types
    - Labels and descriptions for documentation
  - Parsed using rdflib and normalized to internal OntologySchema.

- **Legacy Format: Markdown**
  - Entity definitions in markdown files (e.g., `entities_extract/`) plus a prompt template.
  - Supported for backward compatibility only.
  - New ontologies should use TTL format.

- **Normalized Internal Representation**
  - Both TTL and Markdown formats are ingested and normalized to OntologySchema.
  - OntologySchema provides helper methods to generate backend-specific configs:
    - `to_gliner_config()`: Entity labels + descriptions for zero-shot NER
    - `to_glirel_config()`: Relation constraints for relation extraction
    - `to_llm_prompt_snippet()`: Compact JSON for LLM prompts
  - **Raw ontology files never passed to extraction backends** - only normalized OntologySchema.

- The ontology is used to:
  - drive LLM extraction (via `ontology.to_llm_prompt_snippet()` helper),
  - provide label sets and relation schema for the spaCy+GLiNER+GLiREL pipeline (via `to_gliner_config()` and `to_glirel_config()` helpers),
  - provide entity types for GLiNER detection in the hybrid pipeline (via `to_gliner_config()` helper),
  - drive LLM enrichment in the hybrid pipeline (via `to_llm_prompt_snippet()` helper),
  - shape the resulting knowledge graph (entity_type and relationship direction).

### 5.4 Namespace / Experiment

- A **namespace** labels all nodes and relationships from a given run or experiment.
- Different namespaces can:
  - use different ontologies,
  - use different extraction/dedup configurations,
  - coexist in the same Neo4j instance.
- This allows side-by-side comparison of experiments without clobbering earlier results.

---

## 6. Functional Requirements (Product Level)

### 6.1 Ingest

- As a user, I can run `kg-forge ingest` on a folder of documents (HTML, PDF, etc.) and:
  - see how many documents were processed, skipped, or failed,
  - see a summary of entities created/updated per entity type,
  - know which namespace was affected.

- I can choose:
  - an **extraction backend** (`--extractor llm|spacy|hybrid`),
    - `llm`: Full LLM-based extraction (highest quality, highest cost, ~5-10s/doc),
    - `spacy`: Zero-shot GLiNER+GLiREL pipeline (fastest, local, ~1-2s/doc),
    - `hybrid`: GLiNER ontology-aware NER + LLM enrichment (balanced quality/cost/speed, ~3-6s/doc),
  - a **dedup backend** (`--dedup-backend none|splink`),
  - a **chunking mode** (`--chunking on|off`, default: off),
  - a **namespace** (`--namespace`) to isolate the run.

- I can:
  - **skip unchanged** documents based on a content hash,
  - **force re-processing** via a flag (`--refresh`),
  - **run in dry-run mode** to only test extraction/dedup/linking and configuration.

- When chunking is enabled (`--chunking=on`):
  - Each document produces two artifacts: `<doc_id>.md` and `<doc_id>.chunks.json`.
  - Entity extraction processes chunks individually for better LLM context control.
  - I can see chunk-level provenance (page, section) in extraction logs and results.

- When ingestion finishes, I can:
  - see a concise summary (entities, docs, key warnings),
  - optionally use hooks / interactive workflows (when configured) to deal with ambiguous cases.

### 6.2 Query

- As a user, I can:
  - list all entity types in a namespace.
  - list entities of a given type (e.g., all Products) in a namespace.
  - list all docs in the namespace.
  - show a specific doc by ID, along with the entities it mentions.
  - find docs and/or entities related to a specific entity (e.g., all docs mentioning Product X).

- Queries should:
  - always respect the active namespace,
  - be available in:
    - a human-readable text format, and
    - a machine-readable JSON output (for scripting / notebooks).

### 6.3 Render

- As a user, I can generate an HTML page that:
  - shows a subgraph (Docs + Entities + relations) for a given namespace,
  - can be scoped by depth and maximum node count,
  - allows basic panning/zooming and inspection of node labels.

- As a user, I can generate an **ontology visualization** that:
  - shows entity types and relations defined in the active ontology,
  - supports different layout algorithms and themes,
  - optionally includes example entities for context.

### 6.4 Ontology Round-Trip

- As a user, I can:
  - **define entity types and relations in TTL** (standard format) or markdown (legacy format).
  - **auto-detect ontology format** - system automatically detects TTL vs Markdown and normalizes to OntologySchema.
  - re-run ingestion (possibly in a new namespace) to see how they impact graph structure.
  - export discovered entities back into markdown files (`export-entities`) for review and curation.
    - (TTL export planned for future iterations)

- The ontology round-trip should be simple enough that:
  - ontology changes can be reviewed in git,
  - experiments can be repeated with slightly updated ontologies,
  - ontologies can be shared and versioned using industry-standard RDF/OWL formats.

### 6.5 Extensibility & Hooks

- As an advanced user, I can:
  - register simple Python hooks that run:
    - before writing to the KG (e.g., to normalize or filter entities/relations),
    - after a batch (e.g., to run additional cleanup or semi-manual review).
- Hooks are optional and:
  - should not be required for a “happy path” run,
  - should be easy to enable/disable via configuration.

---

## 7. Non-Functional Requirements (Product Level)

- **Fast iteration**
  - Ingestion runs should be fast enough on a typical Confluence space
    to support multiple ontology/extraction/dedup iterations per week.

- **Local-first**
  - v1 runs locally on a developer or architect’s machine with a local Neo4j instance.

- **Reproducibility**
  - Given the same input content, ontology, configuration, and namespace,
    we should be able to rebuild the same graph structure.

- **Debuggability**
  - Clear logs for:
    - ingestion progress,
    - extraction backend used and failures,
    - dedup decisions (at least at an aggregate level),
    - graph write failures.

- **Pluggability**
  - Extractor and dedup backends should be swappable via config flags,
    without code changes by end users.

(Performance, scaling, and fault tolerance beyond a single user/machine
are explicitly out of scope for v1.)

---

## 8. Success Metrics (for v1 Experiment)

We will consider v1 successful if:

1. **Ontology Iteration**
   - Ontology and entity definitions can be adjusted and re-run easily.
   - Users can visibly see the impact of ontology changes in the graph and ontology visualization.
   - The `export-entities` loop is actually used to improve definitions.

2. **Extraction & Dedup Quality (Qualitative)**
   - For a sample of docs, entities and relations are:
     - mostly correct,
     - de-duplicated into sensible canonical entities,
     - useful for navigation and analysis.
   - Users can qualitatively compare at least:
     - `llm` vs `spacy` vs `hybrid` extractors,
     - dedup vs no-dedup,
     and articulate pros/cons in terms of:
       - extraction accuracy (precision/recall of entities and relations),
       - processing speed (documents per second),
       - API costs (LLM token usage),
       - robustness (handling of edge cases, graceful degradation).

3. **Graph Exploration**
   - At least a handful of real questions about our engineering landscape
     can be answered more easily via the graph than via raw Confluence search.
     (e.g., “which docs show up under RAG + KD + Platform Engineering?”)

4. **Future Product Readiness**
   - We have enough learnings to specify:
     - what a production-grade KE + Content Lake graph solution should look like,
     - which ontology patterns work,
     - which extraction/dedup/linking strategies are promising,
     - and which entity/relationship types are essential.

---

## 9. Constraints & Assumptions

- v1 is **for internal experimentation only**.
- We assume:
  - Access to a Neo4j instance (local is fine).
  - Access to an LLM backend (e.g., Bedrock) for the LLM extractor.
  - Ability to install and run Splink locally for dedup.
- We accept:
  - Manual curation and editing of markdown files.
  - Occasional extraction or dedup errors, as long as:
    - they are visible in logs,
    - and we can skip/redo documents or runs easily via namespaces.

---

## 10. Open Questions

- Which exact entity types are *must-have* for the first experiment?
- How fine-grained should “Topics” be vs more concrete entity types?
- How much surface area should we expose in v1 for:
  - extractor configuration (LLM models, spaCy model choices),
  - dedup configuration (thresholds, rules)?
- To what extent do we want interactive / human-in-the-loop flows in v1 vs. simple offline hooks?
- How important is export to other tools (e.g., CSV, JSON, direct Cypher queries) in v1?

These questions will be refined as we run the first experiments and observe how
the graph behaves on real Confluence exports and different configuration combinations.
