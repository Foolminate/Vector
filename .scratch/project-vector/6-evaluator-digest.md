---
id: 6
title: Agent 2: Evaluator & Markdown Digest
status: completed
labels: [feature, ai, reporting]
---

## Parent
.scratch/project-vector/1-core-pipeline.md

## What to build
Implement the deep qualitative analysis using a heavyweight LLM (Claude 3.5 Sonnet) and generate the daily Markdown report.

## Acceptance criteria
- [x] Agent 2 performs deep analysis on all promoted jobs.
- [x] Agent 2 identifies "Architectural Opportunities" and "Red Flags" per the JSON schema.
- [x] `python main.py digest` generates a clean, readable Markdown file in `digests/`.
- [x] The report highlights Hamilton/Waikato and Remote roles as top priorities.

## Blocked by
- .scratch/project-vector/5-review-cli.md
