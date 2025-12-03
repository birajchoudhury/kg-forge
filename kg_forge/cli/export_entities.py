"""Export entities command for kg-forge CLI."""

import click
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from kg_forge.config.settings import get_settings
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.command("export-entities")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="entities_extract",
    help="Directory to write entity markdown files (default: entities_extract/)"
)
@click.option(
    "--namespace",
    help="Source namespace (default from config, alphanumeric only)"
)
def export_entities(
    output_dir: Path,
    namespace: Optional[str] = None
) -> None:
    """
    Export entities from knowledge graph to markdown files.
    
    Extracts entity definitions from the Neo4j knowledge graph and writes
    them to markdown files in the specified output directory.
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
            return
        
        console.print(f"[bold blue]Exporting entities from namespace: {target_namespace}[/bold blue]")
        
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Connect to Neo4j and export entities
        with Neo4jClient(config) as client:
            # Query for all entity types in the namespace
            query = """
            MATCH (e:Entity {namespace: $namespace})
            RETURN DISTINCT e.entity_type as entity_type
            ORDER BY entity_type
            """
            
            result = client.run(query, namespace=target_namespace)
            entity_types = [record["entity_type"] for record in result]
            
            if not entity_types:
                console.print(f"[yellow]No entities found in namespace '{target_namespace}'[/yellow]")
                return
            
            console.print(f"[green]Found {len(entity_types)} entity types[/green]")
            
            # Export each entity type to a markdown file
            for entity_type in entity_types:
                export_entity_type(client, target_namespace, entity_type, output_dir)
                
            console.print(f"[green]Successfully exported entities to {output_dir}[/green]")
            
    except Exception as e:
        logger.error(f"Error exporting entities: {e}")
        console.print(f"[red]Error: {e}[/red]")


def export_entity_type(client: Neo4jClient, namespace: str, entity_type: str, output_dir: Path) -> None:
    """Export a specific entity type to a markdown file."""
    # Query for entities of this type
    query = """
    MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type})
    RETURN e.name as name, e.normalized_name as normalized_name, 
           e.aliases as aliases, e.confidence as confidence
    ORDER BY e.name
    LIMIT 100
    """
    
    result = client.run(query, namespace=namespace, entity_type=entity_type)
    entities = list(result)
    
    if not entities:
        return
    
    # Create markdown content
    content = f"# {entity_type.title()}\n\n"
    content += f"**ID**: {entity_type.lower().replace(' ', '_')}\n\n"
    content += f"**Name**: {entity_type.title()}\n\n"
    content += f"**Description**: Auto-generated from knowledge graph export.\n\n"
    content += "**Examples**:\n\n"
    
    # Add examples from the entities
    for i, entity in enumerate(entities[:10]):  # Limit to 10 examples
        name = entity["name"]
        aliases = entity.get("aliases", []) or []
        confidence = entity.get("confidence", 1.0)
        
        content += f"- {name}"
        if aliases and len(aliases) > 1:  # More than just the canonical name
            alias_list = [a for a in aliases if a != name]
            if alias_list:
                content += f" (aliases: {', '.join(alias_list[:3])})"  # Show up to 3 aliases
        content += f" [confidence: {confidence:.2f}]\n"
    
    if len(entities) > 10:
        content += f"- ... and {len(entities) - 10} more entities\n"
    
    content += "\n**Relations**:\n\n"
    content += "*(Relations to be defined based on domain knowledge)*\n\n"
    
    # Write to file
    filename = f"{entity_type.lower().replace(' ', '_')}.md"
    output_file = output_dir / filename
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    console.print(f"[blue]Exported {len(entities)} {entity_type} entities to {filename}[/blue]")