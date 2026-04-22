# Embedding Indexing Failures Troubleshooting Guide

**Last Updated**: 2026-04-22  
**Applies To**: OmoiOS Embedding Service v1.0+  
**Related Services**: `EmbeddingService`, `MemoryService`, `SpecDedupService`

---

## Overview

This guide covers troubleshooting for embedding generation failures, vector dimension mismatches, and indexing issues in OmoiOS. The embedding service supports multiple providers (Fireworks AI, OpenAI, Local FastEmbed) for generating text embeddings used in semantic search, similarity matching, and deduplication. Failures can occur during model loading, API calls, dimension validation, or batch processing.

---

## Common Error Scenarios

### 1. Embedding Provider API Failure

**Error Message**:
```
Fireworks embedding failed after 3 attempts: RateLimitError
OpenAI embedding failed: AuthenticationError
Embedding dimension mismatch: got 768, expected 1536
```

**Root Causes**:
- Missing or invalid API key (`EMBEDDING_FIREWORKS_API_KEY` or `EMBEDDING_OPENAI_API_KEY`)
- Rate limiting from provider
- Network connectivity issues
- Model name incorrect or deprecated
- Dimension configuration mismatch

**Diagnosis Steps**:

1. Check embedding configuration:
```python
from omoi_os.config import get_app_settings

settings = get_app_settings()
print(f"Provider: {settings.embedding.provider}")
print(f"Model: {settings.embedding.model_name}")
print(f"Dimensions: {settings.embedding.dimensions}")
print(f"Fireworks key configured: {bool(settings.embedding.fireworks_api_key)}")
print(f"OpenAI key configured: {bool(settings.embedding.openai_api_key)}")
print(f"Lazy load: {settings.embedding.lazy_load}")
```

2. Test embedding generation:
```python
from omoi_os.services.embedding import EmbeddingService

# Test with explicit provider
service = EmbeddingService(provider="fireworks")
try:
    embedding = service.generate_embedding("Test text for embedding")
    print(f"Success! Dimensions: {len(embedding)}")
    print(f"Sample values: {embedding[:5]}")
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}")
```

3. Check API key validity:
```bash
# Test Fireworks API key
curl https://api.fireworks.ai/inference/v1/models \
  -H "Authorization: Bearer $EMBEDDING_FIREWORKS_API_KEY"

# Test OpenAI API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $EMBEDDING_OPENAI_API_KEY"
```

4. Verify model availability:
```python
# Check if model exists and supports requested dimensions
# Fireworks qwen3-embedding-8b supports variable dimensions
# OpenAI text-embedding-3-small supports up to 1536
```

**Fix**:
```python
# In backend/.env or .env.local
# For Fireworks (recommended - fast & affordable)
EMBEDDING_PROVIDER=fireworks
EMBEDDING_FIREWORKS_API_KEY=fw_...
EMBEDDING_MODEL_NAME=fireworks/qwen3-embedding-8b
EMBEDDING_DIMENSIONS=1536

# For OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_OPENAI_API_KEY=sk-...
EMBEDDING_MODEL_NAME=text-embedding-3-small

# For local (no API key needed)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-large
```

Handle API failures with fallback:
```python
async def generate_with_fallback(text: str):
    providers = ["fireworks", "openai", "local"]
    
    for provider in providers:
        try:
            service = EmbeddingService(provider=provider)
            embedding = service.generate_embedding(text)
            return embedding
        except Exception as e:
            logger.warning(f"{provider} failed: {e}")
            continue
    
    raise RuntimeError("All embedding providers failed")
```

---

### 2. Local Model Loading Failure

**Error Message**:
```
ImportError: fastembed not installed. Run: uv add fastembed
Failed to load FastEmbed model: intfloat/multilingual-e5-large
Local model loading timeout after 300 seconds
```

**Root Causes**:
- `fastembed` package not installed
- Model download failed or corrupted
- Insufficient disk space for model cache
- Network issues during model download
- Cache directory permissions issue

**Diagnosis Steps**:

1. Check fastembed installation:
```bash
uv pip show fastembed
# If not installed:
uv add fastembed
```

2. Verify model cache directory:
```python
import os
from omoi_os.config import get_app_settings

settings = get_app_settings()
cache_dir = settings.embedding.cache_dir
print(f"Cache dir: {cache_dir}")
print(f"Exists: {os.path.exists(cache_dir)}")
print(f"Writable: {os.access(cache_dir, os.W_OK)}")

# Check disk space
import shutil
total, used, free = shutil.disk_usage(cache_dir)
print(f"Free space: {free // (2**30)} GB")
```

3. Check model loading status:
```python
from omoi_os.services.embedding import (
    is_model_loaded, 
    wait_for_model_ready,
    get_local_model_instance
)

print(f"Model loaded: {is_model_loaded()}")

# Wait for model with timeout
ready = wait_for_model_ready(timeout=60)
print(f"Model ready: {ready}")

# Get instance if loaded
model = get_local_model_instance()
print(f"Model instance: {model}")
```

4. Preload model in background:
```python
from omoi_os.services.embedding import preload_embedding_model

# Start background loading
preload_embedding_model()

# Check loading status
import time
time.sleep(5)
print(f"Model loaded: {is_model_loaded()}")
```

**Fix**:
```python
# Install fastembed
# In backend/pyproject.toml or via command:
uv add fastembed

# Set proper cache directory
# In backend/.env:
EMBEDDING_CACHE_DIR=/path/to/large/disk/.cache/fastembed

# Or use home directory (default)
EMBEDDING_CACHE_DIR=~/.cache/fastembed

# Ensure directory exists and is writable
mkdir -p ~/.cache/fastembed
chmod 755 ~/.cache/fastembed

# Preload at startup to avoid first-request delay
# In api/main.py lifespan:
from omoi_os.services.embedding import preload_embedding_model
preload_embedding_model()
```

---

### 3. Dimension Mismatch Errors

**Error Message**:
```
Embedding dimension mismatch: got 1024, expected 1536
pgvector indexing issues: dimension mismatch
HNSW index creation failed: expected 1536 dimensions, got 1024
```

**Root Causes**:
- Local model (e5-large) outputs 1024 dimensions but pgvector expects 1536
- Configuration changed after embeddings stored
- Mixed providers used inconsistently
- Database column dimension mismatch

**Diagnosis Steps**:

1. Check actual vs expected dimensions:
```python
from omoi_os.services.embedding import EmbeddingService, DEFAULT_EMBEDDING_DIMENSIONS

service = EmbeddingService()
print(f"Expected dimensions: {service.dimensions}")
print(f"Default dimensions: {DEFAULT_EMBEDDING_DIMENSIONS}")

# Generate test embedding
test_emb = service.generate_embedding("Test")
print(f"Actual dimensions: {len(test_emb)}")
```

2. Check database column dimensions:
```sql
-- Check vector column dimensions in database
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM 
    information_schema.columns 
WHERE 
    data_type = 'vector';

-- Check specific table
SELECT pg_typeof(embedding_vector) FROM tasks LIMIT 1;
```

3. Verify padding is working:
```python
# Local embeddings should be padded to 1536
from omoi_os.services.embedding import EmbeddingService

local_service = EmbeddingService(provider="local")
embedding = local_service.generate_embedding("Test", is_query=True)

print(f"Embedding length: {len(embedding)}")
print(f"Non-zero elements: {sum(1 for x in embedding if x != 0)}")

# First 1024 should have values, rest should be 0
```

**Fix**:
```python
# The EmbeddingService automatically pads local embeddings
# See _generate_local_embedding() in embedding.py

# If you need to migrate existing embeddings:
async def reindex_with_correct_dimensions():
    from omoi_os.services.embedding import EmbeddingService
    
    service = EmbeddingService(provider="fireworks")  # Use API provider
    
    # Re-embed all documents
    for doc in documents:
        new_embedding = service.generate_embedding(doc.text)
        doc.embedding_vector = new_embedding
    
    session.commit()

# Or adjust database column:
# Migration to change vector dimensions
# ALTER TABLE tasks ALTER COLUMN embedding_vector TYPE vector(1536);
```

---

### 4. Batch Embedding Failures

**Error Message**:
```
Fireworks batch embedding failed: Request too large
OpenAI batch embedding failed: Rate limit exceeded
Batch size 1000 exceeds maximum of 100
```

**Root Causes**:
- Batch size too large for provider
- Rate limiting on batch endpoints
- Memory exhaustion processing large batches
- Timeout on long-running batch requests

**Diagnosis Steps**:

1. Test batch sizes:
```python
from omoi_os.services.embedding import EmbeddingService

service = EmbeddingService()
texts = [f"Text {i}" for i in range(100)]

try:
    embeddings = service.batch_generate_embeddings(texts)
    print(f"Success! Generated {len(embeddings)} embeddings")
except Exception as e:
    print(f"Failed: {e}")
    # Try smaller batch
    embeddings = []
    batch_size = 10
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embeddings = service.batch_generate_embeddings(batch)
        embeddings.extend(batch_embeddings)
```

2. Monitor rate limits:
```python
# Check rate limit headers (if available)
# Fireworks: X-RateLimit-Remaining
# OpenAI: x-ratelimit-remaining-requests
```

3. Check memory usage:
```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")

# Monitor during batch operation
```

**Fix**:
```python
async def batch_embed_with_chunking(
    texts: list[str],
    batch_size: int = 50
) -> list[list[float]]:
    """Process embeddings in smaller batches."""
    from omoi_os.services.embedding import EmbeddingService
    
    service = EmbeddingService()
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        
        # Add retry logic
        for attempt in range(3):
            try:
                batch_embeddings = service.batch_generate_embeddings(batch)
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        # Brief pause between batches
        if i + batch_size < len(texts):
            await asyncio.sleep(0.5)
    
    return all_embeddings
```

---

### 5. Similarity Search Returning Poor Results

**Error Message**:
```
Cosine similarity returning NaN values
Euclidean distance calculation error
Search results irrelevant to query
```

**Root Causes**:
- Zero vectors in database
- Normalization issues
- Wrong similarity metric used
- Query/document embedding mismatch (query vs passage prefix)
- Index not built or corrupted

**Diagnosis Steps**:

1. Check for zero vectors:
```python
import numpy as np

# Check if any embeddings are zero vectors
for emb in embeddings:
    if np.linalg.norm(emb) == 0:
        print("Found zero vector!")
```

2. Verify similarity calculation:
```python
from omoi_os.services.embedding import EmbeddingService

service = EmbeddingService()

# Test with known similar texts
text1 = "Machine learning is a subset of AI"
text2 = "AI includes machine learning techniques"
text3 = "The weather is nice today"

emb1 = service.generate_embedding(text1, is_query=False)
emb2 = service.generate_embedding(text2, is_query=False)
emb3 = service.generate_embedding(text3, is_query=False)

sim12 = service.cosine_similarity(emb1, emb2)
sim13 = service.cosine_similarity(emb1, emb3)

print(f"Similar texts similarity: {sim12:.4f}")  # Should be high
print(f"Different texts similarity: {sim13:.4f}")  # Should be low
```

3. Check local model prefixes:
```python
# For multilingual-e5-large, prefixes matter
# Query should use: "query: " + text
# Document should use: "passage: " + text

query_emb = service.generate_embedding("machine learning", is_query=True)
doc_emb = service.generate_embedding("machine learning guide", is_query=False)

sim = service.cosine_similarity(query_emb, doc_emb)
print(f"Query-doc similarity: {sim:.4f}")
```

**Fix**:
```python
# Ensure proper prefix usage for local models
def search_similar(
    query: str,
    documents: list[str],
    top_k: int = 5
) -> list[tuple[str, float]]:
    from omoi_os.services.embedding import EmbeddingService
    
    service = EmbeddingService()
    
    # Generate query embedding with is_query=True
    query_emb = service.generate_embedding(query, is_query=True)
    
    # Generate document embeddings with is_query=False
    doc_embs = service.batch_generate_embeddings(documents, is_query=False)
    
    # Calculate similarities
    similarities = []
    for doc, doc_emb in zip(documents, doc_embs):
        sim = service.cosine_similarity(query_emb, doc_emb)
        if not np.isnan(sim):
            similarities.append((doc, sim))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]
```

---

## Prevention

### 1. Provider Health Checks

```python
async def check_embedding_health():
    """Health check for embedding service."""
    from omoi_os.services.embedding import EmbeddingService
    
    try:
        service = EmbeddingService()
        embedding = service.generate_embedding("Health check")
        
        return {
            "status": "healthy",
            "provider": service.provider.value,
            "dimensions": len(embedding),
            "model": service.model_name
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

### 2. Dimension Validation

```python
# Always validate dimensions before storing
from omoi_os.services.embedding import DEFAULT_EMBEDDING_DIMENSIONS

def validate_embedding(embedding: list[float]) -> bool:
    if len(embedding) != DEFAULT_EMBEDDING_DIMENSIONS:
        logger.error(f"Dimension mismatch: {len(embedding)} != {DEFAULT_EMBEDDING_DIMENSIONS}")
        return False
    
    if all(x == 0 for x in embedding):
        logger.error("Zero vector detected")
        return False
    
    return True
```

### 3. Retry Configuration

```python
# The EmbeddingService has built-in retry logic
# MAX_RETRIES = 3
# RETRY_BASE_DELAY = 1.0 seconds
# RETRY_MAX_DELAY = 10.0 seconds

# For critical operations, add additional retries:
async def generate_with_extra_retry(text: str, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            return service.generate_embedding(text)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = min(2 ** attempt, 30)
            await asyncio.sleep(delay)
```

### 4. Monitoring

```python
# Track embedding metrics:
# - Generation latency
# - Provider success rates
# - Dimension mismatch frequency
# - Cache hit rates (for local model)
```

### 5. Fallback Strategy

```python
# Implement provider fallback
PROVIDER_PRIORITY = ["fireworks", "openai", "local"]

async def generate_embedding_robust(text: str):
    for provider in PROVIDER_PRIORITY:
        try:
            service = EmbeddingService(provider=provider)
            return service.generate_embedding(text)
        except Exception as e:
            logger.warning(f"{provider} failed: {e}")
    
    raise RuntimeError("All embedding providers failed")
```

---

## Related Documentation

- [Embedding Service](../../backend/omoi_os/services/embedding.py)
- [Memory Service](../../backend/omoi_os/services/memory.py)
- [Spec Deduplication](../../backend/omoi_os/services/spec_dedup.py)
- [Task Deduplication](../../backend/omoi_os/services/task_dedup.py)
- [Configuration](../../backend/config/base.yaml)

---

## Quick Reference: Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMBEDDING_PROVIDER` | `fireworks` | Provider: fireworks, openai, local |
| `EMBEDDING_FIREWORKS_API_KEY` | None | Fireworks AI API key |
| `EMBEDDING_OPENAI_API_KEY` | None | OpenAI API key |
| `EMBEDDING_MODEL_NAME` | Provider-specific | Override model name |
| `EMBEDDING_DIMENSIONS` | 1536 | Output dimensions |
| `EMBEDDING_CACHE_DIR` | `~/.cache/fastembed` | Local model cache |
| `EMBEDDING_LAZY_LOAD` | `true` | Defer model loading |
| `EMBEDDING_PRELOAD_IN_BACKGROUND` | `false` | Preload at startup |

---

## Quick Reference: Provider Details

| Provider | Model | Dimensions | API Key Required | Notes |
|----------|-------|------------|------------------|-------|
| Fireworks | qwen3-embedding-8b | 1536 (configurable) | Yes | Fast, affordable, recommended |
| OpenAI | text-embedding-3-small | 1536 | Yes | Production quality |
| Local | multilingual-e5-large | 1024 (padded to 1536) | No | No API calls, slower |

---

## Quick Reference: Key Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `generate_embedding()` | Single text embedding | `embedding.py:354` |
| `batch_generate_embeddings()` | Batch embedding | `embedding.py:426` |
| `cosine_similarity()` | Calculate similarity | `embedding.py:601` |
| `euclidean_distance()` | Calculate distance | `embedding.py:627` |
| `preload_embedding_model()` | Background preload | `embedding.py:100` |
| `wait_for_model_ready()` | Wait for local model | `embedding.py:129` |
| `_call_with_retry()` | Retry logic | `embedding.py:509` |
| `_validate_embedding()` | Dimension validation | `embedding.py:566` |
