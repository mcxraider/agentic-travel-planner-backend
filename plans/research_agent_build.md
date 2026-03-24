# Research Agent MVP — Implementation Plan

## Context

The research agent currently returns hardcoded mock POIs. This plan replaces it with a production
multi-agent research pipeline built as a proper LangGraph graph: each sub-agent is a dedicated node
with `RetryPolicy` for transient failures, a shared repair node for LLM-recoverable parse/validation
failures, a checkpointer for fault tolerance and resumability, and LangSmith tracing throughout.

**Key decisions locked in:**
- All research is LLM-generated (no external APIs for MVP)
- Budget scope: in-destination only — accommodation, food, activities, local transport. The user's
  stated budget is treated as already excluding flights, visas, and travel insurance. The
  `BudgetAnalysis` prompt must state this explicitly so the LLM does not subtract flights.
- "Curated Highlights" = ranked shortlist (top must-dos, best dining, hidden gems) synthesized from
  all prior sub-agent outputs for the planner
- New `ResearchOutputV2` contract (V1 preserved, not modified)
- Sub-agents are individual LangGraph nodes, not helper functions called from a stage wrapper
- Transient errors (API, network, rate-limit) → handled by `RetryPolicy` at the node level using the
  `retry_policy=` keyword. Verified locally against pinned `langgraph==1.0.7`: import
  `RetryPolicy` from `langgraph.types` and pass it via `graph.add_node(..., retry_policy=...)`.
- Parse/validation failures → written to state, routed to shared `repair_node`; repair routing is
  criticality-aware: non-critical node failures skip forward, critical node failures route to a
  `degraded_aggregate` branch. Critical nodes for MVP are `overview`, `budget`, and `activities`.
- Unexpected errors → bubble up and crash the node (let LangGraph surface them)
- Graph compiled with `MemorySaver` checkpointer; invoked with `thread_id = session_id`
- LangSmith tracing enabled via environment variables
- Aggregate uses **explicit degraded mode**: no synthetic defaults; fields backed by fallible nodes
  are represented as `Optional` or empty collections in the schema, and typed metadata records
  `degraded`, `missing_sections`, `critical_failures`, and per-section status

---

## Architecture

```
ClarificationOutput (input)
        ↓
  weather_node ──(parse_ok)──→ overview_node ──(parse_ok)──→ budget_node
       │                            │                              │
  (parse_err)                 (parse_err)                   (parse_err) ← CRITICAL
       └────────────────────────────┴──────────────────────────────┘
                                    ↓
                              repair_node
                 (rebuilds prompt with bad response + error context)
                        ↓                       ↓
              (repair succeeded         (repair failed, max attempts)
               OR non-critical)                 │
                        │                       ├─ if CRITICAL node → degraded_aggregate
                        │                       └─ if non-critical  → next node (skip)
                        ↓
                   next_node

  Node criticality:
    CRITICAL   = {overview, budget, activities}    → degraded_aggregate on unrecoverable failure
    NON-CRITICAL = all others            → skip and continue

  budget_node → accommodation_node → activities_node → dining_node
                → transport_node → highlights_node
                → aggregate_node → END
          ↑
  degraded_aggregate (reached only on critical failure; marks output degraded)

  Each sub-agent node has retry_policy= for:
    openai.APIError, openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError
```

**Node sequence (linear):**
```
weather → overview → budget → accommodation → activities → dining → transport → highlights → aggregate → END
```
Each node has a conditional edge: `parse_ok → next_node`, `parse_error → repair`.
`repair` routes based on criticality: critical failure → `degraded_aggregate`; non-critical → skip to next node.

---

## Status Snapshot

**Implemented so far**
- Stage 1 complete: `ResearchOutputV2` contract added and exported; `ResearchState` rewritten for
  the multi-node pipeline
- Stage 2 complete: structured-output helper added to `agents/shared/llm/client.py`; research
  prompt templates and builders created for all 8 sub-agents
- Stage 3 complete: shared node executor added plus individual node files for weather, overview,
  budget, accommodation, activities, dining, transport, and highlights
- Stage 4 complete: shared `repair_node` added; routing functions added; `max_repair_attempts`
  added to research graph config
- Stage 5 complete: `aggregate_node` and `degraded_aggregate_node` added with explicit degraded-mode
  metadata and no synthetic defaults
- Stage 6 complete: the compiled research graph now wires the staged 11-node pipeline with
  `RetryPolicy` and a default `MemorySaver` checkpointer
- Stage 7 complete: the orchestrator `_research_wrapper` now invokes the compiled research graph
  with `thread_id = research-{session_id}`
- Stage 8 complete: LangSmith environment variables were added to `.env`, and startup comments in
  `agents/main.py` document that tracing is automatic when enabled
- Stage 9 complete: `agents/tests/test_research_pipeline.py` now exists with live end-to-end and
  checkpoint-resume coverage gated behind `RUN_LIVE_LLM_TESTS=1`

**Important current transitional state**
- `agents/research/nodes/research.py` is still present as a legacy mock node and standalone test
  target, but it is no longer the active path for the compiled research graph or orchestrator
- `agents/research/graph/routing.py` is fully wired into the compiled graph
- `agents/research/graph/config.py` now includes the full Stage 6 config surface
- There is no remaining Stage 1-9 implementation work tracked in this plan; only optional cleanup
  remains if the legacy mock `research_node` should be removed later

---

## ResearchOutputV2 Schema

To be created at `agents/shared/contracts/research_output_v2.py`:

```python
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class WeatherInfo(BaseModel):
    season: str
    temperature_range_celsius: Dict[str, float]   # {"min": x, "max": x}
    precipitation_likelihood: Literal["low", "moderate", "high"]
    daylight_hours: Optional[float]
    clothing_recommendations: List[str]
    weather_notes: List[str]

class AccommodationArea(BaseModel):
    neighborhood: str
    description: str
    why_suitable: str        # tailored to user profile (party, mobility, budget)
    price_tier: Literal["budget", "mid-range", "luxury"]
    pros: List[str]
    cons: List[str]

class Activity(BaseModel):
    name: str                # specific real name (e.g. "Senso-ji Temple")
    category: str            # "culture"|"food"|"nature"|"adventure"|"shopping"|"nightlife"
    description: str
    estimated_duration_hours: float
    estimated_cost_usd: Optional[float]
    best_time_to_visit: Optional[str]
    booking_required: bool
    tags: List[str]

class DiningRecommendation(BaseModel):
    name: str                # specific real restaurant/market name
    cuisine_type: str
    description: str
    price_tier: Literal["budget", "mid-range", "fine-dining"]
    estimated_cost_per_person_usd: Optional[float]
    must_try_dishes: List[str]
    neighborhood: Optional[str]
    best_for: str            # "breakfast"|"lunch"|"dinner"|"any"

class TransportOption(BaseModel):
    mode: str
    description: str
    estimated_daily_cost_usd: Optional[float]
    coverage: str
    tips: List[str]

class CuratedHighlight(BaseModel):
    rank: int
    category: Literal["experience", "dining", "hidden_gem"]
    title: str
    why_it_matters: str      # why this is a must for THIS specific user profile
    estimated_duration_hours: Optional[float]
    estimated_cost_usd: Optional[float]

class InDestinationBudget(BaseModel):
    total_available_usd: float
    trip_duration_days: int
    daily_budget_usd: float
    breakdown: Dict[str, float]  # {"accommodation": x, "food": x, "activities": x, "transport": x}
    budget_assessment: Literal["tight", "comfortable", "generous"]
    budget_tips: List[str]

class CityResearchV2(BaseModel):
    city_name: Optional[str] = None
    country: Optional[str] = None
    destination_overview: Optional[str] = None
    recommended_days: Optional[int] = None
    weather: Optional[WeatherInfo] = None
    accommodation_areas: List[AccommodationArea] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list)
    dining: List[DiningRecommendation] = Field(default_factory=list)

class ResearchMetadata(BaseModel):
    generated_at: str
    session_id: Optional[str] = None
    degraded: bool = False
    missing_sections: List[str] = Field(default_factory=list)
    critical_failures: List[str] = Field(default_factory=list)
    section_status: Dict[str, Literal["ok", "missing", "critical_failure"]] = Field(default_factory=dict)

class ResearchOutputV2(BaseModel):
    destination: str
    trip_duration_days: int
    travel_party: str
    cities: List[CityResearchV2]
    transportation: List[TransportOption] = Field(default_factory=list)
    curated_highlights: List[CuratedHighlight] = Field(default_factory=list)
    budget_analysis: Optional[InDestinationBudget] = None
    metadata: ResearchMetadata
```

---

## Implementation Stages

### Stage 1 — Contracts & Schema Foundation

Status: complete

**Goal:** Lock in the data contract and state schema before any node code is written.

**Create `agents/shared/contracts/research_output_v2.py`**
Full `ResearchOutputV2` and all nested models from above. Export via `agents/shared/contracts/__init__.py`.

**Update `agents/research/schemas.py`** — rewrite `ResearchState` TypedDict:

```python
class ResearchState(TypedDict):
    # --- Inputs (from ClarificationOutput + orchestrator) ---
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float            # in-destination budget only; flights/visa excluded
    currency: str
    travel_party: str
    activity_preferences: Optional[List[str]]
    pace_preference: Optional[str]
    dining_style: Optional[List[str]]
    accommodation_style: Optional[List[str]]
    mobility_level: Optional[str]
    dietary_restrictions: Optional[str]   # maps from clarification.dietary_severity
    top_3_must_dos: Optional[dict]
    budget_priority: Optional[str]
    tourist_vs_local: Optional[str]
    clarification_output: Optional[dict]  # full ClarificationOutput snapshot

    # --- Sub-agent outputs (populated as nodes complete) ---
    weather_output: Optional[dict]
    destination_overview_output: Optional[dict]
    budget_analysis_output: Optional[dict]
    accommodation_output: Optional[dict]
    activities_output: Optional[dict]
    dining_output: Optional[dict]
    transportation_output: Optional[dict]
    curated_highlights_output: Optional[dict]

    # --- Final output ---
    research_output: Optional[dict]     # validated ResearchOutputV2
    research_complete: bool

    # --- Repair loop state ---
    repair_target: Optional[str]        # node name that failed parsing (e.g. "weather")
    repair_attempt_count: int           # how many repair attempts for current target
    last_bad_response: Optional[str]    # raw LLM response that failed to parse
    last_repaired_node: Optional[str]   # used by repair router to determine next node

    # --- Tracking ---
    errors: Annotated[List[str], operator.add]
    messages: Annotated[List[dict], operator.add]
    session_id: Optional[str]
```

**Verification:** Import succeeds. `ResearchOutputV2(**minimal_fixture)` passes Pydantic validation in a Python REPL.

---

### Stage 2 — Prompt Templates, Builders & Structured Output Strategy

Status: complete

**Goal:** Write all 8 sub-agent prompts and decide how to get structured JSON reliably from the LLM.

**Structured Output Strategy**

Do NOT rely on `"Return ONLY valid JSON"` instructions alone. Use OpenAI's structured output:

Option A (preferred): `client.beta.chat.completions.parse(response_format=WeatherInfo, ...)` — returns a fully validated Pydantic object directly. Eliminates all JSON parsing and Pydantic construction from the node.

Option B (fallback): `response_format={"type": "json_object"}` combined with explicit schema in the system prompt. Still requires `json.loads()` + Pydantic construction, but removes free-form prose.

**Add to `agents/shared/llm/client.py`:**

```python
def parse_llm_response(
    client: OpenAI,
    user_prompt: str,
    system_prompt: str,
    response_model: Type[BaseModel],
    model: str = "gpt-4.1",
) -> Tuple[BaseModel, Dict[str, int]]:
    """
    Calls OpenAI with structured output via .parse().
    Returns (validated_pydantic_instance, usage_dict).
    Raises openai.LengthFinishReasonError if output was truncated.
    Raises pydantic.ValidationError if schema mismatch (should not happen with structured output).
    API/network errors bubble up — let RetryPolicy handle them.
    """
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=response_model,
    )
    parsed = completion.choices[0].message.parsed
    usage = {
        "input_tokens": completion.usage.prompt_tokens,
        "output_tokens": completion.usage.completion_tokens,
        "total_tokens": completion.usage.total_tokens,
    }
    return parsed, usage
```

**Create `agents/research/prompts/templates.py`**

One `SystemPromptConfig` (Pydantic) + `SYSTEM_PROMPT_TEMPLATE` string per sub-agent:

| Sub-Agent | Key Config Inputs | Output Schema |
|-----------|------------------|---------------|
| `WeatherPromptConfig` | destination, city, start_date, end_date | `WeatherInfo` |
| `OverviewPromptConfig` | destination, city, trip_duration, travel_party | `DestinationOverviewOutput` (simple wrapper: overview str + recommended_days int) |
| `BudgetPromptConfig` | budget, currency, trip_duration, travel_party, budget_priority | `InDestinationBudget` |
| `AccommodationPromptConfig` | destination, city, accommodation_style, mobility_level, budget_tier, travel_party | `AccommodationAreasOutput` (wrapper: List[AccommodationArea]) |
| `ActivitiesPromptConfig` | destination, city, activity_preferences, tourist_vs_local, pace_preference, mobility_level, must_dos | `ActivitiesOutput` (wrapper: List[Activity]) |
| `DiningPromptConfig` | destination, city, dining_style, dietary_restrictions, budget_tier, travel_party | `DiningOutput` (wrapper: List[DiningRecommendation]) |
| `TransportPromptConfig` | destination, city, mobility_level, budget_tier, trip_duration | `TransportOutput` (wrapper: List[TransportOption]) |
| `HighlightsPromptConfig` | destination, must_dos, activity_prefs, activities_json, dining_json, overview | `HighlightsOutput` (wrapper: List[CuratedHighlight]) |

Note: OpenAI `.parse()` requires the `response_format` to be a Pydantic `BaseModel`, not a raw `List[T]`.
Wrapper models (e.g. `ActivitiesOutput(items: List[Activity])`) solve this.

**Budget scope: explicit in template**

The `BudgetPromptConfig` template must include:
```
The user's budget of {budget} {currency} is their IN-DESTINATION spending budget only.
This amount covers accommodation, food, activities, and local transport for {trip_duration} days.
Flights, visas, travel insurance, and pre-trip purchases are already handled separately.
Allocate this full {budget} {currency} across the four in-destination categories.
```

**Create `agents/research/prompts/builders.py`**

One builder per sub-agent returning `Tuple[str, str]` (system_prompt, user_prompt). Stage 2+ builders
read relevant Stage 1 outputs from state (e.g., `build_accommodation_prompts` reads `budget_analysis_output`
from state to derive `budget_tier`; `build_highlights_prompts` includes summarized activities + dining JSON).

**Verification:** Call each builder with a synthetic state dict. Confirm no `KeyError` and output is non-empty.

---

### Stage 3 — Sub-Agent Node Functions

Status: complete, with one deferred cleanup item

**Goal:** Each sub-agent is a standalone LangGraph node function. API/network errors bubble up (handled
by `RetryPolicy`). Parse/validation failures write to state and return — the conditional edge routes to
`repair_node`.

**File per node:** `agents/research/nodes/{name}_node.py`

Pattern:

```python
# agents/research/nodes/weather_node.py

def weather_node(state: ResearchState) -> Dict[str, Any]:
    """
    LangGraph node: generates WeatherInfo for the destination.

    Error handling:
      - APIError / RateLimitError / APITimeoutError → bubble up → RetryPolicy retries
      - LengthFinishReasonError (truncated output) → bubble up → RetryPolicy retries
      - Parse/schema failure → write repair_target to state → conditional edge → repair_node
      - Unexpected errors → bubble up (crash node)
    """
    client = get_cached_client()
    config = DEFAULT_CONFIG
    session_id = state.get("session_id", "unknown")
    debug_logger = get_or_create_logger(session_id)
    _log = f"[session={session_id}] [graph=research] [node=weather]"

    system_prompt, user_prompt = build_weather_prompts(state)

    logger.info(f"{_log} Calling LLM")
    start = time.perf_counter()

    # API errors bubble up — RetryPolicy handles them at graph level
    result, usage = parse_llm_response(
        client, user_prompt, system_prompt,
        response_model=WeatherInfo,
        model=config.model,
    )
    duration_ms = (time.perf_counter() - start) * 1000

    if debug_logger:
        debug_logger.log_llm_call(
            round_num=1, system_prompt=system_prompt, user_prompt=user_prompt,
            response=result.model_dump_json(), duration_ms=duration_ms,
            input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"],
            model=config.model,
        )

    logger.info(f"{_log} Done | season={result.season}")
    return {
        "weather_output": result.model_dump(),
        "repair_target": None,
        "messages": [{"role": "system", "content": f"weather complete: {result.season}"}],
    }
```

Note: With `parse_llm_response()` using `.parse()`, parse/schema failures are rare (OpenAI enforces
the schema). They can still occur (e.g., `LengthFinishReasonError`). Treat truncation as a transient
failure that `RetryPolicy` retries. Only genuine schema mismatches (shouldn't happen with structured
output) route to repair.

**If `.parse()` is not available on the deployed model:** fall back to `json_object` mode + manual
`json.loads()` + Pydantic construction. In that case, `json.JSONDecodeError` and `ValidationError` are
caught and written to state:

```python
except (json.JSONDecodeError, ValidationError) as e:
    logger.warning(f"{_log} Parse failure: {e}")
    return {
        "weather_output": None,
        "repair_target": "weather",
        "last_bad_response": raw_response,
        "repair_attempt_count": state.get("repair_attempt_count", 0),
    }
```

**Node files to create:**
- `agents/research/nodes/weather_node.py` → `weather_node()`
- `agents/research/nodes/overview_node.py` → `overview_node()`
- `agents/research/nodes/budget_node.py` → `budget_node()`
- `agents/research/nodes/accommodation_node.py` → `accommodation_node()`
- `agents/research/nodes/activities_node.py` → `activities_node()`
- `agents/research/nodes/dining_node.py` → `dining_node()`
- `agents/research/nodes/transport_node.py` → `transport_node()`
- `agents/research/nodes/highlights_node.py` → `highlights_node()`

`agents/research/nodes/research.py` has been retained as a legacy mock helper and standalone test
target, but the compiled research graph and orchestrator no longer route through it.
`agents/research/sub_agents/` does not exist in the current repo, so no deletion work is needed there.

**Verification:** Invoke each node directly with a synthetic `ResearchState`. Assert return dict has
the expected output key set and no exception raised.

---

### Stage 4 — Repair Node & Routing Functions

Status: complete

**Goal:** A single shared repair node handles all parse/validation failures. It reads `repair_target`
from state, rebuilds the prompt with error context, retries the LLM call, and then hands control to
the router, which either advances, skips a non-critical missing section, or branches to
`degraded_aggregate` for unrecoverable critical failures.

**Create `agents/research/nodes/repair_node.py`**

```python
# Ordered sequence — used to route forward after repair
NODE_SEQUENCE = [
    "weather", "overview", "budget",
    "accommodation", "activities", "dining",
    "transport", "highlights",
]

def repair_node(state: ResearchState) -> Dict[str, Any]:
    """
    Attempts to recover from a parse/validation failure in a sub-agent node.

    Reads: repair_target (which node failed), last_bad_response (raw LLM output that failed).
    Retries: up to 2 times total. In the current implementation this retry loop is handled
    internally inside `repair_node()` before control returns to the graph router.
    Never routes directly itself; the repair router decides the next branch.

    On success: sets {target}_output, clears repair fields.
    On failure (max attempts): leaves {target}_output as None, records error.
    """
    target = state["repair_target"]
    attempt = state.get("repair_attempt_count", 0)
    bad_response = state.get("last_bad_response", "")
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=research] [node=repair] [target={target}]"

    logger.warning(f"{_log} Attempt {attempt + 1}")

    if attempt >= 2:
        # Max repair attempts reached — leave output missing and let the router decide
        # whether to skip forward or enter degraded mode based on node criticality.
        logger.error(f"{_log} Max repair attempts reached, skipping")
        return {
            "errors": [f"{target}: max repair attempts reached, output will be missing"],
            "last_repaired_node": target,
            "repair_target": None,
            "repair_attempt_count": 0,
            "last_bad_response": None,
        }

    # Build repair prompt: include bad response + schema reminder
    system_prompt, original_user_prompt = _build_prompts_for_target(target, state)
    repair_user_prompt = (
        f"{original_user_prompt}\n\n"
        f"Your previous response failed schema validation. Here it was:\n\n"
        f"```\n{bad_response}\n```\n\n"
        f"Please regenerate a valid response strictly matching the required schema."
    )

    client = get_cached_client()
    config = DEFAULT_CONFIG
    response_model = _response_model_for_target(target)

    try:
        result, usage = parse_llm_response(
            client, repair_user_prompt, system_prompt,
            response_model=response_model,
            model=config.model,
        )
        logger.info(f"{_log} Repair succeeded")
        return {
            f"{target}_output": result.model_dump(),
            "last_repaired_node": target,
            "repair_target": None,
            "repair_attempt_count": 0,
            "last_bad_response": None,
        }
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"{_log} Repair attempt {attempt + 1} failed: {e}")
        return {
            "repair_attempt_count": attempt + 1,
            "last_repaired_node": target,
            "last_bad_response": bad_response,
        }


def _build_prompts_for_target(target: str, state: ResearchState) -> Tuple[str, str]:
    """Dispatch to the correct prompt builder based on target node name."""
    builders = {
        "weather": build_weather_prompts,
        "overview": build_overview_prompts,
        "budget": build_budget_prompts,
        "accommodation": build_accommodation_prompts,
        "activities": build_activities_prompts,
        "dining": build_dining_prompts,
        "transport": build_transport_prompts,
        "highlights": build_highlights_prompts,
    }
    return builders[target](state)


def _response_model_for_target(target: str) -> Type[BaseModel]:
    """Return the Pydantic model for structured output based on target node."""
    return {
        "weather": WeatherInfo,
        "overview": DestinationOverviewOutput,
        "budget": InDestinationBudget,
        "accommodation": AccommodationAreasOutput,
        "activities": ActivitiesOutput,
        "dining": DiningOutput,
        "transport": TransportOutput,
        "highlights": HighlightsOutput,
    }[target]
```

**Routing functions** (in `agents/research/graph/routing.py`):

```python
# Ordered pipeline sequence
NODE_SEQUENCE = [
    "weather", "overview", "budget",
    "accommodation", "activities", "dining",
    "transport", "highlights", "aggregate",
]

# CRITICAL nodes: unrecoverable failure routes to degraded_aggregate instead of skipping forward.
# Rationale:
# - overview anchors city identity/country/overview text for the final contract
# - budget feeds downstream feasibility and planner tradeoffs
# - activities is the primary semantic input to highlights and itinerary synthesis
CRITICAL_NODES = {"overview", "budget", "activities"}

def _next_node(current: str) -> str:
    idx = NODE_SEQUENCE.index(current)
    return NODE_SEQUENCE[idx + 1] if idx + 1 < len(NODE_SEQUENCE) else "aggregate"


# One routing function per sub-agent node
def route_after_weather(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "weather" else "overview"

def route_after_overview(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "overview" else "budget"

def route_after_budget(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "budget" else "accommodation"

def route_after_accommodation(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "accommodation" else "activities"

def route_after_activities(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "activities" else "dining"

def route_after_dining(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "dining" else "transport"

def route_after_transport(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "transport" else "highlights"

def route_after_highlights(state: ResearchState) -> str:
    return "repair" if state.get("repair_target") == "highlights" else "aggregate"


def route_after_repair(state: ResearchState) -> str:
    """
    Routes after a repair attempt.

    If repair succeeded (output slot is populated): route to next node in sequence.
    If repair failed (output slot still None):
      - CRITICAL node → degraded_aggregate (do not silently continue with broken state)
      - Non-critical node → next node in sequence (skip the missing output)
    """
    last = state.get("last_repaired_node", "")
    repair_succeeded = state.get(f"{last}_output") is not None

    if not repair_succeeded and last in CRITICAL_NODES:
        return "degraded_aggregate"

    return _next_node(last)
```

**Verification:** Construct a state with `repair_target="weather"`, `repair_attempt_count=0`,
`last_bad_response="{bad json}"`. Invoke `repair_node()`. Assert either `weather_output` is set
or `errors` contains the failure message. Call routing functions with test states and assert
correct string is returned.

---

### Stage 5 — Aggregate Node (Explicit Degraded Mode)

Status: complete

**Goal:** Assemble all sub-agent outputs into `ResearchOutputV2`. No synthetic defaults for missing
sections. Missing outputs are tracked explicitly in typed metadata. The chosen mode is **explicit
degraded**: the contract allows absent values to remain absent, and the aggregate always records what
is missing so the planner and any downstream consumer can make informed decisions.

Two aggregate nodes are needed:
- `aggregate_node` — normal path (all critical nodes succeeded)
- `degraded_aggregate_node` — reached when a critical node failed unrecoverably; marks output as
  degraded with full accounting of what is missing

**Create `agents/research/nodes/aggregate_node.py`**

```python
def _build_research_output(
    state: ResearchState,
) -> Tuple[ResearchOutputV2, List[str], List[str], Dict[str, Literal["ok", "missing", "critical_failure"]]]:
    """
    Shared assembly logic for both aggregate paths.
    Returns (output, missing_sections, critical_failures, section_status).
    No synthetic defaults: missing outputs produce empty lists or None, never fabricated data.
    """
    missing_sections: List[str] = []
    critical_failures: List[str] = []
    section_status: Dict[str, Literal["ok", "missing", "critical_failure"]] = {}

    def _mark(section: str, present: bool, critical: bool = False) -> None:
        if present:
            section_status[section] = "ok"
            return
        missing_sections.append(section)
        if critical:
            critical_failures.append(section)
            section_status[section] = "critical_failure"
        else:
            section_status[section] = "missing"

    # Weather (non-critical, Optional in schema)
    weather = None
    if state.get("weather_output"):
        weather = WeatherInfo(**state["weather_output"])
    _mark("weather", weather is not None)

    # Overview
    overview_data = state.get("destination_overview_output") or {}
    _mark("destination_overview", bool(overview_data), critical=True)

    city_name = overview_data.get("city_name")
    if not city_name and state.get("destination_cities") and len(state["destination_cities"]) == 1:
        # This is sourced from clarification/orchestrator input, not synthesized by the aggregate.
        city_name = state["destination_cities"][0]

    # Accommodation
    accommodation = []
    if state.get("accommodation_output"):
        accommodation = [AccommodationArea(**a) for a in state["accommodation_output"].get("items", [])]
    _mark("accommodation", state.get("accommodation_output") is not None)

    # Activities
    activities = []
    if state.get("activities_output"):
        activities = [Activity(**a) for a in state["activities_output"].get("items", [])]
    _mark("activities", state.get("activities_output") is not None, critical=True)

    # Dining
    dining = []
    if state.get("dining_output"):
        dining = [DiningRecommendation(**d) for d in state["dining_output"].get("items", [])]
    _mark("dining", state.get("dining_output") is not None)

    city = CityResearchV2(
        city_name=city_name,
        country=overview_data.get("country"),
        destination_overview=overview_data.get("overview"),
        recommended_days=overview_data.get("recommended_days"),
        weather=weather,
        accommodation_areas=accommodation,
        activities=activities,
        dining=dining,
    )

    # Transportation
    transportation = []
    if state.get("transportation_output"):
        transportation = [TransportOption(**t) for t in state["transportation_output"].get("items", [])]
    _mark("transportation", state.get("transportation_output") is not None)

    # Highlights
    highlights = []
    if state.get("curated_highlights_output"):
        highlights = [CuratedHighlight(**h) for h in state["curated_highlights_output"].get("items", [])]
    _mark("curated_highlights", state.get("curated_highlights_output") is not None)

    # Budget
    budget = None
    if state.get("budget_analysis_output"):
        budget = InDestinationBudget(**state["budget_analysis_output"])
    _mark("budget_analysis", budget is not None, critical=True)

    degraded = len(missing_sections) > 0
    output = ResearchOutputV2(
        destination=state["destination"],
        trip_duration_days=state["trip_duration"],
        travel_party=state["travel_party"],
        cities=[city],
        transportation=transportation,
        curated_highlights=highlights,
        budget_analysis=budget,
        metadata=ResearchMetadata(
            generated_at=datetime.utcnow().isoformat(),
            session_id=state.get("session_id"),
            degraded=degraded,
            missing_sections=missing_sections,
            critical_failures=critical_failures,
            section_status=section_status,
        ),
    )
    return output, missing_sections, critical_failures, section_status


def aggregate_node(state: ResearchState) -> Dict[str, Any]:
    """Normal aggregate path. All critical nodes succeeded."""
    _log = f"[session={state.get('session_id')}] [node=aggregate]"
    logger.info(f"{_log} Assembling ResearchOutputV2")

    try:
        output, missing, critical_failures, _ = _build_research_output(state)
        if critical_failures:
            logger.error(f"{_log} Critical sections unexpectedly missing on normal path: {critical_failures}")
            return {
                "research_output": None,
                "research_complete": False,
                "errors": [f"aggregate: critical sections missing on normal path: {critical_failures}"],
            }
        if missing:
            logger.warning(f"{_log} Non-critical sections missing: {missing}")
        return {
            "research_output": output.model_dump(),
            "research_complete": True,
            "errors": [f"missing non-critical sections: {missing}"] if missing else [],
        }
    except ValidationError as e:
        logger.error(f"{_log} Validation failed: {e}")
        return {
            "research_output": None,
            "research_complete": False,
            "errors": [f"aggregate: schema validation failed: {e}"],
        }


def degraded_aggregate_node(state: ResearchState) -> Dict[str, Any]:
    """
    Degraded path. Reached when a CRITICAL node (overview, budget, or activities)
    failed after max repairs.
    Assembles whatever is available, marks output degraded.
    Sets research_complete = True so the orchestrator receives something, but degraded=true
    in metadata signals the planner to treat the output with caution.
    """
    _log = f"[session={state.get('session_id')}] [node=degraded_aggregate]"
    logger.warning(f"{_log} Entering degraded mode due to critical node failure")

    try:
        output, missing, critical_failures, _ = _build_research_output(state)
        logger.warning(
            f"{_log} Degraded output assembled. Missing: {missing}. Critical failures: {critical_failures}"
        )
        return {
            "research_output": output.model_dump(),
            "research_complete": True,   # complete but degraded — planner checks metadata
            "errors": [f"degraded: critical sections missing: {critical_failures}"],
        }
    except ValidationError as e:
        logger.error(f"{_log} Even degraded assembly failed: {e}")
        return {
            "research_output": None,
            "research_complete": False,
            "errors": [f"degraded_aggregate: schema validation failed: {e}"],
        }
```

**Verification:**
- Full fixture → `aggregate_node` → `research_complete == True`, `metadata.degraded is False`, `metadata.missing_sections == []`
- Fixture with `weather_output=None` and all critical outputs present → `aggregate_node` → `metadata.degraded is True`, `metadata.missing_sections == ["weather"]`
- Fixture with `budget_analysis_output=None` → `degraded_aggregate_node` → `research_complete == True`, `metadata.critical_failures == ["budget_analysis"]`

---

### Stage 6 — Graph Assembly, RetryPolicy & Checkpointer

Status: complete

**Goal:** Wire all 11 nodes into the graph with `RetryPolicy` for transient failures, compile with a
`MemorySaver` checkpointer, and invoke with `thread_id = session_id` for persistence and resumability.

**Update `agents/research/graph/config.py`:**

```python
from dataclasses import dataclass, field

@dataclass
class ResearchGraphConfig:
    recursion_limit: int = 25          # 11 nodes + repair detours
    model: str = "gpt-4.1"
    llm_timeout: int = 90
    max_repair_attempts: int = 2
    max_activities: int = 20
    max_dining: int = 15
    max_accommodation_areas: int = 5
    max_highlights: int = 8
    # RetryPolicy settings (for transient API errors)
    transient_max_attempts: int = 3
    transient_initial_interval: float = 1.0
    transient_backoff_factor: float = 2.0
    transient_max_interval: float = 10.0
```

**Create `agents/research/graph/routing.py`** — all `route_after_*` functions (from Stage 4).

**Rewrite `agents/research/graph/build.py`:**

```python
import openai
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy       # verified locally against langgraph==1.0.7
from langgraph.checkpoint.memory import MemorySaver

from agents.research.schemas import ResearchState
from agents.research.graph.config import ResearchGraphConfig, DEFAULT_CONFIG
from agents.research.graph.routing import (
    route_after_weather, route_after_overview, route_after_budget,
    route_after_accommodation, route_after_activities, route_after_dining,
    route_after_transport, route_after_highlights, route_after_repair,
)
from agents.research.nodes.weather_node import weather_node
from agents.research.nodes.overview_node import overview_node
from agents.research.nodes.budget_node import budget_node
from agents.research.nodes.accommodation_node import accommodation_node
from agents.research.nodes.activities_node import activities_node
from agents.research.nodes.dining_node import dining_node
from agents.research.nodes.transport_node import transport_node
from agents.research.nodes.highlights_node import highlights_node
from agents.research.nodes.repair_node import repair_node
from agents.research.nodes.aggregate_node import aggregate_node, degraded_aggregate_node

_TRANSIENT_ERRORS = (
    openai.APIError,
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)

def _build_retry_policy(config: ResearchGraphConfig) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=config.transient_max_attempts,
        initial_interval=config.transient_initial_interval,
        backoff_factor=config.transient_backoff_factor,
        max_interval=config.transient_max_interval,
        retry_on=_TRANSIENT_ERRORS,
    )


def create_research_graph(
    config: Optional[ResearchGraphConfig] = None,
    checkpointer=None,
) -> CompiledStateGraph:
    """
    Creates and compiles the research agent graph.

    Args:
        config: Graph config; defaults to DEFAULT_CONFIG.
        checkpointer: LangGraph checkpointer; defaults to MemorySaver.
                      Pass SqliteSaver or PostgresSaver for production persistence.
    """
    if config is None:
        config = DEFAULT_CONFIG
    if checkpointer is None:
        checkpointer = MemorySaver()

    retry_policy = _build_retry_policy(config)
    graph = StateGraph(ResearchState)

    # Add sub-agent nodes with retry_policy= for transient failures
    # The keyword is retry_policy=, NOT retry= (common mistake — LangGraph docs are explicit)
    for name, fn in [
        ("weather", weather_node),
        ("overview", overview_node),
        ("budget", budget_node),
        ("accommodation", accommodation_node),
        ("activities", activities_node),
        ("dining", dining_node),
        ("transport", transport_node),
        ("highlights", highlights_node),
    ]:
        graph.add_node(name, fn, retry_policy=retry_policy)

    # Repair and aggregate nodes — no retry_policy (they handle their own failure modes)
    graph.add_node("repair", repair_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("degraded_aggregate", degraded_aggregate_node)

    # Entry
    graph.set_entry_point("weather")

    # Conditional edges: each sub-agent node can route to next node or repair
    graph.add_conditional_edges("weather", route_after_weather,
        {"overview": "overview", "repair": "repair"})
    graph.add_conditional_edges("overview", route_after_overview,
        {"budget": "budget", "repair": "repair"})
    graph.add_conditional_edges("budget", route_after_budget,
        {"accommodation": "accommodation", "repair": "repair"})
    graph.add_conditional_edges("accommodation", route_after_accommodation,
        {"activities": "activities", "repair": "repair"})
    graph.add_conditional_edges("activities", route_after_activities,
        {"dining": "dining", "repair": "repair"})
    graph.add_conditional_edges("dining", route_after_dining,
        {"transport": "transport", "repair": "repair"})
    graph.add_conditional_edges("transport", route_after_transport,
        {"highlights": "highlights", "repair": "repair"})
    graph.add_conditional_edges("highlights", route_after_highlights,
        {"aggregate": "aggregate", "repair": "repair"})

    # Repair: routes forward on success/non-critical failure, to degraded_aggregate on critical failure
    graph.add_conditional_edges("repair", route_after_repair, {
        "overview": "overview", "budget": "budget",
        "accommodation": "accommodation", "activities": "activities",
        "dining": "dining", "transport": "transport",
        "highlights": "highlights", "aggregate": "aggregate",
        "degraded_aggregate": "degraded_aggregate",
    })

    graph.add_edge("aggregate", END)
    graph.add_edge("degraded_aggregate", END)

    return graph.compile(checkpointer=checkpointer)
```

**Implemented:** `agents/research/graph/build.py` now compiles the staged graph with all 11 nodes,
applies `retry_policy=` to the eight LLM-backed sub-agent nodes, and defaults the compiled graph to
`MemorySaver()` when no explicit checkpointer is supplied. `agents/research/graph/config.py` now
contains the full retry/backoff and result-limit surface described above.

**Verification:** `create_research_graph()` compiles successfully in the project venv. ASCII graph
printing remains optional and requires `grandalf` to be installed locally.

---

### Stage 7 — Orchestrator Integration

Status: complete

**Goal:** Update `_research_wrapper` to build `ResearchState` from `ClarificationOutput` fields and
invoke the research graph with `thread_id = session_id` so checkpointing tracks the run.

**Update `_research_wrapper` in `agents/graph/build.py`:**

```python
from agents.research.graph.build import create_research_graph

def _research_wrapper(state: OrchestratorState) -> Dict[str, Any]:
    clarification = state.get("clarification_output") or {}
    session_id = state.get("session_id", "unknown")

    research_state: ResearchState = {
        "destination": state["destination"],
        "destination_cities": state.get("destination_cities"),
        "start_date": state["start_date"],
        "end_date": state["end_date"],
        "trip_duration": state["trip_duration"],
        "budget": state["budget"],
        "currency": state["currency"],
        "travel_party": state["travel_party"],
        # Clarification preferences
        "activity_preferences": clarification.get("activity_preferences"),
        "pace_preference": clarification.get("pace_preference"),
        "dining_style": clarification.get("dining_style"),
        "accommodation_style": clarification.get("accommodation_style"),
        "mobility_level": clarification.get("mobility_level"),
        "dietary_restrictions": clarification.get("dietary_severity"),
        "top_3_must_dos": clarification.get("top_3_must_dos"),
        "budget_priority": clarification.get("budget_priority"),
        "tourist_vs_local": clarification.get("tourist_vs_local"),
        "clarification_output": clarification,
        # Initialize sub-agent output slots
        "weather_output": None, "destination_overview_output": None,
        "budget_analysis_output": None, "accommodation_output": None,
        "activities_output": None, "dining_output": None,
        "transportation_output": None, "curated_highlights_output": None,
        # Initialize repair fields
        "repair_target": None, "repair_attempt_count": 0,
        "last_bad_response": None, "last_repaired_node": None,
        # Initialize final + tracking
        "research_output": None, "research_complete": False,
        "errors": [], "messages": [],
        "session_id": session_id,
    }

    research_graph = create_research_graph()

    # thread_id = session_id → checkpointer tracks this run; can resume if orchestrator restarts
    invoke_config = {"configurable": {"thread_id": f"research-{session_id}"}}
    result = research_graph.invoke(research_state, config=invoke_config)

    if not result.get("research_complete"):
        errors = result.get("errors", [])
        logger.error(f"Research pipeline incomplete. Errors: {errors}")

    return {
        "research_output": result.get("research_output"),
        "current_agent": "planner",
        "messages": result.get("messages", []),
        "errors": result.get("errors", []),
    }
```

**Implemented:** `agents/graph/build.py` now constructs a full `ResearchState`, includes the
relevant clarification fields, initializes all per-node output slots and repair fields, and invokes
the compiled research graph with `thread_id = f"research-{session_id}"`. The wrapper propagates
`research_output`, `messages`, and accumulated `errors` back into the orchestrator state.

**Verification:** The orchestrator test suite was updated to stub the research graph offline and to
validate orchestrator research handoff against `ResearchOutputV2`.

---

### Stage 8 — Observability (LangSmith)

Status: complete

**Goal:** Enable LangSmith tracing so every graph run is traceable in the LangSmith UI.
LangGraph sends traces automatically when the environment variables are set.

**Add to `.env`:**
```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-key>
LANGSMITH_PROJECT=travel-planner-research
```

**Add to `agents/main.py` startup** (reads from env automatically via LangGraph's integration):
```python
# LangSmith tracing is enabled automatically when LANGSMITH_TRACING=true is set.
# No code changes required beyond the environment variables above.
# Each graph.invoke() with a thread_id becomes a named run in LangSmith.
```

**What you get for free:**
- Full token-level traces per node
- Visual graph execution timeline
- Retry events from `RetryPolicy`
- Repair loop detours visible as node re-entries
- Per-session thread grouping (one thread per session_id)

**Implemented:** `.env` now includes `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and
`LANGSMITH_PROJECT`, and `agents/main.py` documents that no explicit code hook is needed beyond the
environment variables because LangGraph picks tracing up automatically.

---

### Stage 9 — Testing

Status: complete

**Create `agents/tests/test_research_pipeline.py`:**

```python
from langgraph.checkpoint.memory import MemorySaver
from agents.research.graph.build import create_research_graph
from agents.shared.contracts.research_output_v2 import ResearchOutputV2

SYNTHETIC_STATE = {
    "destination": "Tokyo",
    "destination_cities": ["Tokyo"],
    "start_date": "2026-04-10",
    "end_date": "2026-04-17",
    "trip_duration": 7,
    "budget": 2000.0,
    "currency": "USD",
    "travel_party": "couple",
    "activity_preferences": ["temples", "food tours", "street markets"],
    "pace_preference": "moderate",
    "tourist_vs_local": "mix",
    "mobility_level": "full",
    "dining_style": ["local street food", "sit-down restaurants"],
    "top_3_must_dos": {"1": "Tsukiji fish market", "2": "TeamLab", "3": "Shibuya crossing"},
    "budget_priority": "experiences_over_comfort",
    "accommodation_style": ["boutique hotel", "central location"],
    "dietary_restrictions": None,
    "clarification_output": None,
    # Initialize all slots
    "weather_output": None, "destination_overview_output": None,
    "budget_analysis_output": None, "accommodation_output": None,
    "activities_output": None, "dining_output": None,
    "transportation_output": None, "curated_highlights_output": None,
    "repair_target": None, "repair_attempt_count": 0,
    "last_bad_response": None, "last_repaired_node": None,
    "research_output": None, "research_complete": False,
    "errors": [], "messages": [],
    "session_id": "test-001",
}

def test_research_pipeline_end_to_end():
    """Full pipeline run with real LLM calls."""
    checkpointer = MemorySaver()
    graph = create_research_graph(checkpointer=checkpointer)
    invoke_config = {"configurable": {"thread_id": "research-test-001"}}

    result = graph.invoke(SYNTHETIC_STATE, config=invoke_config)

    assert result["research_complete"] is True
    assert result["research_output"] is not None

    output = ResearchOutputV2(**result["research_output"])
    assert output.destination == "Tokyo"
    assert len(output.cities) >= 1
    assert len(output.cities[0].activities) >= 5
    assert len(output.curated_highlights) >= 3
    # Budget is in-destination only — full amount preserved
    assert output.budget_analysis.total_available_usd == 2000.0
    assert output.budget_analysis.trip_duration_days == 7
    # Activities reference Tokyo-specific places
    names = [a.name for a in output.cities[0].activities]
    assert any(k in n for n in names for k in ("Senso", "Shibuya", "Tsukiji", "TeamLab", "Shinjuku"))


def test_research_pipeline_checkpoint_resume():
    """Verify checkpointer stores state and graph can be re-invoked on the same thread."""
    checkpointer = MemorySaver()
    graph = create_research_graph(checkpointer=checkpointer)
    invoke_config = {"configurable": {"thread_id": "research-resume-001"}}

    result = graph.invoke(SYNTHETIC_STATE, config=invoke_config)
    assert result["research_complete"] is True

    # Re-invoke on same thread — checkpointer returns final state immediately
    state_snapshot = graph.get_state(invoke_config)
    assert state_snapshot.values["research_complete"] is True
```

**Implemented:** `agents/tests/test_research_pipeline.py` was added with the two live integration
tests above. The file is intentionally gated behind `RUN_LIVE_LLM_TESTS=1` so the default test
suite does not make paid networked LLM calls unexpectedly.

**Verification:** `venv/bin/python -m pytest agents/tests/test_research_pipeline.py -q` collects
cleanly and skips both tests unless `RUN_LIVE_LLM_TESTS=1` is set.

---

## Implementation Status By File

| File | Planned Work | Current Status |
|------|--------------|----------------|
| `agents/shared/contracts/research_output_v2.py` | Create | Done |
| `agents/research/schemas.py` | Rewrite | Done |
| `agents/shared/contracts/__init__.py` | Export V2 contract | Done |
| `agents/shared/llm/client.py` | Add `parse_llm_response` and support structured fallback | Done |
| `agents/research/prompts/templates.py` | Create | Done |
| `agents/research/prompts/builders.py` | Create | Done |
| `agents/research/prompts/__init__.py` | Export prompt builders | Done |
| `agents/research/nodes/base.py` | Add shared node execution helper | Done |
| `agents/research/nodes/weather_node.py` | Create | Done |
| `agents/research/nodes/overview_node.py` | Create | Done |
| `agents/research/nodes/budget_node.py` | Create | Done |
| `agents/research/nodes/accommodation_node.py` | Create | Done |
| `agents/research/nodes/activities_node.py` | Create | Done |
| `agents/research/nodes/dining_node.py` | Create | Done |
| `agents/research/nodes/transport_node.py` | Create | Done |
| `agents/research/nodes/highlights_node.py` | Create | Done |
| `agents/research/nodes/repair_node.py` | Create | Done |
| `agents/research/nodes/aggregate_node.py` | Create | Done |
| `agents/research/nodes/__init__.py` | Export new nodes | Done |
| `agents/research/graph/routing.py` | Create | Done |
| `agents/research/graph/config.py` | Expand for full graph config | Done |
| `agents/research/graph/build.py` | Rewrite to compiled 11-node graph | Done |
| `agents/research/nodes/research.py` | Delete after new graph is wired | Optional cleanup only |
| `agents/graph/build.py` (`_research_wrapper`) | Invoke compiled research graph | Done |
| `.env` | Add LangSmith vars | Done |
| `agents/tests/test_research_pipeline.py` | Create | Done |

---

## Reusable Utilities (do not rewrite)

| Utility | Location | Used by |
|---------|----------|---------|
| `get_cached_client()` | `agents/shared/llm/client.py` | All sub-agent nodes |
| `get_llm_response_with_usage()` | `agents/shared/llm/client.py` | Fallback if `.parse()` unavailable |
| `get_or_create_logger()` | `agents/shared/logging/debug_logger.py` | All sub-agent nodes |
| `save_system_prompt() / load_system_prompt()` | `agents/shared/cache/session_store.py` | Optional per-node caching |

---

## Verification (End-to-End)

```bash
# Set env
export OPENAI_API_KEY_1="..."
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT=travel-planner-research
export RUN_LIVE_LLM_TESTS=1

# Start server
uvicorn agents.main:app --reload --port 8000

# 1. Unit test the research pipeline
python3 -m pytest agents/tests/test_research_pipeline.py -v

# 2. Full API flow
curl -X POST http://localhost:8000/api/clarification/start \
  -H "Content-Type: application/json" \
  -d '{"user_name": "Test", "citizenship": "US", "destination": "Tokyo",
       "start_date": "2026-04-10", "end_date": "2026-04-17",
       "budget": 2000, "currency": "USD", "travel_party": "couple"}'
# → save SESSION_ID

curl -X POST http://localhost:8000/api/clarification/respond \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<SESSION_ID>", "responses": {...}}'
# → repeat until complete == true

curl -X POST http://localhost:8000/api/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<SESSION_ID>"}'

# ✅ research_output.cities[0].activities contain Tokyo-specific named places
# ✅ budget_analysis.total_available_usd == 2000 (no flight deduction)
# ✅ curated_highlights includes at least one of user's stated must-dos
# ✅ planner_output.days reference activity/dining names from research_output
# ✅ LangSmith UI shows a traced run with 11 nodes and all token counts
# ✅ errors list is empty (or only non-critical sub-agent skips if any)
```


# Run the tests
```RUN_LIVE_LLM_TESTS=1 venv/bin/python -m pytest agents/tests/test_research_pipeline.py -q```
Use it like this:

venv/bin/python scripts/research_batch_review.py --write-template logs/research_batch_states.json

Edit the generated logs/research_batch_states.json, then preview the review shell without making LLM calls:
venv/bin/python scripts/research_batch_review.py \
  --input logs/research_batch_states.json \
  --dry-run

Then run the real batch test:
venv/bin/python scripts/research_batch_review.py \
  --input logs/research_batch_states.json

Each run creates a timestamped folder under logs/research_batch_reviews/ with:
report.md
results.json
normalized_states.json
