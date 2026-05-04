# Issue: TUI Dynamic Digest View & Note Sync

## Parent
[.scratch/project-vector/20-dynamic-daily-digests.md](.scratch/project-vector/20-dynamic-daily-digests.md)

## What to build
Refactor the TUI's Digest View to use the dynamic `DigestManager`. Implement a split-pane layout for date selection and ensure that any notes added/viewed in this mode are synchronized with the database.

## Acceptance criteria
- [ ] Digest view in `src/review_tui.py` uses a split layout (Sidebar for dates, Main for Markdown).
- [ ] Selecting a date in the sidebar updates the Markdown viewer dynamically via `DigestManager`.
- [ ] If a user edits a note in the Review pane, it is reflected in the Digest view upon refresh/save (and vice-versa).
- [ ] Integration test in `tests/test_tui.py` verifies the dynamic rendering flow.

## Blocked by
- [.scratch/project-vector/22-digest-manager.md](.scratch/project-vector/22-digest-manager.md)
