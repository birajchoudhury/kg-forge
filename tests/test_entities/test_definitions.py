"""Tests for entity definition loading and parsing."""

import pytest
import tempfile
from pathlib import Path
from kg_forge.entities.definitions import EntityDefinitionLoader
from kg_forge.entities.models import EntityDefinition, RelationDefinition, ExampleDefinition


class TestEntityDefinitionLoader:
    """Tests for EntityDefinitionLoader class."""
    
    @pytest.fixture
    def sample_entity_md(self):
        """Sample entity definition markdown content."""
        return """# ID: Product

## Name: Product Management

## Description
Product entities represent business products, services, or offerings.
They can include physical products, digital services, or hybrid offerings.

## Relations
- Component : USES : USED_BY
- Technology : IMPLEMENTS : IMPLEMENTED_BY
- Team : OWNS : OWNED_BY

## Examples

### SaaS Platform
A cloud-based software as a service platform that provides analytics capabilities
for enterprise customers.

### Mobile Application
Native mobile app for iOS and Android that connects to backend services
and provides user-facing functionality.
"""
    
    @pytest.fixture
    def minimal_entity_md(self):
        """Minimal entity definition with just ID."""
        return """# ID: MinimalEntity
"""
    
    @pytest.fixture
    def prompt_template_md(self):
        """Sample prompt template content."""
        return """You are an AI assistant that extracts entities from text.

Extract entities of the following types:

{{ENTITY_TYPE_DEFINITIONS}}

Please identify and extract entities from the provided text.
"""
    
    @pytest.fixture
    def temp_entities_dir(self, sample_entity_md, minimal_entity_md, prompt_template_md):
        """Create temporary directory with test entity files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            entities_dir = Path(temp_dir)
            
            # Create sample entity files
            (entities_dir / "product.md").write_text(sample_entity_md)
            (entities_dir / "minimal.md").write_text(minimal_entity_md)
            (entities_dir / "prompt_template.md").write_text(prompt_template_md)
            
            yield entities_dir
    
    def test_load_entity_definitions_success(self, temp_entities_dir):
        """Test successful loading of entity definitions."""
        loader = EntityDefinitionLoader()
        definitions = loader.load_entity_definitions(temp_entities_dir)
        
        assert len(definitions) == 2  # product.md and minimal.md (excludes prompt_template.md)
        
        # Find product definition
        product_def = next((d for d in definitions if d.id == "Product"), None)
        assert product_def is not None
        assert product_def.name == "Product Management"
        assert "Product entities represent business products" in product_def.description
        assert len(product_def.relations) == 3
        assert len(product_def.examples) == 2
        assert product_def.source_file == "product.md"
        
        # Find minimal definition
        minimal_def = next((d for d in definitions if d.id == "MinimalEntity"), None)
        assert minimal_def is not None
        assert minimal_def.name is None
        assert minimal_def.description is None
        assert len(minimal_def.relations) == 0
        assert len(minimal_def.examples) == 0
        assert minimal_def.source_file == "minimal.md"
    
    def test_load_entity_definitions_nonexistent_dir(self):
        """Test loading from non-existent directory."""
        loader = EntityDefinitionLoader()
        
        with pytest.raises(FileNotFoundError, match="Entity definitions directory not found"):
            loader.load_entity_definitions(Path("/nonexistent/path"))
    
    def test_load_single_definition_complete(self, temp_entities_dir):
        """Test loading single complete entity definition."""
        loader = EntityDefinitionLoader()
        product_file = temp_entities_dir / "product.md"
        
        definition = loader.load_single_definition(product_file)
        
        assert definition.id == "Product"
        assert definition.name == "Product Management"
        assert definition.description is not None
        assert "Product entities represent business products" in definition.description
        
        # Check relations
        assert len(definition.relations) == 3
        component_rel = next((r for r in definition.relations if r.target_type == "Component"), None)
        assert component_rel is not None
        assert component_rel.to_label == "USES"
        assert component_rel.from_label == "USED_BY"
        
        # Check examples
        assert len(definition.examples) == 2
        saas_example = next((e for e in definition.examples if e.title == "SaaS Platform"), None)
        assert saas_example is not None
        assert "cloud-based software" in saas_example.description
    
    def test_parse_entity_definition_id_variations(self):
        """Test parsing different ID section formats."""
        loader = EntityDefinitionLoader()
        
        # Test with colon and space
        content1 = "# ID: TestEntity\n## Description\nTest description"
        definition1 = loader._parse_entity_definition(content1, Path("test.md"))
        assert definition1.id == "TestEntity"
        
        # Test with no space after colon
        content2 = "# ID:AnotherEntity\n## Description\nTest description"
        definition2 = loader._parse_entity_definition(content2, Path("test.md"))
        assert definition2.id == "AnotherEntity"
    
    def test_parse_relations_section(self):
        """Test parsing relations section."""
        loader = EntityDefinitionLoader()
        
        content = """# ID: TestEntity
## Relations
- Component : USES : USED_BY
- Technology : IMPLEMENTS : IMPLEMENTED_BY
- InvalidRelation : MISSING_LABEL
"""
        
        definition = loader._parse_entity_definition(content, Path("test.md"))
        
        assert len(definition.relations) == 2  # Invalid relation should be skipped
        
        relations_dict = {r.target_type: r for r in definition.relations}
        assert "Component" in relations_dict
        assert relations_dict["Component"].to_label == "USES"
        assert relations_dict["Component"].from_label == "USED_BY"
        
        assert "Technology" in relations_dict
        assert relations_dict["Technology"].to_label == "IMPLEMENTS"
        assert relations_dict["Technology"].from_label == "IMPLEMENTED_BY"
    
    def test_parse_examples_section(self):
        """Test parsing examples section."""
        loader = EntityDefinitionLoader()
        
        content = """# ID: TestEntity
## Examples

### First Example
This is the first example with
multiple lines of description.

### Second Example
This is the second example.

### Third Example
This is the third example
with even more
multiple lines.
"""
        
        definition = loader._parse_entity_definition(content, Path("test.md"))
        
        assert len(definition.examples) == 3
        
        examples_dict = {e.title: e for e in definition.examples}
        
        assert "First Example" in examples_dict
        first_desc = examples_dict["First Example"].description
        assert "first example with" in first_desc
        assert "multiple lines" in first_desc
        
        assert "Second Example" in examples_dict
        assert examples_dict["Second Example"].description == "This is the second example."
        
        assert "Third Example" in examples_dict
        third_desc = examples_dict["Third Example"].description
        assert "third example" in third_desc
        assert "even more" in third_desc
    
    def test_load_prompt_template(self, temp_entities_dir):
        """Test loading prompt template."""
        loader = EntityDefinitionLoader()
        template_path = temp_entities_dir / "prompt_template.md"
        
        template_content = loader.load_prompt_template(template_path)
        
        assert "You are an AI assistant" in template_content
        assert "{{ENTITY_TYPE_DEFINITIONS}}" in template_content
    
    def test_load_prompt_template_missing(self):
        """Test loading non-existent prompt template."""
        loader = EntityDefinitionLoader()
        
        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            loader.load_prompt_template(Path("/nonexistent/template.md"))
    
    def test_build_merged_prompt(self, temp_entities_dir):
        """Test building merged prompt with entity definitions."""
        loader = EntityDefinitionLoader()
        
        # Load template and definitions
        template_path = temp_entities_dir / "prompt_template.md"
        template = loader.load_prompt_template(template_path)
        definitions = loader.load_entity_definitions(temp_entities_dir)
        
        # Build merged prompt
        merged_prompt = loader.build_merged_prompt(template, definitions)
        
        # Verify placeholder was replaced
        assert "{{ENTITY_TYPE_DEFINITIONS}}" not in merged_prompt
        
        # Verify entity definitions were included
        assert "# ID: Product" in merged_prompt
        assert "# ID: MinimalEntity" in merged_prompt
        
        # Verify separator is used
        assert "---" in merged_prompt
        
        # Verify template content is preserved
        assert "You are an AI assistant" in merged_prompt
    
    def test_build_merged_prompt_no_definitions(self):
        """Test building merged prompt with no entity definitions."""
        loader = EntityDefinitionLoader()
        
        template = "Template with {{ENTITY_TYPE_DEFINITIONS}} placeholder"
        merged_prompt = loader.build_merged_prompt(template, [])
        
        # Placeholder should be replaced with empty string
        assert merged_prompt == "Template with  placeholder"
    
    def test_duplicate_entity_ids(self, temp_entities_dir):
        """Test handling duplicate entity IDs."""
        # Create another file with duplicate ID
        duplicate_content = """# ID: Product
## Name: Duplicate Product
## Description
This is a duplicate entity definition.
"""
        (temp_entities_dir / "duplicate.md").write_text(duplicate_content)
        
        loader = EntityDefinitionLoader()
        definitions = loader.load_entity_definitions(temp_entities_dir)
        
        # Should still load all files, but loader should track the duplication
        product_definitions = [d for d in definitions if d.id == "Product"]
        assert len(product_definitions) == 2  # Both files loaded
        
        # Check that loader tracked the duplicate in loaded_definitions
        assert "Product" in loader.loaded_definitions
        # The last one loaded should be the one in loaded_definitions
        assert loader.loaded_definitions["Product"].source_file in ["product.md", "duplicate.md"]