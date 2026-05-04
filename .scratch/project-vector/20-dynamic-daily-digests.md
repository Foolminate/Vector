# Issue: Dynamic Database-Driven Daily Digests

## Labels
`needs-triage`, `enhancement`

## Problem Statement

Currently, the TUI's "Digest View" relies on static Markdown files written to the disk. This creates a disjointed user experience where users can only view a test digest or the most recently generated static file, without the ability to navigate between historical digests. Furthermore, because these static digests are disconnected from the primary jobs database, it is difficult to persistently add human notes directly within the digest view and associate them with the underlying job record. The user needs a unified, dynamic view that groups AI evaluations logically (e.g., by day) directly from the database.

## Solution

We will migrate the digest system from static files to a dynamic, database-driven approach. We will introduce a new deep module, `src/digest_manager.py`, responsible for aggregating and formatting evaluated jobs into Daily Digests based on a new `evaluated_at` timestamp. The TUI will be updated with a split-pane layout to allow users to select past digests by date, and human notes added during digest review will be synchronized directly to the database.

## User Stories

1. As an evaluator, I want AI evaluations to be stamped with the date they were analyzed, so that they can be logically grouped.
2. As a reviewer, I want to see a list of dates representing past "Daily Digests", so that I can browse historical job evaluations.
3. As a reviewer, I want to select a date from the list and see a dynamically generated Markdown digest of all jobs evaluated on that day, so that I don't have to rely on static files.
4. As a reviewer, I want to be able to enter human notes while viewing a dynamic digest, so that my insights are persisted directly to the corresponding job in the database.
5. As a reviewer, I want to easily toggle between the Full/Review job list and the Daily Digest list, so that my workflow remains seamless.
6. As a system administrator, I want `evaluator.py` to continue generating static Markdown backups, so that I have a portable record of evaluations.

## Implementation Decisions

- **New Deep Module (`src/digest_manager.py`):** We will extract the digest aggregation and rendering logic from the TUI and `evaluator.py` into a dedicated `DigestManager` class. This module will handle querying the database by date, grouping jobs, and returning formatted Markdown strings.
- **Database Schema:** We will add an `evaluated_at` (TIMESTAMP) column to the `jobs` table via a new migration (`migrations/v6_add_evaluated_at.sql`).
- **Evaluator Logic:** `src/evaluator.py` will update `evaluated_at = CURRENT_TIMESTAMP` when successfully saving an analysis. It will still call `DigestManager` to generate and save a static backup file.
- **TUI Layout:** The Digest View in `src/review_tui.py` will be converted to a `Horizontal` container with a `ListView` on the left (showing available dates) and a `Markdown` viewer on the right.
- **Data Flow:** The TUI will use `DigestManager.get_available_dates()` to populate the list, and `DigestManager.render_digest(date)` to populate the markdown pane.

## Testing Decisions

A good test verifies external behavior without tightly coupling to implementation details. We will perform comprehensive testing across these modules:
- **`tests/test_migration_runner.py`**: Verify the new migration applies cleanly and the `evaluated_at` column exists.
- **`tests/test_digest_manager.py` (New):** Test that `get_available_dates()` groups timestamps correctly and `render_digest()` outputs expected markdown formatting. We will use SQLite in-memory databases populated with fixture data.
- **`tests/test_evaluator.py`**: Ensure the evaluation saving logic correctly updates the `evaluated_at` timestamp.
- **`tests/test_tui.py`**: Verify the split-pane layout renders correctly, the list contains dates, and selection updates the markdown viewer.

## Out of Scope

- Modifying the AI prompt or evaluation criteria itself.
- Implementing search/filtering within the digest markdown text (this is purely navigation).
- Migrating previously generated static digests back into the database retroactively (they will remain on disk).

## Further Notes

Extracting `DigestManager` as a deep module ensures the TUI remains purely responsible for rendering UI events, maintaining a clean MVC-like separation of concerns.