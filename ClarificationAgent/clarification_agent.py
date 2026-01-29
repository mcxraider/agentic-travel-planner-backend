# imports
import json
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator
from openai import OpenAI
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# module-level cache
_client: OpenAI | None = None
#@title SYSTEM PROMPT
SYSTEM_PROMPT_PART_1 = f"""# Role: Trip Planning Clarification Agent

You are a travel planning assistant conducting a clarification interview to understand the user's travel preferences.

Your ONLY responsibility is to ask clarification questions and return them in a strictly structured, machine-parsable format. You must NOT plan, suggest, or recommend any itinerary.

You are interacting with a frontend that will parse structured multiple-choice responses.

---

## Dynamic Destination Context (IMPORTANT):

The destination will be provided dynamically as:
- Destination Country
- Destination Cities (if known)
- Season and travel dates

You MUST:
- Ask destination-specific questions based ONLY on the provided destination context
- NEVER hardcode assumptions about a specific country
- Adapt interest examples dynamically (e.g. mountains, nightlife, culture, food, climate, geography, seasonal activities)

---
## Information You Already Have (Pre-filled):
"""

SYSTEM_PROMPT_PART_2 = """
---

## REQUIRED INFO (Highest Priority)

1. **activity_preferences** (choose at least 2):
   * nature / hiking
   * history / museums
   * food / gastronomy
   * shopping
   * adventure / adrenaline
   * art / culture
   * nightlife
   * relaxation / wellness

2. **pace_preference**:
   * relaxed
   * moderate
   * intense

3. **tourist_vs_local_preference**:
   * major tourist landmarks
   * hidden gems / local spots
   * balanced mix

4. **mobility_walking_capacity**:
   * minimal walking (<5k steps/day)
   * moderate walking (~10k steps/day)
   * high walking (15k+ steps/day or hiking-intensive)

5. **dining_style** (multiple allowed):
   * street food
   * casual dining
   * fine dining
   * self-cooking (bring own food)

---

## RECOMMENDED INFO (Medium Priority)

6. **primary_activity_focus** (single priority):
   (Generate options based on Activity Preferences)

7. **destination_specific_interests** (Top Things to Do):
   (Generate 10–15 top activities based on destination and season)
   * Include option: "Other (Input your own)"

8. **transportation_preference** (multiple allowed):
   * public transport
   * taxis / ride-hailing
   * rental car
   * walking / cycling

9. **arrival_time**:
   * Early morning (before 9am)
   * Mid-morning (9am-12pm)
   * Afternoon (12pm-5pm)
   * Evening (after 5pm)
   * (Allow custom input)

10. **departure_time**:
    * Early morning (before 9am)
    * Mid-morning (9am-12pm)
    * Afternoon (12pm-5pm)
    * Evening (after 5pm)
    * (Allow custom input)

11. **special_logistics**:
    (Free text input for complex logistics)

---

## NICE-TO-HAVE INFO (Lowest Priority)

12. **wifi_need**:
    * Essential
    * Preferred but not critical
    * Not important

13. **schedule_preference**:
    * tightly packed every day
    * tightly packed on some days, relaxed on others
    * mostly moderate pacing
    * relaxed
    * very relaxed / spontaneous

---

## Question Priority Order (STRICT):

1. REQUIRED questions (1–5) in numerical order
2. RECOMMENDED questions (6–11) in numerical order
3. NICE-TO-HAVE questions (12–13) in numerical order

Rules:
- NEVER skip an unanswered higher-priority question
- NEVER ask lower-priority questions while higher-priority ones are missing

---

## Completeness Score Rules:

- Each REQUIRED item answered: +13 points (max 65)
- Each RECOMMENDED item answered: +4 points (max 24)
- Each NICE-TO-HAVE item answered: +3.5 points (max ~11)

Maximum score: 100

---

## Question Rounds & Limits:

- EXACTLY 4 questions in Round 1
- AT MOST 5 questions in Rounds 2 and 3
- Maximum 3 rounds total
- Stop immediately once stopping condition is met

---

## OUTPUT FORMAT (STRICT — JSON ONLY):

### During Clarification Rounds (Rounds 1-3):

When asking questions, output ONLY valid JSON using the following schema:
```json
{
  "status": "in_progress",
  "round": <number>,
  "questions": [
    {
      "question_id": "<string>",
      "field": "<field_name>",
      "multi_select": <true | false>,
      "question_text": "<string>",
      "options": ["Option A", "Option B", "Other (Please specify)"],
      "allow_custom_input": <true | false>
    }
  ],
  "state": {
    "answered_fields": ["<field_name>"],
    "missing_fields": ["<field_name>"],
    "completeness_score": <number>
  }
}
```

---

## FINAL OUTPUT FORMAT (CRITICAL):

When you determine that clarification is complete (completeness score ≥ 80 OR 3 rounds completed), you MUST output in the following format:

**First line:** The exact text "Clarification Done" (no quotes in output)

**Second part:** A complete JSON object containing ALL collected information.

### Final Output Schema:
```json
{
  "activity_preferences": [<array>],
  "pace_preference": "<string>",
  "tourist_vs_local_preference": "<string>",
  "mobility_walking_capacity": "<string>",
  "dining_style": [<array>],
  "primary_activity_focus": "<string>",
  "destination_specific_interests": [<array>],
  "transportation_preference": [<array>],
  "arrival_time": "<string>",
  "departure_time": "<string>",
  "special_logistics": "<string or null>",
  "wifi_need": "<string>",
  "schedule_preference": "<string>"
}
```

---

## Response Constraints (STRICT):

- Output JSON ONLY (no markdown code blocks, no prose, no explanations)
- Do NOT explain questions
- Do NOT summarize user responses
- Do NOT provide recommendations
- When completing clarification, output ONLY "Clarification Done" followed by the final JSON

---

## Stop Rule (MANDATORY):

If:
- Completeness score ≥ 80
OR
- 3 rounds of questions have been asked

Then output "Clarification Done" followed by the complete JSON object.
"""


#@title STATE DEFINITION
class ClarificationState(TypedDict):
    """State schema for the clarification agent"""
    # User context (pre-filled)
    user_name: str
    citizenship: str
    health_limitations: Optional[str]
    work_obligations: Optional[str]
    dietary_restrictions: Optional[str]
    specific_interests: Optional[str]

    # Trip basics (pre-filled)
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float
    currency: str
    travel_party: str
    budget_scope: str

    # Clarification process state
    current_round: int
    completeness_score: int
    clarification_complete: bool

    # Questions and responses
    current_questions: Optional[dict]  # JSON with questions
    user_response: Optional[dict]  # User's answers to current questions

    # Accumulated answers (build up over rounds)
    collected_data: dict

    # Messages for tracking conversation
    messages: Annotated[List[dict], operator.add]


def build_user_context(state: ClarificationState) -> str:
    context = f"""
User Profile:
- Name: {state['user_name']}
- Citizenship: {state['citizenship']}
- Health limitations: {state.get('health_limitations', 'None specified')}
- Work obligations: {state.get('work_obligations', 'None specified')}
- Dietary restrictions: {state.get('dietary_restrictions', 'None specified')}
- Specific interests: {state.get('specific_interests', 'None specified')}

Trip Basics:
- Destination: {state['destination']}
- Dates: {state['start_date']} to {state['end_date']} ({state['trip_duration']} days)
- Budget: {state['budget']} {state['currency']} total for the trip
- Travel party: {state['travel_party']}
- Budget scope: {state['budget_scope']}
"""
    return context

def build_system_prompt(state: ClarificationState, system_prompt_1, system_prompt_2) -> str:
    user_context = build_user_context(state)
    system_prompt = system_prompt_1 + user_context + system_prompt_2
    return system_prompt


def build_user_prompt(collected_data_text, user_response_text, state: ClarificationState) -> str:
    prompt = f"""{collected_data_text}{user_response_text}
This is Round {state['current_round']}. Generate questions or complete clarification as appropriate."""
    return prompt


def build_user_response_text(state):
    if state.get('user_response') and state['current_round'] > 1:
        user_response_text = f"\n\nUser's responses from Round {state['current_round'] - 1}:\n{json.dumps(state['user_response'], indent=2)}"
    else:
        user_response_text = ""
    return user_response_text

def build_collected_data(state):
    if state.get('collected_data'):
        collected_data_text = f"\n\nInformation collected so far:\n{json.dumps(state['collected_data'], indent=2)}"
    else:
        collected_data_text = ""
    return collected_data_text


def get_llm_response(client, user_prompt, system_prompt):
    # Call OpenAI Chat Completion API
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response


def parse_response(state: ClarificationState, response) -> dict:
    llm_response = response.choices[0].message.content.strip()

    # Parse the response
    if llm_response.startswith("Clarification Done"):
        # Extract the JSON part (everything after "Clarification Done")
        json_part = llm_response.replace("Clarification Done", "").strip()
        try:
            final_data = json.loads(json_part)
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error in final data: {e}")
            print(f"Raw response: {llm_response}")
            raise

        return {
            **state,
            "clarification_complete": True,
            "collected_data": final_data,
            "completeness_score": 100,
            "messages": [{"role": "assistant", "content": "Clarification complete!", "data": final_data}]
        }
    else:
        # Parse as questions JSON
        try:
            questions_data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error in questions: {e}")
            print(f"Raw response: {llm_response}")
            raise

        return {
            **state,
            "current_round": state["current_round"],
            "current_questions": questions_data,
            "completeness_score": questions_data["state"]["completeness_score"],
            "messages": [{"role": "assistant", "content": "Questions generated", "questions": questions_data}]
        }

def output_generator(state: ClarificationState) -> ClarificationState:
    """
    Final output generator - formats the collected data nicely.
    """
    print("\n" + "="*80)
    print("CLARIFICATION COMPLETE!")
    print("="*80)
    print(f"\nCompleteness Score: {state['completeness_score']}/100")
    print(f"Rounds Completed: {state['current_round']}")
    print("\nCollected Data:")
    print(json.dumps(state['collected_data'], indent=2))
    print("="*80 + "\n")

    return state

def get_cached_client() -> OpenAI:
    """Returns cached instance of OpenAI client"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key= os.environ.get("OPENAI_API_KEY_1")
        )
    print("client initialised correctly")
    return _client


#@title Agent
def clarification_agent(state: ClarificationState) -> ClarificationState:
    """
    Clarification agent that asks questions based on missing information.

    This is a MOCK implementation - replace with actual LLM call using your prompt.
    """

    try:
        client = get_cached_client()

        # Read the prompt from the document you provided
        system_prompt = build_system_prompt(state, SYSTEM_PROMPT_PART_1, SYSTEM_PROMPT_PART_2)

        # Build the user response context if this isn't round 1
        user_response_text = build_user_response_text(state)

        # Build collected data context
        collected_data_text = build_collected_data(state)

        # craft user prompt
        user_prompt = build_user_prompt(collected_data_text, user_response_text, state)

        print("\n" + "="*80)
        print(f"🤖 Round {state['current_round']} - Calling LLM")
        print("="*80)
        print(f"\n📋 USER PROMPT:\n{user_prompt}")
        print(f"\n📊 State Debug:")
        print(f"   - collected_data: {state.get('collected_data', {})}")
        print(f"   - current_round: {state['current_round']}")
        print(f"   - completeness_score: {state.get('completeness_score', 0)}")
        print("="*80)

        # get LLM response
        response = get_llm_response(client, user_prompt, system_prompt)

        # filter results
        result = parse_response(state, response)
        print(f"✅ Round {state['current_round']} completed - Score: {result.get('completeness_score', 0)}/100")
        return result
    except Exception as e:
        print(f"❌ Error in clarification_agent: {e}")
        import traceback
        traceback.print_exc()
        raise

#@title Langgraph routing
# ============================================================================
# ROUTING LOGIC
# ============================================================================

def should_continue(state: ClarificationState) -> str:
    """Determine whether to continue asking questions or finish"""
    if state['clarification_complete']:
        return "output"
    else:
        return "clarification"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_clarification_graph():
    """Create and compile the LangGraph workflow"""
    graph = StateGraph(ClarificationState)

    # Add nodes
    graph.add_node("clarification", clarification_agent)
    graph.add_node("output", output_generator)

    # Set entry point
    graph.set_entry_point("clarification")

    # Add conditional routing
    graph.add_conditional_edges(
        "clarification",
        should_continue,
        {
            "clarification": "clarification",  # Loop back for more questions
            "output": "output"  # Move to final output
        }
    )

    # End after output
    graph.add_edge("output", END)

    # Compile with checkpointing for state persistence
    memory = MemorySaver()
    app = graph.compile(
        checkpointer=memory,
        interrupt_after=["clarification"]  # Pause after clarification to wait for user input
    )

    return app

#@title Clarification module testing utilities
# ============================================================================
# TESTING UTILITIES
# ============================================================================

def create_initial_state(
    user_name: str,
    destination: str,
    start_date: str,
    end_date: str,
    budget: float,
    currency: str
) -> ClarificationState:
    """Create an initial state for testing"""

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    duration = (end - start).days + 1

    return {
        # User context
        "user_name": user_name,
        "citizenship": "Singaporean",
        "health_limitations": None,
        "work_obligations": None,
        "dietary_restrictions": None,
        "specific_interests": None,

        # Trip basics
        "destination": destination,
        "destination_cities": None,
        "start_date": start_date,
        "end_date": end_date,
        "trip_duration": duration,
        "budget": budget,
        "currency": currency,
        "travel_party": "2 adults",
        "budget_scope": "Total trip budget",

        # Process state
        "current_round": 1,
        "completeness_score": 0,
        "clarification_complete": False,

        # Data collection
        "current_questions": None,
        "user_response": None,
        "collected_data": {},
        "messages": []
    }


def simulate_user_responses(questions_data: dict) -> dict:
    """
    Simulate user responses to questions for testing.
    In production, this would come from the frontend.

    Expected input format from user:
    1) A, B, C
    2) B
    3) Custom text input
    4) D
    """
    print("\n" + "="*80)
    print(f"ROUND {questions_data['round']}")
    print("="*80)

    responses = {}

    # Display all questions first
    for i, q in enumerate(questions_data['questions'], 1):
        print(f"\n{i}) {q['question_text']}")
        print(f"   Field: {q['field']}")
        print(f"   Multi-select: {q['multi_select']}")
        print(f"   Options:")
        for j, opt in enumerate(q['options'], 0):
            # Label options as A, B, C, D, etc.
            label = chr(65 + j)  # 65 is ASCII for 'A'
            print(f"      {label}) {opt}")
        if q.get('allow_custom_input'):
            print(f"      Or enter custom text")

    print("\n" + "-"*80)
    print("Enter your responses (format: 'A, B' for multiple or 'A' for single choice)")
    print("-"*80 + "\n")

    # Collect user input
    user_inputs = {}
    total_questions = len(questions_data['questions'])
    while len(user_inputs) < total_questions:
        try:
            user_input = input(f"Response for question {len(user_inputs) + 1}/{total_questions}: ").strip()

            if not user_input:
                print("   ⚠️  Please enter a response")
                continue

            # Parse the input
            # Expected format: "A, B, C" or "A" or "Custom text"
            question_idx = len(user_inputs)  # Current question index (0-based)
            user_inputs[question_idx] = user_input

        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
            return responses

    # Map user inputs to actual responses
    for i, q in enumerate(questions_data['questions']):
        if i not in user_inputs:
            continue

        user_input = user_inputs[i].strip()

        # Check if it's option letters or custom text
        if ',' in user_input or len(user_input) <= 3:  # Likely option selection
            # Parse option letters (A, B, C, etc.)
            selected_letters = [s.strip().upper() for s in user_input.split(',')]

            # Convert letters to option values
            selected_options = []
            for letter in selected_letters:
                if letter and letter.isalpha():
                    option_idx = ord(letter) - 65  # Convert A->0, B->1, etc.
                    if 0 <= option_idx < len(q['options']):
                        selected_options.append(q['options'][option_idx])

            # Store response
            if q['multi_select']:
                responses[q['field']] = selected_options
            else:
                responses[q['field']] = selected_options[0] if selected_options else None
        else:
            # Custom text input
            responses[q['field']] = user_input

    print("\n" + "="*80)
    print("Responses recorded:")
    for field, value in responses.items():
        print(f"  {field}: {value}")
    print("="*80)

    return responses

def test_clarification_agent():
    """Run the complete test of the clarification agent"""

    # Create the graph
    app = create_clarification_graph()

    # Create initial state
    initial_state = create_initial_state(
        user_name="Ronnie",
        destination="Colorado, USA",
        start_date="2026-12-15",
        end_date="2026-12-21",
        budget=3000.0,
        currency= "USD"
    )

    # Configuration for thread persistence
    config = {"configurable": {"thread_id": "test_user_123"}}

    print("\n🚀 Starting Clarification Agent Test\n")

    try:
        # Invoke with initial state - graph will generate first round of questions
        print("📝 Executing first clarification round...")
        result = app.invoke(initial_state, config)

        if result is None:
            print("❌ Invoke returned None - graph execution failed")
            return None

        # Keep looping until clarification is complete
        while not result.get('clarification_complete', False):

            # Check if we have questions to answer
            questions_data = result.get('current_questions')

            if not questions_data:
                print("❌ No questions generated but clarification not complete. Something went wrong.")
                # Debugging print to see raw LLM response if it failed to parse questions
                if result.get('messages'):
                    print("Last message:", result['messages'][-1])
                break

            # Get user responses
            user_responses = simulate_user_responses(questions_data)

            # Update collected data by merging with previous data
            new_collected_data = {**result.get('collected_data', {}), **user_responses}

            # Prepare the next state with user responses
            # Increment round and clear previous questions
            next_state = {
                "user_response": user_responses,
                "collected_data": new_collected_data,
                "current_round": result["current_round"] + 1,
                "current_questions": None  # Clear previous questions
            }

            # Continue the graph with user responses
            # This will execute the 'clarification' node again
            print(f"\n📝 Continuing with round {next_state['current_round']}...")
            result = app.invoke(next_state, config)

            if result is None:
                print("❌ Invoke returned None during loop")
                break

        if result and result.get('clarification_complete'):
            print("\n✅ Clarification completed!")
            print(f"\nFinal completeness score: {result['completeness_score']}/100")
            print(f"Total rounds: {result['current_round']}")

        return result

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    final_result = test_clarification_agent()
    print(final_result)
