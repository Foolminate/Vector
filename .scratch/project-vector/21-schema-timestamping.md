# Issue: Schema & Evaluator Timestamping

## Parent
[.scratch/project-vector/20-dynamic-daily-digests.md](.scratch/project-vector/20-dynamic-daily-digests.md)

## What to build
Add the necessary database infrastructure to support grouping jobs by evaluation date. This involves adding an `evaluated_at` column and ensuring the evaluator populates it during its run.

## Acceptance criteria
- [ ] Migration `migrations/v6_add_evaluated_at.sql` adds `evaluated_at TIMESTAMP` to the `jobs` table.
- [ ] `src/evaluator.py` updates the `evaluated_at` column when saving a successful analysis.
- [ ] Automated test in `tests/test_evaluator.py` verifies the timestamp is set after evaluation.

## Blocked by
None - can start immediately
