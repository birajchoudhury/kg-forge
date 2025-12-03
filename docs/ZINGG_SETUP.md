# Zingg Real Implementation Setup

This document explains how to enable the real Zingg ML-based entity resolution in KG Forge.

## Overview

KG Forge includes both a fake implementation (for testing/development) and a real implementation of Zingg entity resolution:

- **Fake Implementation**: Always available, provides ML-inspired heuristics for testing
- **Real Implementation**: Requires Java/Spark setup, provides full ML-based clustering

## Current Status

The Zingg backend will automatically use:
- **Real implementation** when all dependencies are available
- **Fake implementation** as fallback when dependencies are missing

## Prerequisites for Real Zingg

### 1. Java Runtime Environment
```bash
# Install Java 8 or 11
sudo apt-get update
sudo apt-get install openjdk-11-jdk

# Verify installation
java -version
```

### 2. Python Dependencies
```bash
# Install the required packages
pip install zingg>=0.4.0 pyspark>=3.4.0 pandas>=1.5.0

# Or install from requirements.txt (Zingg line is now uncommented)
pip install -r requirements.txt
```

### 3. Spark Setup
Zingg uses Apache Spark for distributed processing. The implementation will automatically configure a local Spark session.

## Verification

To check if real Zingg is available:

```python
from kg_forge.dedup.zingg_backend import ZinggDedupBackend

backend = ZinggDedupBackend()
print(f"Real Zingg available: {backend.zingg_available}")
```

## Usage

### CLI Usage
```bash
# Zingg will automatically use real implementation when available
kg-forge ingest --source ./data --dedup-backend zingg

# Check logs to see which implementation is being used:
# "Real Zingg deduplication backend initialized" = Real implementation
# "Missing dependencies for real Zingg" = Fake implementation
```

### Programmatic Usage
```python
from kg_forge.dedup.zingg_backend import ZinggDedupBackend
from kg_forge.models.lexical import LexicalGraph

# Initialize backend
backend = ZinggDedupBackend(confidence_threshold=0.8)

# Process mentions - will use real Zingg if available
result = backend.deduplicate(lexical_graph, "namespace")

# Check which implementation was used
implementation = result.metadata["dedup_backend"]
print(f"Used: {implementation}")  # "zingg_real" or "zingg_fake"
```

## Real vs Fake Implementation Differences

| Feature | Fake Implementation | Real Implementation |
|---------|-------------------|-------------------|
| **Dependencies** | None (built-in) | Java + Spark + Zingg |
| **Performance** | Fast, lightweight | Full ML processing |
| **Accuracy** | Heuristic-based | ML model training |
| **Scalability** | Small datasets | Large-scale datasets |
| **Clustering** | Rule-based similarity | ML-based classification |
| **Training** | No model training | Trains on your data |

## Troubleshooting

### Common Issues

1. **Java not found**
   ```
   Error: JAVA_HOME not set
   Solution: export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
   ```

2. **Spark configuration errors**
   ```
   Error: Spark session creation failed
   Solution: Check Java version (8 or 11 recommended)
   ```

3. **Zingg import errors**
   ```
   Error: No module named 'zingg'
   Solution: pip install zingg>=0.4.0
   ```

### Debug Information

Enable debug logging to see detailed Zingg processing:

```python
import logging
logging.getLogger("kg_forge.dedup.zingg_backend").setLevel(logging.DEBUG)
```

## Performance Considerations

### Real Implementation
- **Startup**: Slower due to Spark initialization
- **Processing**: Optimized for larger datasets (>1000 mentions)  
- **Memory**: Higher memory usage due to Spark
- **Results**: More accurate clustering with ML models

### Fake Implementation  
- **Startup**: Instant
- **Processing**: Fast for smaller datasets (<1000 mentions)
- **Memory**: Minimal memory footprint
- **Results**: Good heuristic-based clustering

## Testing

Run the test suite to verify both implementations:

```bash
# Test fake implementation (always works)
python -m pytest tests/test_cli/test_zingg_integration.py -v

# Test real implementation (requires dependencies)
python -m pytest tests/test_cli/test_zingg_integration.py::TestZinggCLIIntegration::test_real_zingg_implementation -v
```

The real implementation test will be skipped if dependencies aren't available.

## Production Deployment

For production use with large datasets:

1. Install all dependencies (Java, Spark, Zingg)
2. Configure appropriate Spark settings for your cluster
3. Monitor memory usage and tune Spark configuration
4. Consider using distributed Spark cluster for very large datasets

The implementation will automatically scale from local testing (fake) to production ML processing (real) based on available dependencies.