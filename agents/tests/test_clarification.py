"""
Testing utilities for the clarification agent.

Provides functions for interactive testing and automated test runs.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from agents.clarification.schemas import ClarificationState
from agents.clarification.graph.build import create_clarification_graph


def create_initial_state(
    user_name: str,
    destination: str,
    start_date: str,
    end_date: str,
    budget: float,
    currency: str,
    citizenship: str = "Singaporean",
    travel_party: str = "2 adults",
    budget_scope: str = "Total trip budget",
    health_limitations: Optional[str] = None,
    work_obligations: Optional[str] = None,
    dietary_restrictions: Optional[str] = None,
    specific_interests: Optional[List[str]] = None,
    destination_cities: Optional[list] = None,
) -> ClarificationState:
    """
    Create an initial state for testing.

    Args:
        user_name: User's name
        destination: Trip destination
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        budget: Trip budget
        currency: Budget currency
        citizenship: User's citizenship
        travel_party: Who is traveling
        budget_scope: What budget covers
        health_limitations: Any health limitations
        work_obligations: Work obligations during trip
        dietary_restrictions: Dietary restrictions
        specific_interests: Specific interests
        destination_cities: Specific cities to visit

    Returns:
        Initial ClarificationState dictionary
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    duration = (end - start).days + 1

    return {
        # User context
        "user_name": user_name,
        "citizenship": citizenship,
        "health_limitations": health_limitations,
        "work_obligations": work_obligations,
        "dietary_restrictions": dietary_restrictions,
        "specific_interests": specific_interests,
        # Trip basics
        "destination": destination,
        "destination_cities": destination_cities,
        "start_date": start_date,
        "end_date": end_date,
        "trip_duration": duration,
        "budget": budget,
        "currency": currency,
        "travel_party": travel_party,
        "budget_scope": budget_scope,
        # Process state
        "current_round": 1,
        "completeness_score": 0,
        "clarification_complete": False,
        # Data collection
        "current_questions": None,
        "user_response": None,
        "collected_data": {},
        "messages": [],
    }


def simulate_user_responses(questions_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate user responses to questions for interactive testing.

    Displays questions and collects user input from the command line.

    Args:
        questions_data: Questions dictionary from the LLM

    Returns:
        Dictionary mapping field names to user responses
    """
    print("\n" + "=" * 80)
    print(f"ROUND {questions_data['round']}")
    print("=" * 80)

    responses = {}

    # Display all questions first
    for i, q in enumerate(questions_data["questions"], 1):
        print(f"\n{i}) {q['question_text']}")
        print(f"   Field: {q['field']}")
        print(f"   Multi-select: {q['multi_select']}")
        print(f"   Options:")
        for j, opt in enumerate(q["options"], 0):
            label = chr(65 + j)  # A, B, C, ...
            print(f"      {label}) {opt}")
        if q.get("allow_custom_input"):
            print(f"      Or enter custom text")

    print("\n" + "-" * 80)
    print("Enter your responses (format: 'A, B' for multiple or 'A' for single choice)")
    print("-" * 80 + "\n")

    # Collect user input
    user_inputs = {}
    total_questions = len(questions_data["questions"])

    while len(user_inputs) < total_questions:
        try:
            user_input = input(
                f"Response for question {len(user_inputs) + 1}/{total_questions}: "
            ).strip()

            if not user_input:
                print("   ⚠️  Please enter a response")
                continue

            question_idx = len(user_inputs)
            user_inputs[question_idx] = user_input

        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
            return responses

    # Map user inputs to actual responses
    for i, q in enumerate(questions_data["questions"]):
        if i not in user_inputs:
            continue

        user_input = user_inputs[i].strip()

        # Check if it's option letters or custom text
        if "," in user_input or len(user_input) <= 3:
            # Parse option letters
            selected_letters = [s.strip().upper() for s in user_input.split(",")]

            # Convert letters to option values
            selected_options = []
            for letter in selected_letters:
                if letter and letter.isalpha():
                    option_idx = ord(letter) - 65
                    if 0 <= option_idx < len(q["options"]):
                        selected_options.append(q["options"][option_idx])

            # Store response
            if q["multi_select"]:
                responses[q["field"]] = selected_options
            else:
                responses[q["field"]] = (
                    selected_options[0] if selected_options else None
                )
        else:
            # Custom text input
            responses[q["field"]] = user_input

    print("\n" + "=" * 80)
    print("Responses recorded:")
    for field, value in responses.items():
        print(f"  {field}: {value}")
    print("=" * 80)

    return responses


def test_clarification_agent(
    user_name: str = "Ronnie",
    destination: str = "Colorado, USA",
    start_date: str = "2026-12-15",
    end_date: str = "2026-12-21",
    budget: float = 3000.0,
    currency: str = "USD",
) -> Optional[Dict[str, Any]]:
    """
    Run the complete interactive test of the clarification agent.

    Creates a graph, runs rounds of clarification with user input,
    and returns the final result.

    Args:
        user_name: User's name for the test
        destination: Trip destination
        start_date: Trip start date
        end_date: Trip end date
        budget: Trip budget
        currency: Budget currency

    Returns:
        Final state dictionary, or None if test failed
    """
    # Create the graph
    app = create_clarification_graph()

    # Create initial state
    initial_state = create_initial_state(
        user_name=user_name,
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
    )

    # Configuration for thread persistence
    config = {"configurable": {"thread_id": "test_user_123"}}

    print("\n🚀 Starting Clarification Agent Test\n")

    try:
        # Invoke with initial state
        print("📝 Executing first clarification round...")
        result = app.invoke(initial_state, config)

        if result is None:
            print("❌ Invoke returned None - graph execution failed")
            return None

        # Keep looping until clarification is complete
        while not result.get("clarification_complete", False):
            # Check if we have questions to answer
            questions_data = result.get("current_questions")

            if not questions_data:
                print(
                    "❌ No questions generated but clarification not complete. "
                    "Something went wrong."
                )
                if result.get("messages"):
                    print("Last message:", result["messages"][-1])
                break

            # Get user responses
            user_responses = simulate_user_responses(questions_data)

            # Update collected data
            new_collected_data = {
                **result.get("collected_data", {}),
                **user_responses,
            }

            # Prepare the next state
            next_state = {
                "user_response": user_responses,
                "collected_data": new_collected_data,
                "current_round": result["current_round"] + 1,
                "current_questions": None,
            }

            # Continue the graph
            print(f"\n📝 Continuing with round {next_state['current_round']}...")
            result = app.invoke(next_state, config)

            if result is None:
                print("❌ Invoke returned None during loop")
                break

        if result and result.get("clarification_complete"):
            print("\n✅ Clarification completed!")
            print(f"\nFinal completeness score: {result['completeness_score']}/100")
            print(f"Total rounds: {result['current_round']}")

        return result

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return None


def run_automated_test(
    responses_per_round: list,
    user_name: str = "TestUser",
    destination: str = "Japan",
    start_date: str = "2026-03-01",
    end_date: str = "2026-03-07",
    budget: float = 2000.0,
    currency: str = "USD",
) -> Optional[Dict[str, Any]]:
    """
    Run an automated test with predefined responses.

    Useful for CI/CD testing without interactive input.

    Args:
        responses_per_round: List of response dicts, one per expected round
        user_name: User's name
        destination: Trip destination
        start_date: Trip start date
        end_date: Trip end date
        budget: Trip budget
        currency: Budget currency

    Returns:
        Final state dictionary, or None if test failed
    """
    app = create_clarification_graph()

    initial_state = create_initial_state(
        user_name=user_name,
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
    )

    config = {
        "configurable": {"thread_id": f"automated_test_{datetime.now().timestamp()}"}
    }

    print("\n🤖 Running automated clarification test\n")

    try:
        result = app.invoke(initial_state, config)
        round_idx = 0

        while not result.get("clarification_complete", False):
            if round_idx >= len(responses_per_round):
                print(f"❌ No more predefined responses for round {round_idx + 1}")
                break

            # Use predefined responses
            user_responses = responses_per_round[round_idx]
            print(f"📝 Round {round_idx + 1} responses: {user_responses}")

            new_collected_data = {
                **result.get("collected_data", {}),
                **user_responses,
            }

            next_state = {
                "user_response": user_responses,
                "collected_data": new_collected_data,
                "current_round": result["current_round"] + 1,
                "current_questions": None,
            }

            result = app.invoke(next_state, config)
            round_idx += 1

            if result is None:
                print("❌ Graph execution failed")
                return None

        if result and result.get("clarification_complete"):
            print("\n✅ Automated test completed!")
            print(f"Final score: {result['completeness_score']}/100")
            print(f"Collected data: {json.dumps(result['collected_data'], indent=2)}")

        return result

    except Exception as e:
        print(f"\n❌ Automated test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    final_result = test_clarification_agent()
    if final_result:
        print("\n" + "=" * 80)
        print("FINAL RESULT:")
        print(json.dumps(final_result.get("collected_data", {}), indent=2))
        print("=" * 80)
