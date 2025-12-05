#!/usr/bin/env python3
"""Debug Bedrock API calls with detailed logging."""
import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from dotenv import load_dotenv
load_dotenv()

from kg_forge.llm.bedrock_client import BedrockClient

# Sample text
text = """
# Content Lake - Content Model

We want to store into the Content Lake:
* the content we receive via Ingestion (Blobs, Meta-data, ACLs)
* the Curated Content we extract
"""

print("="*60)
print("Testing Bedrock Client Directly")
print("="*60)

try:
    print("\n1. Initializing Bedrock client...")
    client = BedrockClient(
        model_name="anthropic.claude-3-haiku-20240307-v1:0",
        region="us-east-1",
        max_tokens=4000,
        temperature=0.1,
        timeout=30
    )
    print("[OK] Client initialized")
    
    print(f"\n2. Calling model with prompt ({len(text)} chars)...")
    result = client.call_model(text, doc_id="debug-test")
    
    print(f"\n3. Response received:")
    print(f"   Response keys: {result.keys()}")
    response_text = result.get('response_text', '')
    print(f"   Response text length: {len(response_text)}")
    print(f"   Response preview (first 500 chars): {response_text[:500]}")
    print(f"   Call duration: {result.get('call_duration', 0):.2f}s")
    
    if not response_text:
        print("\n[ERROR] EMPTY RESPONSE - Debugging...")
        print(f"   Full result keys: {result.keys()}")
        print(f"   Full result: {result}")
        
except Exception as e:
    print(f"\n[ERROR]: {e}")
    import traceback
    traceback.print_exc()
