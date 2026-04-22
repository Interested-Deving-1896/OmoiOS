# GitHub Webhook Errors Troubleshooting Guide

**Last Updated**: 2026-04-22  
**Applies To**: OmoiOS v1.9+  
**Related Components**: `github_integration.py`, `github_api.py`, `github_routes.py`

---

## Overview

OmoiOS integrates with GitHub via webhooks to receive real-time events for pushes, pull requests, and issues. This guide covers common webhook-related errors, their diagnosis, and resolution steps. The webhook system is critical for keeping project state synchronized with GitHub repositories.

The webhook handler (`handle_github_webhook` in `github_routes.py`) processes events and delegates to `GitHubIntegrationService` for business logic. Failures can occur at multiple layers: signature validation, payload parsing, API communication, or database operations.

---

## Common Error Scenarios

### 1. Webhook Signature Validation Failures

**Error Message**: `Invalid webhook signature` (HTTP 401)

**Symptoms**:
- GitHub webhook deliveries show "400 Bad Request" or "401 Unauthorized"
- Webhook secret mismatch errors in logs
- Events not triggering expected actions in OmoiOS

**Root Causes**:
1. **Missing or incorrect webhook secret**: The `github_webhook_secret` field in the Project model is empty or doesn't match GitHub's configured secret
2. **Signature format mismatch**: GitHub sends `sha256=<hash>` but code expects different format
3. **Payload body mismatch**: Raw body used for signature calculation differs from parsed body
4. **Secret rotation**: Secret was rotated in GitHub but not updated in OmoiOS

**Diagnosis Steps**:

```bash
# 1. Check if project has webhook secret configured
curl -H "Authorization: Bearer $TOKEN" \
  https://api.omoios.dev/api/v1/github/connected | jq '.[] | {owner, repo, webhook_configured}'

# 2. Verify GitHub webhook configuration
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/hooks | jq '.[] | {id, config: .config.secret}'

# 3. Check recent webhook deliveries in GitHub
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/hooks/$HOOK_ID/deliveries | jq '.[] | {id, status, delivered_at}'
```

**Code Reference** (`github_integration.py:59-91`):
```python
def verify_webhook_signature(
    self, payload_body: bytes, signature: str, secret: str
) -> bool:
    if not signature or not secret:
        return False
    if not signature.startswith("sha256="):
        return False
    expected_signature = signature[7:]  # Remove "sha256=" prefix
    mac = hmac.new(
        secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    calculated_signature = mac.hexdigest()
    return hmac.compare_digest(expected_signature, calculated_signature)
```

**Fixes**:

1. **Update webhook secret**:
```python
# In database or via API
project.github_webhook_secret = "new-secret-from-github"
project.github_connected = True
session.commit()
```

2. **Regenerate webhook URL with new secret**:
```bash
# Disconnect and reconnect repository
curl -X POST https://api.omoios.dev/api/v1/github/connect \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"owner": "myorg", "repo": "myrepo", "webhook_secret": "new-secret"}'
```

3. **Verify signature calculation** (debug script):
```python
import hmac
import hashlib

payload = b'{"action":"opened","number":123,...}'
secret = "your-webhook-secret"
signature = "sha256=abc123..."

expected = signature[7:]
mac = hmac.new(secret.encode(), payload, hashlib.sha256)
calculated = mac.hexdigest()
print(f"Match: {hmac.compare_digest(expected, calculated)}")
```

---

### 2. Payload Parsing Errors

**Error Message**: `Invalid repository data` or `Missing PR number`

**Symptoms**:
- Webhook returns 200 but no action taken
- Logs show "Invalid repository data" or missing field errors
- Events acknowledged but not processed

**Root Causes**:
1. **Unexpected event structure**: GitHub changed payload format
2. **Missing required fields**: PR number, repository owner, or repo name not present
3. **Malformed JSON**: Encoding issues or truncated payloads
4. **Wrong event type**: Handler expects `pull_request` but receives `pull_request_review`

**Diagnosis Steps**:

```bash
# 1. Capture actual webhook payload
curl -X POST https://api.omoios.dev/api/v1/webhooks/github \
  -H "X-GitHub-Event: pull_request" \
  -H "Content-Type: application/json" \
  -d @test_payload.json

# 2. Check payload structure
echo '{"repository":{"owner":{"login":"test"},"name":"repo"},"pull_request":{"number":1}}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('owner:', d.get('repository',{}).get('owner',{}).get('login'))"
```

**Code Reference** (`github_integration.py:158-176`):
```python
async def _handle_push_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login")
    repo = repository.get("name")
    commits = payload.get("commits", [])
    
    if not owner or not repo:
        return {"success": False, "message": "Invalid repository data"}
```

**Fixes**:

1. **Add defensive parsing**:
```python
# Wrap field access with defaults
owner = payload.get("repository", {}).get("owner", {}).get("login") if payload.get("repository") else None
repo = payload.get("repository", {}).get("name") if payload.get("repository") else None
pr_number = payload.get("pull_request", {}).get("number") if payload.get("pull_request") else None
```

2. **Log full payload for debugging**:
```python
logger.debug(f"Webhook payload: {json.dumps(payload, indent=2)}")
```

3. **Validate before processing**:
```python
required_fields = ["repository.owner.login", "repository.name"]
missing = [f for f in required_fields if not get_nested(payload, f)]
if missing:
    return {"success": False, "message": f"Missing fields: {missing}"}
```

---

### 3. Rate Limiting from GitHub API

**Error Message**: `GitHub API authentication failed: 403` or `API rate limit exceeded`

**Symptoms**:
- Operations fail intermittently
- Error messages mention "rate limit" or "403 Forbidden"
- Works for some users/repos but not others

**Root Causes**:
1. **Unauthenticated requests**: No GitHub token configured (60 requests/hour limit)
2. **Token expiration**: OAuth token expired or revoked
3. **Shared token exhaustion**: Multiple services using same token
4. **Abusive pattern**: Too many requests in short timeframe

**Diagnosis Steps**:

```bash
# 1. Check rate limit status
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit | jq '.rate | {limit, remaining, reset}'

# 2. Check token scopes
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user | jq '.login'

# 3. Review OmoiOS logs for rate limit headers
# Look for: X-RateLimit-Remaining, X-RateLimit-Reset
```

**Code Reference** (`github_api.py:289-307`):
```python
if response.status_code != 200:
    error_detail = response.text[:500] if response.text else "No error details"
    logger.error(
        f"GitHub API error for user {user_id}: "
        f"status={response.status_code}, "
        f"response={error_detail}"
    )
    if response.status_code in (401, 403):
        raise ValueError(
            f"GitHub API authentication failed: {response.status_code}. "
            f"Token may be invalid or expired. Please reconnect your GitHub account."
        )
```

**Fixes**:

1. **Check and refresh token**:
```python
# Verify token is valid
user_attrs = user.attributes or {}
token = user_attrs.get("github_access_token")
if not token:
    logger.warning(f"No GitHub token found for user {user_id}")
    return []
```

2. **Implement exponential backoff**:
```python
import time
import random

def github_api_call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
            else:
                raise
```

3. **Use conditional requests** (ETag caching):
```python
# Store ETag from previous request
headers["If-None-Match"] = stored_etag
response = client.get(url, headers=headers)
if response.status_code == 304:
    # Not modified, use cached data
    return cached_data
```

---

### 4. Repository Access Errors

**Error Message**: `Project not found for owner/repo` or `Repository not found`

**Symptoms**:
- Webhook events received but no project linked
- "Project not found" errors in logs
- Commits/PRs not associated with tickets

**Root Causes**:
1. **Repository not connected**: Project exists but `github_connected=False`
2. **Owner/repo mismatch**: Case sensitivity or renamed repositories
3. **Deleted repository**: GitHub repo deleted but webhook still active
4. **Transferred repository**: Repo moved to different owner

**Diagnosis Steps**:

```bash
# 1. List connected repositories
curl -H "Authorization: Bearer $TOKEN" \
  https://api.omoios.dev/api/v1/github/connected | jq '.[] | {owner, repo, connected}'

# 2. Check specific project
curl -H "Authorization: Bearer $TOKEN" \
  https://api.omoios.dev/api/v1/projects/$PROJECT_ID | jq '{github_owner, github_repo, github_connected}'

# 3. Verify repository exists on GitHub
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO | jq '{id, full_name, private}'
```

**Code Reference** (`github_integration.py:169-183`):
```python
with self.db.get_session() as session:
    project = (
        session.query(Project)
        .filter(
            Project.github_owner == owner,
            Project.github_repo == repo,
        )
        .first()
    )
    
    if not project:
        return {
            "success": False,
            "message": f"Project not found for {owner}/{repo}",
        }
```

**Fixes**:

1. **Reconnect repository**:
```bash
curl -X POST https://api.omoios.dev/api/v1/github/connect \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"project_id": "proj-123", "owner": "new-owner", "repo": "new-repo"}'
```

2. **Update project GitHub info**:
```python
project.github_owner = "new-owner"
project.github_repo = "new-repo-name"
project.github_connected = True
session.commit()
```

3. **Case-insensitive matching** (if needed):
```python
project = (
    session.query(Project)
    .filter(
        func.lower(Project.github_owner) == owner.lower(),
        func.lower(Project.github_repo) == repo.lower(),
    )
    .first()
)
```

---

### 5. Branch Protection Conflicts

**Error Message**: `Required status check failed` or `Branch protection rules`

**Symptoms**:
- PR creation succeeds but merge fails
- "405 PR not mergeable" errors
- CI checks passing but merge blocked

**Root Causes**:
1. **Required reviews**: Branch requires approving reviews
2. **Status checks**: Required CI checks not passing
3. **Stale reviews**: Code changed after approval
4. **Admin bypass disabled**: Even admins can't force merge

**Diagnosis Steps**:

```bash
# 1. Check branch protection rules
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/branches/main/protection | jq '.required_status_checks'

# 2. Check PR mergeable status
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER | jq '{mergeable, mergeable_state}'

# 3. List required status checks
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/branches/main/protection/required_status_checks | jq '.contexts'
```

**Code Reference** (`github_api.py:853-924`):
```python
async def merge_pull_request(...) -> MergeResult:
    response = await client.put(
        f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/merge",
        headers=self._headers(token),
        json=data,
    )
    
    if response.status_code == 405:
        return MergeResult(
            success=False,
            message="PR not mergeable",
            error=result.get("message", "Merge conflicts or other issue"),
        )
```

**Fixes**:

1. **Check mergeable status before attempting**:
```python
pr = await self.get_pull_request(user_id, owner, repo, pr_number)
if pr.mergeable is False:
    return MergeResult(
        success=False,
        message="PR has merge conflicts",
        error="Resolve conflicts before merging"
    )
```

2. **Use appropriate merge method**:
```python
# Try squash merge first, fallback to regular merge
try:
    result = await self.merge_pull_request(..., merge_method="squash")
except:
    result = await self.merge_pull_request(..., merge_method="merge")
```

3. **Wait for status checks**:
```python
import asyncio

async def wait_for_checks(user_id, owner, repo, pr_number, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        pr = await self.get_pull_request(user_id, owner, repo, pr_number)
        if pr.mergeable and pr.mergeable_state == "clean":
            return True
        await asyncio.sleep(10)
    return False
```

---

### 6. PR Creation Failures

**Error Message**: `Failed to create pull request` or `Validation Failed`

**Symptoms**:
- Agent completes work but no PR created
- "422 Validation Failed" errors
- PR created but with wrong base/head

**Root Causes**:
1. **Branch doesn't exist**: Head branch not pushed to remote
2. **Base branch protected**: Can't create PR against protected branch
3. **Duplicate PR**: PR already exists for same branches
4. **Invalid title/body**: Empty title or too long body

**Diagnosis Steps**:

```bash
# 1. Check if branch exists
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/branches/feature-branch | jq '{name, commit: .commit.sha}'

# 2. List existing PRs between branches
curl -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/pulls?state=all&head=$OWNER:feature-branch&base=main" | jq '.[] | {number, state, title}'

# 3. Check recent PR creation attempts
# Review OmoiOS logs for full error response
```

**Code Reference** (`github_api.py:653-699`):
```python
async def create_pull_request(...) -> PullRequestCreateResult:
    data = {
        "title": title,
        "head": head,
        "base": base,
        "draft": draft,
    }
    if body:
        data["body"] = body
    
    response = await client.post(
        f"{self.BASE_URL}/repos/{owner}/{repo}/pulls",
        headers=self._headers(token),
        json=data,
    )
    
    if response.status_code == 201:
        return PullRequestCreateResult(success=True, ...)
    else:
        return PullRequestCreateResult(
            success=False,
            error=result.get("message", "Failed to create pull request"),
        )
```

**Fixes**:

1. **Ensure branch is pushed**:
```bash
# In agent workflow
git push -u origin feature-branch || echo "Push failed"
```

2. **Check for existing PR**:
```python
existing_prs = await self.list_pull_requests(user_id, owner, repo, state="open")
for pr in existing_prs:
    if pr.head_branch == head and pr.base_branch == base:
        return PullRequestCreateResult(
            success=True,
            number=pr.number,
            html_url=pr.html_url,
            message="PR already exists"
        )
```

3. **Validate PR data**:
```python
if not title or len(title.strip()) == 0:
    title = f"Auto-generated PR for {head}"
if body and len(body) > 65536:
    body = body[:65530] + "..."
```

---

## Prevention

### 1. Webhook Secret Management

- Store secrets in environment variables, not code
- Rotate secrets quarterly
- Use different secrets for production vs staging
- Monitor failed signature validations in logs

### 2. API Rate Limit Monitoring

```python
# Add to monitoring
async def check_github_rate_limit(user_id):
    token = self._get_user_token_by_id(user_id)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/rate_limit",
            headers=self._headers(token)
        )
        data = response.json()
        remaining = data['rate']['remaining']
        if remaining < 100:
            logger.warning(f"GitHub rate limit low for user {user_id}: {remaining} remaining")
```

### 3. Defensive Programming

- Always validate payload structure before processing
- Use type hints and Pydantic models for validation
- Log full error context including request IDs
- Implement circuit breakers for external API calls

### 4. Testing

```python
# Unit test for webhook signature
def test_verify_webhook_signature():
    service = GitHubIntegrationService(...)
    payload = b'{"action":"opened"}'
    secret = "test-secret"
    
    # Calculate expected signature
    import hmac, hashlib
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    signature = f"sha256={mac.hexdigest()}"
    
    assert service.verify_webhook_signature(payload, signature, secret) is True
    assert service.verify_webhook_signature(payload, signature, "wrong-secret") is False
```

---

## Related Documentation

- [GitHub Integration Architecture](../../docs/architecture/10-github-integration.md)
- [API Route Catalog](../../docs/architecture/13-api-route-catalog.md)
- [Contributing Guide](../../CONTRIBUTING.md)
- [GitHub Webhooks Documentation](https://docs.github.com/en/webhooks)
