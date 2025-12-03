"""Render ontology visualization command for kg-forge CLI."""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.table import Table

from kg_forge.config.settings import get_settings
from kg_forge.ontology_manager import get_ontology_manager
from kg_forge.render.ontology_visualizer import OntologyVisualizer
from kg_forge.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.command("render-ontology")
@click.option(
    "--ontology-pack",
    type=str,
    help="Ontology pack to visualize (default: active or auto-detected)"
)
@click.option(
    "--out", 
    type=click.Path(path_type=Path),
    default="ontology.html",
    help="Output HTML file path (default: ontology.html)"
)
@click.option(
    "--layout",
    type=click.Choice(['force-directed', 'hierarchical', 'circular', 'grid'], case_sensitive=False),
    default='force-directed',
    help="Graph layout algorithm (default: force-directed)"
)
@click.option(
    "--include-examples",
    is_flag=True,
    default=False,
    help="Include entity examples as additional nodes"
)
@click.option(
    "--theme",
    type=click.Choice(['light', 'dark'], case_sensitive=False),
    default='light',
    help="Visualization theme (default: light)"
)
@click.pass_context
def render_ontology(
    ctx: click.Context,
    ontology_pack: Optional[str],
    out: Path,
    layout: str,
    include_examples: bool,
    theme: str
):
    """
    Render ontology visualization as HTML file.
    
    Generates an interactive HTML visualization of the ontology structure
    showing entity types and their relationships using Cytoscape.js.
    """
    try:
        # Load configuration
        settings = get_settings()
        
        # Display configuration
        console.print("[bold]KG Forge Ontology Visualization[/bold]")
        console.print(f"Output: {out}")
        console.print(f"Layout: {layout}")
        console.print(f"Theme: {theme}")
        if include_examples:
            console.print("Including entity examples as nodes")
        console.print()
        
        # Initialize ontology manager
        ontology_manager = get_ontology_manager()
        
        # Determine which ontology pack to use
        if ontology_pack:
            try:
                ontology_manager.set_active_ontology(ontology_pack)
                console.print(f"Using specified ontology pack: [bold]{ontology_pack}[/bold]")
            except ValueError as e:
                console.print(f"[red]Error: Ontology pack '{ontology_pack}' not found: {e}[/red]")
                _display_available_ontologies(ontology_manager)
                ctx.exit(1)
        else:
            active_pack = ontology_manager.get_active_ontology()
            if active_pack:
                console.print(f"Using active ontology pack: [bold]{active_pack.info.id}[/bold]")
            else:
                console.print("[red]Error: No ontology pack available[/red]")
                _display_available_ontologies(ontology_manager)
                ctx.exit(1)
        
        # Get entity definitions
        console.print("Loading entity definitions...")
        entity_definitions = ontology_manager.get_entity_definitions()
        
        if not entity_definitions:
            console.print("[yellow]⚠[/yellow] No entity definitions found")
            console.print("Make sure your ontology pack contains entity definition files")
            ctx.exit(1)
        
        # Display entity types summary
        _display_ontology_summary(entity_definitions)
        
        # Generate visualization
        console.print(f"Generating ontology visualization: {out}")
        with console.status("[bold blue]Building HTML file..."):
            visualizer = OntologyVisualizer()
            active_pack = ontology_manager.get_active_ontology()
            pack_id = active_pack.info.id if active_pack else "unknown"
            
            visualizer.generate_html(
                entity_definitions=entity_definitions,
                output_path=out,
                ontology_pack_id=pack_id,
                layout=layout,
                include_examples=include_examples,
                theme=theme
            )
        
        # Success message
        file_size = out.stat().st_size
        console.print(f"[green]OK[/green] Ontology visualization generated: {out} ({file_size:,} bytes)")
        console.print(f"Open [bold]{out}[/bold] in your browser to explore the ontology")
        
    except Exception as e:
        logger.error(f"Render ontology command failed: {e}", exc_info=True)
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(3)


def _display_available_ontologies(ontology_manager) -> None:
    """Display available ontology packs."""
    available = ontology_manager.list_available_ontologies()
    if available:
        console.print("\n[bold]Available ontology packs:[/bold]")
        for pack in available:
            console.print(f"  - [cyan]{pack['id']}[/cyan]: {pack['name']}")
    else:
        console.print("\n[yellow]No ontology packs found[/yellow]")


def _display_ontology_summary(entity_definitions: List) -> None:
    """Display summary of entity types and relationships."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Entity Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Relations", justify="right", style="blue")
    table.add_column("Examples", justify="right", style="yellow")
    
    total_relations = 0
    total_examples = 0
    
    for definition in entity_definitions:
        relations_count = len(definition.relations) if definition.relations else 0
        examples_count = len(definition.examples) if definition.examples else 0
        
        total_relations += relations_count
        total_examples += examples_count
        
        table.add_row(
            definition.id,
            definition.name or "N/A",
            str(relations_count),
            str(examples_count)
        )
    
    console.print("\n[bold]Ontology Summary:[/bold]")
    console.print(table)
    
    console.print(f"\n[bold]Total:[/bold] {len(entity_definitions)} entity types, "
                 f"{total_relations} relationships, {total_examples} examples\n")