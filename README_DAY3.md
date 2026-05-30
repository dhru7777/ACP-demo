# ACP Demo — Day 3

## Prompt Turn + NLP Intent + UI Polish

**Date:** May 21, 2026
**Author:** Dheeraj Maske
**Builds on:** Day 2 — Session Layer (session/new, session/load, session/resume, session/close)

---

## What we implemented today

The ACP prompt turn — the buyer sends a **natural language message** instead of a hardcoded
structured request. The seller parses intent from the text, looks up its catalog, and returns an offer.

We also polished the demo UI significantly: collapsible capabilities bubble, shoe image in offer card,
re-ordered boot sequence, and deployment fixes for Railway.

---

## ACP Flow — Before vs After

### Day 2 (4 steps)

```
Buyer Agent                          Seller Agent
     │  initialize                        │
     │ ──────────────────────────────────►│
     │  ◄──── capabilities                │
     │        canCreateSession: true       │
     │                                    │
     │  session/new                        │
     │ ──────────────────────────────────►│
     │  ◄──── sessionId: sess_abc123 ─────│
     │                                    │
     │  commerce/request                  │
     │  item: air_max_270 [hardcoded]     │
     │ ──────────────────────────────────►│
     │  ◄──── offer: $150.00 ─────────────│
     │                                    │
     │  session/close                     │
     │ ──────────────────────────────────►│
```

### Day 3 (5 steps — prompt turn added)

```
Buyer Agent                          Seller Agent
     │  initialize                        │
     │ ──────────────────────────────────►│
     │  ◄──── capabilities                │
     │        canCreateSession: true       │
     │        authMethods: []              │
     │                                    │
     │  session/new                        │
     │ ──────────────────────────────────►│
     │  ◄──── sessionId: sess_abc123 ─────│
     │                                    │
     │  session/prompt                    │  ← NEW
     │  "Buy me a Nike Air Max 270,       │
     │   budget $200"                     │
     │ ──────────────────────────────────►│
     │        [intent extraction]          │
     │        item: air_max_270            │
     │        max_price: 200.00            │
     │        [catalog lookup]             │
     │  ◄──── offer: $150.00 ─────────────│
     │        stopReason: end_turn         │
     │                                    │
     │  session/close                     │
     │ ──────────────────────────────────►│
```

---

## Files Modified

### Updated: `seller_agent.py`

**New: `parse_prompt_intent(text)`** — simulates LLM extraction with keyword + regex matching.


| Input                                      | Extracted                                               |
| ------------------------------------------ | ------------------------------------------------------- |
| "Buy me a Nike Air Max 270, budget $200"   | `{item: air_max_270, max_price: 200.0}`                 |
| "I want Air Force 1, max $120"             | `{item: air_force_1, max_price: 120.0}`                 |
| "Get me React Infinity shoes, budget $160" | `{item: react_infinity_4, max_price: 160.0}`            |
| "I want something cheap"                   | `{item: None, max_price: 500.0}` → returns catalog list |


In production this would be a real LLM call (Anthropic/OpenAI) with structured output extraction.
The keyword matching simulates what the LLM would return.

**New: `handle_session_prompt(id_, params)`**

```
session/prompt params:
  sessionId    — validated against session_manager
  prompt       — list of ContentBlocks, we read type: "text"

session/prompt response:
  stopReason   — "end_turn" (ACP spec)
  parsedIntent — what the "LLM" extracted (item + max_price)
  agentMessage — human-readable response from seller
  offer        — full offer object if item found and budget met
```

Also added `GET /` health endpoint so Railway's health check passes and deployments don't roll back.

---

### Updated: `demo.html`


| Change                               | What it does                                                                                           |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Prompt input box                     | Text field pre-filled with "Buy me a Nike Air Max 270, budget $200" — appears after session is created |
| `session/prompt` fetch               | Replaces hardcoded `commerce/request` — sends typed text to seller                                     |
| Intent extracted bubble              | Shows `item: air_max_270 / max_price: $200.00` in seller feed after parsing                            |
| Shoe image in offer card             | Nike Air Max 270 photo appears as a circle beside the price                                            |
| Collapsible capabilities bubble      | Both feeds show compact summary with "▾ show details" toggle                                           |
| Boot sequence reorder                | "nike store agent online" → "buyer agent authenticated and ready"                                      |
| `[simulated LLM extraction]` removed | Cleaner output                                                                                         |


---

### New: `air_max_270.png`

Product photo added to project root. Referenced in `demo.html` via `ITEM_IMAGES` map:

```javascript
const ITEM_IMAGES = {
  'air_max_270': 'air_max_270.png'
  // add air_force_1.png, react_infinity_4.png when available
};
```

### Updated: `railway.json`

Added explicit health check configuration to prevent Railway from rolling back deployments:

```json
{
  "deploy": {
    "startCommand": "uvicorn seller_agent:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/",
    "healthcheckTimeout": 30
  }
}
```

---

## ACP Spec Compliance — Day 3 Status


| ACP Requirement                         | Day 1 | Day 2 | Day 3           |
| --------------------------------------- | ----- | ----- | --------------- |
| `initialize` handshake                  | ✅     | ✅     | ✅               |
| `session/new`                           | ❌     | ✅     | ✅               |
| `session/load`                          | ❌     | ✅     | ✅               |
| `session/resume`                        | ❌     | ✅     | ✅               |
| `session/close`                         | ❌     | ✅     | ✅               |
| `session/prompt` with text ContentBlock | ❌     | ❌     | ✅               |
| `stopReason: end_turn`                  | ❌     | ❌     | ✅               |
| Natural language intent extraction      | ❌     | ❌     | ✅ (keyword sim) |
| `session/cancel`                        | ❌     | ❌     | ❌               |
| SSE streaming for `session/update`      | ❌     | ❌     | ❌               |
| `session/request_permission`            | ❌     | ❌     | ❌               |
| Tool calls via MCP                      | ❌     | ❌     | ❌               |
| Authentication (`authenticate` method)  | ❌     | ❌     | ❌               |
| Payment execution                       | ❌     | ❌     | ❌               |


---

## Production vs Demo Gap — Day 3


| What we built               | What production would use                                      |
| --------------------------- | -------------------------------------------------------------- |
| Keyword matching for intent | Real LLM call (OpenAI/Anthropic) with structured output        |
| In-memory catalog dict      | Vector DB (Pinecone / pgvector) for semantic similarity search |
| Inline HTTP response        | SSE stream of `session/update` notifications                   |
| No MCP connection           | MCP server connected to inventory DB and payment API           |


---

## How to Run Locally

```bash
# Terminal 1 — seller
source venv/bin/activate
uvicorn seller_agent:app --port 8002

# Open demo.html in browser
# Make sure SELLER = 'http://localhost:8002' in demo.html
open demo.html
```

Try different prompts in the text input:

- `"Buy me a Nike Air Max 270, budget $200"` → offer at $150
- `"I want Air Force 1, max $120"` → offer at $110
- `"Get me React Infinity shoes, budget $160"` → offer at $160
- `"I want something cheap"` → seller responds with catalog list
- `"I want React Infinity but only have $50"` → budget too low response

---

## Where to Start Day 4


| Priority | Task                                    | File                            | Notes                                            |
| -------- | --------------------------------------- | ------------------------------- | ------------------------------------------------ |
| 1        | Real LLM call for intent extraction     | `seller_agent.py`               | Replace `parse_prompt_intent()` with OpenAI call |
| 2        | `session/cancel` handler                | `seller_agent.py` + `demo.html` | Let buyer abort a prompt mid-flight              |
| 3        | Stripe payment execution                | `seller_agent.py`               | `commerce/pay` method with real Stripe API       |
| 4        | SSE streaming for `session/update`      | `seller_agent.py`               | Stream intent extraction steps in real-time      |
| 5        | Vector DB catalog search                | `seller_agent.py`               | Replace dict lookup with Pinecone/pgvector       |
| 6        | Add shoe images for all 3 catalog items | `demo.html`                     | Drop images in project, add to `ITEM_IMAGES`     |


---

## Live Links

- **Frontend:** Netlify — `demo.html`
- **Backend:** `https://acp-demo-production.up.railway.app` — deployed via `railway up` CLI
- **Health check:** `https://acp-demo-production.up.railway.app/` → returns `{"status":"ok","version":"2.0.0"}`

