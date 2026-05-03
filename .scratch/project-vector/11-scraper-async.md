---
id: 11
title: Concurrent Detail Page Scraping
status: needs-triage
labels: [needs-triage]
---

## Parent

#7 Production Readiness Improvements

## What to build
Refactor `src/collector.py` to optimize job detail scraping. Use `asyncio.Semaphore(3)` and `asyncio.gather()` to fetch up to 3 detail pages concurrently instead of awaiting them strictly sequentially. Strip tracking parameters from URLs before saving to ensure robust deduplication.

## Acceptance criteria
- [ ] Scraper batches detail requests concurrently up to a limit of 3.
- [ ] Deduplication correctly ignores URL tracking parameters.
- [ ] Total execution time for scraping jobs is demonstrably reduced.
- [ ] Tests verify that the semaphore enforces the concurrency limit.

## Blocked by
None - can start immediately
