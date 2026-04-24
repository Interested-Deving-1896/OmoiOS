# OmoiOS Engineering Rules

Rules here encode tripwires we've already stepped on. Each file captures one
class of recurring bug: the shape of the mistake, why it happens here
specifically, and the pattern that prevents it.

**Read the rule that matches the file you're about to touch.** They exist
because the same correction has been given twice.

## Index

| Rule | When it applies |
|------|-----------------|
| [sqlalchemy-session-handling.md](sqlalchemy-session-handling.md) | Writing any FastAPI dependency or route handler that loads ORM objects and returns them across a session boundary |
| [sqlalchemy-reserved-keywords.md](sqlalchemy-reserved-keywords.md) | Naming a column on a model that inherits from `Base` |
| [feature-flag-surfaces.md](feature-flag-surfaces.md) | Adding, enabling, or gating v1 API surfaces |

## Adding a new rule

1. Name the file after the *mistake*, not the fix (e.g.
   `detached-instance-error.md`, not `session-expunge-pattern.md`). You'll
   search for what went wrong, not what worked.
2. Start with a concrete failure example — stack trace, wrong output, the
   visible symptom — before the rule itself. The header should let someone
   grepping for their error find the page.
3. Explain *why* the rule exists (the incident, the subtle SQLAlchemy
   behavior, the codebase invariant). A rule without a "why" becomes a
   cargo-cult pattern people work around.
4. Add a row to the index above.

## How agents should use this directory

Both `CLAUDE.md` and `AGENTS.md` link here. When starting work on a route
handler, dependency, model, or v1 API surface, check if a rule applies before
writing code — not after the CI failure.
