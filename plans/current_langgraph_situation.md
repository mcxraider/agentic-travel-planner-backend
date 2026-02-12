# LangGraph Architecture: Current State, Information Flow & Recommendations

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Your Desired Architecture vs What You Actually Have](#2-desired-vs-actual)
3. [Current Architecture Deep Dive](#3-current-architecture-deep-dive)
4. [Information Flow: Step by Step](#4-information-flow)
5. [Bad Coding Practices Found](#5-bad-coding-practices)
6. [What Needs to Change](#6-what-needs-to-change)
7. [File Reference](#7-file-reference)

---

## 1. Executive Summary

**The short answer: No, your codebase is NOT structured as a single pipeline.**

You want:
```
Entry → Clarification Agent (HITL) → Research Agent (parallel) → Planner Agent → END
```

What you actually have:
```
[Graph 1 - Clarification]          [Graph 2 - Orchestrator]
Entry → clarification_node         Entry → route_next_agent
         ↕ (HITL loop)                     ├→ research_node (mock, sequential)
      output_node → END                    ├→ planner_node (mock, sequential)
                                           └→ complete → END
```

These are **two completely separate LangGraph `StateGraph` instances** with **no connection between them**. The frontend is responsible for calling the clarification API first, extracting the output, and passing it into the orchestrator API as a second, independent call. There is no single graph that flows from clarification through research to planning.

Additionally, the research agent has **no parallel workflows** — it's a single synchronous mock node, not the parallel research architecture you described wanting.

---

## 2. Desired vs Actual

### What You Want

```
                         ┌─────────────────────────────┐
                         │      SINGLE LANGGRAPH        │
                         │                              │
  User Input ──────────► │  clarification_node          │
                         │       ↕ (HITL: pause/resume) │
                         │       ↓                      │
                         │  research_agent              │
                         │    ├─ parallel: flights      │
                         │    ├─ parallel: hotels       │
                         │    ├─ parallel: attractions   │
                         │    └─ aggregate results      │
                         │       ↓                      │
                         │  planner_agent               │
                         │       ↓                      │
                         │      END                     │
                         └─────────────────────────────┘
```

### What You Actually Have

```
  ┌────────────────────────────┐        ┌─────────────────────────────┐
  │  GRAPH 1: Clarification    │        │  GRAPH 2: Orchestrator      │
  │                            │        │                             │
  │  /api/clarification/start  │        │  /api/orchestrator/run      │
  │  /api/clarification/respond│        │                             │
  │                            │        │                             │
  │  clarification_node ◄──┐   │  API   │  route_next_agent           │
  │       │                │   │  gap   │    ├→ research_wrapper      │
  │       ▼                │   │ ◄────► │    │   (mock, sequential)   │
  │  should_continue()     │   │        │    ├→ planner_wrapper       │
  │    ├─ loop back ───────┘   │        │    │   (mock, sequential)   │
  │    └─ output_node → END    │        │    └→ complete → END        │
  └────────────────────────────┘        └─────────────────────────────┘
         ▲                                        ▲
         │           FRONTEND BRIDGES             │
         └────────────────────────────────────────┘
           Frontend calls /start, /respond until complete,
           then extracts clarification_output and POSTs it
           to /orchestrator/run as a separate request.
```

### Gap Summary

| Aspect | Desired | Actual | Status |
|--------|---------|--------|--------|
| Single unified graph | One graph, entry to end | Two separate graphs | **Missing** |
| Clarification → Research handoff | Automatic (within graph) | Manual (frontend bridges the gap via API) | **Missing** |
| Research: parallel sub-agents | Parallel workflows (flights, hotels, POIs) | Single mock function call, no parallelism | **Missing** |
| Planner agent | LLM-powered planning | Mock data generator | **Skeleton only** |
| Research agent | LLM-powered research | Mock data generator | **Skeleton only** |
| Human-in-the-loop | Clarification only | Clarification only | **Correct** |
| Contract-based handoffs | Between all agents | Defined but not fully exercised | **Partial** |

---

## 3. Current Architecture Deep Dive

### 3.1 Clarification Graph

**Files:** `agents/clarification/graph/build.py`, `agents/clarification/nodes/`, `agents/clarification/schemas.py`

```python
# From agents/clarification/graph/build.py
graph = StateGraph(ClarificationState)
graph.add_node("clarification", clarification_node)
graph.add_node("output", output_node)
graph.set_entry_point("clarification")
graph.add_conditional_edges("clarification", should_continue, {
    "clarification": "clarification",   # Loop back
    "output": "output",                 # Done
})
graph.add_edge("output", END)
app = graph.compile(checkpointer=MemorySaver(), interrupt_after=["clarification"])
```

**How HITL works:**
1. `interrupt_after=["clarification"]` pauses graph execution after the clarification node runs
2. `MemorySaver()` checkpointer stores the graph state at the pause point
3. When the user responds via `/api/clarification/respond`, the API merges user responses into state and calls `graph.invoke(next_state, config)` which resumes from the checkpoint
4. The routing function `should_continue()` decides: loop or output

**State schema (`ClarificationState`):**
- 6 user context fields (name, citizenship, health info, etc.)
- 9 trip basics (destination, dates, budget, etc.)
- 3 process state fields (round, score, complete flag)
- 5 data collection fields (questions, responses, data accumulator)
- 1 tracking field (session_id)

**What it produces:** `ClarificationOutputV2` — a Pydantic model with tiered preferences (Tier 1 critical through Tier 4 optimization), conflict resolutions, and completeness score.

### 3.2 Orchestrator Graph

**Files:** `agents/graph/build.py`, `agents/graph/router.py`, `agents/graph/state.py`

```python
# From agents/graph/build.py
graph = StateGraph(OrchestratorState)
graph.add_node("research_node", _research_wrapper)
graph.add_node("planner_node", _planner_wrapper)
graph.add_node("complete", _complete_node)
graph.set_conditional_entry_point(route_next_agent, {
    "research_node": "research_node",
    "planner_node": "planner_node",
    "complete": "complete",
})
# After each node, re-route to determine next step
graph.add_conditional_edges("research_node", route_next_agent, {...})
graph.add_conditional_edges("planner_node", route_next_agent, {...})
graph.add_edge("complete", END)
app = graph.compile()  # No checkpointer, no interrupts
```

**Key design decision:** Wrapper nodes adapt `OrchestratorState` → agent-specific state, call the agent node function directly, and merge results back. This avoids LangGraph sub-graph state schema conflicts but means research/planner don't run as their own compiled graphs within the orchestrator.

**Routing logic (`route_next_agent`):**
```python
if research_output is None → "research_node"
elif planner_output is None → "planner_node"
else → "complete"
```

This is strictly sequential: research always runs before planner.

### 3.3 Research Agent (Stub)

**Files:** `agents/research/nodes/research.py`, `agents/research/mock_data.py`

- Single node: `research_node()` calls `generate_mock_research()` → validates against `ResearchOutputV1`
- No LLM calls, no parallel workflows, no sub-graph
- The `agents/research/graph/build.py` defines a trivial `research_node → END` graph, but this graph is **never used** — the orchestrator calls the node function directly via the wrapper

**Mock output structure:**
- `CityResearch` with points of interest per city
- `LogisticsInfo` (currency, transport, safety)
- `BudgetAnalysis` (category breakdowns)

### 3.4 Planner Agent (Stub)

**Files:** `agents/planner/nodes/planner.py`, `agents/planner/mock_data.py`

- Single node: `planner_node()` calls `generate_mock_itinerary()` → validates against `PlannerOutputV1`
- No LLM calls, no optimization logic
- Same pattern as research — `agents/planner/graph/build.py` defines a graph that is never used

**Mock output structure:**
- `ItineraryDay` with events, themes, costs per day
- `CostSummary` with budget breakdown

### 3.5 Shared Contracts

**Files:** `agents/shared/contracts/`

Three Pydantic models define what each agent produces:
- `ClarificationOutputV2` → preferences, conflicts, score
- `ResearchOutputV1` → city research, POIs, logistics, budget analysis
- `PlannerOutputV1` → itinerary days, events, cost summary

These are well-defined and are the **strongest part of the architecture** — they provide clear boundaries between agents.

---

## 4. Information Flow

### 4.1 End-to-End Flow (How It Actually Works Today)

```
STEP 1: Frontend → POST /api/clarification/start
        Body: { user_name, destination, dates, budget, ... }

        Backend: Creates ClarificationState → invokes clarification graph
                 Graph pauses after clarification_node (HITL interrupt)

        Response: { session_id, round: 1, questions: [...], state, data }

STEP 2: Frontend → POST /api/clarification/respond  (repeat 2-4 times)
        Body: { session_id, responses: { field: value, ... } }

        Backend: Merges responses into state.data (server-side)
                 Increments round → resumes graph from checkpoint
                 clarification_node runs → should_continue() checks score

        Response: { questions: [...] } OR { complete: true, data: {...} }

        ── FRONTEND MANUALLY EXTRACTS clarification_output HERE ──

STEP 3: Frontend → POST /api/orchestrator/run
        Body: { destination, dates, budget, ..., clarification_output: {...} }

        Backend: Creates OrchestratorState → invokes orchestrator graph
                 route_next_agent → research_wrapper → route → planner_wrapper → complete
                 ALL runs in one synchronous invoke() call

        Response: { research_output: {...}, planner_output: {...} }
```

### 4.2 Data Flow Between Agents

```
ClarificationState                    OrchestratorState
┌──────────────────┐                  ┌──────────────────────┐
│ user_name        │                  │ destination          │
│ destination      │   Frontend       │ start_date           │
│ start_date       │   copies         │ budget               │
│ budget           │ ──────────────►  │ ...                  │
│ ...              │   trip fields    │                      │
│                  │                  │ clarification_output  │
│ data: {          │   Frontend       │   (dict from V2)     │
│   activity_prefs │   copies as      │                      │
│   pace_pref      │ ──────────────►  │                      │
│   dining_style   │   single dict    │                      │
│   ...            │                  │                      │
│ }                │                  │                      │
└──────────────────┘                  └──────────┬───────────┘
                                                 │
                                      ┌──────────▼───────────┐
                                      │ _research_wrapper     │
                                      │  Extracts:           │
                                      │   - trip context     │
                                      │   - activity_prefs   │
                                      │   - pace_preference  │
                                      │   - dining_style     │
                                      │   - accommodation    │
                                      │   - mobility_level   │
                                      │  Calls research_node │
                                      │  Returns:            │
                                      │   research_output    │
                                      └──────────┬───────────┘
                                                 │
                                      ┌──────────▼───────────┐
                                      │ _planner_wrapper      │
                                      │  Extracts:           │
                                      │   - trip context     │
                                      │   - activity_prefs   │
                                      │   - pace_preference  │
                                      │   - dining_style     │
                                      │   - daily_rhythm     │
                                      │   - arrival/departure│
                                      │   - research_output  │  ◄── from previous step
                                      │  Calls planner_node  │
                                      │  Returns:            │
                                      │   planner_output     │
                                      └──────────┬───────────┘
                                                 │
                                      ┌──────────▼───────────┐
                                      │ _complete_node        │
                                      │  Logs completion     │
                                      │  Returns to END      │
                                      └──────────────────────┘
```

### 4.3 What the Wrappers Actually Do

The orchestrator uses **wrapper functions** (not sub-graphs) to bridge state schemas. This is because:
- `OrchestratorState` has different fields than `ResearchState` or `PlannerState`
- LangGraph sub-graphs require matching state schemas
- Wrappers manually extract relevant fields, call the node, and merge results back

```python
# Simplified version of what _research_wrapper does:
def _research_wrapper(state: OrchestratorState) -> Dict:
    clarification = state.get("clarification_output") or {}
    research_state = {
        "destination": state["destination"],
        "budget": state["budget"],
        "activity_preferences": clarification.get("activity_preferences"),
        # ... extract ~14 fields manually
    }
    result = _research_node(research_state)
    return {"research_output": result.get("research_output")}
```

---

## 5. Bad Coding Practices Found

### 5.1 CRITICAL: Debug Print Statements in Production Code

**Files affected:**
- `agents/clarification/nodes/clarification.py` — Lines 73, 97-99, 122-125, 136-140, 146, 151
- `agents/clarification/clarification_api.py` — Line 202
- `agents/shared/cache/session_store.py` — Line 83 (per agent report)

```python
# clarification.py:97-99
print("\n" + "=" * 80)
print(f"🤖 Round {state['current_round']} - Calling LLM (v2)")
print("=" * 80)

# clarification.py:122-125
print(f"\n📈 Token Usage: {usage['input_tokens']} in / {usage['output_tokens']} out")
print(f"⏱️  LLM Duration: {duration_ms:.2f}ms")

# clarification.py:73
print("CACHE MISS: Rebuilt system prompt")

# clarification_api.py:202
print(result)  # Dumps entire state dict to stdout
```

**Why it's bad:** These bypass the structured logging system you already built (`DebugLogger`). In production, `print()` goes to stdout unstructured, can't be filtered/searched, and the `print(result)` on line 202 dumps potentially sensitive user data to stdout.

**Fix:** Replace all `print()` with `logger.info()` / `logger.debug()` calls.

### 5.2 CRITICAL: Logger Configuration at Module Level

**File:** `agents/clarification/nodes/clarification.py` — Lines 28-37

```python
logger = logging.getLogger("agents.clarification")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
```

**Why it's bad:** This adds a new handler every time the module is imported. If the module is re-imported (e.g., during testing or hot-reload), you get **duplicate log lines**. Logger configuration should happen once in the application entry point, not in individual modules.

**Fix:** Configure logging once in `agents/main.py` or a `logging_config.py`. Individual modules should only call `logging.getLogger(__name__)`.

### 5.3 HIGH: Generic Exception Retry

**File:** `agents/shared/llm/client.py` — Lines 45-50

```python
@retry(
    retry=retry_if_exception_type((Exception,)),  # Catches EVERYTHING
)
```

**Why it's bad:** This retries on ALL exceptions, including `ValueError`, `KeyError`, `TypeError`, etc. These are programming errors that should fail fast, not be retried. Only transient errors (rate limits, timeouts, network errors) should trigger retries.

**Fix:** Use specific OpenAI exceptions:
```python
from openai import APIError, RateLimitError, APITimeoutError
retry=retry_if_exception_type((APIError, RateLimitError, APITimeoutError))
```

### 5.4 HIGH: No Client Timeout Configuration

**File:** `agents/shared/llm/client.py` — Line 41

```python
_client = OpenAI(api_key=api_key)  # No timeout!
```

**Why it's bad:** If OpenAI's API hangs, your server thread hangs indefinitely. The tenacity retry won't help because the call never returns to trigger a retry.

**Fix:** `_client = OpenAI(api_key=api_key, timeout=60.0)`

### 5.5 HIGH: Memory Leaks in Session Management

**File:** `agents/clarification/clarification_api.py` — Lines 42, 361-363

```python
_sessions: Dict[str, Dict[str, Any]] = {}  # Grows forever

# Cleanup is commented out:
# remove_logger(session_id)
# delete_session_cache(session_id)
```

**Why it's bad:** Sessions, loggers, and cache files accumulate indefinitely. In a long-running server, this will consume increasing memory and disk space. The cleanup code exists but is commented out.

**Fix:** Uncomment cleanup code. Add TTL-based session expiry. Consider Redis or a proper session store.

### 5.6 MEDIUM: Research/Planner Sub-Graphs Are Built But Never Used

**Files:** `agents/research/graph/build.py`, `agents/planner/graph/build.py`

Both files define `create_research_graph()` / `create_planner_graph()` functions that build LangGraph `StateGraph` instances. However, the orchestrator calls the node functions directly via wrappers — these compiled graphs are dead code.

**Why it's bad:** Confusing for developers. Creates the impression that these sub-graphs are used somewhere when they're not. If someone modifies these graphs thinking it will change behavior, nothing happens.

**Fix:** Either remove the sub-graph builders (if you'll always use the wrapper pattern), or refactor the orchestrator to actually use sub-graphs.

### 5.7 MEDIUM: Duplicated State Field Extraction

**File:** `agents/graph/build.py` — `_research_wrapper` and `_planner_wrapper`

Both wrappers manually extract ~14 fields from `OrchestratorState` into agent-specific state dicts. This extraction logic is fragile — if you add a field to `ResearchState`, you must remember to also update the wrapper.

**Fix:** Create a state adapter utility, or use LangGraph's sub-graph support with proper state schema mapping.

### 5.8 MEDIUM: Inline `traceback.print_exc()` Import

**File:** `agents/clarification/nodes/clarification.py` — Lines 152-154

```python
except Exception as e:
    import traceback       # Import inside except block
    traceback.print_exc()  # Print to stdout
```

**Why it's bad:** Lazy import inside an exception handler, printing to stdout instead of using the logger. The logger can capture the traceback via `logger.exception()`.

**Fix:** `logger.exception(f"Error in clarification_node: {e}")`

### 5.9 MEDIUM: Graph Recreated Per Request

**File:** `agents/graph/orchestrator_api.py` — Line 89

```python
@router.post("/run")
async def run_orchestrator(request):
    graph = create_orchestrator_graph()  # New graph every request!
```

Compare with the clarification API which correctly caches its graph:
```python
# agents/clarification/clarification_api.py
_graph = None
def get_graph():
    global _graph
    if _graph is None:
        _graph = create_clarification_graph()
    return _graph
```

**Fix:** Cache the orchestrator graph the same way the clarification graph is cached.

### 5.10 LOW: Inconsistent Naming Between Env Var and Convention

**File:** `agents/shared/llm/client.py` — Line 35

```python
api_key = os.environ.get("OPENAI_API_KEY_1")  # Why "_1"?
```

The `_1` suffix is unconventional and confusing. Standard practice is `OPENAI_API_KEY`.

### 5.11 LOW: CORS Allows All Origins

**File:** `agents/main.py` — Lines 23-28

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Wide open
)
```

Fine for development, but the comment says "Configure appropriately for production" — this should be addressed before deployment.

---

## 6. What Needs to Change

### 6.1 Unify Into a Single Pipeline (Structural Change)

To achieve your desired `Entry → Clarification → Research → Planner → END` flow, you have two options:

**Option A: Single Graph with HITL (Recommended)**

Build one `StateGraph` that contains all agents. The clarification portion uses `interrupt_after` for HITL, then automatically flows into research and planner once clarification completes.

```
Entry → clarification_node  ←──┐ (HITL loop)
             │                 │
        should_continue() ─────┘
             │ (complete)
             ▼
        research_subgraph (with parallel branches)
             │
             ▼
        planner_node
             │
             ▼
            END
```

This eliminates the frontend bridging problem — the orchestrator picks up automatically after clarification completes.

**Option B: Keep Separate Graphs, Add Backend Bridging**

Keep the two graphs separate but add a backend endpoint that chains them:
```python
@router.post("/plan-trip")
async def plan_trip():
    # Run clarification to completion (multi-turn with HITL)
    # Then automatically invoke orchestrator with clarification output
```

This is simpler to implement but less elegant than Option A.

### 6.2 Add Parallel Research Workflows

Your research agent should use LangGraph's parallel execution. Instead of a single `research_node`, structure it as:

```
research_entry → fan_out
                  ├─ attractions_researcher (parallel)
                  ├─ logistics_researcher (parallel)
                  ├─ dining_researcher (parallel)
                  └─ budget_researcher (parallel)
                aggregate_results → research_output
```

LangGraph supports this via `Send()` API or by defining multiple branches from a single node.

### 6.3 Replace Mock Data with LLM Calls

Both `research_node` and `planner_node` currently call mock data generators. These need to be replaced with:
1. System/user prompt construction (similar to how clarification does it)
2. LLM calls via `get_llm_response_with_usage()`
3. Structured output parsing (similar to `parse_clarification_response_v2()`)

### 6.4 Clean Up Logging

1. Remove ALL `print()` statements
2. Configure logging once in `agents/main.py`
3. Individual modules use only `logger = logging.getLogger(__name__)`

### 6.5 Fix LLM Client

1. Add timeout to OpenAI client
2. Use specific exception types for retry
3. Rename env var to `OPENAI_API_KEY` (or keep `_1` if you have multiple keys, but document why)

### 6.6 Fix Session Management

1. Uncomment cleanup code
2. Add TTL-based session expiry
3. Cache the orchestrator graph instance (like clarification does)

---

## 7. File Reference

### Core Architecture Files

| File | Purpose | Status |
|------|---------|--------|
| `agents/main.py` | FastAPI entry point, logging config, mounts routers | **Updated** - centralized logging |
| `agents/clarification/graph/build.py` | Clarification LangGraph construction | Clean |
| `agents/clarification/graph/config.py` | Graph config (rounds, model, interrupts) | Clean |
| `agents/clarification/nodes/clarification.py` | Main clarification node (LLM calls) | **Fixed** - structured logging, no prints |
| `agents/clarification/nodes/routing.py` | should_continue() routing logic | **Updated** - logs routing decisions |
| `agents/clarification/nodes/output.py` | Final output formatting | **Fixed** - structured logging, no prints |
| `agents/clarification/clarification_api.py` | Clarification REST endpoints | **Updated** - HITL state logging |
| `agents/clarification/schemas.py` | ClarificationState + API models | Clean |
| `agents/clarification/prompts/templates.py` | V2 system prompt template | Clean |
| `agents/clarification/prompts/builders.py` | Prompt construction functions | Clean |
| `agents/clarification/response_parser.py` | LLM response JSON parsing | Has dead code |
| `agents/graph/build.py` | Orchestrator graph construction | **Updated** - node entry/exit logging |
| `agents/graph/router.py` | route_next_agent() logic | **Updated** - logs routing decisions |
| `agents/graph/state.py` | OrchestratorState schema | Clean |
| `agents/graph/orchestrator_api.py` | Orchestrator REST endpoint | **Updated** - pipeline lifecycle logging |
| `agents/research/nodes/research.py` | Research node (mock) | **Updated** - structured logging |
| `agents/research/mock_data.py` | Mock research data generator | Working |
| `agents/research/graph/build.py` | Research sub-graph (UNUSED) | Dead code |
| `agents/planner/nodes/planner.py` | Planner node (mock) | **Updated** - structured logging |
| `agents/planner/mock_data.py` | Mock itinerary data generator | Working |
| `agents/planner/graph/build.py` | Planner sub-graph (UNUSED) | Dead code |
| `agents/shared/llm/client.py` | OpenAI client + retry | **Fixed** - timeout, specific exceptions |
| `agents/shared/contracts/clarification_output.py` | ClarificationOutputV2 | Clean |
| `agents/shared/contracts/research_output.py` | ResearchOutputV1 | Clean |
| `agents/shared/contracts/planner_output.py` | PlannerOutputV1 | Clean |
| `agents/shared/logging/debug_logger.py` | Per-session JSON logging | Clean |
| `agents/shared/cache/session_store.py` | System prompt file cache | **Fixed** - no prints |

---

## 8. Fixes Applied (2026-02-12)

### 8.1 Resolved Issues

The following issues from Section 5 have been fixed:

| Issue | Status | What Changed |
|-------|--------|-------------|
| 5.1 Debug print statements | **FIXED** | All `print()` removed from production code (clarification_node, output_node, clarification_api, session_store). Replaced with `logger.info()` / `logger.debug()` |
| 5.2 Module-level logger config | **FIXED** | Handler/formatter setup removed from clarification_node.py and output_node.py. All modules now use `logger = logging.getLogger(__name__)` only |
| 5.3 Generic exception retry | **FIXED** | Retry now targets `APIError, RateLimitError, APITimeoutError, APIConnectionError` instead of `Exception` |
| 5.4 No client timeout | **FIXED** | Added `timeout=60.0` to `OpenAI()` constructor |
| 5.8 Inline traceback import | **FIXED** | Replaced `import traceback; traceback.print_exc()` with `logger.exception()` |

### 8.2 Centralized Logging Configuration

Added to `agents/main.py` — single source of truth for log formatting:

```python
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, ...)
```

Third-party loggers (httpcore, httpx, openai) silenced to WARNING level.

### 8.3 Structured Debug Logging

Every log line now includes a **structured prefix** for grep-ability:

```
[session=<uuid>] [graph=<graph_name>] [node=<node_name>] <message>
```

This allows filtering by:
- **Session**: `grep "session=abc-123"` — trace one user's entire journey
- **Graph**: `grep "graph=clarification"` or `grep "graph=orchestrator"`
- **Node**: `grep "node=clarification"`, `grep "node=research"`, `grep "node=planner"`, etc.
- **Router**: `grep "router="` — see all routing decisions
- **API**: `grep "api=start"`, `grep "api=respond"`, `grep "api=run"`
- **HITL**: `grep "WAITING FOR HUMAN FEEDBACK"` — see exactly when graph pauses

### 8.4 What Gets Logged Now

**Clarification Graph:**

| Event | Log Level | Example |
|-------|-----------|---------|
| Node entry | INFO | `[session=...] [graph=clarification] [node=clarification] Entering node \| round=1, score=0/100` |
| LLM call start | INFO | `... Calling LLM \| model=gpt-4.1-mini, filled_fields=0/18` |
| LLM response | INFO | `... LLM responded \| duration=1234ms, tokens_in=500, tokens_out=200` |
| Node finish | INFO | `... Node finished \| complete=false, score=45/100, questions_generated=4` |
| HITL pause | INFO | `... will pause for human feedback (interrupt_after=clarification)` |
| Router decision | INFO | `[session=...] [graph=clarification] [router=should_continue] Routing to 'clarification' (loop)` |
| Session start | INFO | `[session=...] [graph=clarification] [api=start] New session \| destination=Bali` |
| Graph paused | INFO | `... Graph paused (interrupt_after=clarification) \| WAITING FOR HUMAN FEEDBACK` |
| Human feedback | INFO | `[session=...] [graph=clarification] [api=respond] Human feedback received \| fields_answered=[...]` |
| Graph resume | INFO | `... Resuming graph from checkpoint \| current_round=1, score=45/100` |
| Graph complete | INFO | `... Graph completed \| score=89/100, total_rounds=3, next_node=output -> END` |

**Orchestrator Graph:**

| Event | Log Level | Example |
|-------|-----------|---------|
| Pipeline start | INFO | `[session=...] [graph=orchestrator] [api=run] Pipeline starting \| destination=Bali, duration=4d` |
| Router decision | INFO | `[session=...] [graph=orchestrator] [router=route_next_agent] Routing to 'research_node'` |
| Research wrapper | INFO | `... [node=research_wrapper] Entering node \| destination=Bali` |
| Research node | INFO | `... [node=research] Research complete \| cities=2, pois=12` |
| Planner wrapper | INFO | `... [node=planner_wrapper] Entering node \| research_available=True` |
| Planner node | INFO | `... [node=planner] Planning complete \| days=4, events=20, cost=$1200/1500` |
| Pipeline complete | INFO | `... [node=complete] Pipeline complete \| research=done, planner=done, errors=0 -> END` |
| Pipeline finish | INFO | `... [api=run] Pipeline finished \| status=complete` |

### 8.5 Sample Log Output

A full orchestrator run now produces logs like:

```
2026-02-12 14:30:01 | INFO     | agents.graph.orchestrator_api      | [session=abc-123] [graph=orchestrator] [api=run] Pipeline starting | destination=Bali, Indonesia, duration=4d, budget=1500.0 USD, has_clarification=True
2026-02-12 14:30:01 | INFO     | agents.graph.orchestrator_api      | [session=abc-123] [graph=orchestrator] [api=run] Invoking orchestrator graph | entry=route_next_agent
2026-02-12 14:30:01 | INFO     | agents.graph.router                | [session=abc-123] [graph=orchestrator] [router=route_next_agent] Routing to 'research_node' | research=False, planner=False
2026-02-12 14:30:01 | INFO     | agents.graph.build                 | [session=abc-123] [graph=orchestrator] [node=research_wrapper] Entering node | destination=Bali, Indonesia, duration=4d, budget=1500.0 USD
2026-02-12 14:30:01 | INFO     | agents.research.nodes.research     | [session=abc-123] [graph=orchestrator] [node=research] Entering node | destination=Bali, Indonesia, cities=['Ubud', 'Seminyak']
2026-02-12 14:30:01 | INFO     | agents.research.nodes.research     | [session=abc-123] [graph=orchestrator] [node=research] Research complete | cities=2, pois=12, budget_assessment=comfortable
2026-02-12 14:30:01 | INFO     | agents.graph.build                 | [session=abc-123] [graph=orchestrator] [node=research_wrapper] Research node returned successfully
2026-02-12 14:30:01 | INFO     | agents.graph.router                | [session=abc-123] [graph=orchestrator] [router=route_next_agent] Routing to 'planner_node' | research=True, planner=False
2026-02-12 14:30:01 | INFO     | agents.graph.build                 | [session=abc-123] [graph=orchestrator] [node=planner_wrapper] Entering node | research_available=True, destination=Bali, Indonesia
2026-02-12 14:30:01 | INFO     | agents.planner.nodes.planner       | [session=abc-123] [graph=orchestrator] [node=planner] Entering node | destination=Bali, Indonesia, duration=4d, research_available=True
2026-02-12 14:30:01 | INFO     | agents.planner.nodes.planner       | [session=abc-123] [graph=orchestrator] [node=planner] Planning complete | days=4, events=20, cost=$1050.00/1500.0
2026-02-12 14:30:01 | INFO     | agents.graph.build                 | [session=abc-123] [graph=orchestrator] [node=planner_wrapper] Planner node returned successfully
2026-02-12 14:30:01 | INFO     | agents.graph.router                | [session=abc-123] [graph=orchestrator] [router=route_next_agent] Routing to 'complete' | research=True, planner=True
2026-02-12 14:30:01 | INFO     | agents.graph.build                 | [session=abc-123] [graph=orchestrator] [node=complete] Pipeline complete | research=done, planner=done, errors=0 -> END
2026-02-12 14:30:01 | INFO     | agents.graph.orchestrator_api      | [session=abc-123] [graph=orchestrator] [api=run] Pipeline finished | status=complete, research=done, planner=done, errors=0, messages=4
```

### 8.6 Remaining Issues (Not Yet Fixed)

| Issue | Priority | Status |
|-------|----------|--------|
| 5.5 Memory leaks (session cleanup commented out) | HIGH | Open |
| 5.6 Research/planner sub-graphs never used (dead code) | MEDIUM | Open |
| 5.7 Duplicated state field extraction in wrappers | MEDIUM | Open |
| 5.9 Orchestrator graph recreated per request | MEDIUM | Open |
| 5.10 Env var naming (`OPENAI_API_KEY_1`) | LOW | Open |
| 5.11 CORS allows all origins | LOW | Open |

### 8.7 Test Results

All 19 tests passing after changes:

```
agents/tests/test_orchestrator.py - 19 passed, 0 failed (0.62s)

TestOrchestratorPipeline:     7/7 passed
TestContracts:                4/4 passed
TestResearchStandalone:       2/2 passed
TestPlannerStandalone:        3/3 passed
TestRouter:                   3/3 passed
```

---

*Report generated from codebase analysis on 2026-02-12. Updated with fixes on 2026-02-12.*
