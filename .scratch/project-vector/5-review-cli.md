---
id: 5
title: Human Review CLI
status: completed
labels: [feature, cli]
---

## Parent
.scratch/project-vector/1-core-pipeline.md

## What to build
An interactive Text User Interface (TUI) using `Textual` to review "Edge Case" roles. This allows the user to browse borderline opportunities, view details, and manually promote or reject them in any order.

## Acceptance criteria
- [x] `python main.py review` launches a TUI.
- [x] Sidebar/List view shows all edge-case jobs with visual selection.
- [x] Detail view displays Job Title, Company, AI Rationale, and Score.
- [x] User can promote (P) or reject (R) the selected role immediately.
- [x] User can open the job URL (O or Enter) in the default web browser.
- [x] Database state updates reactively in the TUI.

## Blocked by
- .scratch/project-vector/4-sorter-triage.md
