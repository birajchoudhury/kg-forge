# Real Zingg Implementation Setup Guide

## Why Use Real Zingg?

The real Zingg implementation provides:
- **Production-grade ML clustering** using trained models
- **Scalable processing** with Apache Spark
- **Advanced entity resolution** with active learning
- **Better accuracy** for large datasets with complex duplicates

## Current Status

- ✅ **Code Implementation**: Real Zingg pipeline is fully implemented
- ❌ **Dependencies**: Required libraries (zingg, pyspark) not installed
- ✅ **Fallback**: System automatically uses fake implementation when dependencies missing

## Installation Requirements

### 1. Java 11+ Setup
```powershell
# Install Java 11 or higher
# Download from https://adoptium.net/
# Ensure JAVA_HOME is set
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-11.0.20.8-hotspot"
```

### 2. Install Python Dependencies
```powershell
pip install pyspark>=3.4.0
pip install zingg>=0.4.0
```

### 3. Verify Installation
```python
python -c "
import pyspark
import zingg.client
print('✅ Real Zingg dependencies available')
"
```

## Why We're Not Installing by Default

1. **Complex Setup**: Java, Spark, and Zingg configuration is complex
2. **Development Focus**: Fake implementation provides sufficient functionality for development
3. **Environment Agnostic**: Not all development environments need full Spark setup
4. **Testing Efficiency**: Fake implementation is faster for unit testing

## When to Use Real vs Fake

### Use Fake Implementation (Current):
- ✅ Development and testing
- ✅ Small datasets (< 10K mentions)  
- ✅ Quick prototyping
- ✅ CI/CD environments

### Use Real Implementation:
- 🎯 Production deployments
- 🎯 Large datasets (> 10K mentions)
- 🎯 Complex entity resolution scenarios
- 🎯 When ML-based accuracy is critical

## How the Hybrid System Works

```python
# The system automatically detects capabilities
from kg_forge.dedup.zingg_backend import ZinggDedupBackend

backend = ZinggDedupBackend()
# backend.zingg_available == True  -> Uses real Zingg
# backend.zingg_available == False -> Uses fake implementation

# Same API, different implementation
result = backend.deduplicate(lexical_graph, namespace)
# Metadata indicates which implementation was used:
# result.metadata["dedup_backend"] == "zingg_real" | "zingg_fake"
```

## Current Recommendation

**Continue using fake implementation** because:
- All functionality is available through the fake implementation
- Same API and test coverage
- No complex environment setup required
- Provides realistic ML-inspired clustering behavior

**Upgrade to real implementation when:**
- Moving to production with large datasets
- Need maximum accuracy for entity resolution
- Have dedicated Spark infrastructure
- Can invest in proper Java/Spark environment setup