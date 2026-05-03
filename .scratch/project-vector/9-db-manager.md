---
id: 9
title: DB Connection Context Manager & Cost Log
status: needs-triage
labels: [needs-triage]
---

## Parent

#7 Production Readiness Improvements

## What to build
Create `migrations/v2_add_cost_log.sql` to initialize a table tracking API token usage. Refactor `src/database.py` to use a context manager for `sqlite3` connections that sets a `busy_timeout` to handle concurrent access gracefully.

## Acceptance criteria
- [ ] `v2_add_cost_log.sql` creates the cost log table when executed.
- [ ] Database connections correctly utilize the context manager pattern.
- [ ] Concurrent reads/writes do not throw "database is locked" errors under load.
- [ ] Tests verify the context manager connection behavior.

## Blocked by
- #8 (Extract Config & Setup Migration Runner)
