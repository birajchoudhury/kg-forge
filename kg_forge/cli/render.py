"""Render command for kg-forge CLI."""

import sys
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table

from kg_forge.config.settings import get_settings
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.graph.exceptions import Neo4jConnectionError as GraphConnectionError
from kg_forge.render.graph_query import GraphQuery, SeedConfig
from kg_forge.render.html_builder import HtmlBuilder
from kg_forge.utils.logging import get_logger
from kg_forge.ontology_manager import get_ontology_manager

console = Console()
logger = get_logger(__name__)


@click.command()
@click.option(
    "--namespace",
    type=str,
    help="Namespace to render (default from config)"
)
@click.option(
    "--out", 
    type=click.Path(path_type=Path),
    default="graph.html",
    help="Output HTML file path (default: graph.html)"
)
@click.option(
    "--depth",
    type=int,
    default=2,
    help="Maximum traversal depth from seeds (default: 2)"
)
@click.option(
    "--max-nodes",
    type=int, 
    default=200,
    help="Maximum nodes in visualization (default: 200)"
)
@click.option(
    "--seed-doc-id",
    type=str,
    help="Start from specific document ID"
)
@click.option(
    "--seed-entity",
    type=str,
    help="Entity name to use as seed (requires --entity-type)"
)
@click.option(
    "--entity-type",
    type=str,
    help="Entity type for --seed-entity"
)
@click.option(
    "--include-types",
    type=str,
    help="Comma-separated entity types to include (e.g. 'Product,Team')"
)
@click.option(
    "--exclude-types", 
    type=str,
    help="Comma-separated entity types to exclude"
)
@click.option(
    "--namespace",
    type=str,
    help="Target namespace (alphanumeric only, default from config)"
)
@click.pass_context
def render(
    ctx: click.Context,
    namespace: Optional[str],
    out: Path,
    depth: int,
    max_nodes: int,
    seed_doc_id: Optional[str],
    seed_entity: Optional[str],
    entity_type: Optional[str],
    include_types: Optional[str],
    exclude_types: Optional[str]
):
    """
    Render knowledge graph visualization as HTML file.
    
    Generates an interactive HTML visualization of the knowledge graph
    by querying Neo4j for a filtered subgraph and embedding the data
    with neovis.js for interactive exploration.
    """
    try:
        # Load configuration
        settings = get_settings()
        target_namespace = namespace or settings.app.default_namespace
        
        # Validate namespace
        try:
            settings.validate_namespace(target_namespace)
        except ValueError as e:
            console.print(f"[red]Invalid namespace: {e}[/red]")
            ctx.exit(1)
        
        # Validate seed entity configuration
        if seed_entity and not entity_type:
            console.print("[red]Error: --seed-entity requires --entity-type[/red]")
            sys.exit(2)
        
        # Display configuration
        console.print("[bold]KG Forge Graph Rendering[/bold]")
        console.print(f"Namespace: {target_namespace}")
        console.print(f"Output: {out}")
        console.print(f"Max Depth: {depth}")
        console.print(f"Max Nodes: {max_nodes}")
        
        if seed_doc_id or seed_entity:
            console.print("[bold]Seed Configuration:[/bold]")
            if seed_doc_id:
                console.print(f"  Document ID: {seed_doc_id}")
            if seed_entity:
                console.print(f"  Entity: {seed_entity} ({entity_type})")
        
        if include_types or exclude_types:
            console.print("[bold]Type Filtering:[/bold]")
            if include_types:
                console.print(f"  Include: {include_types}")
            if exclude_types:
                console.print(f"  Exclude: {exclude_types}")
        
        console.print()
        
        # Initialize components
        neo4j_client = Neo4jClient(settings)
        graph_query = GraphQuery(neo4j_client)
        
        # Get ontology-aware styling
        ontology_manager = get_ontology_manager()
        if settings.app.ontology_pack:
            try:
                ontology_manager.set_active_ontology(settings.app.ontology_pack)
            except Exception as e:
                logger.warning(f"Failed to activate ontology pack '{settings.app.ontology_pack}': {e}")
        
        active_pack = ontology_manager.get_active_ontology()
        ontology_id = active_pack.info.id if active_pack else None
        html_builder = HtmlBuilder(ontology_id=ontology_id)
        
        # Test Neo4j connection
        console.print("Testing Neo4j connection...")
        try:
            neo4j_client.connect()
            console.print("[green]OK[/green] Connected to Neo4j")
        except GraphConnectionError as e:
            console.print(f"[red]FAIL[/red] Neo4j connection failed: {e}")
            console.print("Make sure Neo4j is running and credentials are correct.")
            sys.exit(1)
        
        # Prepare seed configuration
        seeds = _build_seed_config(seed_doc_id, seed_entity, entity_type)
        
        # Parse type filters
        include_type_list = _parse_type_list(include_types) if include_types else None
        exclude_type_list = _parse_type_list(exclude_types) if exclude_types else None
        
        # Query subgraph
        console.print("Querying subgraph from Neo4j...")
        with console.status("[bold green]Executing graph query..."):
            graph_data = graph_query.get_subgraph(
                namespace=target_namespace,
                seeds=seeds,
                depth=depth,
                max_nodes=max_nodes,
                include_types=include_type_list,
                exclude_types=exclude_type_list
            )
        
        # Debug: Check graph data status
        # print(f"DEBUG: GraphData nodes={len(graph_data.nodes)}, rels={len(graph_data.relationships)}, is_empty={graph_data.is_empty()}")
        
        if graph_data.is_empty():
            console.print(f"[yellow]WARN[/yellow] No graph data found for namespace '{target_namespace}'")
            console.print("Make sure you have ingested content with [bold]kg-forge ingest[/bold]")
            # Still generate empty visualization
        else:
            # Display query results
            _display_graph_summary(graph_data, max_nodes)
        
        # Generate HTML visualization
        console.print(f"Generating HTML visualization: {out}")
        with console.status("[bold blue]Building HTML file..."):
            max_nodes_reached = graph_data.node_count >= max_nodes
            seed_info = html_builder.generate_seed_info(seeds) if not seeds.is_empty else None
            
            html_builder.generate_html(
                graph_data=graph_data,
                output_path=out,
                namespace=target_namespace,
                seed_info=seed_info,
                depth=depth,
                max_nodes=max_nodes,
                max_nodes_reached=max_nodes_reached
            )
        
        # Success message
        file_size = out.stat().st_size
        console.print(f"[green]OK[/green] Visualization generated: {out} ({file_size:,} bytes)")
        console.print(f"Open [bold]{out}[/bold] in your browser to explore the graph")
        
    except GraphConnectionError as e:
        logger.error(f"Neo4j connection error: {e}")
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Render command failed: {e}", exc_info=True)
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(3)


def _build_seed_config(
    seed_doc_id: Optional[str],
    seed_entity: Optional[str], 
    entity_type: Optional[str]
) -> SeedConfig:
    """Build seed configuration from CLI arguments."""
    doc_ids = [seed_doc_id] if seed_doc_id else []
    entities = []
    
    if seed_entity and entity_type:
        entities.append({"name": seed_entity, "type": entity_type})
    
    return SeedConfig(doc_ids=doc_ids, entities=entities)


def _parse_type_list(type_string: str) -> List[str]:
    """Parse comma-separated type list from CLI argument."""
    return [t.strip() for t in type_string.split(",") if t.strip()]


def _display_graph_summary(graph_data, max_nodes: int):
    """Display summary of retrieved graph data."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    table.add_row("Nodes Retrieved", str(graph_data.node_count))
    table.add_row("Relationships Retrieved", str(graph_data.relationship_count))
    
    if graph_data.node_count >= max_nodes:
        table.add_row("Status", f"[yellow]Limited to {max_nodes} nodes[/yellow]")
    else:
        table.add_row("Status", "[green]Complete subgraph[/green]")
    
    console.print(table)
    console.print()
    
    # Display node type breakdown
    if graph_data.nodes:
        _display_node_breakdown(graph_data.nodes)


def _display_node_breakdown(nodes):
    """Display breakdown of nodes by type."""
    type_counts = {}
    
    for node in nodes:
        if "Doc" in node.labels:
            node_type = "Document"
        elif "Entity" in node.labels:
            entity_type = node.properties.get("entity_type", "Unknown")
            node_type = f"Entity:{entity_type}"
        else:
            node_type = ":".join(node.labels)
        
        type_counts[node_type] = type_counts.get(node_type, 0) + 1
    
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Node Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    for node_type, count in sorted(type_counts.items()):
        table.add_row(node_type, str(count))
    
    console.print("Node Type Breakdown:")
    console.print(table)
    console.print()
