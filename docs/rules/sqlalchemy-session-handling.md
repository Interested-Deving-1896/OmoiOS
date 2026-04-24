# SQLAlchemy Session Handling

**Category**: Rule · **Severity**: High · **Last updated**: 2026-04-24

## The error that brings you here

```
sqlalchemy.orm.exc.DetachedInstanceError: Instance <User at 0x...> is not
bound to a Session; attribute refresh operation cannot proceed
```

…raised from somewhere *outside* the function that loaded the object, usually
deep inside a downstream handler (`current_user.id`, `user.attributes`,
`current_user.organization_id`).

You'll hit this any time a FastAPI dependency uses a `with
db.get_session()` block, loads an ORM object, closes the block, and returns
the object for other dependencies/handlers to use.

## Why it happens in this codebase

`omoi_os.services.database.DatabaseService.get_session()` is a *sync*
context manager. When the `with` block exits, the session is closed, the
object becomes **detached**, and any unloaded attribute (especially JSONB
columns like `user.attributes` that default to lazy loading) triggers a
refresh on the dead session. Boom.

The JWT path in `api/dependencies.py::get_current_user` avoids this by
force-loading the JSONB field and *explicitly expunging* the instance before
returning. Anything that doesn't follow that exact dance re-introduces the
bug.

## The rule

If a dependency/function loads an ORM object inside a sync-session block and
returns that object across the boundary, it **must**:

1. Access every lazily-loaded attribute the downstream caller will touch —
   explicitly, once, inside the `with`. JSONB fields are the usual culprit.
   A bare `_ = user.attributes` is enough to force-load.
2. Call `session.refresh(obj)` so the instance has fresh state tied to the
   current session identity map.
3. Call `session.expunge(obj)` to detach cleanly — this tells SQLAlchemy
   "don't try to lazy-load anything ever again," so subsequent attribute
   access on a closed session is a plain Python attribute read instead of a
   refresh attempt.

### Canonical pattern

```python
with db.get_session() as session:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "not found")

    # 1. Force-load anything the caller will use
    _ = user.attributes  # JSONB field with lazy loading

    # 2. Pull fresh state into the identity map
    session.refresh(user)

    # 3. Detach cleanly so access outside this block is safe
    session.expunge(user)

    return user
```

### What doesn't work (and why)

| Anti-pattern | Why it fails |
|--------------|--------------|
| Just `return session.get(User, id)` | Session closes → detached → any attribute touch outside the `with` raises. |
| `user = session.get(...); return user` with no expunge | Same as above. "It worked in one test" means the test never touched an un-materialized column. |
| Turning off autoflush / autoexpire | Hides the symptom locally but creates stale reads elsewhere. |
| Returning a Pydantic `model_validate(user)` instead | Works if `from_attributes=True` and no lazy columns are needed for serialization. Only a partial escape: you can't pass the ORM instance down to other dependencies. |
| Swapping to the async session inside a sync dep | Creates transaction boundary mismatches; don't mix paradigms in one dependency. |

## When you're adding a *new* kind of auth/resource dependency

Every new `get_*_from_token`/`get_current_*` helper that returns an ORM
object goes through the same three-step dance above. Copy from
`get_current_user` in `backend/omoi_os/api/dependencies.py`, not from some
older handler that happens to "work" without expunging.

If you're resolving **API-key** callers (not JWT), the same rule applies —
the API key path must force-load, refresh, and expunge before returning. We
added the fallback on 2026-04-24 to make platform keys usable across the
`/api/v1/sessions`, `/tasks`, and related routes; it works *only* because it
ends with `refresh(user); expunge(user); return user`.

## When you're writing a *service* method that returns an ORM instance

Prefer returning a plain dict or a Pydantic model instead. Services that
return ORM objects push the expunge burden onto every caller and every caller
forgets. `WebhookService.create_subscription` does it correctly — ends the
`with` block with `refresh + expunge`. Use that as the template.

## Debugging tip

When you see `DetachedInstanceError` in a stack trace, the *real* bug is
always at the **return site** of whatever loaded that object — not at the
access site where the trace surfaces. Walk backward from the line that raises
until you find the function that opened and closed the session. That
function is missing the expunge.
