# Issue: Digest Manager Deep Module

## Parent
[.scratch/project-vector/20-dynamic-daily-digests.md](.scratch/project-vector/20-dynamic-daily-digests.md)

## What to build
Extract the digest aggregation and rendering logic into a new deep module `src/digest_manager.py`. This module will serve as the single source of truth for grouping jobs by date and generating markdown content for both the TUI and static file exports.

## Acceptance criteria
- [ ] `src/digest_manager.py` implemented with `get_available_dates()` and `render_digest(date)`.
- [ ] Logic correctly handles Hamiltonian/Remote priority sorting and inclusion of human notes.
- [ ] `src/evaluator.py` is refactored to use `DigestManager` for its static file exports.
- [ ] New unit tests in `tests/test_digest_manager.py` cover aggregation and markdown formatting.

## Blocked by
- [.scratch/project-vector/21-schema-timestamping.md](.scratch/project-vector/21-schema-timestamping.md)
