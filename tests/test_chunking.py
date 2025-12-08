"""Tests for document chunking functionality."""

import pytest
from pathlib import Path
from kg_forge.models.curation import DocumentChunk, CurationResult, DocumentMetadata
from kg_forge.models.lexical import LexicalGraph, LexicalMention, LexicalRelation, empty_lexical_graph


class TestDocumentChunk:
    """Test DocumentChunk model."""
    
    def test_create_chunk(self):
        """Test creating a basic DocumentChunk."""
        chunk = DocumentChunk(
            chunk_id="doc.pdf_chunk_001",
            doc_id="doc.pdf",
            page=1,
            section="Introduction",
            start_offset=0,
            end_offset=500,
            text="This is chunk text...",
            metadata={"source": "docling"}
        )
        
        assert chunk.chunk_id == "doc.pdf_chunk_001"
        assert chunk.doc_id == "doc.pdf"
        assert chunk.page == 1
        assert chunk.section == "Introduction"
        assert chunk.start_offset == 0
        assert chunk.end_offset == 500
        assert chunk.text == "This is chunk text..."
        assert chunk.metadata["source"] == "docling"
    
    def test_chunk_with_optional_page_section(self):
        """Test chunk with None values for optional page/section fields."""
        chunk = DocumentChunk(
            chunk_id="doc.html_chunk_001",
            doc_id="doc.html",
            page=None,
            section=None,
            start_offset=0,
            end_offset=100,
            text="Chunk without page/section info",
            metadata={}
        )
        
        assert chunk.chunk_id == "doc.html_chunk_001"
        assert chunk.page is None
        assert chunk.section is None
        assert chunk.start_offset == 0
        assert chunk.end_offset == 100


class TestCurationResultWithChunks:
    """Test CurationResult with chunks."""
    
    def test_curation_result_without_chunks(self):
        """Test standard CurationResult without chunks."""
        result = CurationResult(
            doc_id="test.pdf",
            curated_text="Sample text",
            markdown_path=Path("output/test.pdf.md"),
            metadata=DocumentMetadata(
                title="Test",
                source_format="pdf"
            ),
            curation_backend="docling"
        )
        
        assert result.chunks is None
        assert result.chunks_path is None
    
    def test_curation_result_with_chunks(self):
        """Test CurationResult with chunks."""
        chunks = [
            DocumentChunk(
                chunk_id="test.pdf_chunk_001",
                doc_id="test.pdf",
                page=1,
                section="Section 1",
                start_offset=0,
                end_offset=100,
                text="Chunk 1 text",
                metadata={}
            ),
            DocumentChunk(
                chunk_id="test.pdf_chunk_002",
                doc_id="test.pdf",
                page=1,
                section="Section 2",
                start_offset=100,
                end_offset=200,
                text="Chunk 2 text",
                metadata={}
            )
        ]
        
        result = CurationResult(
            doc_id="test.pdf",
            curated_text="Sample text",
            markdown_path=Path("output/test.pdf.md"),
            metadata=DocumentMetadata(
                title="Test",
                source_format="pdf"
            ),
            curation_backend="docling",
            chunks=chunks,
            chunks_path=Path("output/test.pdf.chunks.json")
        )
        
        assert result.chunks is not None
        assert len(result.chunks) == 2
        assert result.chunks[0].chunk_id == "test.pdf_chunk_001"
        assert result.chunks[1].chunk_id == "test.pdf_chunk_002"
        assert result.chunks_path == Path("output/test.pdf.chunks.json")
    
    def test_curation_result_to_dict_with_chunks(self):
        """Test serialization of CurationResult with chunks."""
        chunks = [
            DocumentChunk(
                chunk_id="test.pdf_chunk_001",
                doc_id="test.pdf",
                page=1,
                section="Intro",
                start_offset=0,
                end_offset=50,
                text="Text",
                metadata={"source": "docling"}
            )
        ]
        
        result = CurationResult(
            doc_id="test.pdf",
            curated_text="Sample text",
            markdown_path=Path("output/test.pdf.md"),
            metadata=DocumentMetadata(
                title="Test",
                source_format="pdf"
            ),
            curation_backend="docling",
            chunks=chunks,
            chunks_path=Path("output/test.pdf.chunks.json")
        )
        
        result_dict = result.to_dict()
        
        assert "chunks" in result_dict
        assert len(result_dict["chunks"]) == 1
        assert result_dict["chunks"][0]["chunk_id"] == "test.pdf_chunk_001"
        # Convert Path to string and normalize separators for cross-platform comparison
        assert str(result_dict["chunks_path"]).replace("\\", "/") == "output/test.pdf.chunks.json"


class TestLexicalGraphMerge:
    """Test LexicalGraph merge functionality for chunk-based extraction."""
    
    def test_merge_two_empty_graphs(self):
        """Test merging two empty graphs."""
        graph1 = empty_lexical_graph("llm")
        graph2 = empty_lexical_graph("llm")
        
        merged = graph1.merge(graph2)
        
        assert len(merged.mentions) == 0
        assert len(merged.relations) == 0
        assert merged.metadata.get("merged_graphs") == 1
    
    def test_merge_graphs_with_mentions(self):
        """Test merging graphs containing mentions."""
        mention1 = LexicalMention(
            id="chunk1_mention_1",
            doc_id="doc.pdf_chunk_001",
            entity_type="Product",
            surface="AWS Bedrock",
            start_offset=0,
            end_offset=11
        )
        
        mention2 = LexicalMention(
            id="chunk2_mention_1",
            doc_id="doc.pdf_chunk_002",
            entity_type="Team",
            surface="KD Team",
            start_offset=150,
            end_offset=157
        )
        
        graph1 = LexicalGraph(
            mentions=[mention1],
            relations=[],
            metadata={"backend": "llm", "chunk_id": "chunk_001"}
        )
        
        graph2 = LexicalGraph(
            mentions=[mention2],
            relations=[],
            metadata={"backend": "llm", "chunk_id": "chunk_002"}
        )
        
        merged = graph1.merge(graph2)
        
        assert len(merged.mentions) == 2
        assert merged.mentions[0].id == "chunk1_mention_1"
        assert merged.mentions[1].id == "chunk2_mention_1"
        assert merged.metadata.get("merged_graphs") == 1
    
    def test_merge_graphs_with_relations(self):
        """Test merging graphs containing relations."""
        mention1 = LexicalMention(
            id="chunk1_m1",
            doc_id="doc.pdf",
            entity_type="Team",
            surface="KD Team",
            start_offset=0,
            end_offset=7
        )
        
        mention2 = LexicalMention(
            id="chunk1_m2",
            doc_id="doc.pdf",
            entity_type="Product",
            surface="AWS Bedrock",
            start_offset=20,
            end_offset=31
        )
        
        relation = LexicalRelation(
            id="chunk1_r1",
            type="USES",
            src_mention_id="chunk1_m1",
            dst_mention_id="chunk1_m2"
        )
        
        mention3 = LexicalMention(
            id="chunk2_m1",
            doc_id="doc.pdf",
            entity_type="Topic",
            surface="RAG",
            start_offset=200,
            end_offset=203
        )
        
        graph1 = LexicalGraph(
            mentions=[mention1, mention2],
            relations=[relation],
            metadata={"backend": "llm"}
        )
        
        graph2 = LexicalGraph(
            mentions=[mention3],
            relations=[],
            metadata={"backend": "llm"}
        )
        
        merged = graph1.merge(graph2)
        
        assert len(merged.mentions) == 3
        assert len(merged.relations) == 1
        assert merged.relations[0].id == "chunk1_r1"
    
    def test_merge_multiple_graphs(self):
        """Test merging more than two graphs sequentially."""
        graphs = []
        for i in range(5):
            mention = LexicalMention(
                id=f"chunk{i}_m1",
                doc_id="doc.pdf",
                entity_type="Topic",
                surface=f"Topic {i}",
                start_offset=i * 100,
                end_offset=i * 100 + 10
            )
            graph = LexicalGraph(
                mentions=[mention],
                relations=[],
                metadata={"backend": "llm", "chunk_id": f"chunk_{i:03d}"}
            )
            graphs.append(graph)
        
        # Merge sequentially
        merged = graphs[0]
        for graph in graphs[1:]:
            merged = merged.merge(graph)
        
        assert len(merged.mentions) == 5
        assert merged.metadata.get("merged_graphs") == 4  # 4 merge operations
    
    def test_merge_preserves_metadata(self):
        """Test that merge preserves and combines metadata."""
        graph1 = LexicalGraph(
            mentions=[],
            relations=[],
            metadata={"backend": "llm", "extraction_time": 1.5, "custom_key": "value1"}
        )
        
        graph2 = LexicalGraph(
            mentions=[],
            relations=[],
            metadata={"backend": "llm", "model": "claude-3", "custom_key": "value2"}
        )
        
        merged = graph1.merge(graph2)
        
        # graph1 metadata takes precedence
        assert merged.metadata["custom_key"] == "value1"
        assert merged.metadata["extraction_time"] == 1.5
        # graph2 unique keys are included
        assert merged.metadata["model"] == "claude-3"
        assert merged.metadata["merged_graphs"] == 1


class TestChunkMetadataInMentions:
    """Test that chunk metadata is properly added to mentions during extraction."""
    
    def test_mention_with_chunk_metadata(self):
        """Test creating mention with chunk-specific features."""
        mention = LexicalMention(
            id="chunk1_m1",
            doc_id="doc.pdf",
            entity_type="Product",
            surface="AWS Bedrock",
            start_offset=50,
            end_offset=61,
            features={
                "chunk_id": "doc.pdf_chunk_001",
                "page": 1,
                "section": "Introduction",
                "confidence": 0.95
            }
        )
        
        assert mention.features["chunk_id"] == "doc.pdf_chunk_001"
        assert mention.features["page"] == 1
        assert mention.features["section"] == "Introduction"
        assert mention.features["confidence"] == 0.95
    
    def test_mention_to_dict_preserves_chunk_metadata(self):
        """Test serialization preserves chunk metadata."""
        mention = LexicalMention(
            id="chunk1_m1",
            doc_id="doc.pdf",
            entity_type="Team",
            surface="KD Team",
            start_offset=0,
            end_offset=7,
            features={
                "chunk_id": "doc.pdf_chunk_001",
                "page": 2,
                "section": "Team Overview"
            }
        )
        
        mention_dict = mention.to_dict()
        
        assert mention_dict["features"]["chunk_id"] == "doc.pdf_chunk_001"
        assert mention_dict["features"]["page"] == 2
        assert mention_dict["features"]["section"] == "Team Overview"
