# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Python backend for an AI-powered trip planning application. The implementation features a **Clarification Agent** that uses LangGraph and OpenAI to gather travel preferences through a multi-round conversational interview before generating itineraries.

## Tech Stack

- **Agent Framework**: LangGraph (state machine-based workflows with checkpointing)
- **API Framework**: FastAPI
- **LLM**: OpenAI GPT-4.1-mini / GPT-5-mini
- **Data Validation**: Pydantic, TypedDict
- **Retry Logic**: Tenacity
- **Environment**: python-dotenv
- **Python**: 3.10+

## Commands

```bash
# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set API key (or use .env file)
export OPENAI_API_KEY_1="your-key"

# Run API server
uvicorn agents.main:app --reload --port 8000

# Run interactive clarification test
python3 -m agents.tests.test_clarification

# Import test
python3 -c "from agents.clarification.graph.build import create_clarification_graph"
```

## Architecture

### Directory Structure

```
agents/
├── shared/                      # Shared infrastructure
│   ├── llm/
│   │   └── client.py           # OpenAI client + retry logic (cached singleton)
│   ├── logging/
│   │   └── debug_logger.py     # Per-session JSON logging, cost tracking
│   ├── cache/
│   │   └── session_store.py    # File-based system prompt caching
│   ├── contracts/
│   │   ├── clarification_output.py  # ClarificationOutputV2 contract
│   │   ├── research_output.py       # ResearchOutputV1 contract
│   │   └── planner_output.py        # PlannerOutputV1 contract
│   └── schemas/                 # Common base models
│
├── clarification/               # Clarification Agent (PRODUCTION-READY)
│   ├── schemas.py              # ClarificationState, Question models (v2)
│   ├── response_parser.py      # JSON parsing logic
│   ├── scoring.py              # Code-based completeness scoring (v2)
│   ├── clarification_api.py    # FastAPI endpoints
│   ├── prompts/
│   │   ├── templates.py        # Typed prompt templates (Pydantic)
│   │   └── builders.py         # Prompt building functions
│   ├── nodes/
│   │   ├── clarification.py    # Main clarification node
│   │   ├── routing.py          # should_continue router
│   │   └── output.py           # output_node
│   └── graph/
│       ├── build.py            # create_clarification_graph
│       └── config.py           # GraphConfig dataclass
│
├── research/                    # Research Agent (MOCK — scaffold only)
│   ├── schemas.py              # ResearchState TypedDict
│   ├── mock_data.py            # Hardcoded research data (to be replaced)
│   ├── nodes/
│   │   └── research.py         # Research node
│   └── graph/
│       ├── build.py
│       └── config.py
│
├── planner/                     # Planner Agent (MOCK — scaffold only)
│   ├── schemas.py              # PlannerState TypedDict
│   ├── mock_data.py            # Hardcoded itinerary (to be replaced)
│   ├── nodes/
│   │   └── planner.py          # Planner node
│   └── graph/
│       ├── build.py
│       └── config.py
│
├── graph/                       # Orchestrator (COMPLETE)
│   ├── build.py                 # research → planner pipeline
│   ├── orchestrator_api.py     # /api/orchestrator endpoints
│   ├── state.py                 # OrchestratorState TypedDict
│   └── router.py                # route_next_agent conditional logic
│
├── main.py                      # FastAPI app entry point
└── tests/
    ├── test_clarification.py   # Clarification agent tests
    ├── test_orchestrator.py    # Full pipeline tests
    └── test_scoring.py         # Completeness scoring unit tests

cache/                           # System prompt cache (session-based)
logs/                            # Per-session debug logs (JSON Lines format)
plans/                           # Architecture plans and status reports
```

### Clarification Agent

A LangGraph-based state machine that conducts multi-round clarification interviews.

**LangGraph Workflow:**
```
Entry → clarification_node → should_continue()
                                ├→ If complete → output_node → END
                                └→ Else → Loop back to clarification
```

**Key Features:**
- Human-in-the-loop via `interrupt_after=["clarification"]` - pauses for user input between rounds
- Thread-based persistence with `MemorySaver` checkpointer
- **System prompt caching** - caches static prompts per session for OpenAI's automatic prompt caching (reduces latency and cost)
- Structured JSON output for frontend parsing (v2 schema)
- Typed prompts with Pydantic validation
- Explicit output contracts for downstream agents
- Per-session debug logging with token usage and cost tracking

**State Schema (`ClarificationState`):**
- User context: name, citizenship, health limitations, work obligations, dietary restrictions, specific interests
- Trip basics: destination, destination_cities, dates, trip_duration, budget, currency, travel_party, budget_scope
- Process state: current_round, completeness_score, clarification_complete
- Data flow: current_questions, user_response, collected_data, data (cumulative v2), messages
- Tracking: session_id

**Question Tier System (v2):**
- **Tier 1 - Critical (10 pts each):** activity_preferences, pace_preference, tourist_vs_local, mobility_level, dining_style
- **Tier 2 - Planning Essentials (4 pts each):** top_3_must_dos, transportation_mode, arrival/departure_time, budget_priority, accommodation_style
- **Tier 3 - Conditional Critical (3 pts each):** wifi_need (if work_obligations), dietary_severity (if dietary_restrictions), accessibility_needs (if health_limitations)
- **Tier 4 - Optimization (3 pts each):** special_logistics, daily_rhythm, downtime_preference

**Stopping Conditions:**
- Score ≥ 85 AND all Tier 1 complete AND no unresolved conflicts
- Score ≥ 85 (even if Tier 2 incomplete)
- Round 4 complete

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/clarification/start` | POST | Start new session |
| `/api/clarification/respond` | POST | Submit responses |
| `/api/clarification/session/{id}` | GET | Get session status |
| `/api/clarification/session/{id}` | DELETE | Delete session |
| `/api/clarification/health` | GET | Clarification health check |
| `/api/orchestrator/run` | POST | Run full research → planner pipeline |
| `/health` | GET | Global health check |

### Key Modules

| Module | Purpose |
|--------|---------|
| `agents/shared/llm/client.py` | OpenAI client singleton with tenacity retry, token usage tracking |
| `agents/shared/cache/session_store.py` | File-based system prompt caching per session |
| `agents/shared/logging/debug_logger.py` | Per-session JSON logging, cost calculation, question extraction |
| `agents/shared/contracts/` | Output contracts: ClarificationOutputV2, ResearchOutputV1, PlannerOutputV1 |
| `agents/clarification/scoring.py` | Code-based completeness scoring (tiered system) |
| `agents/clarification/prompts/templates.py` | V2 system prompt template with Pydantic config model |
| `agents/clarification/prompts/builders.py` | Dynamic prompt construction |
| `agents/clarification/response_parser.py` | LLM response JSON parsing |
| `agents/clarification/schemas.py` | ClarificationState, QuestionV2, API request/response models |
| `agents/clarification/nodes/clarification.py` | Main graph node |
| `agents/clarification/graph/build.py` | Graph assembly with optional checkpointing |
| `agents/clarification/graph/config.py` | GraphConfig dataclass (limits, interrupts) |
| `agents/clarification/clarification_api.py` | FastAPI router with session management |
| `agents/graph/build.py` | Orchestrator pipeline (research → planner) |
| `agents/graph/orchestrator_api.py` | Orchestrator FastAPI router |

### Testing Utilities

Located in `agents/tests/`:

- `test_clarification.py`: `create_initial_state()`, `simulate_user_responses()`, `test_clarification_agent()`, `run_automated_test()`
- `test_orchestrator.py`: Full pipeline integration tests with mock data
- `test_scoring.py`: Unit tests for completeness scoring logic

## Environment Variables

```
OPENAI_API_KEY_1      # OpenAI API key for LLM calls
PROMPT_CACHE_DIR      # Optional: custom cache directory (default: ./cache)
```

## Design Decisions

1. **Typed prompts**: Prompts as Pydantic models for validation and testability
2. **Pure nodes**: Nodes are pure functions with no inline prompts or API calls
3. **Separated graph config**: `graph/config.py` for easy tuning without touching wiring
4. **Contracts**: Explicit output contracts (`ClarificationOutput`) for agent handoffs
5. **Cached client singleton**: Single OpenAI client instance reused across calls
6. **System prompt caching**: Static prompts cached to disk for OpenAI's automatic caching
7. **Session-based logging**: Each session gets isolated debug logs with token/cost tracking

---

## Coding Standards

### Production-Grade Code Requirements

This codebase is designed for **production use with future refactoring and extensibility in mind**. All code contributions must adhere to the following principles:

### Modularity
- **Single file, single purpose**: Each module should have one clear responsibility
- **Logical grouping**: Related functionality belongs in dedicated directories (e.g., `prompts/`, `nodes/`, `graph/`)
- **Clean imports**: Use `__init__.py` files to expose public APIs and hide implementation details
- **Avoid monolithic files**: If a file exceeds ~300 lines, consider splitting it

### Single Responsibility Principle (SRP)
- **One reason to change**: Each class/function should have exactly one reason to change
- **Separation of concerns**:
  - `schemas.py` - Data models only, no business logic
  - `templates.py` - Prompt content only, no formatting logic
  - `builders.py` - Prompt assembly only, no LLM calls
  - `client.py` - LLM communication only, no business logic
  - `nodes/*.py` - Graph node logic only, one node per file
- **No god classes**: Split large classes into focused components

### DRY (Don't Repeat Yourself)
- **Centralize shared logic**: Common utilities go in `agents/shared/`
- **Reuse models**: Define data structures once in `schemas.py`, import everywhere
- **Template patterns**: Use base classes/mixins for common behaviors
- **Configuration over duplication**: Use config objects instead of repeating values

### Code Quality Standards
- **Type hints everywhere**: All function signatures must have type annotations
- **Docstrings required**: All public functions/classes need docstrings explaining purpose, args, and returns
- **Pydantic for validation**: Use Pydantic models for external data (API requests, LLM responses)
- **TypedDict for internal state**: Use TypedDict for LangGraph state schemas
- **Error handling**: Use specific exceptions, handle edge cases gracefully
- **Logging**: Use structured logging with context (session_id, round, etc.)

### File Organization Pattern
```python
"""
Module docstring explaining purpose.
"""

# Standard library imports
from typing import Optional, List

# Third-party imports
from pydantic import BaseModel

# Local imports
from agents.shared.llm import get_cached_client

# Constants
DEFAULT_VALUE = "something"

# Public classes/functions
class MyModel(BaseModel):
    """Docstring."""
    pass

def my_function() -> str:
    """Docstring."""
    pass
```

### Extensibility Guidelines
- **Design for change**: New agents should follow the same patterns as `clarification/`
- **Plugin architecture**: Each agent is self-contained with its own `graph/`, `nodes/`, `prompts/`
- **Contract-based communication**: Agents communicate via explicit contracts in `shared/contracts/`
- **Config-driven behavior**: Use dataclasses/Pydantic for configuration, not magic constants

---

## Implementation Status

See `plans/status.md` for the full status report. Summary:

| Component | Status |
|-----------|--------|
| Clarification Agent | ✅ Production-ready |
| Orchestrator | ✅ Complete |
| Research Agent | ⚠️ Mock data only |
| Planner Agent | ⚠️ Mock data only |
| Validator Agent | ❌ Not started |
| Session storage | ⚠️ In-memory (not persistent) |
| Auth / rate limiting | ❌ Not implemented |
| Async support | ❌ Handlers are synchronous |
| API versioning | ❌ Not applied |

---

## FastAPI Best Practices (TODOs)

These are structural patterns to adopt as the codebase grows. Follow them for all new code and migrate existing code opportunistically.

### 1. Settings via `pydantic-settings`

Replace scattered `os.environ.get()` and hardcoded model names with a central `Settings` object in `agents/core/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    model_name: str = "gpt-4.1-mini"
    max_clarification_rounds: int = 4
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
```

### 2. Dependency Injection via `Depends()`

Inject `settings`, `session_store`, and `llm_client` into route handlers via `Depends()` rather than importing module-level globals. Put shared dependency functions in `agents/core/dependencies.py`.

### 3. Centralized Exception Handling

Define typed exception classes in `agents/core/exceptions.py` (e.g. `SessionNotFoundError`, `ParseError`). Register them with `@app.exception_handler()` in `main.py` instead of scattering `HTTPException` raises in route handlers.

### 4. Middleware

Add to `agents/core/middleware.py`:
- **RequestIDMiddleware**: Attach a `X-Request-ID` UUID to every request for traceability
- **RequestLoggingMiddleware**: Log method, path, status code, and duration for every request

### 5. API Versioning

Nest all routes under `/api/v1/` using a versioned `APIRouter` in `agents/api/v1/router.py`. This allows breaking changes without breaking existing clients.

### 6. Async Handlers + `ainvoke`

All route handlers should be `async def`. Replace `graph.invoke()` with `graph.ainvoke()` so FastAPI's event loop is not blocked during LLM calls.

### 7. Service Layer

Move business logic out of `*_api.py` files into dedicated service modules (e.g. `agents/services/clarification_service.py`). API files should only handle request/response serialization and call into services.

### 8. Background Tasks

Use `BackgroundTasks` for non-blocking work (e.g. writing session logs, updating caches) that doesn't need to complete before the response is sent.

### 9. Response Models + Status Codes

Every route decorator should declare `response_model=` and the correct `status_code=` (e.g. `201` for creates). This drives OpenAPI schema generation and catches serialization errors early.

### 10. OpenAPI Documentation

Add `tags=`, `summary=`, and `description=` to every router and route for a useful `/docs` page.
