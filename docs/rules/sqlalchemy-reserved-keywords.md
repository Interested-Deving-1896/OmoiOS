# SQLAlchemy Reserved Keywords

**Category**: Rule · **Severity**: Critical · **Last updated**: 2026-04-24

## The error that brings you here

```
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved
when using the Declarative API.
```

Raised at **import time**, before the app even starts. Every import of the
offending model blows up; the API won't serve any route.

## Why it happens in this codebase

SQLAlchemy's `DeclarativeBase` (which our `Base` inherits from) reserves
several attribute names for its own machinery. Using them as column names
isn't a runtime bug — it's a declaration error that fires the moment the
class is defined.

## Banned attribute names

| Reserved | What it's for | Safe alternatives |
|----------|---------------|-------------------|
| `metadata` | `Base.metadata` (the `MetaData` object) | `change_metadata`, `item_metadata`, `config_data`, `extra_data` |
| `registry` | SQLAlchemy's internal registry system | `agent_registry`, `service_registry` |
| `declared_attr` | Declarative attribute decorator | `custom_field`, `dynamic_attribute` |

## The rule

Never name a mapped column `metadata`, `registry`, or `declared_attr` on any
class that inherits from `Base`. Pick one of the domain-specific alternatives
in the table above — `metadata` in particular shows up constantly because
"metadata" is a generic word that means nothing.

If you're unsure whether a name is reserved, grep existing models: if nobody
else uses it, that's your first clue.

## Good and bad side by side

```python
# ❌ Won't even import
class TicketHistory(Base):
    __tablename__ = "ticket_history"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)  # InvalidRequestError

# ✅ Works, and the name describes what the field actually holds
class TicketHistory(Base):
    __tablename__ = "ticket_history"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    change_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
```

## Extra reading

See `backend/CLAUDE.md` → "SQLAlchemy Reserved Keywords" for the same rule
restated in the top-level guide.
