# agentic-travel-planner-backend

This repository contains the backend for an “agentic” travel planner — a system that can take a travel idea, ask smart follow‑up questions, do supporting research, and produce a structured plan.

It’s designed to feel less like a single one‑shot response and more like a small team workflow: clarify the request, gather context, draft an itinerary, and sanity‑check the output.

Under the hood, the workflow is modeled as a small decision-and-step graph (using LangGraph) so the system can move between stages predictably while still adapting to what the user needs.

## What it does

Given an initial user prompt (for example, “plan a long weekend in Tokyo for food and museums”), the backend:

- Figures out what’s missing or ambiguous and asks for clarifications.
- Uses the answers to steer what information it should look for.
- Produces a coherent travel plan that matches the user’s constraints and preferences.
- Applies basic validation so the final output is consistent and complete.

## Rough flow

At a high level the system moves through a few phases:

1. **Clarify**: Identify unknowns (dates, budget, pace, must‑dos) and ask targeted questions.
2. **Research**: Collect supporting details that help the plan feel grounded.
3. **Plan**: Assemble an itinerary and travel guidance in a structured format.
4. **Validate**: Check that the result meets expectations (e.g., nothing obviously missing or contradictory).

## How the codebase is organized

The main pieces map to the phases above:

- `agents/`: The “brains” that coordinate the overall behavior.
- `agents/clarification/`: The clarification loop — generating questions and turning answers into usable constraints.
- `agents/clarification/graph/`: The LangGraph-based workflow structure for moving between steps.
- `agents/research/`: Research helpers used to inform the plan.
- `agents/planner/`: Planning logic that turns constraints + research into an itinerary.
- `validator/`: Lightweight checks to catch incomplete or inconsistent outputs.
- `shared/`: Shared schemas, logging, and common utilities used across modules.
- `tests/`: A small test suite focusing on the clarification behavior.
- `logs/`: Notes and run logs captured during development/experimentation.

## What “agentic” means here

In this project, “agentic” simply means the planner can:

- Decide what it needs to ask next.
- Use those answers to change its approach.
- Break the task into steps (rather than trying to do everything in one go).
- Produce outputs that are easier to consume downstream (structured, validated, consistent).

## Status

This is an actively evolving backend; the exact outputs and behavior may change as prompts, validation, and planning heuristics are refined.
