"""CLI commands for entity definition management."""

import json
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..config.settings import get_settings
from ..entities import EntityDefinitionLoader

logger = logging.getLogger(__name__)
console = Console()


@click.group()
def entities():
    """Entity definition management commands."""
    pass


@entities.command('list-types')
@click.option(
    '--entities-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help='Directory containing entity definition files (default: from config)'
)
@click.option('--format', 'output_format', 
    type=click.Choice(['table', 'json']), 
    default='table',
    help='Output format'
)
def list_types(entities_dir: Optional[Path], output_format: str):
    """List all available entity types."""
    
    logger.debug(f"Listing entity types from {'directory' if entities_dir else 'active ontology'}")
    
    try:
        if entities_dir:
            # Use legacy file-based loading when directory is specified
            from kg_forge.entities.definitions import EntityDefinitionLoader
            loader = EntityDefinitionLoader()
            definitions = loader.load_entity_definitions(entities_dir)
        else:
            # Use ontology pack when no directory specified
            from kg_forge.ontology_manager import get_ontology_manager
            ontology_manager = get_ontology_manager()
            active_ontology = ontology_manager.get_active_ontology()
            definitions = active_ontology.get_entity_definitions()
        
        if not definitions:
            console.print("[yellow]No entity definitions found[/yellow]")
            return
        
        if output_format == 'json':
            # JSON output for programmatic use
            entity_list = [
                {
                    "id": defn.id,
                    "name": defn.name,
                    "source_file": defn.source_file,
                    "relations_count": len(defn.relations),
                    "examples_count": len(defn.examples)
                }
                for defn in sorted(definitions, key=lambda d: d.id)
            ]
            # Use print instead of console.print to avoid ANSI formatting
            print(json.dumps(entity_list, indent=2))
        else:
            # Rich table output for human consumption
            table = Table(title="Entity Type Definitions")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Relations", justify="right", style="blue")
            table.add_column("Examples", justify="right", style="magenta")
            table.add_column("Source File", style="dim")
            
            for defn in sorted(definitions, key=lambda d: d.id):
                table.add_row(
                    defn.id,
                    defn.name or "[dim]N/A[/dim]",
                    str(len(defn.relations)),
                    str(len(defn.examples)),
                    defn.source_file or ""
                )
            
            console.print(table)
            console.print(f"\n[dim]Found {len(definitions)} entity type definitions[/dim]")
            
    except Exception as e:
        logger.error(f"Failed to load entity definitions: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(f"Failed to load entity definitions: {e}")


@entities.command('show-type')
@click.argument('entity_id')
@click.option(
    '--entities-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help='Directory containing entity definition files (default: from config)'
)
@click.option('--format', 'output_format',
    type=click.Choice(['rich', 'json', 'raw']),
    default='rich',
    help='Output format'
)
def show_type(entity_id: str, entities_dir: Optional[Path], output_format: str):
    """Show detailed information about a specific entity type."""
    
    logger.debug(f"Loading entity type '{entity_id}' from {'directory' if entities_dir else 'active ontology'}")
    
    try:
        if entities_dir:
            # Use legacy file-based loading when directory is specified
            from kg_forge.entities.definitions import EntityDefinitionLoader
            loader = EntityDefinitionLoader()
            definitions = loader.load_entity_definitions(entities_dir)
        else:
            # Use ontology pack when no directory specified
            from kg_forge.ontology_manager import get_ontology_manager
            ontology_manager = get_ontology_manager()
            active_ontology = ontology_manager.get_active_ontology()
            definitions = active_ontology.get_entity_definitions()
            
        # Find matching definition
        definition = next((d for d in definitions if d.id == entity_id), None)
        
        if not definition:
            available_ids = [d.id for d in definitions]
            console.print(f"[red]Entity type '{entity_id}' not found[/red]")
            console.print(f"[dim]Available types: {', '.join(sorted(available_ids))}[/dim]")
            raise click.ClickException(f"Entity type '{entity_id}' not found")
        
        if output_format == 'json':
            # JSON output for programmatic use
            print(json.dumps(definition.to_dict(), indent=2))
            
        elif output_format == 'raw':
            # Raw markdown output
            if definition.raw_markdown:
                console.print(definition.raw_markdown)
            else:
                console.print(f"[yellow]No raw markdown available for {entity_id}[/yellow]")
                
        else:
            # Rich formatted output for human consumption
            _display_entity_definition_rich(definition)
            
    except Exception as e:
        logger.error(f"Failed to show entity type {entity_id}: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(f"Failed to show entity type: {e}")


@entities.command('build-prompt')
@click.option(
    '--entities-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help='Directory containing entity definition files (default: from config)'
)
@click.option(
    '--template-file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help='Prompt template file (default: entities_dir/prompt_template.md)'
)
@click.option(
    '--output',
    type=click.Path(dir_okay=False, path_type=Path),
    help='Output file for merged prompt (default: stdout)'
)
def build_prompt(entities_dir: Optional[Path], template_file: Optional[Path], output: Optional[Path]):
    """Build complete prompt by merging template with entity definitions."""
    
    logger.debug(f"Building prompt from {'directory' if entities_dir else 'active ontology'}")
    
    try:
        if entities_dir:
            # Use legacy file-based loading when directory is specified
            from kg_forge.entities.definitions import EntityDefinitionLoader
            loader = EntityDefinitionLoader()
            
            if not template_file:
                template_file = entities_dir / "prompt_template.md"
            
            # Load template
            template_content = loader.load_prompt_template(template_file)
            # Load entity definitions
            definitions = loader.load_entity_definitions(entities_dir)
        else:
            # Use ontology pack when no directory specified
            from kg_forge.ontology_manager import get_ontology_manager
            ontology_manager = get_ontology_manager()
            active_ontology = ontology_manager.get_active_ontology()
            definitions = active_ontology.get_entity_definitions()
            # Get template from ontology pack
            template_content = active_ontology.get_prompt_template()
        
        if not definitions:
            console.print("[yellow]Warning: No entity definitions found[/yellow]")
        
        # Build merged prompt
        from kg_forge.entities.definitions import EntityDefinitionLoader
        loader = EntityDefinitionLoader()
        merged_prompt = loader.build_merged_prompt(template_content, definitions)
        
        # Output result
        if output:
            output.write_text(merged_prompt, encoding='utf-8')
            console.print(f"[green]Merged prompt written to[/green] {output}")
            console.print(f"[dim]Entity definitions:[/dim] {len(definitions)} types from ontology")
        else:
            console.print(merged_prompt)
            
    except Exception as e:
        logger.error(f"Failed to build prompt: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(f"Failed to build prompt: {e}")


@entities.command('validate')
@click.option(
    '--entities-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help='Directory containing entity definition files (default: from config)'
)
@click.option('--format', 'output_format',
    type=click.Choice(['table', 'json']),
    default='table',
    help='Output format'
)
def validate(entities_dir: Optional[Path], output_format: str):
    """Validate entity definitions."""
    
    logger.debug(f"Validating entity definitions from {'directory' if entities_dir else 'active ontology'}")
    
    try:
        validation_results = []
        
        if entities_dir:
            # Use legacy file-based validation when directory is specified
            from kg_forge.entities.definitions import EntityDefinitionLoader
            loader = EntityDefinitionLoader()
            
            # Get all markdown files
            md_files = sorted(entities_dir.glob("*.md"))
            entity_files = [f for f in md_files if f.name != "prompt_template.md"]
            
            for file_path in entity_files:
                result = {
                    "file": file_path.name,
                    "status": "valid",
                    "issues": []
                }
                
                try:
                    definition = loader.load_single_definition(file_path)
                    
                    # Validation checks
                    if not definition.id:
                        result["issues"].append("Missing entity ID")
                    if not definition.name:
                        result["issues"].append("Missing name")
                    if not definition.description:
                        result["issues"].append("Missing description")
                    
                    if result["issues"]:
                        result["status"] = "warnings"
                        
                except Exception as e:
                    result["status"] = "error"
                    result["issues"].append(f"Parse error: {str(e)}")
                
                validation_results.append(result)
                
        else:
            # Use ontology pack validation when no directory specified
            from kg_forge.ontology_manager import get_ontology_manager
            ontology_manager = get_ontology_manager()
            active_ontology = ontology_manager.get_active_ontology()
            definitions = active_ontology.get_entity_definitions()
            
            for definition in definitions:
                result = {
                    "entity_id": definition.id,
                    "status": "valid", 
                    "issues": []
                }
                
                # Basic validation checks
                if not definition.id:
                    result["issues"].append("Missing entity ID")
                if not definition.name:
                    result["issues"].append("Missing name")
                if not definition.description:
                    result["issues"].append("Missing description")
                
                if result["issues"]:
                    result["status"] = "warnings"
                
                validation_results.append(result)
        
        # Output results
        if output_format == 'json':
            print(json.dumps(validation_results, indent=2))
        else:
            _display_validation_results_rich(validation_results)
            
    except Exception as e:
        logger.error(f"Failed to validate entity definitions: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(f"Failed to validate entity definitions: {e}")


def _display_entity_definition_rich(definition):
    """Display entity definition using Rich formatting."""
    # Header with entity ID and name
    title = f"Entity Type: {definition.id}"
    if definition.name:
        title += f" ({definition.name})"
    
    console.print(Panel(title, style="bold cyan"))
    
    # Basic information
    info_table = Table(show_header=False, box=None)
    info_table.add_column("Field", style="bold")
    info_table.add_column("Value")
    
    info_table.add_row("ID", definition.id)
    info_table.add_row("Name", definition.name or "[dim]N/A[/dim]")
    info_table.add_row("Source File", definition.source_file or "[dim]N/A[/dim]")
    
    console.print(info_table)
    console.print()
    
    # Description
    if definition.description:
        console.print(Panel(
            Text(definition.description, style="dim"),
            title="Description",
            title_align="left"
        ))
    
    # Relations
    if definition.relations:
        relations_table = Table(title="Relations")
        relations_table.add_column("Target Type", style="cyan")
        relations_table.add_column("To Label", style="green")
        relations_table.add_column("From Label", style="yellow")
        
        for rel in definition.relations:
            relations_table.add_row(rel.target_type, rel.to_label, rel.from_label)
        
        console.print(relations_table)
    
    # Examples
    if definition.examples:
        console.print(f"\n[bold]Examples ({len(definition.examples)}):[/bold]")
        for i, example in enumerate(definition.examples, 1):
            console.print(f"\n[bold cyan]{i}. {example.title}[/bold cyan]")
            console.print(Text(example.description, style="dim"))


def _display_validation_results_rich(results):
    """Display validation results using Rich formatting."""
    table = Table(title="Entity Definition Validation Results")
    
    # Check if we have file-based or entity-based results
    has_files = any("file" in result for result in results)
    
    if has_files:
        table.add_column("File", style="cyan")
    else:
        table.add_column("Entity ID", style="cyan")
        
    table.add_column("Status", justify="center")
    table.add_column("Issues")
    
    valid_count = 0
    warning_count = 0
    error_count = 0
    
    for result in results:
        # Style status based on result
        status = result["status"]
        if status == "valid":
            status_display = "[green]✓ Valid[/green]"
            valid_count += 1
        elif status == "warnings":
            status_display = "[yellow]⚠ Warnings[/yellow]"
            warning_count += 1
        else:
            status_display = "[red]✗ Error[/red]"
            error_count += 1
        
        # Format issues
        issues_display = ""
        if result["issues"]:
            issues_display = "\n".join(f"• {issue}" for issue in result["issues"])
        
        # Use file or entity_id as identifier
        identifier = result.get("file", result.get("entity_id", "unknown"))
        table.add_row(identifier, status_display, issues_display or "[dim]None[/dim]")
    
    console.print(table)
    
    # Summary
    total_items = len(results)
    item_type = "files" if has_files else "entities"
    console.print(f"\n[dim]Validation Summary:[/dim]")
    console.print(f"  Total {item_type}: {total_items}")
    console.print(f"  [green]Valid: {valid_count}[/green]")
    console.print(f"  [yellow]Warnings: {warning_count}[/yellow]") 
    console.print(f"  [red]Errors: {error_count}[/red]")