# PRD: Advanced TUI for Human Review & Discovery

## Problem Statement

The current TUI (`src/review_tui.py`) is a basic list-detail view that immediately commits decisions (Promote/Reject) to the database. This makes it difficult for the user to review their decisions before finalizing them. Furthermore, the UI lacks support for rich text formatting (Markdown), does not allow overriding historical entries, and provides no way to view the final generated "Digest" reports. There is also a missed opportunity to capture human context (notes) during review and use the "related searches" discovered by the scraper.

## Solution

Enhance the TUI to support a "Staged Decision" workflow, where updates are buffered in memory until a final "Confirm & Save" action is performed. The UI will be upgraded to support Markdown rendering for job details and digests. A new "Full Database" mode will allow overriding any entry. A "Human Notes" feature will be added to the database and TUI, allowing user-provided context to be included in future digests.

## User Stories

1. As a reviewer, I want the TUI to automatically focus the first item in the list on startup, so I can start reviewing immediately without extra clicks.
2. As a reviewer, I want to promote or reject a job without it immediately disappearing from the list, so I can review my choices before saving.
3. As a reviewer, I want a visual indicator (like `[P]` or `[R]`) and a background color change on list items I have modified, so I can easily identify staged changes.
4. As a reviewer, I want the selection to automatically move to the next entry after I make a decision, so I can process the list efficiently.
5. As a reviewer, I want a "Confirm & Save" button/key that commits all my staged changes to the database at once.
6. As a reviewer, I want to toggle between "Review Mode" (edge-case only) and "Full Mode" (all jobs), so I can override decisions for any job in history.
7. As a reviewer, I want the job details to render with proper Markdown formatting (bold, headings, lists), so they are easier to read.
8. As a reviewer, I want to view the latest generated digest file directly within the TUI, so I can verify the final output.
9. As a reviewer, I want to add "Human Notes" to a job listing, so I can record specific thoughts (e.g., commute, culture fit).
10. As a career seeker, I want my "Human Notes" to appear in the generated digests, so I have all context in one report.
11. As a reviewer, I want to see a list of "Related Searches" discovered by the scraper and have them digested by Gemini Pro, so I can get recommendations on new search keywords.

## Implementation Decisions

### Modules & Interactions
- **`src/database.py`**: Add a `notes` column to the `jobs` table via migration. Extend `DatabaseManager` to save notes and update `analyzed` jobs.
- **`src/review_tui.py`**:
    - Switch `Static` details pane to `MarkdownViewer` (or `Markdown` widget).
    - Implement an `in_memory_buffer` for staged status changes and notes.
    - Implement `ModeToggle` (Review vs. Full).
    - Add a `DigestViewer` screen/modal to read and display `digests/latest.md`.
    - Add a `NotesInput` field in the detail pane.
- **`src/evaluator.py`**: Update `generate_digest` to include the `notes` column from the database if it is populated.

### Technical Clarifications
- **Deferred Updates**: Decision actions (P/R) will update a local state object. The `JobItem` will update its label and style based on this state.
- **Auto-Advance**: `ListView.index += 1` will be called after decision keybinds.
- **Markdown**: Textual's `Markdown` widget will be used for the details pane.
- **Digest Logic**: The TUI will look for the most recent file in the `digests/` directory.

### Schema Changes
- `ALTER TABLE jobs ADD COLUMN notes TEXT;`
- (Completed) `search_suggestions` table to store related searches.

## Testing Decisions

- **Good Tests**: Verify that staging a change does NOT update the DB, while clicking "Save" DOES. Verify that toggling modes correctly filters/unfilters the list.
- **Modules to Test**: `src/review_tui.py` (App logic), `src/database.py` (Notes persistence).
- **Prior Art**: `tests/test_tui.py` currently exists for basic navigation.

## Out of Scope

- Editing the Markdown digest file directly from the TUI.
- Automatic enqueuing of related searches without human/AI review.
- Real-time LLM analysis within the TUI (keep it to display of previous analysis).

## Further Notes

The "Human Notes" feature should be treated as high priority to ensure that personal context isn't lost between the review and digest phases.
