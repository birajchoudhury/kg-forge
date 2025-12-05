"""
Metrics collection and reporting for ingest pipeline.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class IngestMetrics:
    """
    Tracks statistics and performance metrics for an ingest run.
    """
    
    # File and document statistics
    files_discovered: int = 0
    docs_curated: int = 0       # Successfully curated documents (Step 3)
    curation_failed: int = 0    # Failed during curation
    docs_processed: int = 0     # Successfully processed documents (full pipeline)
    docs_skipped: int = 0       # Skipped due to unchanged content hash
    docs_failed: int = 0        # Failed during extraction/processing
    
    # Entity statistics
    entities_extracted: int = 0 # Raw entities extracted before dedup
    entities_deduped: int = 0   # Canonical entities after deduplication
    entities_created: int = 0   # New entities created in Neo4j
    entities_updated: int = 0   # Existing entities updated
    entities_linked: int = 0    # Entities linked to existing KG entities
    
    # Relationship statistics  
    mentions_created: int = 0   # Doc->Entity MENTIONS relationships
    relations_created: int = 0  # Entity->Entity relationships
    
    # Performance metrics
    processing_time: float = 0.0    # Total processing time in seconds
    curation_time: float = 0.0      # Time spent on document curation
    llm_time: float = 0.0           # Time spent on LLM calls
    neo4j_time: float = 0.0         # Time spent on Neo4j operations
    
    # Error tracking
    consecutive_failures: int = 0   # Current consecutive failure count
    failure_details: List[str] = field(default_factory=list)  # Error messages
    
    # Internal timing
    _start_time: float = field(default_factory=time.time, init=False)
    
    def record_file_discovered(self) -> None:
        """Record that a file was discovered."""
        self.files_discovered += 1
    
    def record_doc_curated(self) -> None:
        """Record successful document curation (Step 3)."""
        self.docs_curated += 1
    
    def record_curation_failed(self, error: str) -> None:
        """Record failed document curation."""
        self.curation_failed += 1
        self.failure_details.append(f"Curation: {error}")
    
    def record_doc_processed(self) -> None:
        """Record successful document processing (full pipeline)."""
        self.docs_processed += 1
        self.consecutive_failures = 0  # Reset failure counter
    
    def record_doc_skipped(self, reason: str = "unchanged") -> None:
        """Record skipped document."""
        self.docs_skipped += 1
        self.consecutive_failures = 0  # Reset failure counter
    
    def record_doc_failed(self, error: str) -> None:
        """Record failed document processing."""
        self.docs_failed += 1
        self.consecutive_failures += 1
        self.failure_details.append(error)
    
    def record_entities_extracted(self, count: int) -> None:
        """Record raw entities extracted (before dedup)."""
        self.entities_extracted += count
    
    def record_entities_deduped(self, count: int) -> None:
        """Record canonical entities after deduplication."""
        self.entities_deduped += count
    
    def record_entity_created(self, count: int = 1) -> None:
        """Record entities created."""
        self.entities_created += count
    
    def record_entity_updated(self, count: int = 1) -> None:
        """Record entities updated."""
        self.entities_updated += count
    
    def record_entities_linked(self, count: int) -> None:
        """Record entities linked to existing KG entities."""
        self.entities_linked += count
    
    def record_mentions_created(self, count: int = 1) -> None:
        """Record MENTIONS relationships created."""
        self.mentions_created += count
    
    def record_relations_created(self, count: int = 1) -> None:
        """Record entity-entity relationships created."""
        self.relations_created += count
    
    def add_curation_time(self, duration: float) -> None:
        """Add time spent on curation operations."""
        self.curation_time += duration
    
    def add_llm_time(self, duration: float) -> None:
        """Add time spent on LLM operations."""
        self.llm_time += duration
    
    def add_neo4j_time(self, duration: float) -> None:
        """Add time spent on Neo4j operations."""
        self.neo4j_time += duration
    
    def finalize(self) -> None:
        """Finalize metrics by calculating total processing time."""
        self.processing_time = time.time() - self._start_time
    
    @property
    def total_docs_attempted(self) -> int:
        """Total documents attempted (processed + skipped + failed)."""
        return self.docs_processed + self.docs_skipped + self.docs_failed
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage (processed / attempted)."""
        attempted = self.total_docs_attempted
        if attempted == 0:
            return 0.0
        return (self.docs_processed / attempted) * 100
    
    @property
    def has_consecutive_failures(self) -> bool:
        """Check if consecutive failure threshold exceeded."""
        return self.consecutive_failures > 10
    
    def to_dict(self) -> Dict[str, any]:
        """Convert metrics to dictionary for serialization."""
        return {
            'files_discovered': self.files_discovered,
            'docs_curated': self.docs_curated,
            'curation_failed': self.curation_failed,
            'docs_processed': self.docs_processed,
            'docs_skipped': self.docs_skipped,
            'docs_failed': self.docs_failed,
            'entities_extracted': self.entities_extracted,
            'entities_deduped': self.entities_deduped,
            'entities_created': self.entities_created,
            'entities_updated': self.entities_updated,
            'entities_linked': self.entities_linked,
            'mentions_created': self.mentions_created,
            'relations_created': self.relations_created,
            'processing_time': round(self.processing_time, 2),
            'curation_time': round(self.curation_time, 2),
            'llm_time': round(self.llm_time, 2),
            'neo4j_time': round(self.neo4j_time, 2),
            'success_rate': round(self.success_rate, 1),
            'consecutive_failures': self.consecutive_failures
        }
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"IngestMetrics("
            f"discovered={self.files_discovered}, "
            f"curated={self.docs_curated}, "
            f"processed={self.docs_processed}, "
            f"skipped={self.docs_skipped}, "
            f"failed={self.docs_failed}, "
            f"entities={self.entities_created}/{self.entities_updated}, "
            f"time={self.processing_time:.1f}s"
            f")"
        )