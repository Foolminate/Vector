# Issue: TUI Full History Mode

## Labels
`enhancement`, `ready-for-agent`

## Parent
[.scratch/project-vector/12-tui-enhancements.md](.scratch/project-vector/12-tui-enhancements.md)

## What to build
Add a "Full Mode" toggle to the TUI to allow reviewing and overriding any job in the database, not just those marked as 'edge-case'.

## Acceptance criteria
- [x] A keybind (e.g., 'F') toggles between "Review Mode" (default, 'edge-case' only) and "Full Mode" (all jobs).
- [x] The list header and sidebar update to indicate the active mode.
- [x] The database query in `refresh_list` respects the active mode.
- [x] Status overrides in Full Mode work identically to the review workflow (staged or immediate).

## Blocked by
None - can start immediately
