# Issue: TUI Staged Decisions Workflow

## Labels
`enhancement`, `ready-for-agent`

## Parent
[.scratch/project-vector/12-tui-enhancements.md](.scratch/project-vector/12-tui-enhancements.md)

## What to build
Refactor the TUI to use an in-memory buffer for status changes (Promote/Reject) instead of immediate database updates. Add a final "Confirm & Save" step.

## Acceptance criteria
- [x] Pressing 'P' or 'R' updates an internal `staged_changes` dictionary, not the DB.
- [x] List items show a visual indicator (e.g., `[P]` or `[R]` prefix) and a style change when staged.
- [x] Selection automatically moves to the next item in the list after a decision keybind.
- [x] First item is automatically focused on app startup.
- [x] A new "Confirm & Save" action (Ctrl+S) commits all staged changes to the database.
- [x] Tests verify that staging is ephemeral until "Save" is called.

## Blocked by
None - can start immediately
