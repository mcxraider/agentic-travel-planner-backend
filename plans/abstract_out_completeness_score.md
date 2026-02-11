# Plan: Abstract Completeness Score Calculation from LLM to Code

## Goal
Move completeness score calculation from the LLM prompt to deterministic Python code to reduce LLM cognitive load and let it focus on quality question generation.

---

## Current State

**LLM Currently Handles:**
1. Calculates score using formula: `Score = (Tier1*8) + (Tier2*4) + (Tier3*3) + (Tier4*3)` (templates.py:241-245)
2. Tracks `missing_tier1`, `missing_tier2` lists
3. Determines `status="complete"` based on stopping conditions (templates.py:225-237)
4. Returns `score` in `state` object (required field - response_parser.py:135)

**What Will Move to Code:**
- Score calculation (deterministic math)
- Missing field tracking (field presence check)
- Completion status determination (rule-based)
- Tier 3 elevation logic (conditional based on user profile)

**What Stays with LLM:**
- Quality question generation with destination context
- Conflict detection (semantic understanding)
- Feasibility warnings (domain reasoning)

---

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `agents/clarification/scoring.py` | **CREATE** | New scoring module with tier config, calculation, stopping logic |
| `agents/clarification/response_parser.py` | **MODIFY** | Import scoring, calculate score in code, override LLM status |
| `agents/clarification/prompts/templates.py` | **MODIFY** | Remove lines 225-245 (stopping conditions + scoring formula) |
| `agents/clarification/schemas.py` | **MODIFY** | Make `score` optional in QuestionsStateV2 |
| `agents/tests/test_scoring.py` | **CREATE** | Unit tests for scoring module |

---

## Implementation Steps

### Step 1: Create Scoring Module
**File:** `agents/clarification/scoring.py`

Create new module with:
- `TierConfig` dataclass - tier field definitions and point values
- `ScoringResult` dataclass - score breakdown with missing/answered fields per tier
- `is_field_answered(data, field)` - check if field has meaningful value
- `get_elevated_tier3_fields(work_obligations, dietary_restrictions, health_limitations)` - determine tier 3 elevations
- `calculate_completeness_score(data, user_profile_fields, config)` - main scoring function
- `should_complete_clarification(scoring_result, current_round, conflicts)` - stopping condition check

**Tier Configuration:**
```python
TIER1_FIELDS = ("activity_preferences", "pace_preference", "tourist_vs_local", "mobility_level", "dining_style")
TIER1_POINTS = 10  # per field (max 50)

TIER2_FIELDS = ("top_3_must_dos", "transportation_mode", "arrival_time", "departure_time", "budget_priority", "accommodation_style")
TIER2_POINTS = 4   # per field (max 24)

TIER3_FIELDS = ("wifi_need", "dietary_severity", "accessibility_needs")
TIER3_POINTS = 3   # per field, elevated to 10 if triggered

TIER4_FIELDS = ("special_logistics", "daily_rhythm", "downtime_preference")
TIER4_POINTS = 3   # per field (max 9)
```

**Stopping Conditions (code-based):**
1. `current_round >= 4` → force complete
2. `score >= 85 AND all Tier 1 complete AND no conflicts` → complete
3. `score >= 85` → complete (even if Tier 2 incomplete)

### Step 2: Update Response Parser
**File:** `agents/clarification/response_parser.py`

Changes:
1. Import scoring module
2. **Line 122:** Remove `"status"` from `required_keys` (code determines completion)
3. **Lines 127-131:** Remove status validation (no longer in LLM output)
4. **Line 135:** Change `state_required = {"collected", "score"}` to `state_required = {"collected"}` (score removed)
5. **Function `build_state_update_for_v2_response`:**
   - Remove `is_complete = parsed_response["status"] == "complete"` (line 160)
   - Call `calculate_completeness_score()` with `response_data` and user profile from `state`
   - Call `should_complete_clarification()` to determine completion (replaces LLM status)
   - Log scoring breakdown for debugging (not in return value)

### Step 3: Simplify Prompt Template
**File:** `agents/clarification/prompts/templates.py`

**REMOVE these sections:**
- Lines 225-237: "# Stopping Conditions" section
- Lines 241-245: "# Scoring Formula" section

**KEEP these sections (LLM still needs for question prioritization):**
- Lines 105-132: Tier definitions (fields and priorities)
- Lines 134-163: Question generation rules
- Lines 149-154: Conflict detection rules

**UPDATE output schema (lines 167-221):**
- Remove `"status"` field from JSON example (code determines)
- Remove `"score"` from state object
- Remove `"missing_tier1"`, `"missing_tier2"` from state object (code calculates)
- Keep `"collected"` and `"conflicts_detected"` (LLM still tracks these)
- Update "Important" notes (lines 216-221) to remove status-related instructions

### Step 4: Update Schemas
**File:** `agents/clarification/schemas.py`

In `QuestionsStateV2` (lines 94-111):
- Remove `score` field entirely (code calculates, not in LLM response)
- Make `missing_tier1`, `missing_tier2` optional with `default=None`
- Add docstring noting these are calculated by code

In `QuestionsResponseV2` (lines 156-172):
- Remove `status` from model (code determines completion)
- Update validator if needed

### Step 5: Add Unit Tests
**File:** `agents/tests/test_scoring.py`

Test cases:
- `is_field_answered()` with None, empty string, empty list, valid values
- `get_elevated_tier3_fields()` with various user profile combinations
- `calculate_completeness_score()` with empty data, partial data, full data
- `should_complete_clarification()` with various round/score/conflict combinations
- Edge case: `top_3_must_dos` as ranked dict

---

## Payload Changes

### LLM Output (Before)
```json
{
  "status": "in_progress",
  "round": 1,
  "questions": [...],
  "state": {
    "collected": ["field1"],
    "missing_tier1": ["field2"],
    "missing_tier2": ["field3"],
    "conflicts_detected": [],
    "score": 45  // REQUIRED - LLM calculates
  },
  "data": {...}
}
```

### LLM Output (After)
```json
{
  "round": 1,
  "questions": [...],
  "state": {
    "collected": ["field1"],
    "conflicts_detected": []
    // status REMOVED - code determines completion
    // score REMOVED - calculated by code
    // missing_tier1/tier2 REMOVED - calculated by code
  },
  "data": {...}
}
```

**Note:** `status` field removed entirely from LLM output. Code is sole authority for completion.

### Internal State Update (code-calculated)
```python
{
  "completeness_score": 45,  # Code-calculated
  "clarification_complete": False,  # Code-determined
  # Scoring breakdown logged only, NOT in API responses
}
```

**Note:** Scoring breakdown (tier1_answered, tier1_missing, completion_reason) logged for debugging but not exposed in API responses to keep payloads lean.

---

## Frontend Schema Changes

### Summary of Breaking Changes

The following fields have been **REMOVED** from API responses. Frontend code referencing these fields needs to be updated.

### `QuestionsStateV2` (in `state` object)

| Field | Change | Frontend Action |
|-------|--------|-----------------|
| `status` | **REMOVED** | Use `complete` field from response instead |
| `score` | **REMOVED** (now optional, will be `null`) | Use `completeness_score` from top-level state if needed |
| `missing_tier1` | **REMOVED** (now optional, will be `null`) | Remove any UI that displays this |
| `missing_tier2` | **REMOVED** (now optional, will be `null`) | Remove any UI that displays this |
| `collected` | **UNCHANGED** | No action needed |
| `conflicts_detected` | **UNCHANGED** | No action needed |

### Before (old `state` object in responses):
```typescript
interface QuestionsStateV2 {
  collected: string[];
  missing_tier1: string[];      // ❌ NOW OPTIONAL/NULL
  missing_tier2: string[];      // ❌ NOW OPTIONAL/NULL
  conflicts_detected: string[];
  score: number;                // ❌ NOW OPTIONAL/NULL
}
```

### After (new `state` object in responses):
```typescript
interface QuestionsStateV2 {
  collected: string[];
  conflicts_detected: string[];
  // These are now optional - may be null or missing
  missing_tier1?: string[] | null;
  missing_tier2?: string[] | null;
  score?: number | null;
}
```

### API Response Changes

**`StartSessionResponseV2`** - No changes to top-level structure:
```typescript
interface StartSessionResponseV2 {
  session_id: string;
  round: number;
  questions: QuestionV2[];
  state: QuestionsStateV2;  // ⚠️ state object changed (see above)
  data: ClarificationDataV2;
}
```

**`RespondResponseV2`** - No changes to top-level structure:
```typescript
interface RespondResponseV2 {
  session_id: string;
  complete: boolean;        // ✅ Use this for completion status
  round: number;
  questions: QuestionV2[];
  state: QuestionsStateV2;  // ⚠️ state object changed (see above)
  data: ClarificationDataV2;
}
```

### Frontend Checklist

- [ ] Update `QuestionsStateV2` TypeScript interface to make `score`, `missing_tier1`, `missing_tier2` optional
- [ ] Remove any UI components that display `state.score` (or handle null gracefully)
- [ ] Remove any UI components that display `state.missing_tier1` / `state.missing_tier2`
- [ ] Ensure completion logic uses `response.complete` boolean, not `state.status`
- [ ] Test clarification flow end-to-end after backend deployment

---

## Verification Plan

1. **Unit Tests:** Run `pytest agents/tests/test_scoring.py`
2. **Integration Test:** Run `python3 -m agents.tests.test_clarification` - interactive CLI test
3. **API Test:**
   - `POST /api/clarification/start` - verify questions generated, score calculated
   - `POST /api/clarification/respond` - verify score updates correctly
   - Verify completion triggers at round 4 or score >= 85
4. **Compare:** Log both LLM-suggested score (if provided) and code-calculated score to validate consistency

---

## Benefits

1. **Consistency:** Deterministic scoring, no LLM variance
2. **Reduced LLM Load:** ~50 fewer tokens of instructions in prompt
3. **Faster Iteration:** Tune scoring rules without prompt changes
4. **Testability:** Scoring logic can be unit tested independently
5. **Debugging:** Clear breakdown of why score is what it is

---

## Rollback Plan

If issues arise:
1. Scoring module is additive - can be ignored by reverting response_parser.py
2. Add `score` back to `state_required` validation
3. Restore removed prompt sections from git history
