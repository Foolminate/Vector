# Domain docs: Single-context

This repository follows a **single-context** layout for domain documentation. This is the default for most projects where the entire codebase shares a single domain language and architectural history.

## Consumer Rules

Skills that need to understand the project's purpose, terminology, or history should look in these locations:

1.  **Domain Language:** Read `CONTEXT.md` at the repo root. This file defines the "what" and "why" of the project, including its core entities and ubiquitous language.
2.  **Architectural Decisions:** Read `docs/adr/*.md`. These files record significant architectural choices (ADRs) and their rationale.

When making changes, these skills should ensure consistency with the established domain language and respect existing architectural decisions.
