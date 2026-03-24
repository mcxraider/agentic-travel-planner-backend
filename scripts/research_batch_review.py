"""
Batch runner for manually reviewing research-agent outputs across synthetic states.

This script helps you curate up to eight synthetic traveler scenarios, run the
staged research graph against each one, and produce a readable Markdown report
plus a raw JSON artifact for deeper inspection.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph.checkpoint.memory import MemorySaver

from agents.research.graph.build import create_research_graph
from agents.shared.contracts.research_output_v2 import ResearchOutputV2


DEFAULT_INPUT_PATH = Path("logs/research_batch_states.json")
DEFAULT_OUTPUT_ROOT = Path("logs/research_batch_reviews")
MAX_SCENARIO_COUNT = 8
DEFAULT_TEMPLATE_SCENARIO_COUNT = 1


BASE_STATE: Dict[str, Any] = {
    "destination": "",
    "destination_cities": None,
    "start_date": "",
    "end_date": "",
    "trip_duration": 0,
    "budget": 0.0,
    "currency": "USD",
    "travel_party": "",
    "activity_preferences": None,
    "pace_preference": None,
    "dining_style": None,
    "accommodation_style": None,
    "mobility_level": None,
    "dietary_restrictions": None,
    "top_3_must_dos": None,
    "budget_priority": None,
    "tourist_vs_local": None,
    "clarification_output": None,
    "weather_output": None,
    "destination_overview_output": None,
    "budget_analysis_output": None,
    "accommodation_output": None,
    "activities_output": None,
    "dining_output": None,
    "transportation_output": None,
    "curated_highlights_output": None,
    "research_output": None,
    "research_complete": False,
    "repair_target": None,
    "repair_attempt_count": 0,
    "last_bad_response": None,
    "last_repaired_node": None,
    "errors": [],
    "messages": [],
    "session_id": None,
}


def build_template_payload(
    scenario_count: int = DEFAULT_TEMPLATE_SCENARIO_COUNT,
) -> Dict[str, Any]:
    """
    Build an editable scenario template.

    Returns:
        JSON-serializable payload containing example scenarios.
    """
    if not 1 <= scenario_count <= MAX_SCENARIO_COUNT:
        raise ValueError(
            f"scenario_count must be between 1 and {MAX_SCENARIO_COUNT}; got {scenario_count}"
        )

    payload = {
        "instructions": [
            f"Edit these {scenario_count} scenarios directly or save this file under a new name.",
            "Only the fields inside each scenario.state block are used by the runner.",
            "You can keep the provided examples or replace them with your own synthetic states.",
            "Run without --dry-run to call the live research graph.",
        ],
        "scenarios": [
            {
                "name": "Tokyo Foodie Couple",
                "notes": "Check if food, local neighborhoods, and must-dos are reflected.",
                "state": {
                    "destination": "Tokyo, Japan",
                    "destination_cities": ["Tokyo"],
                    "start_date": "2026-04-10",
                    "end_date": "2026-04-17",
                    "trip_duration": 7,
                    "budget": 2200.0,
                    "currency": "USD",
                    "travel_party": "couple",
                    "activity_preferences": ["food tours", "markets", "temples"],
                    "pace_preference": "moderate",
                    "dining_style": ["local street food", "sit-down restaurants"],
                    "accommodation_style": ["boutique hotel", "central location"],
                    "mobility_level": "full",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Tsukiji Outer Market",
                        "2": "teamLab Planets",
                        "3": "Senso-ji Temple",
                    },
                    "budget_priority": "experiences_over_comfort",
                    "tourist_vs_local": "mix",
                },
            },
            {
                "name": "Paris Luxury Anniversary",
                "notes": "Evaluate romance, upscale dining, and luxury stay positioning.",
                "state": {
                    "destination": "Paris, France",
                    "destination_cities": ["Paris"],
                    "start_date": "2026-05-14",
                    "end_date": "2026-05-19",
                    "trip_duration": 5,
                    "budget": 5000.0,
                    "currency": "USD",
                    "travel_party": "couple celebrating anniversary",
                    "activity_preferences": [
                        "fine dining",
                        "art museums",
                        "river cruises",
                    ],
                    "pace_preference": "relaxed",
                    "dining_style": ["fine dining", "wine bars"],
                    "accommodation_style": ["luxury hotel", "romantic neighborhood"],
                    "mobility_level": "full",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Seine dinner cruise",
                        "2": "Musee d'Orsay",
                        "3": "Eiffel Tower at sunset",
                    },
                    "budget_priority": "comfort_over_savings",
                    "tourist_vs_local": "balanced",
                },
            },
            {
                "name": "Bangkok Budget Solo",
                "notes": "Check if recommendations stay budget-aware without becoming generic.",
                "state": {
                    "destination": "Bangkok, Thailand",
                    "destination_cities": ["Bangkok"],
                    "start_date": "2026-01-08",
                    "end_date": "2026-01-13",
                    "trip_duration": 5,
                    "budget": 600.0,
                    "currency": "USD",
                    "travel_party": "solo traveler",
                    "activity_preferences": ["street food", "temples", "night markets"],
                    "pace_preference": "fast-paced",
                    "dining_style": ["street food", "casual"],
                    "accommodation_style": ["hostel", "budget hotel"],
                    "mobility_level": "full",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Chatuchak Market",
                        "2": "Wat Pho",
                        "3": "Chinatown food crawl",
                    },
                    "budget_priority": "maximize_value",
                    "tourist_vs_local": "local",
                },
            },
            {
                "name": "Rome Family With Kids",
                "notes": "Evaluate family-friendly pacing and attraction mix.",
                "state": {
                    "destination": "Rome, Italy",
                    "destination_cities": ["Rome"],
                    "start_date": "2026-06-20",
                    "end_date": "2026-06-25",
                    "trip_duration": 5,
                    "budget": 2600.0,
                    "currency": "USD",
                    "travel_party": "2 adults and 2 children",
                    "activity_preferences": ["history", "gelato stops", "easy walking"],
                    "pace_preference": "relaxed",
                    "dining_style": ["family-friendly trattorias"],
                    "accommodation_style": ["family apartment", "quiet neighborhood"],
                    "mobility_level": "moderate",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Colosseum",
                        "2": "Trevi Fountain",
                        "3": "Villa Borghese",
                    },
                    "budget_priority": "balanced",
                    "tourist_vs_local": "tourist",
                },
            },
            {
                "name": "Barcelona Vegetarian Remote Worker",
                "notes": "Check wifi/work practicality and vegetarian dining relevance.",
                "state": {
                    "destination": "Barcelona, Spain",
                    "destination_cities": ["Barcelona"],
                    "start_date": "2026-03-02",
                    "end_date": "2026-03-09",
                    "trip_duration": 7,
                    "budget": 1800.0,
                    "currency": "USD",
                    "travel_party": "solo remote worker",
                    "activity_preferences": ["cafes", "architecture", "beach walks"],
                    "pace_preference": "moderate",
                    "dining_style": ["vegetarian-friendly cafes", "healthy casual"],
                    "accommodation_style": ["aparthotel", "walkable district"],
                    "mobility_level": "full",
                    "dietary_restrictions": "vegetarian",
                    "top_3_must_dos": {
                        "1": "Sagrada Familia",
                        "2": "Gothic Quarter",
                        "3": "Barceloneta sunset walk",
                    },
                    "budget_priority": "balanced",
                    "tourist_vs_local": "mix",
                },
            },
            {
                "name": "Singapore Accessible Senior Trip",
                "notes": "Evaluate mobility sensitivity and practical transport choices.",
                "state": {
                    "destination": "Singapore",
                    "destination_cities": ["Singapore"],
                    "start_date": "2026-02-11",
                    "end_date": "2026-02-16",
                    "trip_duration": 5,
                    "budget": 2400.0,
                    "currency": "USD",
                    "travel_party": "2 seniors",
                    "activity_preferences": [
                        "gardens",
                        "light sightseeing",
                        "food halls",
                    ],
                    "pace_preference": "relaxed",
                    "dining_style": ["hawker centres", "casual"],
                    "accommodation_style": ["comfortable hotel", "easy transit access"],
                    "mobility_level": "limited",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Gardens by the Bay",
                        "2": "Singapore Botanic Gardens",
                        "3": "Marina Bay promenade",
                    },
                    "budget_priority": "comfort_over_savings",
                    "tourist_vs_local": "balanced",
                },
            },
            {
                "name": "Marrakesh Adventure Friends",
                "notes": "Check if the output stays specific and avoids generic 'market/riad' filler.",
                "state": {
                    "destination": "Marrakesh, Morocco",
                    "destination_cities": ["Marrakesh"],
                    "start_date": "2026-10-05",
                    "end_date": "2026-10-10",
                    "trip_duration": 5,
                    "budget": 1400.0,
                    "currency": "USD",
                    "travel_party": "3 friends",
                    "activity_preferences": ["street photography", "food", "day trips"],
                    "pace_preference": "fast-paced",
                    "dining_style": ["local eateries", "rooftop dining"],
                    "accommodation_style": ["stylish riad", "medina access"],
                    "mobility_level": "full",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Jemaa el-Fnaa",
                        "2": "Bahia Palace",
                        "3": "Atlas Mountains day trip",
                    },
                    "budget_priority": "experiences_over_comfort",
                    "tourist_vs_local": "mix",
                },
            },
            {
                "name": "New York First-Time Weekend",
                "notes": "Evaluate how well a short trip is prioritized and ranked.",
                "state": {
                    "destination": "New York City, USA",
                    "destination_cities": ["New York City"],
                    "start_date": "2026-09-18",
                    "end_date": "2026-09-21",
                    "trip_duration": 3,
                    "budget": 1700.0,
                    "currency": "USD",
                    "travel_party": "2 friends",
                    "activity_preferences": ["iconic landmarks", "jazz bars", "pizza"],
                    "pace_preference": "fast-paced",
                    "dining_style": ["pizza", "classic diners", "cocktail bars"],
                    "accommodation_style": ["mid-range hotel", "central"],
                    "mobility_level": "full",
                    "dietary_restrictions": None,
                    "top_3_must_dos": {
                        "1": "Top of the Rock",
                        "2": "Central Park",
                        "3": "Greenwich Village jazz club",
                    },
                    "budget_priority": "balanced",
                    "tourist_vs_local": "tourist",
                },
            },
        ],
    }
    payload["scenarios"] = payload["scenarios"][:scenario_count]
    return payload


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed argument namespace
    """
    parser = argparse.ArgumentParser(
        description="Run and review the research agent across synthetic scenarios."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to the JSON file containing scenario definitions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where the report folder should be created.",
    )
    parser.add_argument(
        "--write-template",
        type=Path,
        help="Write an editable eight-scenario template to this path and exit.",
    )
    parser.add_argument(
        "--scenario-count",
        type=int,
        default=DEFAULT_TEMPLATE_SCENARIO_COUNT,
        help=f"How many scenarios to include when writing a template ({1}-{MAX_SCENARIO_COUNT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and generate the report shell without calling the live graph.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    """
    Convert a human-readable label into a filesystem- and thread-safe slug.

    Args:
        value: Raw label

    Returns:
        Lowercase slug
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "scenario"


def write_template(path: Path, scenario_count: int) -> None:
    """
    Write the default scenario template.

    Args:
        path: Destination file path
        scenario_count: Number of scenarios to include
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_template_payload(scenario_count=scenario_count)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def load_scenarios(path: Path) -> List[Dict[str, Any]]:
    """
    Load scenarios from disk.

    Args:
        path: JSON file path

    Returns:
        List of scenario dictionaries
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}. Run with --write-template {path} first."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        scenarios = payload.get("scenarios")
    else:
        scenarios = payload

    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Input JSON must contain a non-empty 'scenarios' list.")

    return scenarios


def build_state(scenario: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Merge a scenario's partial state into the full research state shape.

    Args:
        scenario: Scenario definition
        index: 1-based scenario index

    Returns:
        Fully-initialized research state
    """
    state_overrides = scenario.get("state")
    if not isinstance(state_overrides, dict):
        raise ValueError(f"Scenario {index} is missing a valid 'state' object.")

    state = copy.deepcopy(BASE_STATE)
    state.update(state_overrides)

    required_keys = [
        "destination",
        "start_date",
        "end_date",
        "trip_duration",
        "budget",
        "currency",
        "travel_party",
    ]
    missing = [key for key in required_keys if not state.get(key)]
    if missing:
        raise ValueError(
            f"Scenario {index} is missing required state fields: {', '.join(missing)}"
        )

    if state["session_id"] is None:
        name = scenario.get("name") or f"scenario-{index:02d}"
        state["session_id"] = f"batch-review-{index:02d}-{slugify(name)}"

    return state


def run_scenario(
    graph: Any,
    scenario: Dict[str, Any],
    state: Dict[str, Any],
    index: int,
    run_prefix: str,
    dry_run: bool,
) -> Dict[str, Any]:
    """
    Execute one scenario or prepare a dry-run placeholder result.

    Args:
        graph: Compiled research graph
        scenario: Scenario metadata
        state: Fully-resolved research state
        index: 1-based scenario index
        run_prefix: Shared run identifier prefix
        dry_run: Whether to skip live graph invocation

    Returns:
        Result payload for reporting
    """
    scenario_name = scenario.get("name") or f"Scenario {index}"
    thread_id = f"{run_prefix}-{index:02d}-{slugify(scenario_name)}"

    if dry_run:
        return {
            "name": scenario_name,
            "notes": scenario.get("notes"),
            "thread_id": thread_id,
            "status": "dry_run",
            "duration_seconds": 0.0,
            "state": state,
            "result": None,
            "validated_output": None,
            "exception": None,
        }

    started_at = time.perf_counter()
    try:
        result = graph.invoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        )
        duration_seconds = time.perf_counter() - started_at
        validated_output = None
        if result.get("research_output") is not None:
            validated_output = ResearchOutputV2.model_validate(
                result["research_output"]
            ).model_dump()

        status = "success" if result.get("research_complete") else "incomplete"
        return {
            "name": scenario_name,
            "notes": scenario.get("notes"),
            "thread_id": thread_id,
            "status": status,
            "duration_seconds": round(duration_seconds, 2),
            "state": state,
            "result": result,
            "validated_output": validated_output,
            "exception": None,
        }
    except Exception as exc:  # noqa: BLE001 - reporting wrapper should capture all failures
        duration_seconds = time.perf_counter() - started_at
        return {
            "name": scenario_name,
            "notes": scenario.get("notes"),
            "thread_id": thread_id,
            "status": "error",
            "duration_seconds": round(duration_seconds, 2),
            "state": state,
            "result": None,
            "validated_output": None,
            "exception": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        }


def comma_join(values: List[str]) -> str:
    """
    Render a list for Markdown output.

    Args:
        values: Sequence of strings

    Returns:
        Joined string or a fallback marker
    """
    return ", ".join(values) if values else "n/a"


def summarize_list(items: List[Dict[str, Any]], key: str, limit: int = 5) -> List[str]:
    """
    Extract a short list of names/titles from output sections.

    Args:
        items: Section payload
        key: Key to read from each item
        limit: Maximum number of entries to keep

    Returns:
        List of summary strings
    """
    summary = [str(item.get(key)) for item in items[:limit] if item.get(key)]
    return summary


def build_report(results: List[Dict[str, Any]], input_path: Path, dry_run: bool) -> str:
    """
    Build a Markdown report for manual review.

    Args:
        results: Scenario run results
        input_path: Source scenario file path
        dry_run: Whether live execution was skipped

    Returns:
        Markdown document string
    """
    generated_at = datetime.now(timezone.utc).isoformat()
    lines: List[str] = [
        "# Research Agent Batch Review",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Input file: `{input_path.resolve()}`",
        f"- Scenario count: `{len(results)}`",
        f"- Run mode: `{'dry-run' if dry_run else 'live'}`",
        "",
        "## Summary",
        "",
        "| # | Scenario | Destination | Status | Degraded | Missing Sections | Duration (s) |",
        "|---|---|---|---|---|---|---:|",
    ]

    for index, item in enumerate(results, start=1):
        validated_output = item.get("validated_output") or {}
        metadata = validated_output.get("metadata") or {}
        state = item.get("state") or {}
        missing = comma_join(metadata.get("missing_sections") or [])
        degraded = metadata.get("degraded", "n/a")
        lines.append(
            "| {index} | {name} | {destination} | {status} | {degraded} | {missing} | {duration:.2f} |".format(
                index=index,
                name=item["name"],
                destination=state.get("destination", "n/a"),
                status=item["status"],
                degraded=degraded,
                missing=missing,
                duration=item["duration_seconds"],
            )
        )

    for index, item in enumerate(results, start=1):
        state = item.get("state") or {}
        result = item.get("result") or {}
        validated_output = item.get("validated_output") or {}
        metadata = validated_output.get("metadata") or {}
        city = (validated_output.get("cities") or [{}])[0]
        budget = validated_output.get("budget_analysis") or {}
        transport = validated_output.get("transportation") or []
        highlights = validated_output.get("curated_highlights") or []
        accommodation = city.get("accommodation_areas") or []
        activities = city.get("activities") or []
        dining = city.get("dining") or []

        lines.extend(
            [
                "",
                f"## {index}. {item['name']}",
                "",
                f"- Notes: {item.get('notes') or 'n/a'}",
                f"- Thread ID: `{item['thread_id']}`",
                f"- Status: `{item['status']}`",
                f"- Duration: `{item['duration_seconds']:.2f}s`",
                "",
                "### Input Snapshot",
                "",
                f"- Destination: `{state.get('destination', 'n/a')}`",
                f"- Cities: `{comma_join(state.get('destination_cities') or [])}`",
                f"- Dates: `{state.get('start_date', 'n/a')} -> {state.get('end_date', 'n/a')}`",
                f"- Trip duration: `{state.get('trip_duration', 'n/a')} days`",
                f"- Budget: `{state.get('budget', 'n/a')} {state.get('currency', 'n/a')}`",
                f"- Travel party: `{state.get('travel_party', 'n/a')}`",
                f"- Activity preferences: `{comma_join(state.get('activity_preferences') or [])}`",
                f"- Dining style: `{comma_join(state.get('dining_style') or [])}`",
                f"- Accommodation style: `{comma_join(state.get('accommodation_style') or [])}`",
                f"- Pace: `{state.get('pace_preference') or 'n/a'}`",
                f"- Tourist vs local: `{state.get('tourist_vs_local') or 'n/a'}`",
                f"- Mobility: `{state.get('mobility_level') or 'n/a'}`",
                f"- Dietary restrictions: `{state.get('dietary_restrictions') or 'n/a'}`",
                "",
                "### Manual Review Checklist",
                "",
                "- [ ] Output matches the traveler profile and trip constraints",
                "- [ ] Activities and dining are specific to the destination, not generic filler",
                "- [ ] Budget analysis feels realistic for the destination and traveler",
                "- [ ] Accommodation and transport recommendations are practical",
                "- [ ] Curated highlights are useful and well-prioritized",
                "- [ ] Any hallucinations, repetition, or weak recommendations are noted below",
                "",
                "Reviewer notes:",
                "```text",
                "",
                "```",
                "",
            ]
        )

        if item["status"] == "error":
            lines.extend(
                [
                    "### Failure",
                    "",
                    f"- Exception type: `{item['exception']['type']}`",
                    f"- Message: `{item['exception']['message']}`",
                    "",
                    "```text",
                    item["exception"]["traceback"].rstrip(),
                    "```",
                ]
            )
            continue

        if item["status"] == "dry_run":
            lines.extend(
                [
                    "### Dry Run",
                    "",
                    "Live execution was skipped. Review the normalized input above before running without `--dry-run`.",
                ]
            )
            continue

        lines.extend(
            [
                "### Output Snapshot",
                "",
                f"- Research complete: `{result.get('research_complete')}`",
                f"- Degraded: `{metadata.get('degraded', 'n/a')}`",
                f"- Missing sections: `{comma_join(metadata.get('missing_sections') or [])}`",
                f"- Critical failures: `{comma_join(metadata.get('critical_failures') or [])}`",
                f"- Budget assessment: `{budget.get('budget_assessment', 'n/a')}`",
                f"- Daily budget: `{budget.get('daily_budget_usd', 'n/a')}`",
                f"- Recommended stay area(s): `{comma_join(summarize_list(accommodation, 'neighborhood', limit=3))}`",
                f"- Top activities: `{comma_join(summarize_list(activities, 'name'))}`",
                f"- Top dining: `{comma_join(summarize_list(dining, 'name', limit=4))}`",
                f"- Transport options: `{comma_join(summarize_list(transport, 'mode', limit=4))}`",
                f"- Curated highlights: `{comma_join(summarize_list(highlights, 'title', limit=5))}`",
                "",
                "### Errors",
                "",
                "```json",
                json.dumps(result.get("errors", []), indent=2, ensure_ascii=True),
                "```",
                "",
                "### Raw Output",
                "",
                "```json",
                json.dumps(validated_output, indent=2, ensure_ascii=True),
                "```",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    """
    Script entry point.

    Returns:
        Process exit code
    """
    args = parse_args()

    if args.write_template:
        write_template(args.write_template, scenario_count=args.scenario_count)
        print(
            f"Wrote template with {args.scenario_count} scenarios to {args.write_template.resolve()}"
        )
        return 0

    try:
        scenarios = load_scenarios(args.input)
    except Exception as exc:  # noqa: BLE001 - CLI should surface user-facing errors
        print(f"Failed to load scenarios: {exc}", file=sys.stderr)
        return 1

    if not 1 <= len(scenarios) <= MAX_SCENARIO_COUNT:
        print(
            f"Input must contain between 1 and {MAX_SCENARIO_COUNT} scenarios; found {len(scenarios)}.",
            file=sys.stderr,
        )
        return 1

    graph = None if args.dry_run else create_research_graph(checkpointer=MemorySaver())
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results: List[Dict[str, Any]] = []

    for index, scenario in enumerate(scenarios, start=1):
        try:
            state = build_state(scenario, index)
        except Exception as exc:  # noqa: BLE001 - continue collecting failures in one report
            results.append(
                {
                    "name": scenario.get("name") or f"Scenario {index}",
                    "notes": scenario.get("notes"),
                    "thread_id": f"{run_id}-{index:02d}-invalid",
                    "status": "error",
                    "duration_seconds": 0.0,
                    "state": scenario.get("state") or {},
                    "result": None,
                    "validated_output": None,
                    "exception": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                }
            )
            continue

        result = run_scenario(graph, scenario, state, index, run_id, args.dry_run)
        results.append(result)
        print(f"[{index}/{len(scenarios)}] {result['name']} -> {result['status']}")

    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "report.md"
    results_path = output_dir / "results.json"
    normalized_states_path = output_dir / "normalized_states.json"

    report_path.write_text(
        build_report(results=results, input_path=args.input, dry_run=args.dry_run),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    normalized_states_path.write_text(
        json.dumps([item["state"] for item in results], indent=2, ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )

    print("")
    print(f"Report written to {report_path.resolve()}")
    print(f"Raw results written to {results_path.resolve()}")
    print(f"Normalized states written to {normalized_states_path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
