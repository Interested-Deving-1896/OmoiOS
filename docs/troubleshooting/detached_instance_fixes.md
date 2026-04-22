# SQLAlchemy DetachedInstanceError Fixes

**Created**: 2025-01-15  
**Updated**: 2025-04-22  
**Status**: Active  
**Purpose**: Comprehensive guide to understanding, detecting, and fixing SQLAlchemy DetachedInstanceError issues in OmoiOS

---

## Table of Contents

1. [Problem Description](#problem-description)
2. [Root Causes](#root-causes)
3. [Detection Methods](#detection-methods)
4. [Fix Procedures](#fix-procedures)
5. [Prevention Strategies](#prevention-strategies)
6. [Code Examples](#code-examples)
7. [Diagnosis Flowchart](#diagnosis-flowchart)
8. [Related Documentation](#related-documentation)

---

## Problem Description

`DetachedInstanceError` is a common SQLAlchemy exception that occurs when attempting to access attributes of a model instance after its associated database session has been closed. This error is particularly prevalent in OmoiOS due to the extensive use of:

- **Context managers** for database sessions (`with db.get_session()`)
- **Async session patterns** in FastAPI routes
- **Service layer abstractions** that return model instances
- **Background workers** that process data outside request contexts

### Error Message Pattern

```
sqlalchemy.orm.exc.DetachedInstanceError: Instance <User at 0x...> is not bound to a Session;
attribute refresh operation cannot proceed. (Background on this error at: https://sqlalche.me/e/14/bhk3)
```

### Impact on OmoiOS

When `DetachedInstanceError` occurs in OmoiOS, it can cause:

1. **API request failures** - HTTP 500 errors returned to clients
2. **Authentication flow breaks** - Users unable to login or refresh tokens
3. **OAuth callback failures** - Third-party login integrations fail
4. **Background task failures** - Workers crash when processing detached objects
5. **Data inconsistency** - Partial writes or orphaned records

---

## Root Causes

### 1. Session Context Boundary Violations

The most common cause is accessing model attributes outside the session context that created them:

```python
# ❌ WRONG: Accessing user.id after session closes
with db.get_session() as session:
    user = session.get(User, user_id)
# Session closes here
access_token = create_token(user.id)  # DetachedInstanceError!
```

### 2. Service Methods Returning Unexpunged Objects

When service methods return model instances without detaching them from the session:

```python
# ❌ WRONG: Returning user without expunging
def get_or_create_user(email: str) -> User:
    with db.get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if not user:
            user = User(email=email)
            session.add(user)
            session.commit()
        return user  # Session closes, user becomes detached!

# Later usage:
user = get_or_create_user("test@example.com")
print(user.id)  # DetachedInstanceError!
```

### 3. Async Session Lifecycle Issues

In FastAPI, async sessions can behave differently than sync sessions:

```python
# ❌ WRONG: Assuming async session stays open
async def get_user(user_id: str) -> User:
    async with db.get_async_session() as session:
        return await session.get(User, user_id)

# In route:
user = await get_user(user_id)
# Session may be closed here depending on FastAPI's dependency injection
access_token = create_token(user.id)  # Potential DetachedInstanceError!
```

### 4. Lazy Loading After Session Close

Accessing relationships or deferred columns after session closure:

```python
# ❌ WRONG: Accessing relationship after session closes
with db.get_session() as session:
    ticket = session.get(Ticket, ticket_id)
# Session closes
for task in ticket.tasks:  # DetachedInstanceError - lazy load fails!
    print(task.title)
```

### 5. Background Worker Context Loss

When passing model instances to background workers:

```python
# ❌ WRONG: Passing detached objects to workers
def process_ticket(ticket_id: str):
    with db.get_session() as session:
        ticket = session.get(Ticket, ticket_id)
    # Session closes
    background_worker.enqueue(ticket)  # Ticket is detached!

# In worker:
def worker_process(ticket):
    print(ticket.title)  # DetachedInstanceError!
```

---

## Detection Methods

### 1. Static Code Analysis

Use grep patterns to find potential violations:

```bash
# Find patterns where objects are returned from session contexts
grep -r "return.*user\|return.*ticket\|return.*task" backend/omoi_os/services/ --include="*.py" | grep -A2 "get_session"

# Find attribute access after session blocks
grep -r "\.id\|\.email\|\.name" backend/omoi_os/api/routes/ --include="*.py" | grep -B5 "get_session\|async_session"
```

### 2. Runtime Detection with SQLAlchemy Events

Add event listeners to detect detached instance access:

```python
from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(Session, 'detached_to_persistent')
def detect_detached_access(session, instance):
    logger.warning(
        f"Detached instance accessed: {instance.__class__.__name__}",
        extra={
            "instance_id": getattr(instance, 'id', None),
            "instance_class": instance.__class__.__name__,
            "stack_trace": traceback.format_stack()
        }
    )
```

### 3. Unit Test Patterns

Create tests that verify session boundaries:

```python
def test_user_not_detached_after_service_call():
    """Ensure users returned from service are not detached."""
    user = oauth_service.get_or_create_user("test@example.com")
    
    # This should not raise DetachedInstanceError
    try:
        _ = user.id
        _ = user.email
    except DetachedInstanceError:
        pytest.fail("User instance became detached after service call")
```

### 4. Integration Test with Session Inspection

```python
async def test_oauth_callback_no_detached_instances():
    """Verify OAuth callback handles sessions correctly."""
    from sqlalchemy.orm import inspect
    
    # Perform OAuth callback
    response = await client.get("/api/v1/auth/oauth/callback?code=test")
    
    # Check that no detached instances exist in response context
    # (This requires instrumentation in the route)
```

### 5. Log Analysis

Monitor application logs for DetachedInstanceError:

```bash
# Search for detached instance errors in logs
grep "DetachedInstanceError" /var/log/omoi_os/app.log

# Count occurrences by endpoint
grep "DetachedInstanceError" /var/log/omoi_os/app.log | grep -oP "route: \K[^ ]+" | sort | uniq -c
```

---

## Fix Procedures

### Fix 1: Extract Values Before Session Close

**Applies to**: OAuth callback routes, auth routes, any route accessing model attributes

**Pattern**:
```python
# ✅ GOOD: Extract ID before session closes
with db.get_session() as session:
    user = session.get(User, user_id)
    user_id = user.id  # Extract while session is open
    user_email = user.email
# Session closes
access_token = create_token(user_id)  # Safe!
```

**Applied in**:
- `backend/omoi_os/api/routes/oauth.py` - OAuth callback
- `backend/omoi_os/api/routes/auth.py` - Login, refresh token, password reset

### Fix 2: Use `session.expunge()` for Returned Objects

**Applies to**: Service methods that return model instances

**Pattern**:
```python
# ✅ GOOD: Expunge before returning
def get_or_create_user(email: str) -> User:
    with db.get_session() as session:
        user = session.query(User).filter_by(email=email).first()
        if not user:
            user = User(email=email)
            session.add(user)
            session.commit()
        session.expunge(user)  # Detach from session
        return user

# Later usage:
user = get_or_create_user("test@example.com")
access_token = create_token(user.id)  # Safe - user is detached but populated
```

**Applied in**:
- `backend/omoi_os/services/oauth_service.py` - `get_or_create_user()`
- `backend/omoi_os/api/dependencies.py` - `get_current_user()`

### Fix 3: Use `expire_on_commit=False` for Async Sessions

**Configuration**:
```python
self.AsyncSessionLocal = async_sessionmaker(
    self.async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent expiration on commit
    autocommit=False,
    autoflush=False,
)
```

**Note**: This is already configured in `DatabaseService` but should be verified when creating custom session makers.

### Fix 4: Eager Load Relationships

When accessing relationships outside session context:

```python
from sqlalchemy.orm import joinedload

# ✅ GOOD: Eager load relationships
with db.get_session() as session:
    ticket = (
        session.query(Ticket)
        .options(joinedload(Ticket.tasks))
        .filter_by(id=ticket_id)
        .first()
    )
    # Access relationship while session is open
    task_count = len(ticket.tasks)
# Session closes - ticket.tasks is already loaded
```

### Fix 5: Use DTOs/Schemas for Cross-Layer Data Transfer

Instead of passing model instances, use Pydantic schemas:

```python
from pydantic import BaseModel

class UserDTO(BaseModel):
    id: str
    email: str
    name: str

def get_user_dto(user_id: str) -> UserDTO:
    with db.get_session() as session:
        user = session.get(User, user_id)
        return UserDTO(
            id=str(user.id),
            email=user.email,
            name=user.name
        )

# Usage:
user_dto = get_user_dto(user_id)
# No session needed - DTO is a plain Python object
access_token = create_token(user_dto.id)
```

---

## Prevention Strategies

### 1. Code Review Checklist

Before merging code that touches database models:

- [ ] Are model attributes accessed only within session contexts?
- [ ] Are service methods that return models using `session.expunge()`?
- [ ] Are relationships eager-loaded if accessed outside sessions?
- [ ] Are DTOs used for cross-layer data transfer?
- [ ] Are async sessions configured with `expire_on_commit=False`?

### 2. Linting Rules

Add custom linting to detect potential issues:

```python
# .ruff.toml or pyproject.toml
[tool.ruff.lint]
# Add custom rules for SQLAlchemy patterns
select = ["E", "F", "W", "C90", "I", "N", "D", "UP", "B", "C4", "SIM"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

### 3. Testing Requirements

All service methods returning model instances must have tests verifying:

```python
def test_service_returns_detached_instance():
    """Ensure service returns detached but populated instances."""
    result = service.get_model_instance()
    
    # Should not raise DetachedInstanceError
    assert result.id is not None
    assert result.name is not None
```

### 4. Documentation Standards

Document session boundaries in function docstrings:

```python
def get_user(user_id: str) -> User:
    """Get user by ID.
    
    Note:
        Returns a detached instance. Access all needed attributes
        immediately or use session.expunge() before returning.
    
    Args:
        user_id: User identifier
        
    Returns:
        User instance (detached from session)
    """
```

### 5. Architecture Patterns

**Preferred: Repository Pattern with DTOs**

```python
class UserRepository:
    def __init__(self, db: DatabaseService):
        self.db = db
    
    def get_by_id(self, user_id: str) -> UserDTO:
        with self.db.get_session() as session:
            user = session.get(User, user_id)
            return UserDTO.from_orm(user)  # Convert to DTO
```

**Avoid: Returning ORM models from service layer**

```python
# ❌ AVOID: Service returning ORM models
class UserService:
    def get_user(self, user_id: str) -> User:  # Returns ORM model
        ...
```

---

## Code Examples

### Example 1: OAuth Service Pattern

```python
# backend/omoi_os/services/oauth_service.py

class OAuthService:
    def get_or_create_user(
        self, 
        email: str, 
        provider: str, 
        provider_user_id: str
    ) -> User:
        """Get or create user from OAuth data.
        
        Returns detached instance to prevent DetachedInstanceError
        when accessing user attributes in route handlers.
        """
        with self.db.get_session() as session:
            # Try to find existing user
            user = (
                session.query(User)
                .join(OAuthAccount)
                .filter(
                    OAuthAccount.provider == provider,
                    OAuthAccount.provider_user_id == provider_user_id
                )
                .first()
            )
            
            if not user:
                # Create new user
                user = User(
                    email=email,
                    is_active=True
                )
                session.add(user)
                
                # Create OAuth account link
                oauth_account = OAuthAccount(
                    user=user,
                    provider=provider,
                    provider_user_id=provider_user_id
                )
                session.add(oauth_account)
                
                session.commit()
            
            # ✅ CRITICAL: Expunge before returning
            session.expunge(user)
            
            # Also expunge related objects if needed
            for oauth in user.oauth_accounts:
                session.expunge(oauth)
            
            return user
```

### Example 2: Auth Route Pattern

```python
# backend/omoi_os/api/routes/auth.py

@router.post("/login")
async def login(
    credentials: LoginCredentials,
    db: DatabaseService = Depends(get_db)
) -> TokenResponse:
    """Authenticate user and return tokens."""
    
    # Authenticate within session context
    async with db.get_async_session() as session:
        user = await authenticate_user(
            session, 
            credentials.email, 
            credentials.password
        )
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # ✅ CRITICAL: Extract values while session is open
        user_id = user.id
        user_email = user.email
        is_active = user.is_active
    
    # Session closed - use extracted values
    if not is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    
    # Create tokens using extracted values (safe!)
    access_token = create_access_token(
        data={"sub": str(user_id), "email": user_email}
    )
    refresh_token = create_refresh_token(data={"sub": str(user_id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )
```

### Example 3: Dependency Injection Pattern

```python
# backend/omoi_os/api/dependencies.py

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: DatabaseService = Depends(get_db)
) -> User:
    """Get current authenticated user.
    
    Returns detached instance to prevent DetachedInstanceError
    in route handlers that access user attributes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    async with db.get_async_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            raise credentials_exception
        
        # ✅ CRITICAL: Expunge before returning
        session.expunge(user)
        return user
```

### Example 4: Background Worker Pattern

```python
# backend/omoi_os/workers/task_worker.py

async def process_task(task_id: str):
    """Process a task in background worker."""
    db = get_db()
    
    # Load task data within session
    with db.get_session() as session:
        task = session.get(Task, task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return
        
        # ✅ Extract all needed data before session closes
        task_data = {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "ticket_id": str(task.ticket_id),
            "required_capabilities": task.required_capabilities,
        }
        
        # Eager load relationships if needed
        ticket = task.ticket
        task_data["ticket_title"] = ticket.title
        task_data["project_id"] = str(ticket.project_id)
    
    # Session closed - use task_data dict (safe!)
    logger.info(f"Processing task: {task_data['title']}")
    
    # Pass plain data to sandbox spawner
    await spawner.spawn_for_task(
        task_id=task_data["id"],
        task_title=task_data["title"],
        project_id=task_data["project_id"]
    )
```

---

## Diagnosis Flowchart

```mermaid
flowchart TD
    A[DetachedInstanceError Occurs] --> B{Where does it happen?}
    
    B -->|In Route Handler| C[Check session context]
    B -->|In Service Method| D[Check return pattern]
    B -->|In Background Worker| E[Check data loading]
    
    C --> F{Accessing attributes<br/>after session close?}
    F -->|Yes| G[Fix: Extract values<br/>before session close]
    F -->|No| H[Check async session<br/>configuration]
    
    H --> I{expire_on_commit=False?}
    I -->|No| J[Fix: Set expire_on_commit=False]
    I -->|Yes| K[Check for lazy loading]
    
    K --> L{Accessing relationships?}
    L -->|Yes| M[Fix: Use eager loading<br/>or extract values]
    L -->|No| N[Investigate other causes]
    
    D --> O{Returning ORM models?}
    O -->|Yes| P{Using session.expunge()?}
    P -->|No| Q[Fix: Add session.expunge()<br/>before return]
    P -->|Yes| R[Check related objects]
    
    R --> S{Related objects accessed?}
    S -->|Yes| T[Fix: Expunge related<br/>objects too]
    S -->|No| U[Check for async issues]
    
    E --> V{Passing ORM objects<br/>to workers?}
    V -->|Yes| W[Fix: Convert to DTOs<br/>or plain dicts]
    V -->|No| X[Check session lifecycle]
    
    G --> Y[Test Fix]
    J --> Y
    M --> Y
    Q --> Y
    T --> Y
    W --> Y
    
    Y --> Z{Error Resolved?}
    Z -->|Yes| AA[Add regression test]
    Z -->|No| AB[Escalate to team]
    
    N --> AB
    U --> AB
    X --> AB
    
    AA --> AC[Update documentation]
    
    style G fill:#90EE90
    style J fill:#90EE90
    style M fill:#90EE90
    style Q fill:#90EE90
    style T fill:#90EE90
    style W fill:#90EE90
    style AA fill:#FFD700
```

---

## Fixed Issues Reference

### 1. OAuth Callback Route (`backend/omoi_os/api/routes/oauth.py`)

**Problem**: User object was created/updated in one session, then `user.id` was accessed in a different session context.

**Fix**: 
- Moved all user creation/update logic into the same session where tokens are generated
- Extract `user_id` while still in session (before it becomes detached)
- Added `session.expunge(user)` to prevent detached instance errors

### 2. OAuth Service `get_or_create_user` (`backend/omoi_os/services/oauth_service.py`)

**Problem**: Returns User object from within a session context manager, which closes when function returns.

**Fix**: Added `session.expunge(user)` before returning to detach the object from the session.

### 3. Auth Route - Login (`backend/omoi_os/api/routes/auth.py`)

**Problem**: `authenticate_user()` returns User from async session, then `user.id` is accessed.

**Fix**: Extract `user_id = user.id` before using it to create tokens.

### 4. Auth Route - Refresh Token (`backend/omoi_os/api/routes/auth.py`)

**Problem**: `get_user_by_id()` returns User from async session, then `user.id` is accessed.

**Fix**: Extract `user_id = user.id` before using it to create tokens.

### 5. Auth Route - Password Reset (`backend/omoi_os/api/routes/auth.py`)

**Problem**: `get_user_by_email()` returns User from async session, then `user.id` is accessed.

**Fix**: Extract `user_id = user.id` before using it to create reset token.

### Already Protected

#### `get_current_user` (`backend/omoi_os/api/dependencies.py`)

✅ **Already safe**: Uses `session.expunge(user)` before returning.

---

## Best Practices Applied

1. **Extract needed values before session closes**: Always extract `user.id` or other needed attributes while the session is still open.

2. **Use `session.expunge()` for objects returned from sync sessions**: When returning model instances from functions that use sync session context managers, expunge them before returning.

3. **Async sessions are safer**: Async sessions in FastAPI typically stay open for the entire request lifecycle, but it's still safer to extract needed values early.

---

## Pattern to Follow

```python
# ❌ BAD - accessing user.id after session closes
with db.get_session() as session:
    user = session.get(User, user_id)
    # session closes here
access_token = create_token(user.id)  # DetachedInstanceError!

# ✅ GOOD - extract ID before session closes
with db.get_session() as session:
    user = session.get(User, user_id)
    user_id = user.id  # Extract while session is open
    session.expunge(user)  # Detach from session
access_token = create_token(user_id)  # Safe!
```

---

## Testing

All fixes have been applied. Test the following flows:

1. OAuth login (GitHub/Google)
2. Regular email/password login
3. Token refresh
4. Password reset request

### Regression Test Suite

```python
# tests/integration/test_auth_flows.py

import pytest
from sqlalchemy.orm import inspect

class TestAuthDetachedInstanceFixes:
    """Regression tests for DetachedInstanceError fixes."""
    
    @pytest.mark.asyncio
    async def test_oauth_callback_no_detached_error(self, client, db):
        """OAuth callback should not raise DetachedInstanceError."""
        response = await client.get(
            "/api/v1/auth/oauth/callback",
            params={"code": "test_code", "provider": "github"}
        )
        
        # Should succeed without 500 error
        assert response.status_code in [200, 302]
    
    @pytest.mark.asyncio
    async def test_login_returns_valid_tokens(self, client, db):
        """Login should return valid tokens without detached errors."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    @pytest.mark.asyncio
    async def test_token_refresh_no_detached_error(self, client, db):
        """Token refresh should not raise DetachedInstanceError."""
        # First login to get refresh token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password"}
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()
```

---

## Related Documentation

- [SQLAlchemy Documentation - Session Basics](https://docs.sqlalchemy.org/en/14/orm/session_basics.html)
- [SQLAlchemy Documentation - DetachedInstanceError](https://sqlalche.me/e/14/bhk3)
- [OmoiOS Backend Guide](../../backend/CLAUDE.md)
- [OmoiOS Database Service](../../backend/omoi_os/services/database.py)
- [OmoiOS OAuth Service](../../backend/omoi_os/services/oauth_service.py)
- [OmoiOS Auth Routes](../../backend/omoi_os/api/routes/auth.py)

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-01-15 | Initial fixes applied | @kivo360 |
| 2025-04-22 | Expanded documentation with flowchart, examples, and prevention strategies | Documentation Team |

---

**Last Updated**: 2025-04-22  
**Document Owner**: Backend Team  
**Review Cycle**: Quarterly
