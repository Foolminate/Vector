# Issue tracker: Local markdown

This repo tracks issues as markdown files stored within the codebase itself. This is a good fit for solo projects, air-gapped environments, or repos without a hosted remote.

## Workflow

1.  **Storage:** Issues live under `.scratch/<feature-name>/<issue-id>.md`.
2.  **Creation:** When using `to-issues` or `to-prd`, create a new markdown file in the relevant subfolder.
3.  **Triage:** The `triage` skill will read these files to determine the current state.
4.  **Format:** Use frontmatter or clear headers to indicate status, labels, and assignment.

```markdown
---
id: 123
title: Example issue
status: needs-triage
labels: [bug]
---
Issue description here.
```
