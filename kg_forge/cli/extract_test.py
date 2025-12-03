"""
CLI command for testing extraction backends.

Provides extract-test command for debugging and comparing extraction backends.
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import click
import logging

from kg_forge.config.settings import get_settings
from kg_forge.ontology_manager import get_ontology_manager
from kg_forge.ontology.base import OntologyPack
from kg_forge.extraction.interface import create_extraction_backend, ExtractionBackend
from kg_forge.models.lexical import LexicalGraph

logger = logging.getLogger(__name__)


@click.command("extract-test")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--backend", 
              type=click.Choice(["llm", "spacy", "fake", "both"], case_sensitive=False),
              default="both",
              help="Extraction backend to test")
@click.option("--entities-dir", 
              type=click.Path(exists=True, path_type=Path),
              help="Path to entity definitions directory")
@click.option("--ontology-pack",
              type=str,
              help="Ontology pack ID to use")
@click.option("--output-format",
              type=click.Choice(["text", "json"], case_sensitive=False),
              default="text",
              help="Output format")
@click.option("--fake-backends",
              is_flag=True,
              help="Use fake backends for testing")
@click.option("--show-comparison",
              is_flag=True,
              help="Show side-by-side comparison when using both backends")
@click.option("--save-results",
              type=click.Path(path_type=Path),
              help="Save results to JSON file")
@click.option("--verbose", "-v",
              is_flag=True,
              help="Enable verbose logging")
def extract_test(input_file: Path,
                backend: str,
                entities_dir: Optional[Path],
                ontology_pack: Optional[str],
                output_format: str,
                fake_backends: bool,
                show_comparison: bool,
                save_results: Optional[Path],
                verbose: bool):
    """Test entity extraction backends with sample documents.
    
    This command allows testing and comparing different extraction backends
    without writing results to the Knowledge Graph. Useful for debugging,
    validation, and backend comparison.
    
    Examples:
        kg-forge extract-test sample.txt --backend llm
        kg-forge extract-test sample.txt --backend both --show-comparison
        kg-forge extract-test sample.txt --fake-backends --output-format json
    """
    # Configure logging
    if verbose:
        logging.getLogger("kg_forge").setLevel(logging.DEBUG)
    
    try:
        # Load configuration
        config = get_settings()
        click.echo(f"Using configuration: loaded from multiple sources")
        
        # Read input content
        content = input_file.read_text(encoding='utf-8')
        doc_id = input_file.stem
        
        click.echo(f"Processing document: {input_file.name} ({len(content)} characters)")
        
        # Load ontology
        ontology = _load_ontology(entities_dir, ontology_pack, config)
        click.echo(f"Loaded ontology: {len(ontology.get_entity_definitions())} entity types")
        
        # Run extraction based on backend selection
        if backend == "both":
            results = _run_both_backends(content, doc_id, ontology, fake_backends)
            _display_both_results(results, output_format, show_comparison)
        else:
            result = _run_single_backend(content, doc_id, ontology, backend, fake_backends)
            _display_single_result(result, output_format)
        
        # Save results if requested
        if save_results:
            if backend == "both":
                _save_both_results(results, save_results)
            else:
                _save_single_result(result, save_results)
            click.echo(f"Results saved to: {save_results}")
        
        click.echo("\nExtraction test completed successfully!")
        
    except Exception as e:
        logger.error(f"Extract test failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(f"Extract test failed: {e}")


def _load_ontology(entities_dir: Optional[Path], 
                  ontology_pack: Optional[str], 
                  config: Any) -> OntologyPack:
    """Load ontology pack for extraction.
    
    Args:
        entities_dir: Custom entities directory
        ontology_pack: Ontology pack ID
        config: Application configuration
    
    Returns:
        Loaded OntologyPack
    """
    ontology_manager = get_ontology_manager()
    
    if ontology_pack:
        return ontology_manager.registry.get_pack(ontology_pack)
    elif entities_dir:
        # Load from custom directory (legacy support) - use default for now
        return ontology_manager.get_active_ontology() or ontology_manager.registry.get_default_pack()
    else:
        # Use active or default ontology
        return ontology_manager.get_active_ontology() or ontology_manager.registry.get_default_pack()


def _run_single_backend(content: str, doc_id: str, ontology: OntologyPack, 
                       backend_name: str, fake_mode: bool) -> Dict[str, Any]:
    """Run extraction with a single backend.
    
    Args:
        content: Document content
        doc_id: Document identifier
        ontology: Ontology pack
        backend_name: Backend to use ('llm' or 'spacy')
        fake_mode: Use fake backend
    
    Returns:
        Extraction result dictionary
    """
    click.echo(f"\nRunning {backend_name.upper()} extraction backend...")
    
    start_time = time.time()
    
    try:
        # Create backend
        actual_backend_name = "fake" if fake_mode else backend_name
        backend_config = {}
        backend = create_extraction_backend(actual_backend_name, backend_config)
        
        # Validate configuration
        if not backend.validate_configuration():
            raise click.ClickException(f"Backend {backend_name} configuration validation failed")
        
        # Run extraction
        graph = backend.extract(content, ontology, doc_id)
        
        extraction_time = time.time() - start_time
        
        # Get backend info
        backend_info = backend.get_backend_info()
        
        result = {
            "backend": backend_name,
            "extraction_time": extraction_time,
            "graph": graph,
            "backend_info": backend_info,
            "success": True,
            "error": None
        }
        
        click.echo(f"✓ {backend_name.upper()} extraction completed in {extraction_time:.2f}s")
        click.echo(f"  Entities: {len(graph.mentions)}")
        click.echo(f"  Relations: {len(graph.relations)}")
        
        return result
        
    except Exception as e:
        extraction_time = time.time() - start_time
        
        result = {
            "backend": backend_name,
            "extraction_time": extraction_time,
            "graph": None,
            "backend_info": {},
            "success": False,
            "error": str(e)
        }
        
        click.echo(f"✗ {backend_name.upper()} extraction failed after {extraction_time:.2f}s: {e}")
        return result


def _run_both_backends(content: str, doc_id: str, ontology: OntologyPack, 
                      fake_mode: bool) -> Dict[str, Dict[str, Any]]:
    """Run extraction with both backends.
    
    Args:
        content: Document content
        doc_id: Document identifier
        ontology: Ontology pack
        fake_mode: Use fake backends
    
    Returns:
        Dictionary with results from both backends
    """
    results = {}
    
    # Run LLM backend
    results["llm"] = _run_single_backend(content, doc_id, ontology, "llm", fake_mode)
    
    # Run spaCy backend
    results["spacy"] = _run_single_backend(content, doc_id, ontology, "spacy", fake_mode)
    
    return results


def _display_single_result(result: Dict[str, Any], output_format: str):
    """Display results from single backend.
    
    Args:
        result: Extraction result
        output_format: Output format ('text' or 'json')
    """
    if output_format == "json":
        _display_json_result(result)
    else:
        _display_text_result(result)


def _display_both_results(results: Dict[str, Dict[str, Any]], 
                         output_format: str, show_comparison: bool):
    """Display results from both backends.
    
    Args:
        results: Results from both backends
        output_format: Output format
        show_comparison: Whether to show comparison
    """
    if output_format == "json":
        # JSON output for both backends
        output = {
            "llm": _serialize_result_for_json(results["llm"]),
            "spacy": _serialize_result_for_json(results["spacy"])
        }
        click.echo(json.dumps(output, indent=2))
    else:
        # Text output
        click.echo("\n" + "="*80)
        click.echo("EXTRACTION RESULTS COMPARISON")
        click.echo("="*80)
        
        for backend_name, result in results.items():
            click.echo(f"\n{backend_name.upper()} Backend Results:")
            click.echo("-" * 40)
            _display_text_result(result)
        
        if show_comparison:
            _display_comparison(results)


def _display_text_result(result: Dict[str, Any]):
    """Display result in text format.
    
    Args:
        result: Extraction result
    """
    if not result["success"]:
        click.echo(f"❌ Extraction failed: {result['error']}")
        return
    
    graph = result["graph"]
    
    click.echo(f"\n📊 Summary:")
    click.echo(f"  Backend: {result['backend']}")
    click.echo(f"  Extraction time: {result['extraction_time']:.2f}s")
    click.echo(f"  Entities found: {len(graph.mentions)}")
    click.echo(f"  Relations found: {len(graph.relations)}")
    
    # Display entities
    if graph.mentions:
        click.echo(f"\n📋 Entities:")
        entity_types = {}
        for mention in graph.mentions:
            if mention.entity_type not in entity_types:
                entity_types[mention.entity_type] = []
            entity_types[mention.entity_type].append(mention)
        
        for entity_type, mentions in entity_types.items():
            click.echo(f"  {entity_type} ({len(mentions)}):")
            for mention in mentions[:5]:  # Show first 5
                confidence = mention.features.get("confidence", mention.features.get("gliner_confidence", "N/A"))
                click.echo(f"    • {mention.surface} (confidence: {confidence})")
            if len(mentions) > 5:
                click.echo(f"    ... and {len(mentions) - 5} more")
    
    # Display relations
    if graph.relations:
        click.echo(f"\n🔗 Relations:")
        relation_types = {}
        for relation in graph.relations:
            if relation.type not in relation_types:
                relation_types[relation.type] = []
            relation_types[relation.type].append(relation)
        
        # Get mention lookup for relation display
        mention_lookup = {m.id: m for m in graph.mentions}
        
        for relation_type, relations in relation_types.items():
            click.echo(f"  {relation_type} ({len(relations)}):")
            for relation in relations[:3]:  # Show first 3
                src_mention = mention_lookup.get(relation.src_mention_id)
                dst_mention = mention_lookup.get(relation.dst_mention_id)
                if src_mention and dst_mention:
                    confidence = relation.features.get("confidence", relation.features.get("glirel_confidence", "N/A"))
                    click.echo(f"    • {src_mention.surface} → {dst_mention.surface} (confidence: {confidence})")
            if len(relations) > 3:
                click.echo(f"    ... and {len(relations) - 3} more")


def _display_json_result(result: Dict[str, Any]):
    """Display result in JSON format.
    
    Args:
        result: Extraction result
    """
    output = _serialize_result_for_json(result)
    click.echo(json.dumps(output, indent=2))


def _serialize_result_for_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize result for JSON output.
    
    Args:
        result: Extraction result
    
    Returns:
        JSON-serializable result
    """
    if not result["success"]:
        return {
            "backend": result["backend"],
            "success": False,
            "error": result["error"],
            "extraction_time": result["extraction_time"]
        }
    
    graph = result["graph"]
    
    return {
        "backend": result["backend"],
        "success": True,
        "extraction_time": result["extraction_time"],
        "summary": graph.summary(),
        "entities": [mention.to_dict() for mention in graph.mentions],
        "relations": [relation.to_dict() for relation in graph.relations],
        "metadata": graph.metadata,
        "backend_info": result["backend_info"]
    }


def _display_comparison(results: Dict[str, Dict[str, Any]]):
    """Display comparison between backends.
    
    Args:
        results: Results from both backends
    """
    click.echo(f"\n🔍 Backend Comparison:")
    click.echo("-" * 40)
    
    llm_result = results["llm"]
    spacy_result = results["spacy"]
    
    # Compare success rates
    llm_success = llm_result["success"]
    spacy_success = spacy_result["success"]
    
    click.echo(f"Success: LLM={'✓' if llm_success else '✗'}, spaCy={'✓' if spacy_success else '✗'}")
    
    if llm_success and spacy_success:
        llm_graph = llm_result["graph"]
        spacy_graph = spacy_result["graph"]
        
        # Compare counts
        click.echo(f"Entities: LLM={len(llm_graph.mentions)}, spaCy={len(spacy_graph.mentions)}")
        click.echo(f"Relations: LLM={len(llm_graph.relations)}, spaCy={len(spacy_graph.relations)}")
        
        # Compare timing
        llm_time = llm_result["extraction_time"]
        spacy_time = spacy_result["extraction_time"]
        click.echo(f"Time: LLM={llm_time:.2f}s, spaCy={spacy_time:.2f}s")
        
        # Find common entities
        llm_entities = {m.surface.lower() for m in llm_graph.mentions}
        spacy_entities = {m.surface.lower() for m in spacy_graph.mentions}
        
        common_entities = llm_entities & spacy_entities
        llm_only = llm_entities - spacy_entities  
        spacy_only = spacy_entities - llm_entities
        
        click.echo(f"Entity overlap: {len(common_entities)} common")
        if llm_only:
            click.echo(f"LLM only: {', '.join(list(llm_only)[:3])}" + ("..." if len(llm_only) > 3 else ""))
        if spacy_only:
            click.echo(f"spaCy only: {', '.join(list(spacy_only)[:3])}" + ("..." if len(spacy_only) > 3 else ""))


def _save_single_result(result: Dict[str, Any], output_file: Path):
    """Save single result to file.
    
    Args:
        result: Extraction result
        output_file: Output file path
    """
    output = _serialize_result_for_json(result)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def _save_both_results(results: Dict[str, Dict[str, Any]], output_file: Path):
    """Save both results to file.
    
    Args:
        results: Results from both backends
        output_file: Output file path
    """
    output = {
        "llm": _serialize_result_for_json(results["llm"]),
        "spacy": _serialize_result_for_json(results["spacy"])
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)