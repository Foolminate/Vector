---
id: 10
title: LLM Client Wrapper with Retries and Cost Logging
status: needs-triage
labels: [needs-triage]
---

## Parent

#7 Production Readiness Improvements

## What to build
Extract all Gemini API interaction logic from `sorter.py` and `evaluator.py` into a new deep module `src/llm_client.py`. Wrap the calls using the `tenacity` library for exponential backoff retries. Extract token usage metadata from the Gemini response and log it to the database via the connection manager.

## Acceptance criteria
- [ ] `llm_client.py` isolates API logic and accepts system prompts.
- [ ] Transient API errors (e.g., 503) trigger `tenacity` retries.
- [ ] Token usage is recorded into the database cost log for every successful call.
- [ ] `sorter.py` and `evaluator.py` use the new client wrapper.
- [ ] Tests verify retry logic and token extraction via mocking.

## Blocked by
- #9 (DB Connection Context Manager & Cost Log)
