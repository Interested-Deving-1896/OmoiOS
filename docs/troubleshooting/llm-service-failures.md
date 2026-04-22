# LLM Service Failures Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/services/llm_service.py` - Main LLM service with retry logic
- `backend/omoi_os/services/pydantic_ai_service.py` - PydanticAI integration
- `backend/omoi_os/config.py` - LLM settings and provider configuration
- `backend/config/base.yaml` - Default LLM parameters

**Related Documentation**:
- **Architecture: LLM Integration**
- [Architecture: LLM Service Internals](../architecture/18-llm-service-internals.md)
- **Structured Output Failures**

---

## Overview

OmoiOS uses a multi-provider LLM strategy managed by `LLMService`. It relies on **PydanticAI** for structured outputs and supports multiple providers including Fireworks AI, Anthropic, and OpenAI-compatible endpoints. The system implements automatic retry with exponential backoff, circuit breaker patterns, and provider failover.

### LLM Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Application   │────▶│   LLMService     │────▶│  PydanticAI     │
│   Code          │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        │              ┌─────────┴─────────┐
        │              │  Provider Pool:   │
        │              │  - Fireworks AI   │
        │              │  - Anthropic      │
        │              │  - OpenAI         │
        │              │  - Z.AI/GLM       │
        │              └───────────────────┘
        │
   ┌────┴────────────────────────────┐
   │  Retry Logic:                   │
   │  - Exponential backoff (1,2,4s)│
   │  - Jitter (0-50% of delay)     │
   │  - Max 3 HTTP retries           │
   │  - Max 5 output validation      │
   └─────────────────────────────────┘
```

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `omoi_os.exceptions.llm.StructuredOutputError: LLM returned invalid JSON` | Response doesn't match Pydantic schema | Check schema complexity, increase retries, or switch provider |
| `openai.RateLimitError: Error code: 429` | Rate limit exceeded (RPM/TPM) | Implement backoff, reduce parallel tasks, or upgrade tier |
| `omoi_os.exceptions.llm.ProviderUnavailableError: Provider 'fireworks' is down` | Upstream provider outage | Enable fallback providers, check status page |
| `omoi_os.exceptions.llm.ContextWindowExceededError: Prompt is too large` | Input exceeds model context limit | Truncate context, exclude large files, or use summarization |
| `openai.AuthenticationError: Error code: 401` | Invalid or expired API key | Verify `.env` configuration, regenerate key |
| `ValueError: fireworks_api_key or LLM api_key must be set` | Missing API credentials | Set `LLM_API_KEY` or `LLM_FIREWORKS_API_KEY` in `.env` |
| `pydantic_ai.exceptions.ModelHTTPError: 503` | Service temporarily unavailable | Wait and retry, or switch provider |
| `pydantic_ai.exceptions.OutputValidationError` | Structured output validation failed | Simplify schema, increase `output_retries` |
| `asyncio.TimeoutError` | Request exceeded timeout | Increase timeout, check provider status |
| `ConnectionError: Failed to establish connection` | Network connectivity issue | Check internet connection, verify base_url |

---

## Diagnostic Commands

### Check LLM Service Health

```bash
# Check LLM service health endpoint
curl -X GET http://localhost:18000/api/v1/health/llm

# Check environment variables
grep -E "API_KEY|LLM_PROVIDER|LLM_MODEL" backend/.env

# Test model connectivity (using internal CLI)
just test-llm-connectivity --model claude-3-5-sonnet

# Tail LLM specific logs
tail -f backend/logs/llm_service.log | grep -E "ERROR|WARNING|retry"

# Check PydanticAI service initialization
cd backend && uv run python -c "
from omoi_os.services.pydantic_ai_service import PydanticAIService
service = PydanticAIService()
print(f'Model: {service.model_string}')
print(f'Provider: {service.provider}')
print('Service initialized successfully')
"
```

### Provider Status Checks

```bash
# Check Fireworks AI status
curl -s https://status.fireworks.ai/api/v2/status.json | jq '.status.description'

# Check Anthropic status
curl -s https://status.anthropic.com/api/v2/status.json | jq '.status.description'

# Check OpenAI status
curl -s https://status.openai.com/api/v2/status.json | jq '.status.description'
```

### Token Usage Monitoring

```bash
# Check token consumption trends
tail -100 backend/logs/llm_usage.csv | awk -F',' '{sum+=$3} END {print "Total tokens:", sum}'

# Monitor current token usage
cd backend && uv run python -c "
from omoi_os.services.cost_tracking import get_cost_tracking_service
costs = get_cost_tracking_service()
print(f'Today: \${costs.get_daily_cost():.2f}')
print(f'Month: \${costs.get_monthly_cost():.2f}')
"
```

---

## Symptom 1: StructuredOutputError

**Error Message**: `omoi_os.exceptions.llm.StructuredOutputError: LLM returned invalid JSON for schema 'TaskPlan'. JSON: { ... }`

**Root Cause**: The LLM response did not match the expected Pydantic model.
1. The model (e.g., `gpt-4o-mini`) hallucinated fields not in the schema
2. The response was truncated due to `max_tokens` being too low
3. The provider (Fireworks AI) injected system messages into the response body
4. JSON parsing failed due to markdown code blocks or extra text

### Diagnostic Steps

1. **Check schema complexity**:
   ```python
   from pydantic import BaseModel
   
   class TaskPlan(BaseModel):
       # Check for deeply nested structures
       steps: list[dict]  # May be too complex
       # Prefer flat structures
       step_names: list[str]
       step_descriptions: list[str]
   ```

2. **Verify model capabilities**:
   ```bash
   # Check current model setting
grep "LLM_MODEL" backend/.env
   # Some models handle structured output better than others
   ```

3. **Review validation errors**:
   ```bash
   tail -f backend/logs/llm_service.log | grep -A5 "OutputValidationError"
   ```

### Fix Procedure

1. **Increase Output Retries**:
   ```python
   result = await llm.structured_output(
       prompt="Analyze this task...",
       output_type=TaskPlan,
       output_retries=5,  # Increase from default 3
       http_retries=3,
   )
   ```

2. **Simplify Schema**:
   ```python
   # Before (complex)
   class TaskPlan(BaseModel):
       steps: list[StepDetail]  # Nested model
       dependencies: dict[str, list[str]]  # Complex structure
   
   # After (simpler)
   class TaskPlan(BaseModel):
       step_names: list[str]
       step_descriptions: list[str]
       dependency_pairs: list[tuple[str, str]]  # Flattened
   ```

3. **Switch Provider**:
   ```bash
   # backend/.env
   LLM_MODEL=claude-sonnet-4-5-20250929
   ANTHROPIC_API_KEY=sk-ant-...
   ```

4. **Review Model Settings**:
   ```yaml
   # backend/config/base.yaml
   llm:
     model: accounts/fireworks/models/minimax-m2p1
     # Ensure model supports structured output
   ```

---

## Symptom 2: Rate Limit Error (429)

**Error Message**: `openai.RateLimitError: Error code: 429 - {'message': 'Rate limit reached for model...'}`

**Root Cause**: You have exceeded the requests-per-minute (RPM) or tokens-per-minute (TPM) limit for the provider.
1. The `OrchestratorWorker` is spawning too many parallel exploration tasks
2. Multiple developers are sharing the same API key
3. Fireworks AI "Tier 0" limits are very restrictive

### Diagnostic Steps

1. **Check current usage**:
   ```bash
   # Review LLM usage logs
   tail -100 backend/logs/llm_usage.csv
   
   # Check rate limit headers (if available)
   curl -I -H "Authorization: Bearer $LLM_API_KEY" \
     https://api.fireworks.ai/inference/v1/models
   ```

2. **Identify high-volume operations**:
   ```bash
   grep -r "structured_output\|llm.complete" backend/omoi_os --include="*.py" | wc -l
   ```

3. **Check parallel task count**:
   ```yaml
   # backend/config/base.yaml
   orchestrator:
     max_parallel_tasks: 5  # Check current setting
   ```

### Fix Procedure

1. **Implement Backoff** (already in `LLMService`):
   The service automatically retries with exponential backoff:
   ```python
   # Exponential backoff with jitter: 1s, 2s, 4s + random jitter
   base_delay = 2**attempt
   jitter = random.uniform(0, 0.5 * base_delay)
   delay = base_delay + jitter
   ```

2. **Reduce Parallel Task Count**:
   ```yaml
   # backend/config/base.yaml
   orchestrator:
     max_parallel_tasks: 3  # Reduce from 5
   ```

3. **Token Budgeting**:
   ```python
   # Use smaller models for simple tasks
   from omoi_os.services.llm_service import get_llm_service
   
   llm = get_llm_service()
   # For simple classification, use cheaper model
   result = await llm.complete(
       "Classify this as bug/feature/docs",
       model="accounts/fireworks/models/gpt-oss-20b"  # Cheaper
   )
   ```

4. **Upgrade Provider Tier**:
   - Fireworks AI: Visit dashboard to upgrade from Tier 0
   - Anthropic: Check usage limits in console
   - OpenAI: Upgrade billing tier

5. **Implement Request Batching**:
   ```python
   # Batch multiple requests together
   async def batch_process(items: list[str]):
       semaphore = asyncio.Semaphore(3)  # Limit concurrency
       
       async def process_one(item: str):
           async with semaphore:
               return await llm.complete(item)
       
       return await asyncio.gather(*[process_one(i) for i in items])
   ```

---

## Symptom 3: Provider Unavailable (503)

**Error Message**: `omoi_os.exceptions.llm.ProviderUnavailableError: Provider 'fireworks' is currently down or overloaded.`

**Root Cause**: The upstream provider is experiencing an outage or high load.

### Diagnostic Steps

1. **Check provider status page**:
   ```bash
   # Fireworks AI
   curl -s https://status.fireworks.ai/api/v2/status.json | jq
   
   # Anthropic
   curl -s https://status.anthropic.com/api/v2/status.json | jq
   ```

2. **Test alternative providers**:
   ```bash
   # Test with different provider
cd backend && uv run python -c "
from omoi_os.services.llm_service import LLMService
from omoi_os.config import LLMSettings

# Try Anthropic
settings = LLMSettings(model='claude-sonnet-4-5-20250929', api_key='sk-ant-...')
llm = LLMService(settings=settings)
result = await llm.complete('Hello')
print('Anthropic works:', result[:50])
"
   ```

3. **Check error frequency**:
   ```bash
   tail -1000 backend/logs/api.log | grep -c "ProviderUnavailableError"
   ```

### Fix Procedure

1. **Enable Automatic Failover**:
   Configure fallback providers in settings:
   ```python
   # backend/omoi_os/services/llm_factory.py
   def create_llm_service(primary_provider: str = "fireworks"):
       providers = {
           "fireworks": FireworksProvider(),
           "anthropic": AnthropicProvider(),
           "openai": OpenAIProvider(),
       }
       
       for name in [primary_provider] + FALLBACK_PROVIDERS:
           try:
               return providers[name]
           except ProviderUnavailableError:
               logger.warning(f"Provider {name} unavailable, trying next")
               continue
   ```

2. **Manual Provider Switch**:
   ```bash
   # backend/.env
   LLM_MODEL=claude-sonnet-4-5-20250929
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Restart Worker**:
   ```bash
   just worker-restart
   ```

4. **Implement Circuit Breaker**:
   ```python
   from omoi_os.utils.resilience import circuit_breaker
   
   @circuit_breaker(failure_threshold=5, recovery_timeout=60)
   async def call_llm_with_fallback(prompt: str):
       return await llm.complete(prompt)
   ```

---

## Symptom 4: Context Window Exceeded

**Error Message**: `omoi_os.exceptions.llm.ContextWindowExceededError: Prompt is too large (215,432 tokens). Max for 'claude-3-5-sonnet' is 200,000.`

**Root Cause**: The context being sent to the agent is too large.
1. The `DiscoveryService` is including too many large files in the context
2. A very deep directory structure was globbed into the prompt
3. Infinite recursion in `get_context()` logic

### Diagnostic Steps

1. **Measure prompt size**:
   ```python
   from omoi_os.utils.token_counter import count_tokens
   
   token_count = count_tokens(prompt)
   print(f"Prompt size: {token_count} tokens")
   ```

2. **Identify large context sources**:
   ```bash
   # Check context gathering in logs
   tail -f backend/logs/api.log | grep -i "context\|tokens"
   ```

3. **Review exclude patterns**:
   ```yaml
   # backend/config/base.yaml
   context:
     exclude_patterns:
       - "node_modules/**"
       - ".git/**"
       - "dist/**"
       - "*.min.js"
   ```

### Fix Procedure

1. **Truncate Context**:
   ```python
   from omoi_os.utils.token_counter import truncate_to_limit
   
   # Truncate to 80% of model limit to leave room for response
   safe_limit = int(model_context_limit * 0.8)
   truncated_prompt = truncate_to_limit(prompt, safe_limit)
   ```

2. **Exclude Large Directories**:
   ```yaml
   # backend/config/base.yaml
   context:
     exclude_patterns:
       - "node_modules/**"
       - ".git/**"
       - "dist/**"
       - "build/**"
       - "*.min.js"
       - "*.map"
       - "vendor/**"
   ```

3. **Summarize Large Files**:
   ```python
   # Instead of full file content, use summary
   async def get_file_summary(file_path: str, max_lines: int = 50) -> str:
       with open(file_path) as f:
           lines = f.readlines()[:max_lines]
       return ''.join(lines) + "\n... (truncated)"
   ```

4. **Use Tiered Context**:
   ```python
   # Send essential context first, expand if needed
   essential_context = get_essential_files()
   if count_tokens(essential_context) < limit:
       expanded_context = add_secondary_files(essential_context)
   ```

---

## Symptom 5: Authentication Error (401)

**Error Message**: `openai.AuthenticationError: Error code: 401 - {'message': 'Incorrect API key provided...'}`

**Root Cause**: The API key is invalid, expired, or not configured.

### Diagnostic Steps

1. **Verify API key in environment**:
   ```bash
   grep -E "LLM_API_KEY|ANTHROPIC_API_KEY|FIREWORKS_API_KEY" backend/.env
   ```

2. **Check for hidden characters**:
   ```bash
   # Check for trailing spaces or newlines
   cat -A backend/.env | grep API_KEY
   ```

3. **Test key directly**:
   ```bash
   # Test Fireworks key
   curl -H "Authorization: Bearer $LLM_FIREWORKS_API_KEY" \
     https://api.fireworks.ai/inference/v1/models
   
   # Test Anthropic key
   curl -H "x-api-key: $ANTHROPIC_API_KEY" \
     https://api.anthropic.com/v1/models
   ```

### Fix Procedure

1. **Verify .env Configuration**:
   ```bash
   # backend/.env
   LLM_API_KEY=fw_xxxxxxxxxxxxxxxxxxxxxxxx
   # or
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
   ```

2. **Regenerate Key**:
   - Fireworks AI: https://app.fireworks.ai/account/api-keys
   - Anthropic: https://console.anthropic.com/settings/keys
   - OpenAI: https://platform.openai.com/api-keys

3. **Check Key Permissions**:
   Ensure the key has access to the model you're trying to use:
   ```bash
   # List available models
   curl -H "Authorization: Bearer $LLM_API_KEY" \
     https://api.fireworks.ai/inference/v1/models | jq '.data[].id'
   ```

4. **Restart Services**:
   ```bash
   just dev-backend-restart
   ```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|---------------|
| `LLM_API_KEY` | Yes* | `null` | Primary LLM API key |
| `LLM_FIREWORKS_API_KEY` | Yes* | `null` | Fireworks AI specific key |
| `ANTHROPIC_API_KEY` | Yes* | `null` | Anthropic Claude API key |
| `LLM_MODEL` | No | `openhands/claude-sonnet-4-5-20250929` | Model identifier |
| `LLM_BASE_URL` | No | `https://api.z.ai/api/coding/paas/v4` | Custom endpoint URL |
| `LLM_MODE` | No | `live` | Operation mode: live, record, replay, null |

*At least one API key must be set

### YAML Configuration (base.yaml)

```yaml
llm:
  model: openai/glm-4.7
  api_key: null  # Set LLM_API_KEY in .env
  base_url: https://api.z.ai/api/coding/paas/v4
  fireworks_api_key: null  # Set LLM_FIREWORKS_API_KEY in .env
  mode: "live"  # live | record | replay | null
  recording_dir: ".llm-recordings"
  replay_strict: false
```

### Model-Specific Settings

| Provider | Default Model | Context Length | Max Output |
|----------|---------------|----------------|------------|
| Fireworks | `accounts/fireworks/models/minimax-m2p1` | 128K | 8K |
| Anthropic | `claude-sonnet-4-5-20250929` | 200K | 64K |
| OpenAI | `gpt-4o` | 128K | 4K |
| Z.AI | `glm-4.7` | 128K | 8K |

---

## Step-by-Step Recovery Procedures

### Procedure 1: Switch LLM Provider

1. **Check current provider**:
   ```bash
   grep "LLM_MODEL\|LLM_API_KEY" backend/.env
   ```

2. **Update to alternative provider**:
   ```bash
   # Switch to Anthropic
   echo 'LLM_MODEL=claude-sonnet-4-5-20250929' >> backend/.env
   echo 'ANTHROPIC_API_KEY=sk-ant-xxxxx' >> backend/.env
   ```

3. **Restart and test**:
   ```bash
   just dev-backend-restart
   curl -X POST http://localhost:18000/api/v1/health/llm
   ```

### Procedure 2: Fix Structured Output Issues

1. **Enable debug logging**:
   ```python
   # In your code
   import logging
   logging.getLogger('pydantic_ai').setLevel(logging.DEBUG)
   ```

2. **Test with simpler schema**:
   ```python
   from pydantic import BaseModel
   
   class SimpleOutput(BaseModel):
       result: str
       confidence: float
   
   result = await llm.structured_output(
       prompt="Test prompt",
       output_type=SimpleOutput,
       output_retries=5
   )
   ```

3. **Fallback to text completion**:
   ```python
   # If structured output keeps failing
   text_result = await llm.complete(prompt)
   # Parse manually as last resort
   ```

### Procedure 3: Handle Rate Limiting

1. **Check current limits**:
   ```bash
   # Review recent usage
   tail -500 backend/logs/llm_usage.csv | awk -F',' '{print $1, $3}' | tail -20
   ```

2. **Implement request queuing**:
   ```python
   import asyncio
   from asyncio import Semaphore
   
   llm_semaphore = Semaphore(3)  # Max 3 concurrent requests
   
   async def rate_limited_llm_call(prompt: str):
       async with llm_semaphore:
           return await llm.complete(prompt)
   ```

3. **Enable request caching**:
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=100)
   async def cached_llm_call(prompt_hash: str):
       return await llm.complete(prompt)
   ```

---

## Prevention Strategies

- **Prompt Caching**: Use Anthropic's prompt caching for large system prompts to reduce latency and cost.

- **Monitoring**: Check `backend/logs/llm_usage.csv` for token consumption trends and set up alerts for:
  - Unusual spike in token usage (>200% of average)
  - High error rate (>5% of requests failing)
  - Rate limit approaching (>80% of quota)

- **Unit Testing**: Run `just test-llm-mocks` to ensure schema validation logic works without hitting real APIs.

- **Validation**: Always use `llm.structured_output()` which includes internal retry loops for malformed JSON.

- **Cost Tracking**: Monitor LLM costs via the cost tracking service:
  ```python
  from omoi_os.services.cost_tracking import get_cost_tracking_service
  costs = get_cost_tracking_service()
  daily = costs.get_daily_cost()
  if daily > 100:  # Alert if > $100/day
      alerting.send_alert(f"High LLM cost: ${daily}")
  ```

- **Provider Diversity**: Configure multiple providers for automatic failover during outages.

---

## Troubleshooting Flowchart

```
LLM Call Fails?
├── Check API Key → Verify in .env, test with curl
├── Check Rate Limit → Review logs, implement backoff
├── Check Provider Status → Visit status page
├── Check Context Size → Count tokens, truncate if needed
├── Check Schema Validity → Simplify Pydantic model
└── Check Network → Test connectivity to provider

Structured Output Fails?
├── Increase output_retries → From 3 to 5
├── Simplify Schema → Remove nested models
├── Switch Provider → Try Anthropic or OpenAI
└── Use Text Completion → Parse manually as fallback

High Latency?
├── Check Token Count → Reduce prompt size
├── Enable Prompt Caching → For repeated system prompts
├── Use Faster Model → Switch to Haiku or GPT-3.5
└── Check Provider Load → Switch to less loaded provider
```

---

## Common Diagnostic Commands

```bash
# Test LLM connectivity
curl -X POST http://localhost:18000/api/v1/health/llm

# Check LLM logs
tail -f backend/logs/llm_service.log | grep -E "ERROR|WARNING"

# Monitor token usage
watch -n 5 'tail -1 backend/logs/llm_usage.csv'

# Test specific provider
cd backend && uv run python -c "
from omoi_os.services.llm_service import get_llm_service
llm = get_llm_service()
result = await llm.complete('Say hello')
print(result)
"

# Check rate limit status (Fireworks)
curl -H "Authorization: Bearer $LLM_FIREWORKS_API_KEY" \
  https://api.fireworks.ai/inference/v1/models

# Count recent errors
grep -c "RateLimitError\|AuthenticationError" backend/logs/api.log
```

---

*End of LLM Service Failures Troubleshooting Guide*

*This guide covers multi-provider LLM integration, structured outputs, rate limiting, and error recovery in OmoiOS.*
