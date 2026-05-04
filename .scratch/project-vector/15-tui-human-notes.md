# Issue: TUI Human Notes Integration

## Labels
`enhancement`, `ready-for-agent`

## Parent
[.scratch/project-vector/12-tui-enhancements.md](.scratch/project-vector/12-tui-enhancements.md)

## What to build
Enable the capture of human context (notes) for each job during review and include them in the generated digests.

## Acceptance criteria
- [x] Database migration adds a `notes` (TEXT) column to the `jobs` table.
- [x] `src/review_tui.py` includes a `TextArea` or `Input` in the detail pane for entering notes.
- [x] Notes are saved to the database during the "Confirm & Save" action (dependent on Issue 14).
- [x] `src/evaluator.py` is updated to include job notes in the Markdown digest if present.
- [x] Tests verify notes persistence and inclusion in digests.

## Blocked by
- [.scratch/project-vector/14-tui-staged-decisions.md](.scratch/project-vector/14-tui-staged-decisions.md) (for saving logic)
