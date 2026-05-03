---
id: 4
title: Agent 1: The Sorter (Triage)
status: completed
labels: [feature, ai]
---

## Parent
.scratch/project-vector/1-core-pipeline.md

## What to build
Implement the initial triage logic using a cost-optimized LLM (GPT-4o-mini). It evaluates raw job descriptions against `DOCTRINE.md` and assigns a score (0-100).

## Acceptance criteria
- [x] Agent 1 correctly reads and follows `DOCTRINE.md`.
- [x] Agent 1 outputs JSON with a score and a short rationale.
- [x] System automatically categorizes jobs into `high-pass`, `edge-case`, or `rejected` based on thresholds.
- [x] Database state is updated to prevent re-processing seen jobs.

## Blocked by
- .scratch/project-vector/3-collector-seek.md
