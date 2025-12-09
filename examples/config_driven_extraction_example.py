"""
Example: Config-Driven Entity Extraction

This example demonstrates the complete workflow of config-driven entity extraction:
1. Define ontology with core and occurrence entities
2. Convert ontology to entity config JSON
3. Extract entities from a document using an LLM

Note: This is a demonstration. To actually run this, you need to:
- Implement a real LLMClient (e.g., BedrockLLMClient)
- Provide real document text
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_forge.ontology.schema import (
    OntologySchema, EntityType, RelationType, Property, Dependency
)

# Direct import to avoid glirel dependency issue
import importlib.util
spec = importlib.util.spec_from_file_location(
    "config_driven",
    project_root / "kg_forge" / "extraction" / "config_driven.py"
)
config_driven = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_driven)

LLMClient = config_driven.LLMClient
extract_entities_from_document = config_driven.extract_entities_from_document


# Step 1: Define Ontology
# =======================

print("=" * 80)
print("STEP 1: Define Ontology with Core and Occurrence Entities")
print("=" * 80)

# Core Entity: Contract
contract = EntityType(
    name="Contract",
    iri="http://example.org/contracts#Contract",
    description="A legal contract or agreement",
    kind="core",  # This is a persistent entity
    properties=[
        Property(
            name="title",
            description="The title or name of the contract",
            datatype="string",
            required=True
        ),
        Property(
            name="contractValue",
            description="The monetary value of the contract",
            datatype="number",
            required=False
        ),
        Property(
            name="effectiveDate",
            description="The date the contract becomes effective",
            datatype="date",
            required=False
        )
    ],
    examples=["Employment Agreement", "Service Contract", "Lease Agreement"]
)

# Core Entity: Party
party = EntityType(
    name="Party",
    iri="http://example.org/contracts#Party",
    description="A party involved in a contract",
    kind="core",  # This is a persistent entity
    properties=[
        Property(
            name="name",
            description="The name of the party",
            datatype="string",
            required=True
        ),
        Property(
            name="role",
            description="The role of the party (e.g., employer, employee, vendor)",
            datatype="string",
            required=False
        ),
        Property(
            name="jurisdiction",
            description="The legal jurisdiction of the party",
            datatype="string",
            required=False
        )
    ],
    examples=["ACME Corporation", "John Smith", "State of California"]
)

# Occurrence Entity: ContractExecution
execution = EntityType(
    name="ContractExecution",
    iri="http://example.org/contracts#ContractExecution",
    description="An execution or signing event of a contract",
    kind="occurrence",  # This is an event/temporal entity
    properties=[
        Property(
            name="executionDate",
            description="The date the contract was executed/signed",
            datatype="date",
            required=True
        ),
        Property(
            name="location",
            description="The location where the contract was executed",
            datatype="string",
            required=False
        ),
        Property(
            name="method",
            description="The method of execution (e.g., physical signature, electronic)",
            datatype="string",
            required=False
        )
    ],
    depends_on=[
        Dependency(
            role="contract",
            entity="Contract",
            cardinality="1"  # Must link to exactly one Contract
        ),
        Dependency(
            role="signatories",
            entity="Party",
            cardinality="1..*"  # Must link to one or more Parties
        )
    ],
    examples=["Signing ceremony on 2024-01-15", "Electronic signature via DocuSign"]
)

# Occurrence Entity: ContractAmendment
amendment = EntityType(
    name="ContractAmendment",
    iri="http://example.org/contracts#ContractAmendment",
    description="An amendment or modification to an existing contract",
    kind="occurrence",  # This is an event/temporal entity
    properties=[
        Property(
            name="amendmentDate",
            description="The date of the amendment",
            datatype="date",
            required=True
        ),
        Property(
            name="description",
            description="Description of what was amended",
            datatype="string",
            required=True
        )
    ],
    depends_on=[
        Dependency(
            role="originalContract",
            entity="Contract",
            cardinality="1"  # Must link to the contract being amended
        )
    ],
    examples=["Amendment to extend contract term", "Salary adjustment amendment"]
)

# Relation: Contract INVOLVES Party
involves = RelationType(
    name="INVOLVES",
    iri="http://example.org/contracts#involves",
    head_types=["Contract"],
    tail_types=["Party"],
    description="A contract involves one or more parties"
)

# Create the ontology schema
schema = OntologySchema(
    entities={
        "Contract": contract,
        "Party": party,
        "ContractExecution": execution,
        "ContractAmendment": amendment
    },
    relations={
        "INVOLVES": involves
    },
    metadata={
        "name": "Contracts Ontology",
        "version": "1.0",
        "description": "Ontology for modeling contracts, parties, and contract events"
    }
)

print(f"✓ Created ontology with {len(schema.entities)} entity types")
print(f"  - Core entities: {[name for name, e in schema.entities.items() if e.kind == 'core']}")
print(f"  - Occurrence entities: {[name for name, e in schema.entities.items() if e.kind == 'occurrence']}")


# Step 2: Convert to Entity Config JSON
# ======================================

print("\n" + "=" * 80)
print("STEP 2: Convert Ontology to Entity Config JSON")
print("=" * 80)

entity_config = schema.to_entity_config()

print("\nEntity Config JSON:")
print(json.dumps(entity_config, indent=2))


# Step 3: Mock LLM Client (for demonstration)
# ============================================

print("\n" + "=" * 80)
print("STEP 3: Define LLM Client")
print("=" * 80)

class MockLLMClient(LLMClient):
    """
    Mock LLM client that returns a pre-defined response.
    
    In production, replace this with a real implementation:
    - BedrockLLMClient for AWS Bedrock
    - OpenAILLMClient for OpenAI API
    - LocalLLMClient for local models (Ollama, etc.)
    """
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # This is a mock response - a real LLM would analyze the document
        mock_response = {
            "core_entities": [
                {
                    "entity_id": "contract-1",
                    "type": "Contract",
                    "properties": {
                        "title": "Employment Agreement",
                        "contractValue": 120000,
                        "effectiveDate": "2024-01-01"
                    },
                    "span": {"page": 1, "start_char": 0, "end_char": 45}
                },
                {
                    "entity_id": "party-1",
                    "type": "Party",
                    "properties": {
                        "name": "TechCorp Inc.",
                        "role": "employer",
                        "jurisdiction": "Delaware"
                    },
                    "span": {"page": 1, "start_char": 100, "end_char": 115}
                },
                {
                    "entity_id": "party-2",
                    "type": "Party",
                    "properties": {
                        "name": "Jane Developer",
                        "role": "employee",
                        "jurisdiction": "California"
                    },
                    "span": {"page": 1, "start_char": 150, "end_char": 165}
                }
            ],
            "occurrence_entities": [
                {
                    "entity_id": "execution-1",
                    "type": "ContractExecution",
                    "properties": {
                        "executionDate": "2024-01-15",
                        "location": "San Francisco, CA",
                        "method": "electronic"
                    },
                    "links": {
                        "contract": "contract-1",
                        "signatories": "party-1"  # In real extraction, would link to both parties
                    },
                    "span": {"page": 2, "start_char": 500, "end_char": 580}
                }
            ]
        }
        return json.dumps(mock_response)

llm_client = MockLLMClient()
print("✓ Created Mock LLM Client (replace with real implementation in production)")


# Step 4: Extract Entities from Document
# =======================================

print("\n" + "=" * 80)
print("STEP 4: Extract Entities from Document")
print("=" * 80)

sample_document = """
EMPLOYMENT AGREEMENT

This Employment Agreement ("Agreement") is entered into as of January 1, 2024,
between TechCorp Inc., a Delaware corporation ("Employer"), and Jane Developer,
an individual residing in California ("Employee").

1. POSITION AND DUTIES
Employee shall serve as Senior Software Engineer and shall report to the CTO.

2. COMPENSATION
Employer shall pay Employee an annual base salary of $120,000, payable in
accordance with Employer's standard payroll practices.

3. TERM
This Agreement shall commence on the Effective Date and shall continue until
terminated by either party.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date
first written above.

EXECUTED on January 15, 2024, in San Francisco, California.

[Electronic Signatures]
TechCorp Inc.
By: /s/ John CEO
    John CEO, Chief Executive Officer

Jane Developer
/s/ Jane Developer
"""

result = extract_entities_from_document(
    entity_config=entity_config,
    doc_id="CONTRACT-2024-001",
    doc_title="TechCorp Employment Agreement - Jane Developer",
    doc_text=sample_document,
    llm_client=llm_client
)

print("\n✓ Extraction Complete!")
print(f"\nExtracted {len(result['core_entities'])} core entities:")
for entity in result['core_entities']:
    print(f"  - {entity['type']}: {entity['properties'].get('name') or entity['properties'].get('title')}")

print(f"\nExtracted {len(result['occurrence_entities'])} occurrence entities:")
for entity in result['occurrence_entities']:
    print(f"  - {entity['type']}: {entity['properties']}")
    print(f"    Links to: {entity['links']}")


# Step 5: Analyze Results
# =======================

print("\n" + "=" * 80)
print("STEP 5: Analyze Extraction Results")
print("=" * 80)

print("\nFull Extraction Result:")
print(json.dumps(result, indent=2))

# Verify dependency constraints
print("\n\nDependency Validation:")
for occ_entity in result['occurrence_entities']:
    entity_type = occ_entity['type']
    entity_def = entity_config['entities'][entity_type]
    
    print(f"\n  {entity_type} ({occ_entity['entity_id']}):")
    for dep in entity_def['depends_on']:
        role = dep['role']
        required_type = dep['entity']
        cardinality = dep['cardinality']
        
        if role in occ_entity['links']:
            linked_id = occ_entity['links'][role]
            linked_entity = next(
                (e for e in result['core_entities'] if e['entity_id'] == linked_id),
                None
            )
            if linked_entity:
                print(f"    ✓ {role} -> {linked_id} ({linked_entity['type']}) [cardinality: {cardinality}]")
            else:
                print(f"    ✗ {role} -> {linked_id} NOT FOUND!")
        else:
            is_required = cardinality in ["1", "1..*"]
            if is_required:
                print(f"    ✗ {role} MISSING (required, cardinality: {cardinality})")
            else:
                print(f"    - {role} not provided (optional, cardinality: {cardinality})")

print("\n" + "=" * 80)
print("Example Complete!")
print("=" * 80)
print("\nTo use this in production:")
print("1. Implement a real LLMClient (e.g., BedrockLLMClient)")
print("2. Load real documents from your data sources")
print("3. Store extracted entities in Neo4j using the graph module")
print("4. Build queries and visualizations using the extracted knowledge graph")
