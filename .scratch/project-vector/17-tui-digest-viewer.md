# Issue: TUI Digest & Suggestion Viewer

## Labels
`enhancement`, `ready-for-agent`

## Parent
[.scratch/project-vector/12-tui-enhancements.md](.scratch/project-vector/12-tui-enhancements.md)

## What to build
Provide a way to view generated digests and discovered search suggestions directly within the TUI.

## Acceptance criteria
- [x] A new "Digest" screen or modal displays the content of the most recent file in `digests/`.
- [x] A "Suggestions" pane or screen displays entries from the `search_suggestions` table.
- [x] Keybinds allow navigating to these screens from the main review view.
- [x] Content is rendered using the Markdown widget where appropriate.

## Blocked by
- [.scratch/project-vector/13-tui-markdown.md](.scratch/project-vector/13-tui-markdown.md) (for rendering)
