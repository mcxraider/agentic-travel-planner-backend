# Project Status Report
*Generated: 2026-03-24*

---

## Summary

**Trippi** is a Python FastAPI + LangGraph backend for AI-powered trip planning. The Clarification Agent is production-ready; the Research and Planner agents are scaffolded with mock data; the Validator agent is planned but not started. Infrastructure is solid but uses in-memory sessions (not production-safe).

---

## What's Been Implemented

### ✅ Clarification Agent — Production-Ready

- **LangGraph workflow**: Entry → `clarification_node` → `should_continue` router → loop or → `output_node` → END
- **Human-in-the-loop**: `interrupt_after=["clarification"]` pauses between rounds for user input
- **State checkpointing**: `MemorySaver` for resumable sessions across requests
- **v2 tiered scoring system** (code-based, not LLM-based):
  - Tier 1 Critical (10 pts each): activity_preferences, pace_preference, tourist_vs_local, mobility_level, dining_style
  - Tier 2 Planning Essentials (4 pts each): top_3_must_dos, transportation_mode, arrival/departure_time, budget_priority, accommodation_style
  - Tier 3 Conditional Critical (3 pts, escalates to Tier 1): wifi_need, dietary_severity, accessibility_needs
  - Tier 4 Optimization (3 pts each): special_logistics, daily_rhythm, downtime_preference
  - Stopping: score ≥ 85 + all Tier 1 complete, OR score ≥ 85 alone, OR round 4 forced stop
- **Typed prompt templates**: Pydantic-validated system/user prompt construction
- **System prompt caching**: Static prompts written to disk per session for OpenAI's cache prefix optimization
- **Per-session debug logging**: JSON Lines format with token usage, cost tracking, extracted questions
- **API endpoints**: Start, respond, session status, delete, health

### ✅ Orchestrator — Complete

- **Sequential pipeline**: research → planner
- **State adapters**: Wrapper nodes convert OrchestratorState ↔ agent-specific states
- **Error collection**: Errors collected per-agent, not propagated (graceful degradation)
- **Routing logic**: Determined by which outputs have been populated
- **API endpoint**: `POST /api/orchestrator/run`

### ✅ Shared Infrastructure — Complete

| Module | What it does |
|--------|-------------|
| `shared/llm/client.py` | OpenAI client singleton, tenacity retry (3 attempts, exponential 2–10s), token tracking |
| `shared/cache/session_store.py` | File-based system prompt cache per session |
| `shared/logging/debug_logger.py` | Per-session JSON logs, cost calculation, question extraction |
| `shared/contracts/` | Output contracts: `ClarificationOutputV2`, `ResearchOutputV1`, `PlannerOutputV1` |

### ✅ Tests — Basic Coverage

- `tests/test_clarification.py` — Interactive and automated clarification agent tests
- `tests/test_orchestrator.py` — Full pipeline tests with mock data
- `tests/test_scoring.py` — Completeness scoring unit tests

---

## What's Partially Done (Mock / Scaffold Only)

### ⚠️ Research Agent — Mock Data Only

- Data structure validated via `ResearchOutputV1` contract ✅
- Content is **hardcoded generic mock data** (temple, market, nature, beach, restaurant, museum)
- No real LLM calls, no external APIs
- **Missing**:
  - [ ] LLM-based research using clarification output
  - [ ] Google Places / TripAdvisor / weather API integrations
  - [ ] Dynamic POI generation filtered by preferences, budget, accessibility
  - [ ] Real pricing and ratings

### ⚠️ Planner Agent — Mock Data Only

- Data structure validated via `PlannerOutputV1` contract ✅
- Content is **hardcoded generic mock itinerary** (cycles: breakfast, market, temple, lunch, tour, shopping, dinner)
- **Missing**:
  - [ ] LLM-based itinerary generation using research output
  - [ ] Constraint satisfaction: budget, must-dos, pace, mobility
  - [ ] Transport routing (Google Maps API or similar)
  - [ ] Schedule optimization (distance, opening hours, transit time)
  - [ ] Conflict resolution (timing overflows, closures)

### ⚠️ Response Parser — v1 Dead Code

- v2 parsing is complete and correct
- v1 backward-compatibility parsing still present but unused
- **Missing**: Cleanup of dead v1 code

---

## What's Not Implemented Yet

### ❌ Validator Agent — Not Started

- Planned in `main.py` (`"status": "planned"`)
- Purpose: Check generated itinerary for conflicts, unreachable events, budget overruns
- Needs: LangGraph graph, schema, node, API endpoint, output contract

### ❌ FastAPI Best Practices — Not Applied

The current FastAPI structure is functional but does not follow production best-practices. See the **FastAPI TODOs** section below.

### ❌ Database / Persistence

- Sessions stored in a global Python dict (`_sessions`) — lost on server restart
- Not thread-safe under concurrent requests
- **Needs**: Redis (session state) or PostgreSQL (persistent history)

### ❌ Authentication / Authorization

- CORS open to `"*"`
- No API key, JWT, or OAuth
- All endpoints publicly accessible

### ❌ Async Execution

- All FastAPI handlers use `def` not `async def`
- `graph.invoke()` is synchronous — blocks the event loop
- **Needs**: `async def` handlers + `graph.ainvoke()` for concurrent request handling

### ❌ Streaming

- No streaming responses for long-running LLM calls
- Users wait for full response before anything renders

### ❌ Rate Limiting

- No per-IP or per-session limits
- Open to abuse

### ❌ DevOps

- No `Dockerfile` or `docker-compose.yml`
- No CI/CD pipeline
- No environment-based config (dev/staging/prod)
- Model name (`gpt-4.1-mini`) hardcoded in multiple places

---

## FastAPI Best Practices TODOs

These are structural improvements your friend flagged. The current setup is functional but needs hardening:

### 1. Project Structure — Adopt Router-per-Domain Pattern

```
agents/
├── main.py                     # App factory only
├── core/
│   ├── config.py               # Settings via pydantic-settings
│   ├── dependencies.py         # Shared FastAPI Depends()
│   ├── exceptions.py           # Custom exception classes
│   └── middleware.py           # Request ID, logging middleware
├── api/
│   ├── v1/
│   │   ├── router.py           # Aggregate all v1 routers
│   │   ├── clarification.py    # Only the HTTP layer
│   │   └── orchestrator.py     # Only the HTTP layer
│   └── health.py
└── services/                   # Business logic (separate from HTTP)
    ├── clarification_service.py
    └── orchestrator_service.py
```

**TODO**: Move business logic out of `clarification_api.py` into a service layer. API files should only handle request/response, not session management.

### 2. Settings Management — Use `pydantic-settings`

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    model_name: str = "gpt-4.1-mini"
    max_clarification_rounds: int = 4
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

**TODO**: Replace scattered `os.environ.get()` and hardcoded model names with a single `settings` object.

### 3. Dependency Injection — Use `Depends()`

```python
# core/dependencies.py
from functools import lru_cache
from agents.core.config import Settings

@lru_cache
def get_settings() -> Settings:
    return Settings()

async def get_session_store() -> SessionStore:
    ...  # yield a store instance
```

**TODO**: Inject `settings`, `session_store`, `llm_client`, and `logger` via `Depends()` instead of importing globals.

### 4. Exception Handling — Centralized Handlers

```python
# core/exceptions.py
class SessionNotFoundError(Exception): ...
class ParseError(Exception): ...
class RoundLimitExceededError(Exception): ...

# main.py
@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

**TODO**: Replace bare `HTTPException(status_code=404)` calls spread across route handlers with typed exception classes + registered handlers.

### 5. Middleware — Request ID + Structured Logging

```python
# core/middleware.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

**TODO**: Add `RequestIDMiddleware` so every request gets a traceable ID. Add request logging middleware (method, path, status, duration).

### 6. API Versioning — Prefix Routes Under `/v1`

```python
# api/v1/router.py
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(clarification_router, prefix="/clarification")
v1_router.include_router(orchestrator_router, prefix="/orchestrator")
```

**TODO**: Version the API so breaking changes can be introduced without breaking existing clients.

### 7. Background Tasks — Use `BackgroundTasks` or Celery

```python
@router.post("/respond")
async def respond(request: RespondRequest, background_tasks: BackgroundTasks):
    result = await clarification_service.respond(request)
    background_tasks.add_task(write_session_logs, result.session_id)
    return result
```

**TODO**: Move non-critical work (logging, cache writes) to background tasks so they don't add latency to the response.

### 8. Async — Convert Handlers and Graph Calls

```python
# Before
@router.post("/start")
def start_session(request: StartSessionRequest):
    result = graph.invoke(state, config)
    ...

# After
@router.post("/start")
async def start_session(request: StartSessionRequest):
    result = await graph.ainvoke(state, config)
    ...
```

**TODO**: All route handlers should be `async def`. Use `graph.ainvoke()` instead of `graph.invoke()`.

### 9. Response Models — Always Declare `response_model`

```python
@router.post("/start", response_model=StartSessionResponseV2, status_code=201)
async def start_session(...): ...
```

**TODO**: All endpoints should declare `response_model` and correct `status_code` on the decorator (currently some are missing).

### 10. OpenAPI Documentation — Add Tags and Summaries

```python
router = APIRouter(
    prefix="/api/clarification",
    tags=["Clarification"],
)

@router.post("/start", summary="Start a new clarification session")
async def start_session(...): ...
```

**TODO**: Add `tags`, `summary`, and `description` to all routes for better `/docs` experience.

---

## Component Status Table

| Component | Status | Notes |
|-----------|--------|-------|
| Clarification Agent | ✅ Production-ready | Full LangGraph + LLM, v2 scoring |
| Orchestrator | ✅ Complete | Sequential pipeline |
| Research Agent | ⚠️ Mock | Hardcoded data, correct schema |
| Planner Agent | ⚠️ Mock | Hardcoded data, correct schema |
| Validator Agent | ❌ Not started | Planned |
| LLM Client | ✅ Complete | Retry, caching |
| Logging | ✅ Complete | Per-session JSON, cost tracking |
| Session Storage | ⚠️ In-memory | Not persistent, not thread-safe |
| Auth / Auth | ❌ Missing | CORS open, no API key |
| Rate Limiting | ❌ Missing | — |
| Async Support | ❌ Missing | Blocking handlers |
| Streaming | ❌ Missing | — |
| Database | ❌ Missing | Needs Redis or Postgres |
| FastAPI Best Practices | ❌ TODOs listed above | — |
| Docker / DevOps | ❌ Missing | No Dockerfile |
| API Versioning | ❌ Missing | All routes unversioned |
| Tests (unit) | ⚠️ Partial | Integration tests only |
