---
id: 8
title: Extract Config & Setup Migration Runner
status: needs-triage
labels: [needs-triage]
---

## Parent

#7 Production Readiness Improvements

## What to build
Move hardcoded AI model IDs to `SEARCH_CONFIG.yaml` and update `config_loader.py`. Implement a new `migration_runner.py` module capable of executing versioned SQL files against SQLite. Create `migrations/v1_init.sql` (containing the current schema and enabling WAL mode) and update `main.py` setup to use the runner.

## Acceptance criteria
- [ ] `SEARCH_CONFIG.yaml` contains Gemini model configuration.
- [ ] `config_loader.py` successfully reads the model configuration.
- [ ] `migration_runner.py` executes unapplied scripts from a `migrations` folder.
- [ ] Tests verify `migration_runner.py` behavior.

## Blocked by
None - can start immediately
