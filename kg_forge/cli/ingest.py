"""Ingest command for kg-forge CLI."""

import sys
import click
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from kg_forge.config.settings import get_settings
from kg_forge.ingest.pipeline import IngestPipeline
from kg_forge.llm.exceptions import ExtractionAbortError
from kg_forge.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.command()
@click.option(
    "--source", 
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Root directory containing document files to process"
)
@click.option(
    "--namespace", 
    help="Namespace for this ingest run (default from config)"
)
@click.option(
    "--dry-run", 
    is_flag=True,
    help="Run pipeline without writing to Neo4j"
)
@click.option(
    "--refresh", 
    is_flag=True,
    help="Reprocess all documents ignoring content hash"
)
@click.option(
    "--interactive", "--biraj", 
    is_flag=True,
    help="Enable interactive mode for hooks"
)
@click.option(
    "--prompt-template", 
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Override default prompt template file"
)
@click.option(
    "--model", 
    help="Override LLM model name from config"
)
@click.option(
    "--max-docs", 
    type=int,
    help="Limit number of documents processed (for debugging)"
)
@click.option(
    "--curator",
    type=click.Choice(["docling", "hyland_ke"], case_sensitive=False),
    help="Curation backend for multi-format document processing (default from config)"
)
@click.option(
    "--extractor",
    type=click.Choice(["llm", "spacy"], case_sensitive=False),
    help="Extraction backend (default from config)"
)
@click.option(
    "--dedup-backend",
    type=click.Choice(["none", "splink", "zingg", "both"], case_sensitive=False),
    help="Deduplication backend (default from config)"
)
@click.option(
    "--fake-llm", 
    is_flag=True,
    help="Use fake LLM for testing (no API calls)"
)
def ingest(
    source: Path,
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
    fake_llm: bool = False
) -> None:
    """
    Ingest document files from source directory into knowledge graph.
    
    This command runs the complete ingest pipeline:
    1. Discovers document files (HTML, PDF, DOCX, PPTX) in source directory
    2. Curates documents to markdown using configurable backend
    3. Extracts entities using configurable backend (LLM or spaCy)
    4. Applies deduplication using configurable backend (Splink/Zingg/none)
    5. Stores documents and entities in Neo4j
    6. Creates relationships between entities
    
    SOURCE: Root directory containing document files to process
    """
    
    try:
        # Load configuration
        config = get_settings()
        
        # Validate namespace
        target_namespace = namespace or config.app.default_namespace
        try:
            config.validate_namespace(target_namespace)
        except ValueError as e:
            console.print(f"[red]Invalid namespace: {e}[/red]")
            sys.exit(1)
        
        console.print(f"[bold blue]KG Forge Ingest Pipeline[/bold blue]")
        console.print(f"Source: {source}")
        console.print(f"Namespace: {target_namespace}")
        
        if dry_run:
            console.print("[yellow]Mode: DRY RUN (no database writes)[/yellow]")
        if refresh:
            console.print("[yellow]Mode: REFRESH (reprocess all documents)[/yellow]")
        if interactive:
            console.print("[cyan]Mode: INTERACTIVE (hooks enabled)[/cyan]")
        if curator:
            console.print(f"Curator: {curator}")
        if fake_llm:
            console.print("[cyan]LLM: FAKE (testing mode)[/cyan]")
        elif model:
            console.print(f"LLM Model: {model}")
        if max_docs:
            console.print(f"Limit: {max_docs} documents")
        
        console.print()
        
        # Initialize and run pipeline
        pipeline = IngestPipeline(
            source_path=source,
            namespace=target_namespace,
            dry_run=dry_run,
            refresh=refresh,
            interactive=interactive,
            prompt_template=prompt_template,
            model=model,
            max_docs=max_docs,
            curator=curator,
            extractor=extractor,
            dedup_backend=dedup_backend,
            fake_llm=fake_llm,
            config=config
        )
        
        # Execute pipeline
        console.print("[bold]Starting ingest pipeline...[/bold]")
        metrics = pipeline.run()
        
        # Display results summary
        _display_results(metrics, dry_run)
        
        # Exit with appropriate code
        if metrics.has_consecutive_failures:
            console.print(f"[red]ERROR: Exceeded maximum consecutive failures ({metrics.consecutive_failures})[/red]")
            sys.exit(2)
        elif metrics.docs_failed > 0:
            console.print(f"[yellow]WARNING: {metrics.docs_failed} documents failed processing[/yellow]")
        
        console.print("[bold green]✓ Ingest pipeline completed successfully[/bold green]")
        
    except ExtractionAbortError as e:
        console.print(f"[red]Ingest aborted: {e}[/red]")
        sys.exit(2)
    except (ConnectionError, FileNotFoundError) as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Ingest pipeline failed")
        sys.exit(3)


def _display_results(metrics, dry_run: bool) -> None:
    """Display ingest results summary."""
    console.print("\n[bold]Ingest Results Summary[/bold]")
    
    # Create metrics table
    table = Table(title="Processing Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")
    
    table.add_row("Files Discovered", str(metrics.files_discovered))
    table.add_row("Documents Curated", str(metrics.docs_curated))
    table.add_row("Curation Failed", str(metrics.curation_failed))
    table.add_row("Documents Processed", str(metrics.docs_processed))
    table.add_row("Documents Skipped", f"{metrics.docs_skipped} (unchanged)")
    table.add_row("Documents Failed", str(metrics.docs_failed))
    table.add_row("Entities Extracted", str(metrics.entities_extracted))
    table.add_row("Entities Deduped", str(metrics.entities_deduped))
    table.add_row("Entities Linked", str(metrics.entities_linked))
    table.add_row("Entities Created", str(metrics.entities_created))
    table.add_row("Entities Updated", str(metrics.entities_updated))
    table.add_row("MENTIONS Created", str(metrics.mentions_created))
    table.add_row("Relations Created", str(metrics.relations_created))
    
    console.print(table)
    
    # Performance metrics
    console.print(f"\n[bold]Performance:[/bold]")
    console.print(f"  Total Time: {metrics.processing_time:.1f}s")
    console.print(f"  Curation Time: {metrics.curation_time:.1f}s")
    console.print(f"  LLM Time: {metrics.llm_time:.1f}s")
    console.print(f"  Neo4j Time: {metrics.neo4j_time:.1f}s") 
    console.print(f"  Success Rate: {metrics.success_rate:.1f}%")
    
    if dry_run:
        console.print(f"\n[yellow]DRY RUN: No changes were written to the database[/yellow]")
    
    if metrics.failure_details:
        console.print(f"\n[red]Recent Failures:[/red]")
        for error in metrics.failure_details[-5:]:  # Show last 5 errors
            console.print(f"  • {error}")
        if len(metrics.failure_details) > 5:
            console.print(f"  ... and {len(metrics.failure_details) - 5} more")
