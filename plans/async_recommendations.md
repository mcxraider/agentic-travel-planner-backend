# Async Optimization Recommendations

## Overview

The codebase is **entirely synchronous** despite running on FastAPI (an async framework). Every I/O-bound operation — LLM calls, file reads, file writes — blocks the event loop. This means concurrent requests queue up and each request holds the thread hostage during the ~1-3 second LLM call.

---

## 1. THE BIGGEST WIN: LLM Client — `agents/shared/llm/client.py`

**#1 bottleneck.** Every LLM call takes 500ms-3000ms+ and is fully synchronous.

| Function                        | Lines    | Problem                                                                                                        |
| ------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `call_llm_with_usage()`         | L52-L85  | Uses `client.chat.completions.create()` — the **synchronous** OpenAI SDK method. Blocks the entire event loop. |
| `get_llm_response_with_usage()` | L88-L116 | Wrapper that calls `call_llm_with_usage()` — also synchronous.                                                 |
| `get_cached_client()`           | L30-L43  | Creates `OpenAI()` (sync client). Needs to become `AsyncOpenAI()`.                                             |

**What to do:** Switch to `openai.AsyncOpenAI` and use `await client.chat.completions.create()`. The `openai` library (v2.16.0) fully supports this. The tenacity `@retry` decorator works with async via `@retry` on an `async def`.

**Impact: CRITICAL** — This is where 90%+ of request latency lives.

---

## 2. LangGraph Node Functions — `agents/clarification/nodes/clarification.py`

| Function               | Lines    | Problem                                                                                                         |
| ---------------------- | -------- | --------------------------------------------------------------------------------------------------------------- |
| `clarification_node()` | L44-L138 | Synchronous `def`. Calls the synchronous LLM client. Also does synchronous file I/O via `load_system_prompt()`. |

**What to do:** Convert to `async def clarification_node(state)`. LangGraph **natively supports async node functions** — if you define a node as `async def`, LangGraph will `await` it automatically. No changes needed in graph wiring.

**Inside this function, 3 I/O calls block:**

- `load_system_prompt(session_id)` — synchronous file read (session_store.py L67)
- `get_llm_response_with_usage(...)` — synchronous LLM call (1-3 seconds)
- `debug_logger.log_llm_call(...)` — synchronous file write (debug_logger.py L135)

---

## 3. Output Node — `agents/clarification/nodes/output.py`

| Function        | Lines   | Problem                                                                                                                                   |
| --------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `output_node()` | L30-L86 | Synchronous `def`. Does `json.dumps` + `print` (minor), but primarily should be async for LangGraph consistency and future extensibility. |

**Impact: LOW** (no heavy I/O currently), but should be `async def` for consistency since LangGraph will run it in the async context.

---

## 4. FastAPI Endpoints — `agents/clarification/clarification_api.py`

Endpoints are declared `async def`, but they call **synchronous** `graph.invoke()`:

| Endpoint                 | Line | Problem                                                                                                                   |
| ------------------------ | ---- | ------------------------------------------------------------------------------------------------------------------------- |
| `start_session()`        | L137 | `result = graph.invoke(initial_state, config)` — **synchronous call inside async handler**. Blocks the entire event loop. |
| `respond_to_questions()` | L327 | Same: `result = graph.invoke(next_state, config)` — blocks event loop.                                                    |

**What to do:** Use `graph.ainvoke()` instead of `graph.invoke()`. LangGraph provides `ainvoke()` as the async equivalent. This enables async node functions to actually run asynchronously.

**Additional sync operations inside these async handlers:**

- `save_system_prompt()` at L127 — synchronous file write
- `build_system_prompt_v2()` at L126 — CPU-bound (fine, but the file write after it isn't)
- `merge_user_responses_into_data()` and `merge_collected_data()` — CPU-bound (fine as-is)

**Impact: CRITICAL** — Using sync `invoke()` inside `async def` handlers negates all of FastAPI's concurrency benefits. Under concurrent requests, this serializes everything.

---

## 5. File-Based Cache (System Prompt) — `agents/shared/cache/session_store.py`

| Function                 | Lines     | Problem                                             |
| ------------------------ | --------- | --------------------------------------------------- |
| `save_system_prompt()`   | L41-L61   | `prompt_path.write_text()` — synchronous file write |
| `load_system_prompt()`   | L64-L86   | `prompt_path.read_text()` — synchronous file read   |
| `delete_session_cache()` | L89-L105  | `shutil.rmtree()` — synchronous directory deletion  |
| `cache_exists()`         | L108-L116 | `path.exists()` — synchronous filesystem check      |

**What to do:** Use `aiofiles` for async file I/O, or use `asyncio.to_thread()` to offload these to a thread pool. Since these are called from within the graph nodes (which should become async), they need to be awaitable.

**Impact: MODERATE** — File I/O is typically fast (microseconds), but under high concurrency it can add up, and more importantly, it blocks the event loop.

---

## 6. Debug Logger — `agents/shared/logging/debug_logger.py`

| Method                            | Lines     | Problem                                                         |
| --------------------------------- | --------- | --------------------------------------------------------------- |
| `_append_to_log()`                | L114-L121 | Opens file and writes JSON — synchronous `open()` + `f.write()` |
| `log_llm_call()`                  | L123-L168 | Calls `_append_to_log()` — blocks on file write                 |
| `log_api_timing()`                | L170-L200 | Calls `_append_to_log()` — blocks on file write                 |
| `log_session_summary()`           | L210-L232 | Calls `_append_to_log()` — blocks on file write                 |
| `extract_questions_to_markdown()` | L253-L333 | Reads and writes files synchronously                            |

**What to do:** Make `_append_to_log()` async with `aiofiles`, or use a background task/queue pattern (fire-and-forget logging). Logging should never block a user-facing request.

**Impact: MODERATE** — Called on every LLM call and API request. Under concurrency, multiple sessions writing to different files will contend.

---

## 7. Graph Construction — `agents/clarification/graph/build.py`

| Function                       | Lines   | Problem                                                                                            |
| ------------------------------ | ------- | -------------------------------------------------------------------------------------------------- |
| `create_clarification_graph()` | L18-L67 | Synchronous, but this is **fine** — it's a one-time setup cost, not per-request. No change needed. |

---

## Recommended Conversion Order (by impact)

```
Priority 1 (Critical - do these first):
  ├── LLM Client → AsyncOpenAI + async call_llm_with_usage()
  ├── clarification_node() → async def
  └── API endpoints → graph.ainvoke() instead of graph.invoke()

Priority 2 (Important):
  ├── session_store.py → aiofiles or asyncio.to_thread()
  └── debug_logger.py → async _append_to_log() or background queue

Priority 3 (Nice-to-have):
  └── output_node() → async def (for consistency)
```

---

## The Dependency Chain

The reason Priority 1 items must be done together is the **async chain rule**:

```
FastAPI async endpoint
  └── calls graph.ainvoke()          ← needs ainvoke
        └── runs clarification_node  ← needs async def
              └── calls LLM          ← needs AsyncOpenAI
```

If any link in this chain is synchronous, it blocks the event loop and negates the benefit of everything above it. That's why the current `async def start_session()` calling `graph.invoke()` is actually **worse** than a regular `def start_session()` — FastAPI would at least run a sync handler in a thread pool.

---

## What Does NOT Need to Be Async

- `should_continue()` in `nodes/routing.py` — pure CPU logic, no I/O
- `scoring.py` — pure computation
- `response_parser.py` — pure string/JSON parsing
- `prompts/builders.py` — pure string formatting
- `prompts/templates.py` — Pydantic models
- `schemas.py` — type definitions
- Graph construction (`build.py`) — one-time setup
