# Multi-Agent Graph Refactor Plan

**Goal**: Create a top-level orchestrator graph that composes agent sub-graphs (clarification → research → planner) sequentially. Each agent keeps its own state + compiled sub-graph, with handoff contracts defining the data passed between them.

---

## Architecture Decisions

| Decision              | Choice                              | Rationale                                                       |
| --------------------- | ----------------------------------- | --------------------------------------------------------------- |
| Agent interaction     | Sequential pipeline                 | Matches natural travel planning flow: clarify → research → plan |
| State management      | Per-agent state + handoff contracts | Clean boundaries, easier testing, explicit interfaces           |
| Orchestrator location | `agents/graph/`                     | Keeps all agent code under `agents/`                            |

---

## Steps

### 1. Create `agents/graph/` orchestrator folder

| File                       | Purpose                                                    |
| -------------------------- | ---------------------------------------------------------- |
| `agents/graph/__init__.py` | Export `create_travel_planner_graph()`                     |
| `agents/graph/build.py`    | Main graph builder that imports and composes sub-graphs    |
| `agents/graph/state.py`    | `OrchestratorState` with `current_agent` and handoff slots |
| `agents/graph/router.py`   | Routing logic to move between agents sequentially          |

### 2. Define handoff contracts in shared

| File                                              | Schema                  | Producer      | Consumer       |
| ------------------------------------------------- | ----------------------- | ------------- | -------------- |
| `agents/shared/contracts/clarification_output.py` | `ClarificationOutputV2` | clarification | research       |
| `agents/shared/contracts/research_output.py`      | `ResearchOutputV1`      | research      | planner        |
| `agents/shared/contracts/planner_output.py`       | `PlannerOutputV1`       | planner       | (final output) |

### 3. Refactor clarification sub-graph

- `create_clarification_graph()` in `agents/clarification/graph/build.py` already returns a compiled sub-graph
- Add an `output_contract` field to `ClarificationState` that maps to `ClarificationOutputV2`
- Ensure the sub-graph's `output_node` populates this contract

### 4. Create research agent sub-graph

New folder `agents/research/` with structure mirroring clarification:

```
agents/research/
├── __init__.py
├── schemas.py              # ResearchState TypedDict
├── research_api.py         # (optional) standalone API for testing
├── graph/
│   ├── __init__.py
│   ├── build.py            # create_research_graph()
│   └── config.py
├── nodes/
│   ├── __init__.py
│   └── research.py         # research_node, routing, output
└── prompts/
    ├── __init__.py
    ├── templates.py
    └── builders.py
```

- **Input**: `ClarificationOutputV2` from contract
- **Output**: populates `ResearchOutputV1` contract

### 5. Create planner agent sub-graph (placeholder)

New folder `agents/planner/` with same structure:

```
agents/planner/
├── __init__.py
├── schemas.py              # PlannerState TypedDict
├── graph/
│   ├── __init__.py
│   ├── build.py            # create_planner_graph()
│   └── config.py
├── nodes/
│   ├── __init__.py
│   └── planner.py
└── prompts/
    ├── __init__.py
    ├── templates.py
    └── builders.py
```

- **Input**: `ResearchOutputV1`
- **Output**: `PlannerOutputV1` (final itinerary)

### 6. Wire orchestrator in `agents/graph/build.py`

```
Entry → clarification_subgraph → handoff_to_research → research_subgraph → handoff_to_planner → planner_subgraph → END
```

- Use `add_node()` with each compiled sub-graph
- Handoff nodes extract contract output and inject into next agent's input state

### 7. Update API layer

- Update `agents/main.py` to import from `agents.graph` instead of `agents.clarification`
- Keep `agents/clarification/clarification_api.py` for legacy/standalone clarification access

---

## Proposed Folder Structure

```
agents/
├── graph/                  # NEW: Top-level orchestrator
│   ├── __init__.py
│   ├── build.py            # create_travel_planner_graph()
│   ├── state.py            # OrchestratorState
│   └── router.py           # Sequential routing
├── clarification/          # UNCHANGED (self-contained sub-graph)
│   ├── graph/build.py
│   ├── nodes/
│   ├── schemas.py
│   └── ...
├── research/               # NEW: Research sub-graph
│   ├── graph/build.py
│   ├── nodes/
│   └── schemas.py
├── planner/                # NEW: Planner sub-graph
│   ├── graph/build.py
│   ├── nodes/
│   └── schemas.py
└── shared/
    └── contracts/          # Handoff schemas
        ├── clarification_output.py
        ├── research_output.py
        └── planner_output.py
```

---

## Verification Checklist

- [ ] Run existing tests: `pytest agents/tests/` to ensure clarification still works standalone
- [ ] Test orchestrator: Create a simple test invoking `create_travel_planner_graph()` and verifying state flows through handoffs
- [ ] Validate contracts: Unit test that each sub-graph's output satisfies its contract schema

---

## Implementation Order

1. Create `agents/graph/` skeleton with state and empty build
2. Add `ResearchOutputV1` and `PlannerOutputV1` contracts to shared
3. Scaffold `agents/research/` folder structure
4. Scaffold `agents/planner/` folder structure
5. Wire orchestrator to call sub-graphs sequentially
6. Add handoff nodes between agents
7. Update `main.py` to use new orchestrator
8. Add integration tests
