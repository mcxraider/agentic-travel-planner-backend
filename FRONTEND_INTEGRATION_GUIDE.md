# Frontend Integration Guide

This guide describes how to integrate a frontend application with the Trippi backend clarification API.

---

## Overview

The clarification flow collects user preferences through multiple rounds of questions. The frontend:

1. Collects trip basics on a **Plan** page.
2. POSTs to `/api/clarification/start` to begin a session.
3. Renders questions and submits answers via `/api/clarification/respond`.
4. Repeats until `complete: true`, then uses `collected_data` downstream.

---

## Base URL

```
http://localhost:8000
```

---

## Endpoints

| Method | Path                                   | Purpose                                      |
| ------ | -------------------------------------- | -------------------------------------------- |
| GET    | `/`                                    | API info (name, version, agent status)       |
| GET    | `/health`                              | Global health check                          |
| POST   | `/api/clarification/start`             | Start a new clarification session            |
| POST   | `/api/clarification/respond`           | Submit answers for the current round         |
| GET    | `/api/clarification/session/{id}`      | Check session status (exists, complete, etc) |
| DELETE | `/api/clarification/session/{id}`      | Delete/cancel a session                      |
| GET    | `/api/clarification/health`            | Clarification service health check           |

---

## TypeScript Types

Use these types in your frontend codebase.

### Request Types

```typescript
/**
 * POST /api/clarification/start
 * Body payload to start a new clarification session.
 */
export interface StartSessionRequest {
  // ───────────────────────────────────────────────
  // User Profile (optional enrichment)
  // ───────────────────────────────────────────────
  user_name: string;                         // Required
  citizenship?: string;                      // Default: "Not specified"
  health_limitations?: string | null;        // e.g., "Bad knees"
  work_obligations?: string | null;          // e.g., "Must work mornings"
  dietary_restrictions?: string | null;      // e.g., "Vegetarian"
  specific_interests?: string[] | null;      // e.g., ["temples", "ramen"]

  // ───────────────────────────────────────────────
  // Trip Basics (collected on Plan page)
  // ───────────────────────────────────────────────
  destination: string;                       // Required – e.g., "Japan"
  destination_cities?: string[] | null;      // e.g., ["Tokyo", "Kyoto"]
  start_date: string;                        // Required – format: "YYYY-MM-DD"
  end_date: string;                          // Required – format: "YYYY-MM-DD"
  budget: number;                            // Required – must be > 0
  currency?: string;                         // Default: "USD"
  travel_party?: string;                     // Default: "1 adult"
  budget_scope?: string;                     // Default: "Total trip budget"
}

/**
 * POST /api/clarification/respond
 * Body payload to submit answers.
 */
export interface RespondRequest {
  session_id: string;                        // UUID from StartSessionResponse
  responses: Record<string, unknown>;        // field → value (string | string[])
}
```

### Response Types

```typescript
/**
 * A single clarification question.
 */
export interface Question {
  question_id: number;
  field: string;                             // Key to use in responses
  multi_select: boolean;                     // true → user can pick multiple
  question_text: string;                     // Display text
  options: string[];                         // Available choices
  allow_custom_input: boolean;               // true → free-text allowed
}

/**
 * Progress/state info returned with questions.
 */
export interface QuestionsState {
  answered_fields: string[];
  missing_fields: string[];
  completeness_score: number;                // 0–100
}

/**
 * Response from POST /api/clarification/start
 */
export interface StartSessionResponse {
  session_id: string;                        // Store this!
  round: number;
  questions: Question[];
  state: QuestionsState;
}

/**
 * Response from POST /api/clarification/respond
 */
export interface RespondResponse {
  session_id: string;
  complete: boolean;

  // Present when complete = false
  round?: number;
  questions?: Question[];
  state?: QuestionsState;

  // Present when complete = true
  collected_data?: Record<string, unknown>;
}

/**
 * Response from GET /api/clarification/session/{id}
 */
export interface SessionStatusResponse {
  session_id: string;
  exists: boolean;
  current_round?: number;
  completeness_score?: number;
  clarification_complete?: boolean;
}
```

---

## Implementation Plan

### 1. Plan Page

This is where the user fills in trip basics before starting clarification.

#### Required Fields (must be collected)

| Field         | Type     | Validation                          |
| ------------- | -------- | ----------------------------------- |
| `user_name`   | `string` | Non-empty                           |
| `destination` | `string` | Non-empty                           |
| `start_date`  | `string` | Format `YYYY-MM-DD`, not in past    |
| `end_date`    | `string` | Format `YYYY-MM-DD`, ≥ `start_date` |
| `budget`      | `number` | > 0                                 |

#### Optional Fields (can pre-fill or leave blank)

| Field                  | Type             | Default               |
| ---------------------- | ---------------- | --------------------- |
| `destination_cities`   | `string[]`       | `null`                |
| `currency`             | `string`         | `"USD"`               |
| `travel_party`         | `string`         | `"1 adult"`           |
| `budget_scope`         | `string`         | `"Total trip budget"` |
| `citizenship`          | `string`         | `"Not specified"`     |
| `health_limitations`   | `string \| null` | `null`                |
| `work_obligations`     | `string \| null` | `null`                |
| `dietary_restrictions` | `string \| null` | `null`                |
| `specific_interests`   | `string[]`       | `null`                |

#### UI Skeleton

```
┌─────────────────────────────────────────────────────────────┐
│  Plan Your Trip                                             │
├─────────────────────────────────────────────────────────────┤
│  Destination       [___________________]                    │
│  Cities (optional) [___________________] + Add              │
│  Start Date        [____-__-__]                             │
│  End Date          [____-__-__]                             │
│  Budget            [________]  Currency [USD ▾]             │
│  Travel Party      [1 adult ▾]                              │
│  Budget Scope      [Total trip budget ▾]                    │
├─────────────────────────────────────────────────────────────┤
│                      [ Start Clarification ]                │
└─────────────────────────────────────────────────────────────┘
```

#### On "Start Clarification" Button Click

1. **Validate** required fields.
2. **Build** `StartSessionRequest` payload.
3. **POST** to `/api/clarification/start`.
4. **Store** `session_id` on the current chat/trip object.
5. **Navigate** to Clarification Questions UI with `questions[]`.

```typescript
async function startClarification(tripData: StartSessionRequest): Promise<StartSessionResponse> {
  const res = await fetch(`${BASE_URL}/api/clarification/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(tripData),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to start session");
  }

  return res.json();
}
```

---

### 2. Clarification Questions Page

Render questions and collect answers in a loop until `complete: true`.

#### Rendering Questions

```typescript
function renderQuestions(questions: Question[]) {
  return questions.map((q) => (
    <QuestionCard
      key={q.question_id}
      question={q}
      onChange={(value) => handleAnswerChange(q.field, value)}
    />
  ));
}
```

#### QuestionCard Logic

| `multi_select` | `allow_custom_input` | UI Component               |
| -------------- | -------------------- | -------------------------- |
| `false`        | `false`              | Radio buttons              |
| `false`        | `true`               | Radio buttons + text input |
| `true`         | `false`              | Checkboxes                 |
| `true`         | `true`               | Checkboxes + text input    |

#### Building the Response Payload

```typescript
// responses: Record<string, string | string[]>
// Key = question.field
// Value = selected option(s) or custom text

const payload: RespondRequest = {
  session_id: currentSessionId,
  responses: {
    pace_preference: "Relaxed",
    dining_style: ["Street food", "Fine dining"],
    // ...
  },
};
```

#### On "Next" / "Submit" Button Click

```typescript
async function submitResponses(
  sessionId: string,
  responses: Record<string, unknown>
): Promise<RespondResponse> {
  const res = await fetch(`${BASE_URL}/api/clarification/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, responses }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to submit responses");
  }

  return res.json();
}
```

#### Handling the Response

```typescript
const result = await submitResponses(sessionId, answers);

if (result.complete) {
  // Done! Move to next stage (e.g., show itinerary, call planner agent)
  saveCollectedData(result.collected_data);
  navigateTo("/itinerary");
} else {
  // More questions
  setCurrentRound(result.round);
  setQuestions(result.questions);
  setState(result.state);
}
```

---

### 3. State Management

Store clarification state per chat/trip. Minimal shape:

```typescript
interface ClarificationState {
  status: "idle" | "in_progress" | "complete";
  sessionId: string | null;
  currentRound: number;
  questions: Question[];
  answers: Record<string, unknown>;          // accumulated
  completenessScore: number;
  collectedData: Record<string, unknown> | null;
}
```

#### State Transitions

```
idle ──(start)──► in_progress ──(respond, complete=false)──► in_progress
                                    │
                                    └──(respond, complete=true)──► complete
```

---

### 4. Error Handling

| HTTP Status | Meaning                        | Frontend Action                        |
| ----------- | ------------------------------ | -------------------------------------- |
| `200`       | Success                        | Process response                       |
| `404`       | Session not found              | Clear local session, prompt restart    |
| `422`       | Validation error (bad payload) | Show field-level errors                |
| `500`       | Server error                   | Show generic error, allow retry        |

---

### 5. Optional: Resume / Status Check

If you want to allow resuming after a page refresh (requires you to persist `sessionId` locally):

```typescript
async function checkSession(sessionId: string): Promise<SessionStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/clarification/session/${sessionId}`);
  return res.json();
}
```

> **Note:** The current backend only returns status, not the pending questions. To support full resume, you'd need to extend the backend or persist questions client-side.

---

### 6. Cleanup / Cancel

```typescript
async function cancelSession(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/clarification/session/${sessionId}`, {
    method: "DELETE",
  });
}
```

---

## Example: Full Happy-Path Flow

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. User fills Plan page                                                      │
│    → destination: "Japan", start_date: "2026-03-10", end_date: "2026-03-15", │
│      budget: 2000, currency: "USD", user_name: "Alex"                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ 2. User clicks "Start Clarification"                                        │
│    → POST /api/clarification/start                                           │
│    ← { session_id: "abc-123", round: 1, questions: [...], state: {...} }     │
├──────────────────────────────────────────────────────────────────────────────┤
│ 3. Frontend renders Round 1 questions                                       │
│    → User selects answers                                                    │
│    → POST /api/clarification/respond { session_id, responses }               │
│    ← { complete: false, round: 2, questions: [...], state: {...} }           │
├──────────────────────────────────────────────────────────────────────────────┤
│ 4. Frontend renders Round 2 questions                                       │
│    → User selects answers                                                    │
│    → POST /api/clarification/respond { session_id, responses }               │
│    ← { complete: false, round: 3, questions: [...], state: {...} }           │
├──────────────────────────────────────────────────────────────────────────────┤
│ 5. Frontend renders Round 3 questions                                       │
│    → User selects answers                                                    │
│    → POST /api/clarification/respond { session_id, responses }               │
│    ← { complete: true, collected_data: { ... } }                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ 6. Frontend stores collected_data, navigates to itinerary/planner            │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference: API Calls

### Start Session

```bash
curl -X POST http://localhost:8000/api/clarification/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Alex",
    "destination": "Japan",
    "start_date": "2026-03-10",
    "end_date": "2026-03-15",
    "budget": 2000,
    "currency": "USD"
  }'
```

### Submit Responses

```bash
curl -X POST http://localhost:8000/api/clarification/respond \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123-...",
    "responses": {
      "pace_preference": "Balanced",
      "dining_style": ["Street food", "Casual sit-down"]
    }
  }'
```

### Check Session Status

```bash
curl http://localhost:8000/api/clarification/session/abc-123-...
```

### Delete Session

```bash
curl -X DELETE http://localhost:8000/api/clarification/session/abc-123-...
```

---

## Notes for Production

1. **Session persistence**: Currently in-memory. Move to Redis or a database.
2. **CORS**: Backend allows all origins (`*`). Restrict in production.
3. **Authentication**: Not implemented. Add JWT/session auth as needed.
4. **Rate limiting**: Not implemented. Consider adding for public APIs.
