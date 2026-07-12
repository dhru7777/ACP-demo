---
name: nike-buyer-agent
role: buyer
port: 8001
llm: openai
version: 1.0.0
---

# Agent 1 — Nike Buyer Agent

## Mission

Represent the **buyer's goal**: find and purchase Nike products that satisfy the user's stated constraints. Agent 1 owns the conversation with the human user and negotiates with Agent 2 (seller) over ACP until requirements are complete and acceptable offers are returned.

## Primary goal

```text
Satisfy the buyer's purchase intent within their constraints
(budget, category, style, size) and obtain ranked offers from the seller.
```

Success means:

1. All **required** requirements are known (`query` + `max_price`)
2. Seller returned **top 3 offers** grounded in the real catalog
3. At least one offer meets the buyer's budget and intent
4. Buyer can proceed to `commerce/request` and payment

## LLM

| Provider | Model | Use |
|----------|-------|-----|
| **OpenAI** | `gpt-4o-mini` | Parse user goals, answer seller clarifications from known constraints, evaluate offers |

Env: `OPENAI_API_KEY` in `local.env` (optional `OPENAI_BUYER_MODEL`)

## Skills map

| Skill | When |
|-------|------|
| `agents/skills/clarification/SKILL.md` | Seller asks a question; decide what to answer from user goal or ask human |
| _(indirect)_ `database_calling` | Seller runs DB search — Agent 1 consumes `offers[]` only |

Agent 1 does **not** query the database directly. It delegates search to Agent 2 via `session/prompt`.

## Agentic conversation loop

```text
User states goal
    ↓
Agent 1 (OpenAI) extracts buyer_requirements
    ↓
session/prompt → Agent 2
    ↓
needs_clarification? ──YES──► Agent 1 fills gap from goal OR asks user → loop
    │
    NO (offers returned)
    ↓
Agent 1 evaluates: do offers match goal?
    │
    NO ──► refine query/budget → session/prompt again (max 3 search retries)
    │
    YES
    ↓
commerce/request → pay
```

**Rule:** Keep talking to Agent 2 until `missing_fields` is empty **and** offers match the buyer goal — or escalate to the user.

## Buyer requirements schema

```json
{
  "query": "cushioned running shoe",
  "max_price": 150,
  "category": "running",
  "style": "cushioned",
  "size": "10",
  "user_goal": "original natural language from user"
}
```

## ACP methods used

| Method | Purpose |
|--------|---------|
| `initialize` | Handshake with seller |
| `session/new` | Start conversation |
| `session/prompt` | Send NL messages; receive offers or clarification |
| `commerce/request` | Lock in a chosen offer |
| `commerce/pay` | Execute payment |
| `session/close` | End session |

## Constraints (demo policy)

From `intent/CONSTRAINTS.md`:

- `budget.max` — never pay above stated max
- `categories.allowed` — optional filter (default: running in strict mode)
- Payment rails: `stripe_fiat` or `x402`

## Entry point

```bash
python -m agents.buyer.orchestrator "I want cushioned running shoes under $150, size 10"
# or: python -m agents
```

Or interactive:

```bash
python -m agents.orchestrator
```

## Related files

| File | Role |
|------|------|
| `agents/orchestrator.py` | Buyer↔seller loop |
| `buyer_agent.py` | Legacy scripted commerce demo |
| `agents/skills/clarification/SKILL.md` | Multi-turn Q&A protocol |
