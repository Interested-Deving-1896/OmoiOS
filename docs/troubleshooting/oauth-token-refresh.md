# OAuth Token Refresh Troubleshooting Guide

**Last Updated**: 2026-04-22  
**Applies To**: OmoiOS Authentication Service v1.0+  
**Related Services**: `AuthService`, JWT Token Management, Session Service

---

## Overview

This guide covers troubleshooting for OAuth token refresh failures, JWT authentication issues, and session management problems in OmoiOS. The authentication system uses JWT access tokens (15-minute expiry) and refresh tokens (7-day expiry), with session-based authentication as an alternative. Failures can occur during token generation, validation, refresh, or session cleanup.

---

## Common Error Scenarios

### 1. JWT Token Validation Failure

**Error Message**:
```
JWTError: Signature verification failed
verify_token returned None
Token type mismatch: expected 'access', got 'refresh'
```

**Root Causes**:
- `AUTH_JWT_SECRET_KEY` environment variable changed or missing
- Token expired (access tokens: 15 minutes, refresh tokens: 7 days)
- Wrong token type used (access vs refresh)
- Token tampered with or malformed
- Clock skew between servers

**Diagnosis Steps**:

1. Check JWT configuration:
```python
from omoi_os.config import get_app_settings

settings = get_app_settings()
print(f"JWT Algorithm: {settings.auth.jwt_algorithm}")
print(f"Access token expiry: {settings.auth.access_token_expire_minutes} minutes")
print(f"Refresh token expiry: {settings.auth.refresh_token_expire_days} days")
print(f"Secret key configured: {bool(settings.auth.jwt_secret_key)}")
```

2. Verify token structure:
```python
from jose import jwt

try:
    payload = jwt.decode(
        token, 
        "your-secret-key", 
        algorithms=["HS256"]
    )
    print(f"Token type: {payload.get('type')}")
    print(f"Expires: {payload.get('exp')}")
    print(f"Issued at: {payload.get('iat')}")
    print(f"Subject (user_id): {payload.get('sub')}")
    print(f"JTI: {payload.get('jti')}")
except jwt.JWTError as e:
    print(f"JWT validation failed: {e}")
```

3. Check token type:
```python
from omoi_os.services.auth_service import AuthService

# Verify access token
access_data = auth_service.verify_token(token, token_type="access")
print(f"Access token valid: {access_data is not None}")

# Verify refresh token
refresh_data = auth_service.verify_token(token, token_type="refresh")
print(f"Refresh token valid: {refresh_data is not None}")
```

**Fix**:
```python
# In backend/.env or .env.local
AUTH_JWT_SECRET_KEY=your-super-secret-key-min-32-chars-long
AUTH_JWT_ALGORITHM=HS256
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=15
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=7

# Generate a secure secret key:
# openssl rand -hex 32
```

Regenerate tokens after secret key rotation:
```python
# Force user to re-authenticate after secret key change
from omoi_os.models.auth import Session
from sqlalchemy import delete

# Invalidate all existing sessions
await db.execute(delete(Session))
await db.commit()
```

---

### 2. Refresh Token Reuse Detection

**Error Message**:
```
Refresh token already used
TokenData jti mismatch
Session invalidated
```

**Root Causes**:
- Refresh token used more than once (potential token theft)
- Session was explicitly invalidated
- User password was reset (invalidates all sessions)
- Token expired beyond refresh window

**Diagnosis Steps**:

1. Check session validity:
```python
from omoi_os.services.auth_service import AuthService

session = await auth_service.verify_session_token(session_token)
if session is None:
    print("Session invalid or expired")
    
# Check database directly
from omoi_os.models.auth import Session
from sqlalchemy import select

result = await db.execute(
    select(Session).where(
        Session.token_hash == token_hash,
        Session.expires_at > utc_now()
    )
)
session = result.scalar_one_or_none()
print(f"Session found: {session is not None}")
```

2. Verify token JTI (JWT ID) tracking:
```python
from omoi_os.services.auth_service import TokenData

token_data = auth_service.verify_token(refresh_token, token_type="refresh")
if token_data:
    print(f"Token JTI: {token_data.jti}")
    print(f"User ID: {token_data.user_id}")
    print(f"Issued at: {token_data.iat}")
```

3. Check for concurrent token usage:
```python
# Look for multiple requests with same refresh token
# This could indicate:
# - Race condition in client code
# - Token theft
# - Poor connection causing retries
```

**Fix**:
```python
# Implement proper refresh token rotation
async def refresh_access_token(refresh_token: str):
    # Verify the refresh token
    token_data = auth_service.verify_token(refresh_token, token_type="refresh")
    if not token_data:
        raise ValueError("Invalid refresh token")
    
    # Generate new token pair (rotation)
    new_access_token, access_jti = auth_service.create_access_token(
        user_id=token_data.user_id
    )
    new_refresh_token, refresh_jti = auth_service.create_refresh_token(
        user_id=token_data.user_id
    )
    
    # Invalidate old session
    await auth_service.invalidate_session_by_jti(token_data.jti)
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
```

---

### 3. Session Cleanup Failures

**Error Message**:
```
Session cleanup failed: database connection error
cleanup_expired_sessions error
Token hash mismatch
```

**Root Causes**:
- Database connection pool exhausted
- Session table locked during cleanup
- Clock skew causing premature/late expiration
- Session token hash calculation mismatch

**Diagnosis Steps**:

1. Check expired sessions:
```python
from omoi_os.models.auth import Session
from omoi_os.utils.datetime import utc_now
from sqlalchemy import select, func

result = await db.execute(
    select(func.count()).select_from(Session).where(
        Session.expires_at <= utc_now()
    )
)
expired_count = result.scalar()
print(f"Expired sessions: {expired_count}")
```

2. Verify token hash calculation:
```python
import hashlib
import secrets

# Session token generation
token = secrets.token_urlsafe(32)
token_hash = hashlib.sha256(token.encode()).hexdigest()

# Verify hash matches
print(f"Token prefix: {token[:10]}...")
print(f"Hash: {token_hash[:16]}...")
```

3. Check cleanup job execution:
```python
# Run manual cleanup
from omoi_os.services.auth_service import AuthService

auth_service = AuthService(db, jwt_secret="...")
try:
    await auth_service.cleanup_expired_sessions()
    print("Cleanup completed successfully")
except Exception as e:
    print(f"Cleanup failed: {e}")
```

**Fix**:
```python
# Implement robust session cleanup with batching
async def cleanup_expired_sessions_batched(batch_size: int = 1000):
    from sqlalchemy import delete
    from omoi_os.models.auth import Session
    from omoi_os.utils.datetime import utc_now
    
    while True:
        # Delete in batches to avoid long locks
        result = await db.execute(
            delete(Session).where(
                Session.expires_at <= utc_now()
            ).limit(batch_size)
        )
        await db.commit()
        
        if result.rowcount == 0:
            break
        
        print(f"Deleted {result.rowcount} expired sessions")
        
        # Brief pause between batches
        await asyncio.sleep(0.1)
```

---

### 4. API Key Authentication Failure

**Error Message**:
```
API key verification failed
Invalid API key format
API key expired
```

**Root Causes**:
- API key format doesn't match expected `sk_live_*` pattern
- Key has been revoked (is_active=False)
- Key has expired (expires_at passed)
- Key hash calculation mismatch
- User associated with key is inactive

**Diagnosis Steps**:

1. Verify API key format:
```python
import re

api_key = "sk_live_..."
pattern = r'^sk_live_[A-Za-z0-9_-]+$'
if not re.match(pattern, api_key):
    print("Invalid API key format")
else:
    prefix = api_key[:16]
    print(f"Key prefix: {prefix}")
```

2. Check key in database:
```python
import hashlib
from omoi_os.models.auth import APIKey
from sqlalchemy import select

hashed_key = hashlib.sha256(api_key.encode()).hexdigest()

result = await db.execute(
    select(APIKey).where(
        APIKey.hashed_key == hashed_key,
        APIKey.is_active.is_(True)
    ).where(
        (APIKey.expires_at.is_(None)) | (APIKey.expires_at > utc_now())
    )
)
api_key_record = result.scalar_one_or_none()

if api_key_record:
    print(f"Key name: {api_key_record.name}")
    print(f"Scopes: {api_key_record.scopes}")
    print(f"Last used: {api_key_record.last_used_at}")
else:
    print("Key not found or inactive/expired")
```

3. Verify user status:
```python
from omoi_os.models.user import User

if api_key_record:
    user_result = await db.execute(
        select(User).where(
            User.id == api_key_record.user_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None)
        )
    )
    user = user_result.scalar_one_or_none()
    print(f"User active: {user is not None}")
```

**Fix**:
```python
# Create new API key with proper validation
async def create_api_key_with_validation(
    user_id: UUID,
    name: str,
    scopes: list[str],
    expires_in_days: Optional[int] = 30
):
    # Validate scopes
    valid_scopes = {"read", "write", "admin", "billing:read", "billing:write"}
    invalid_scopes = set(scopes) - valid_scopes
    if invalid_scopes:
        raise ValueError(f"Invalid scopes: {invalid_scopes}")
    
    # Create key
    api_key, full_key = await auth_service.create_api_key(
        user_id=user_id,
        name=name,
        scopes=scopes,
        expires_in_days=expires_in_days
    )
    
    # Return full key (shown only once)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": full_key,  # Only time this is returned
        "prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "expires_at": api_key.expires_at
    }
```

---

### 5. Password Reset Token Issues

**Error Message**:
```
Password reset token invalid or expired
reset_password returned False
Token type mismatch: expected 'password_reset'
```

**Root Causes**:
- Token expired (1-hour validity window)
- Token already used
- Wrong token type
- User account deleted or deactivated
- Token not found in verification

**Diagnosis Steps**:

1. Verify token validity:
```python
from omoi_os.services.auth_service import AuthService

token_data = auth_service.verify_token(reset_token, token_type="password_reset")
if token_data:
    print(f"Token valid for user: {token_data.user_id}")
    print(f"Token JTI: {token_data.jti}")
else:
    print("Token invalid or expired")
```

2. Check token expiration:
```python
from jose import jwt
from datetime import datetime

try:
    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    exp_timestamp = payload.get("exp")
    exp_datetime = datetime.fromtimestamp(exp_timestamp)
    print(f"Token expires: {exp_datetime}")
    print(f"Current time: {datetime.utcnow()}")
    print(f"Time remaining: {exp_datetime - datetime.utcnow()}")
except jwt.ExpiredSignatureError:
    print("Token has expired")
except jwt.JWTError as e:
    print(f"Token validation error: {e}")
```

3. Verify user still exists:
```python
if token_data:
    user = await auth_service.get_user_by_id(token_data.user_id)
    if not user:
        print("User not found or inactive")
    elif not user.is_active:
        print("User account is deactivated")
```

**Fix**:
```python
# Implement secure password reset flow
async def reset_password_secure(token: str, new_password: str):
    # Validate password strength first
    is_valid, error_msg = auth_service.validate_password_strength(new_password)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Verify token
    token_data = auth_service.verify_token(token, token_type="password_reset")
    if not token_data:
        raise ValueError("Invalid or expired reset token")
    
    # Reset password
    success = await auth_service.reset_password(token, new_password)
    if success:
        # All sessions invalidated automatically by reset_password()
        return {"status": "success", "message": "Password reset successful"}
    else:
        raise ValueError("Password reset failed")
```

---

## Prevention

### 1. Token Rotation Strategy

Implement proper refresh token rotation:
```python
# Always rotate refresh tokens on use
# Store used JTIs in a short-term cache (Redis) to detect reuse
# If a refresh token is used twice, invalidate all user sessions
```

### 2. Secure Secret Management

```bash
# Never commit secrets to git
# backend/.env
AUTH_JWT_SECRET_KEY=openssl rand -hex 32

# Use different secrets per environment
# Development, staging, production should all have unique keys
```

### 3. Session Monitoring

```python
# Track session metrics
# - Active sessions per user
# - Session duration
# - Concurrent sessions
# - Failed authentication attempts
```

### 4. Clock Synchronization

```bash
# Ensure all servers use NTP
# Clock skew > 1 minute can cause JWT validation issues
ntpd -qg
```

### 5. Rate Limiting

```python
# Implement rate limiting on authentication endpoints
# - Login attempts: 5 per minute per IP
# - Password reset: 3 per hour per email
# - API key usage: configurable per key
```

---

## Related Documentation

- [Auth Service Implementation](../../backend/omoi_os/services/auth_service.py)
- [Authentication Routes](../../backend/omoi_os/api/routes/auth.py)
- [User Model](../../backend/omoi_os/models/user.py)
- [Auth Models](../../backend/omoi_os/models/auth.py)
- [CLAUDE.md - Auth Configuration](../../backend/CLAUDE.md)

---

## Quick Reference: Token Lifetimes

| Token Type | Default Lifetime | Use Case |
|------------|------------------|----------|
| Access Token | 15 minutes | API authentication |
| Refresh Token | 7 days | Obtain new access tokens |
| Session Token | 7 days | Session-based auth |
| Email Verification | 24 hours | Verify email address |
| Password Reset | 1 hour | Reset forgotten password |
| API Key | Configurable | Programmatic access |

---

## Quick Reference: Key Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `create_access_token()` | Generate JWT access token | `auth_service.py:110` |
| `create_refresh_token()` | Generate JWT refresh token | `auth_service.py:131` |
| `verify_token()` | Validate JWT token | `auth_service.py:152` |
| `verify_session_token()` | Validate session token | `auth_service.py:308` |
| `verify_api_key()` | Validate API key | `auth_service.py:398` |
| `create_reset_token()` | Generate password reset token | `auth_service.py:481` |
| `cleanup_expired_sessions()` | Remove stale sessions | `auth_service.py:338` |
| `validate_password_strength()` | Check password requirements | `auth_service.py:66` |
