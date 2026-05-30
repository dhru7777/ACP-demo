# ACP Demo — Day 4
## Catalog Search, Multi-Turn Agentic Conversation + Claude Intent

**Date:** May 23, 2026  
**Author:** Dheeraj Maske  
**Builds on:**
- [Day 1 — Handshake + Commerce Intent](./Readme_Day1.md)
- [Day 2 — Session Layer](./README_DAY2.md)
- [Day 3 — Prompt Turn + NLP Intent](./README_DAY3.md)

---

## What we implemented today

Day 4 turns the demo from a **3-item scripted shop** into a **real agentic negotiation loop**:

1. **100-item Nike catalog** with modular fuzzy search (vector-DB ready)
2. **Multi-turn `session/prompt`** — seller asks for budget if missing; buyer agent auto-replies
3. **Claude Haiku** for natural language intent parsing (regex fallback if no API key)
4. **Human-in-the-loop** — edit prompts before send; tap an offer card to override the agent
5. **Intent-first offer selection** — agent picks by relevance score, not cheapest price
6. **Mobile-friendly UI** — compact offer cards and left-aligned decision bubbles

---

## Progress arc (Day 1 → Day 4)

| Day | Focus | Key ACP methods |
|---|---|---|
| **Day 1** | Handshake + hardcoded commerce | `initialize`, `commerce/request` |
| **Day 2** | Session context + history | `session/new`, `session/load`, `session/resume`, `session/close` |
| **Day 3** | Natural language prompt turn | `session/prompt`, `stopReason: end_turn` |
| **Day 4** | Agentic negotiation + catalog search | Multi-turn `session/prompt`, `needs_clarification`, offer selection |

---

## ACP Flow — Day 4 (multi-turn)

```
Buyer Agent                          Seller Agent
     │  initialize                        │
     │ ──────────────────────────────────►│
     │  ◄──── capabilities                │
     │        itemCount: 100              │
     │        categories: running, ...    │
     │                                    │
     │  session/new                        │
     │ ──────────────────────────────────►│
     │  ◄──── sessionId ──────────────────│
     │                                    │
     │  session/prompt (turn 1)           │
     │  "I want comfortable running shoes"│
     │ ──────────────────────────────────►│
     │        [Claude parses intent]       │
     │        no budget detected           │
     │  ◄──── needs_clarification ────────│
     │        "What's your budget?"        │
     │                                    │
     │  session/prompt (turn 2)           │
     │  "My budget is $150"               │  ← buyer agent auto-replies
     │ ──────────────────────────────────►│
     │        [catalog_search → top 3]     │
     │  ◄──── offers[] with scores ───────│
     │                                    │
     │  [agent picks best intent match]    │
     │  [human has 4s to tap another card]│
     │                                    │
     │  commerce/pay  [Phase 2]           │
     │ ──────────────────────────────────►│
```

---

## Files Created / Modified

### New: `catalog.py`

100 real Nike shoes across 10 categories ($18–$285). Each item has:

```python
{
  "name": "Nike React Infinity Run Flyknit 3",
  "price": 140.00,
  "category": "running",
  "keywords": ["running", "react", "cushioned", ...],
  "description": "Max cushion for high-mileage runners"
}
```

`get_catalog_summary()` returns count + categories only — **never exposes the full inventory** to clients.

---

### New: `search.py`

Modular search layer with a stable public interface:

| Method | Purpose |
|---|---|
| `catalog_search.search(query, max_price, top_k)` | Fuzzy match → ranked results with `score` |
| `catalog_search.get(item_id)` | Lookup by ID |
| `catalog_search.count()` | Total items |
| `catalog_search.summary()` | Safe stats for capabilities |

**Current backend:** keyword overlap + difflib fuzzy matching.  
**Future swap:** override `_search_impl()` with Pinecone/pgvector or MCP — no other files change.

---

### Updated: `session_manager.py`

Added `update_context(session_id, context)` to store multi-turn state:

```python
{
  "awaiting_budget": True,
  "pending_query": "comfortable running shoes",
  "turn": 2
}
```

---

### Updated: `seller_agent.py`

| Feature | Details |
|---|---|
| `claude_parse_intent()` | Claude Haiku extracts intent, budget, clarification need |
| `_regex_fallback()` | Works when `ANTHROPIC_API_KEY` is missing |
| Multi-turn `handle_session_prompt()` | Turn 1: ask budget · Turn 2: search + return offers |
| `_build_offers()` | Returns top 3 offers with `score` field |
| Capabilities | `itemCount: 100`, `categories: [...]` — no item list leaked |

**Env var:** `ANTHROPIC_API_KEY` in Railway Variables or `local.env` locally.

---

### Updated: `demo.html`

| Feature | Details |
|---|---|
| `BUYER_PROFILE` | User configures budget ($150) + initial intent once |
| 5s prompt countdown | Click input → timer stops, human takes control |
| Offer grid | 3 compact cards: name · price · match % |
| 4s offer countdown | Tap a card to override agent pick |
| `agentPickOffer()` | Highest relevance score within budget — not cheapest |
| Mobile layout | Stacked cards, left-aligned, compact decision text |

**Decision example:**
```
→ Nike React Infinity 3 · $140 · 33%
  Nike Free RN 5.0 · $100 · 32%
  Nike Revolution 7 · $65 · 38%

agent chose Nike React Infinity 3 · 33% match · $140
```

---

### Updated: `.gitignore`

Added `local.env` and `.env` so API keys are never committed.

---

### Updated: `requirements.txt`

Added `anthropic` package for Claude integration.

---

## ACP Spec Compliance — Day 4 Status

| ACP Requirement | Day 1 | Day 2 | Day 3 | Day 4 |
|---|---|---|---|---|
| `initialize` handshake | ✅ | ✅ | ✅ | ✅ |
| Session layer (new/load/resume/close) | ❌ | ✅ | ✅ | ✅ |
| `session/prompt` with text ContentBlock | ❌ | ❌ | ✅ | ✅ |
| Multi-turn clarification (`needs_clarification`) | ❌ | ❌ | ❌ | ✅ |
| Natural language intent (LLM) | ❌ | ❌ | keyword | ✅ Claude |
| Catalog search (not hardcoded items) | ❌ | ❌ | ❌ | ✅ 100 items |
| Human-in-the-loop override | ❌ | ❌ | ❌ | ✅ |
| Agent autonomous decision + reasoning | ❌ | ❌ | ❌ | ✅ |
| `session/cancel` | ❌ | ❌ | ❌ | ❌ |
| SSE streaming | ❌ | ❌ | ❌ | ❌ |
| Payment execution | ❌ | ❌ | ❌ | ❌ |

---

## Production vs Demo Gap — Day 4

| What we built | What production would use |
|---|---|
| In-memory 100-item catalog | Product DB + CDN for images |
| difflib fuzzy search | Vector DB (Pinecone / pgvector) |
| Claude Haiku inline call | Dedicated intent service + caching |
| HTTP inline responses | SSE `session/update` streaming |
| Buyer profile in JS | Encrypted buyer agent config + wallet |
| Simulated payment step | Stripe / x402 agent-to-agent payment |

---

## How to Run Locally

```bash
cd acp-demo
source venv/bin/activate
pip install -r requirements.txt

# Load API key (optional — falls back to regex without it)
export $(cat local.env)

# Terminal 1 — seller
uvicorn seller_agent:app --host 0.0.0.0 --port 8002 --reload
# Should see: [Claude] Anthropic client ready — using LLM for intent parsing

# Open demo.html — set SELLER to localhost
open demo.html
```

**Try these flows:**
- Default demo: `"I want comfortable running shoes"` → seller asks budget → agent replies `$150` → 3 offers → agent picks best match
- Human interrupt: click the prompt input during countdown → edit text → press Enter
- Offer override: tap a different card during the 4s offer countdown

---

## Where to Start Day 5

| Priority | Task | File | Notes |
|---|---|---|---|
| 1 | Stripe payment execution | `seller_agent.py` | `commerce/pay` with real Stripe API |
| 2 | Wire payment in demo Step 5 | `demo.html` | Replace placeholder with live pay call |
| 3 | Vector DB catalog search | `search.py` | Swap `_search_impl()` for Pinecone |
| 4 | `session/cancel` handler | `seller_agent.py` | Abort mid-flight prompt |
| 5 | SSE streaming for `session/update` | `seller_agent.py` | Stream intent + search steps live |
| 6 | Buyer agent script parity | `buyer_agent.py` | Mirror demo flow in terminal client |

---

## Live Links

- **Frontend:** Netlify — `demo.html`
- **Backend:** `https://acp-demo-production.up.railway.app`
- **Health check:** `GET /` → `{"status":"ok","version":"2.0.0","session":true}`

**Railway env var required for Claude:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Quick reference — all README files

| File | What it covers |
|---|---|
| [Readme_Day1.md](./Readme_Day1.md) | Handshake, commerce/request, Phase 1 demo |
| [README_DAY2.md](./README_DAY2.md) | Session layer, session_manager.py |
| [README_DAY3.md](./README_DAY3.md) | session/prompt, keyword intent, UI polish |
| [README_DAY4.md](./README_DAY4.md) | Catalog, search, Claude, multi-turn, agent pick |
| [README_DAY5.md](./README_DAY5.md) | x402 USDC payment, wallets, commerce/pay, receipt PDF |
