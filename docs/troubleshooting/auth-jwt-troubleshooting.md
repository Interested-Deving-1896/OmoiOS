# Auth and JWT Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/services/auth_service.py` - Core authentication logic
- `backend/omoi_os/api/routes/auth.py` - API endpoints
- `backend/omoi_os/config.py` - JWT settings and configuration
- `backend/omoi_os/services/token_blacklist.py` - Token revocation

**Related Documentation**:
- **Architecture: Auth & Security**
- [Backend CLAUDE.md](../../backend/CLAUDE.md)
- [OAuth Redirect URI Fix](oauth_redirect_uri_fix.md)

---

## Overview

OmoiOS uses a dual-token JWT authentication system with access tokens (15-minute expiry) and refresh tokens (7-day expiry). The system implements HS256 signing, token rotation, blacklisting for security, and rate limiting to prevent brute force attacks.

### Authentication Flow

```
User Login → Access Token (15min) + Refresh Token (7d) → API Requests
     ↓
Token Expires → Refresh Endpoint → New Token Pair (rotation)
     ↓
Logout → Blacklist Tokens → Force Re-authentication
```

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `jose.exceptions.JWTError: Signature verification failed` | JWT secret mismatch or tampered token | Verify `AUTH_JWT_SECRET_KEY` consistency across services |
| `401 Unauthorized` with `{"detail": "Not authenticated"}` | Missing or malformed Authorization header | Check `Bearer <token>` format and header presence |
| `401 Unauthorized` with `{"detail": "Token expired"}` | Access token past `exp` claim | Use refresh token to obtain new access token |
| `429 Too Many Requests` | Rate limit exceeded (login: 5/min, register: 3/hour) | Wait for window to reset or adjust rate limits |
| `sqlalchemy.exc.DetachedInstanceError` | Session closed before lazy-loaded attributes accessed | Use eager loading (`selectinload`) or refresh session |
| `403 Forbidden` with `{"detail": "Insufficient permissions"}` | Missing required scope/role | Update user roles or adjust endpoint requirements |
| `ValueError: Password must be at least 8 characters` | Password validation failed | Ensure password meets complexity requirements |
| `ValueError: Email already registered` | Duplicate email on registration | Use unique email or implement email verification |
| `RuntimeError: Token blacklist service not initialized` | Redis unavailable for token blacklisting | Check Redis connection or disable blacklisting in dev |
| `401 Unauthorized` with `{"detail": "Invalid refresh token"}` | Refresh token expired or blacklisted | Re-authenticate with credentials |

---

## Diagnostic Commands

### Verify JWT Configuration

```bash
# Check if secret key is set and length
grep "AUTH_JWT_SECRET_KEY" backend/.env
python -c "import os; key = os.getenv('AUTH_JWT_SECRET_KEY', ''); print(f'Key length: {len(key)} chars')"

# Verify JWT token structure (requires jwt-cli)
jwt decode <token> --header
jwt decode <token> --payload

# Check token expiry
echo "<token>" | cut -d. -f2 | base64 -d 2>/dev/null | jq '.exp'

# Test auth endpoint health
curl -X GET http://localhost:18000/api/v1/health
```

### Database Session Diagnostics

```bash
# Check for detached instance errors in logs
tail -f backend/logs/api.log | grep -i "detached\|DetachedInstanceError"

# Verify user session queries
cd backend && uv run python -c "
from omoi_os.config import get_app_settings
from omoi_os.services.database import DatabaseService
settings = get_app_settings()
db = DatabaseService(connection_string=settings.database.url)
print('Database connection successful')
"
```

### Token Blacklist Diagnostics

```bash
# Check Redis connection for token blacklist
redis-cli -h localhost -p 16379 ping

# View blacklist entries
redis-cli -h localhost -p 16379 keys "token:blacklist:*"

# Check auth event log
redis-cli -h localhost -p 16379 lrange "auth:events" 0 10
```

---

## Symptom 1: Invalid Signature Error

**Error Message**: `jose.exceptions.JWTError: Signature verification failed.`

**Root Cause**: The secret key used to verify the token does not match the key used to sign it, or the algorithm specified in the header is being tampered with.

### Diagnostic Steps

1. **Verify Secret Key Source**:
   Ensure the `AUTH_JWT_SECRET_KEY` in `backend/.env` matches the one on the signing server.
   ```bash
   # Check if secret key is set
   grep "AUTH_JWT_SECRET_KEY" backend/.env
   ```

2. **Check Algorithm Consistency**:
   OmoiOS uses `HS256`. Verify the token header.
   ```bash
   # Inspect token header (requires jwt-cli or similar)
   jwt decode <token> --header
   ```

3. **Validate Secret Key Length**:
   Production requires minimum 32 characters.
   ```python
   from omoi_os.config import get_app_settings
   settings = get_app_settings()
   secret = settings.auth.jwt_secret_key
   print(f"Secret length: {len(secret)} chars")
   assert len(secret) >= 32, "Secret too short for production!"
   ```

### Fix Procedure

- **Step 1**: If the secret key is missing, generate a new 32-byte hex string:
  ```bash
  openssl rand -hex 32
  ```
- **Step 2**: Update `backend/.env` and restart the backend service (`just dev-backend`).
- **Step 3**: Ensure all services sharing the JWT (e.g., sidecars, external workers) use the identical key.
- **Step 4**: In production, the system validates secret strength at startup. See `AuthSettings._reject_weak_jwt_secret_in_production()` in `config.py`.

---

## Symptom 2: Expired Token (TokenExpiredError)

**Error Message**: `{"detail": "Could not validate credentials", "reason": "Token expired"}`

**Root Cause**: The current system time is beyond the `exp` claim in the JWT payload.

### Diagnostic Steps

1. **Check System Time**:
   Ensure the server and client clocks are synchronized.
   ```bash
   date -u
   ```

2. **Inspect Token Payload**:
   Check the `iat` (issued at) and `exp` (expires at) fields.
   ```bash
   jwt decode <token> --payload
   ```

3. **Verify Token Type**:
   Access tokens expire in 15 minutes, refresh tokens in 7 days.
   ```bash
   echo "<token>" | cut -d. -f2 | base64 -d 2>/dev/null | jq '{type: .type, exp: .exp, iat: .iat}'
   ```

### Fix Procedure

- **Increase Expiry Duration**:
  Modify `access_token_expire_minutes` in `backend/config/base.yaml` if tokens are expiring too quickly for your workflow. Default is `15`.
  ```yaml
  auth:
    access_token_expire_minutes: 30  # Increase from 15
  ```

- **Implement Refresh Token Flow**:
  The `/api/v1/auth/refresh` endpoint handles token rotation:
  ```bash
  curl -X POST http://localhost:18000/api/v1/auth/refresh \
    -H "Content-Type: application/json" \
    -d '{"refresh_token": "<refresh_token>"}'
  ```

- **Frontend Auto-Refresh**:
  The frontend should intercept 401 responses and automatically refresh tokens before retrying requests.

---

## Symptom 3: Missing or Malformed Authorization Header

**Error Message**: `401 Unauthorized` with `{"detail": "Not authenticated"}`

**Root Cause**: The `Authorization` header is missing, or does not follow the `Bearer <token>` format.

### Diagnostic Steps

1. **Check Request Headers**:
   Verify the client is sending the header correctly.
   ```bash
   curl -v -H "Authorization: Bearer <token>" http://localhost:18000/api/v1/users/me
   ```

2. **Verify Middleware Placement**:
   Ensure auth dependencies are correctly registered in route definitions.

3. **Check Cookie Auth**:
   OmoiOS also supports httpOnly cookies. Verify cookie settings:
   ```bash
   curl -v --cookie "access_token=<token>" http://localhost:18000/api/v1/users/me
   ```

### Fix Procedure

- **Frontend Client**:
  Update `frontend/lib/api/client.ts` to ensure the token is retrieved from `localStorage` or `cookies` and appended to the header.
  ```typescript
  const token = localStorage.getItem('access_token');
  headers['Authorization'] = `Bearer ${token}`;
  ```

- **Backend Route**:
  Ensure the route uses `Depends(get_current_user)` to trigger the auth logic.
  ```python
  @router.get("/protected")
  async def protected_route(current_user: User = Depends(get_current_user)):
      return {"message": f"Hello {current_user.email}"}
  ```

---

## Symptom 4: DetachedInstanceError in Auth Logic

**Error Message**: `sqlalchemy.exc.DetachedInstanceError: Instance <User at 0x...> is not bound to a Session`

**Root Cause**: The database session was closed before the user object's lazy-loaded attributes (like roles or permissions) were accessed.

### Diagnostic Steps

1. **Trace SQLAlchemy Session**:
   Check `backend/omoi_os/api/dependencies.py` for session lifecycle.

2. **Verify Eager Loading**:
   Identify if roles are being lazy-loaded inside the auth check.
   ```python
   from sqlalchemy.orm import selectinload
   stmt = select(User).options(selectinload(User.organizations))
   ```

3. **Check Session Scope**:
   Ensure user objects are accessed within the request-bound session context.

### Fix Procedure

- **Option 1: Eager Load**:
  Modify queries to use `selectinload` or `joinedload` for related attributes.
  ```python
  from sqlalchemy.orm import selectinload
  result = await db.execute(
      select(User)
      .where(User.id == user_id)
      .options(selectinload(User.organizations))
  )
  ```

- **Option 2: Extract ID Early**:
  Extract user ID before session closes, then use it for subsequent operations.
  ```python
  user_id = user.id  # Extract before session closes
  # ... session closes ...
  # Use user_id instead of user.id later
  ```

- **Option 3: Session Scope**:
  Ensure the user object remains within the scope of the request-bound database session.

---

## Symptom 5: Scoped Permission Denied

**Error Message**: `403 Forbidden` with `{"detail": "Insufficient permissions"}`

**Root Cause**: The user is authenticated but lacks the specific scope required for the endpoint.

### Diagnostic Steps

1. **Inspect Token Scopes**:
   Check the `scopes` array in the JWT payload.
   ```json
   {
     "sub": "user_id",
     "scopes": ["read:projects", "write:sandboxes"]
   }
   ```

2. **Verify Endpoint Requirements**:
   Check the `Security` dependency in the FastAPI route definition.

3. **Check User Roles**:
   Verify user's role assignments in the database.
   ```sql
   SELECT u.email, u.role, u.is_super_admin 
   FROM users u 
   WHERE u.id = '<user_id>';
   ```

### Fix Procedure

- **Update User Roles**:
  Modify the user's role in the database to include the missing permission.
  ```python
  await db.execute(
      update(User)
      .where(User.id == user_id)
      .values(role="admin")
  )
  ```

- **Adjust Policy**:
  If the scope requirement is too strict, update the route dependency.
  ```python
  @router.get("/admin-only")
  async def admin_route(
      current_user: User = Depends(get_current_active_user),
  ):
      if not current_user.is_super_admin:
          raise HTTPException(403, "Admin access required")
  ```

---

## Symptom 6: Rate Limiting (429 Too Many Requests)

**Error Message**: `429 Too Many Requests` with account lockout message

**Root Cause**: Too many failed login attempts or exceeded endpoint rate limits.

### Diagnostic Steps

1. **Check Rate Limit Configuration**:
   ```yaml
   # backend/config/base.yaml
   auth:
     max_login_attempts: 5
     login_attempt_window_minutes: 15
   ```

2. **View Auth Events in Redis**:
   ```bash
   redis-cli -h localhost -p 16379 lrange "auth:events" 0 20
   ```

3. **Check Failed Login Count**:
   ```bash
   redis-cli -h localhost -p 16379 get "auth:failed:<email>"
   ```

### Fix Procedure

- **Clear Failed Attempts**:
  ```bash
  redis-cli -h localhost -p 16379 del "auth:failed:<email>"
  ```

- **Adjust Rate Limits** (development only):
  ```yaml
  auth:
    max_login_attempts: 10  # Increase for testing
    login_attempt_window_minutes: 5
  ```

- **Wait for Lockout to Expire**:
  Default lockout window is 15 minutes.

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|---------------|
| `AUTH_JWT_SECRET_KEY` | Yes | `dev-secret-key-change-in-production` | JWT signing secret (min 32 chars in prod) |
| `AUTH_JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Access token lifetime |
| `AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime |
| `AUTH_MAX_LOGIN_ATTEMPTS` | No | `5` | Failed attempts before lockout |
| `AUTH_SESSION_EXPIRE_DAYS` | No | `30` | Session cookie lifetime |

### YAML Configuration (base.yaml)

```yaml
auth:
  jwt_secret_key: dev-secret-key-change-in-production
  jwt_algorithm: HS256
  access_token_expire_minutes: 15
  refresh_token_expire_days: 7
  min_password_length: 8
  require_uppercase: true
  require_lowercase: true
  require_digit: true
  require_special_char: true
  max_login_attempts: 5
  login_attempt_window_minutes: 15
  session_expire_days: 30
```

### Password Requirements

The system enforces password complexity via `AuthService.validate_password_strength()`:

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (`!@#$%^&*(),.?":{}|<>\[\]\~\`_+\-=/;'\'`)
- Not in common password list (password, 12345678, qwerty123, etc.)

---

## Step-by-Step Recovery Procedures

### Procedure 1: Reset JWT Secret in Production

1. **Generate new secret**:
   ```bash
   openssl rand -hex 32
   ```

2. **Update environment**:
   ```bash
   # backend/.env.local (production)
   AUTH_JWT_SECRET_KEY=<new-secret>
   ```

3. **Restart services**:
   ```bash
   just dev-backend-restart
   ```

4. **Invalidate all existing tokens** (force re-login):
   ```bash
   redis-cli -h localhost -p 16379 FLUSHDB  # Clear all sessions
   ```

### Procedure 2: Fix DetachedInstanceError

1. **Identify the failing query**:
   ```python
   # Before (problematic)
   user = await db.execute(select(User).where(User.id == user_id))
   return user.scalar_one()  # Session closes here
   # Later: user.organizations  # ERROR: DetachedInstanceError
   ```

2. **Apply eager loading**:
   ```python
   # After (fixed)
   from sqlalchemy.orm import selectinload
   user = await db.execute(
       select(User)
       .where(User.id == user_id)
       .options(selectinload(User.organizations))
   )
   return user.scalar_one()
   ```

3. **Alternative: Extract ID early**:
   ```python
   user = await db.execute(select(User).where(User.id == user_id))
   user_obj = user.scalar_one()
   user_id = user_obj.id  # Extract before session closes
   # Use user_id for subsequent operations
   ```

### Procedure 3: Debug Token Blacklist Issues

1. **Check Redis connectivity**:
   ```bash
   redis-cli -h localhost -p 16379 ping
   ```

2. **Verify blacklist service initialization**:
   ```python
   from omoi_os.services.token_blacklist import get_token_blacklist
   try:
       blacklist = get_token_blacklist()
       print("Blacklist service initialized")
   except RuntimeError as e:
       print(f"Blacklist service error: {e}")
   ```

3. **Clear blacklist (emergency)**:
   ```bash
   redis-cli -h localhost -p 16379 keys "token:blacklist:*" | xargs redis-cli del
   ```

---

## Security Best Practices

1. **Never Log JWTs**:
   Ensure tokens are redacted in all log files. The system automatically logs auth events to Redis without including full tokens.

2. **Use Strong Secrets**:
   Avoid using common strings or default values for `AUTH_JWT_SECRET_KEY`. Production validation enforces minimum 32 characters.

3. **Rotate Keys**:
   Periodically rotate the signing keys to limit the impact of a potential leak. Coordinate rotation with token invalidation.

4. **HTTPS Only**:
   Never transmit tokens over unencrypted channels. OmoiOS enforces TLS in production via `AuthSettings._reject_weak_jwt_secret_in_production()`.

5. **Token Rotation**:
   The refresh endpoint implements token rotation - old refresh tokens are blacklisted when new ones are issued. This prevents token reuse attacks.

6. **Rate Limiting**:
   Login endpoints are rate-limited (5/minute) to prevent brute force attacks. Failed attempts are tracked in Redis.

7. **Password Security**:
   Passwords are hashed using bcrypt with salt. Never store plain-text passwords.

---

## Troubleshooting Flowchart

```
Receive 401?
├── Check Header Format → Must be "Bearer <token>"
├── Check Token Expiry → Use /auth/refresh if expired
├── Check Secret Key → Verify AUTH_JWT_SECRET_KEY matches
└── Check Token Blacklist → May be revoked

Receive 403?
├── Check Token Payload → Verify "scopes" claim
├── Check User Roles → Query database for role assignment
└── Check Endpoint Requirements → Verify @requires_auth decorator

Internal Server Error (500) on Auth?
├── Check DB Connection → Verify PostgreSQL connectivity
├── Check Secret Key Formatting → Must be string, not bytes
├── Check jose Library Version → python-jose[cryptography] required
└── Check Redis for Blacklist → Verify token_blacklist service
```

---

## Common Diagnostic Commands

```bash
# Generate a test JWT for a specific user
uv run python -m omoi_os.scripts.generate_test_token --user-id <uuid>

# Check backend auth logs
tail -f backend/logs/api.log | grep "auth"

# Verify JWT_SECRET length
python -c "import os; print(len(os.getenv('AUTH_JWT_SECRET_KEY', '')))"

# Test login endpoint
curl -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# Test token refresh
curl -X POST http://localhost:18000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'

# Check rate limit status
redis-cli -h localhost -p 16379 get "auth:failed:<email>"

# View recent auth events
redis-cli -h localhost -p 16379 lrange "auth:events" 0 10
```

---

*End of Auth and JWT Troubleshooting Guide*

*This guide covers the full stack of authentication logic in OmoiOS, from token generation to session management and security best practices.*
