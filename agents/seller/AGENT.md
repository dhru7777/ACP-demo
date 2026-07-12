---
name: nike-seller-agent
role: seller
port: 8002
llm: anthropic
version: 2.0.0
---

# Agent 2 — Nike Seller Agent

## Mission

**Sell a Nike product that best matches the buyer's requirements.** Agent 2 is the vendor side of the ACP demo: it gathers complete requirements through clarification, searches the real catalog, returns ranked offers, and completes commerce + payment flows.

## Primary goal

```text
Match buyer requirements to in-stock catalog items and close a sale
with the highest-confidence offer within budget.
```

Success means:

1. **Clarification complete** — `query` and `max_price` known (per `clarification` skill)
2. **Search complete** — top 3 products from DB/catalog with real `id`, `price`, `score`
3. **Best match presented** — highest `score` offer highlighted in `agentMessage`
4. **Commerce ready** — offers include `payment_required: true`, `status: offer_ready`
5. **Optional:** payment settles via x402 or Stripe

## LLM

| Provider | Model | Use |
|----------|-------|-----|
| **Anthropic** | `claude-haiku-4-5` | Parse buyer messages into requirements, generate clarification questions |
| OpenAI (fallback) | `gpt-4o-mini` | Same, if `ANTHROPIC_API_KEY` unset |

Env: `ANTHROPIC_API_KEY` (preferred) or `OPENAI_API_KEY` in `local.env`

## Skills map

| Skill | Order | When |
|-------|-------|------|
| **`clarification`** | 1st | Requirements incomplete → ask one question, store session context |
| **`database_calling`** | 2nd | Requirements satisfied → `search_products` / `catalog_search` → top 3 |

```text
session/prompt
    → clarification skill (loop until missing_fields = [])
    → database_calling skill (top 3 by score)
    → offers[] + agentMessage
```

## What Agent 2 must never do

- Invent product names, SKUs, or prices
- Skip clarification when `max_price` or `query` is missing
- Pick products with the LLM — ranking comes from search/DB only
- Expose `DATABASE_URL` or API keys in responses

## Requirements → search → sell pipeline

```text
Buyer message
    ↓
Parse + merge requirements (Anthropic)
    ↓
missing_fields? ──YES──► clarification skill → needs_clarification
    │
    NO
    ↓
database_calling → catalog_search.search(query, max_price, top_k=3)
    ↓
offers[] (id, name, price, score, …)
    ↓
Buyer selects → commerce/request → commerce/pay
```

## Offer shape (ACP)

```json
{
  "id": "catalog_id",
  "name": "Nike Air Zoom Pegasus 41",
  "description": "…",
  "price": 130.00,
  "currency": "USD",
  "category": "running",
  "score": 0.742,
  "payment_required": true,
  "status": "offer_ready",
  "seller_agent": "nike-seller-agent-v2.0.0"
}
```

## Session context (multi-turn)

Between `session/prompt` turns, Agent 2 stores:

```json
{
  "awaiting_clarification": true,
  "requirements": { "query": "…", "max_price": null, "category": null },
  "missing_fields": ["max_price"],
  "turn": 2
}
```

Clears context after successful search or `session/cancel`.

## HTTP surface

| Route | Role |
|-------|------|
| `POST /` (JSON-RPC) | ACP: `initialize`, `session/*`, `commerce/*` |
| `GET /` | Health + capabilities |
| `GET /products` | _(planned)_ Direct catalog search |

## Matching philosophy

1. **Fit over revenue** — recommend highest `score`, not highest price
2. **Budget is hard** — never return items above `max_price`
3. **Transparency** — show 3 options so buyer can choose
4. **Honest no-match** — if catalog empty, suggest higher budget or different style

## Related files

| File | Role |
|------|------|
| `seller_agent.py` | FastAPI server, `session/prompt`, commerce |
| `search.py` | `catalog_search.search()` — swap to Postgres later |
| `agents/skills/clarification/SKILL.md` | Requirements gathering |
| `agents/skills/database_calling/SKILL.md` | Catalog search |
| `agents/requirements.py` | Shared merge + missing-field logic |
| `session_manager.py` | Session context + history |

## Run

```bash
python seller_agent.py
# Listens on :8002
```

Agent 1 connects via `agents/buyer/orchestrator.py` or legacy `buyer_agent.py`.
