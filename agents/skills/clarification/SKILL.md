---
name: clarification
description: >-
  Multi-turn clarification between buyer and seller agents until all required
  purchase requirements are known. Detects missing fields (budget, category,
  style, size), asks one focused question per turn, merges partial answers
  across session context, and only proceeds to catalog search when constraints
  are satisfied. Use when session/prompt returns needs_clarification, when
  buyer intent is incomplete, or before calling database_calling.
---

# Clarification — Requirements Gathering Skill

## Purpose

Keep the buyer–seller conversation going **until every required field is known** and the buyer's goal can be searched in the catalog. Ask **one question at a time**. Never search the database or invent offers while required fields are still missing.

## When to use this skill

Use **before** `database_calling` when:

- Buyer message lacks budget, product intent, or other required fields
- `session/prompt` would return `stopReason: "needs_clarification"`
- Agent 1 has a goal but Agent 2 cannot search yet
- Prior turn stored partial requirements in session context

Do **not** use for payment, wallet, or post-offer negotiation — only for **gathering requirements**.

---

## Required vs optional fields

| Field | Required for search? | Priority | Example question |
|-------|---------------------|----------|------------------|
| `query` | **Yes** | 1 | "What kind of shoe are you looking for?" |
| `max_price` | **Yes** | 2 | "What's your budget for this purchase?" |
| `category` | No* | 3 | "Running, basketball, lifestyle, or something else?" |
| `style` | No | 4 | "Any preference — cushioned, lightweight, stability?" |
| `size` | No | 5 | "What size do you need?" |

\*Set `category` when the buyer names one explicitly; otherwise infer from `query` during search.

### Goal satisfied (ready for `database_calling`)

```text
query is non-empty AND max_price is a positive number
```

Optional fields improve search quality but **must not block** search once required fields are set.

---

## Architecture

```text
Buyer message (Agent 1 or user)
    ↓
Merge into session requirements { query, max_price, category?, style?, size? }
    ↓
missing = detect_missing(requirements)
    ↓
missing empty?  ──YES──► database_calling (top 3 search)
    │
    NO
    ↓
Pick highest-priority missing field → ask ONE question
    ↓
stopReason: needs_clarification → wait for next turn
    ↓
Buyer answers → merge → repeat until satisfied
```

**Session context keys** (seller stores between turns):

```json
{
  "awaiting_clarification": true,
  "requirements": {
    "query": "basketball shoe",
    "max_price": null,
    "category": "basketball",
    "style": null,
    "size": null
  },
  "missing_fields": ["max_price"],
  "turn": 2
}
```

---

## Step 1 — Merge new input into requirements

On every `session/prompt` turn:

1. Load `requirements` from session context (or start empty).
2. Parse the latest message (LLM or regex).
3. **Only overwrite** fields when the new message provides a non-null value.
4. Never clear a field that was set on a prior turn.

### Merge rules

| Signal in message | Field to set |
|-------------------|--------------|
| Product description | `query` |
| `$150`, `under 200`, `budget 120` | `max_price` |
| `running`, `basketball`, `trail` | `category` (and enrich `query`) |
| `cushioned`, `lightweight`, `stability` | `style` |
| `size 10`, `US 9.5` | `size` |

**Turn 2+ budget-only reply:** If `query` already in context, accept `max_price` alone.

---

## Step 2 — Detect missing fields

```python
REQUIRED = ["query", "max_price"]
OPTIONAL = ["category", "style", "size"]

def missing_fields(req: dict) -> list[str]:
    out = []
    if not (req.get("query") or "").strip():
        out.append("query")
    price = req.get("max_price")
    if price is None or price <= 0:
        out.append("max_price")
    return out
```

Return `missing_fields` sorted by priority table above.

---

## Step 3 — Ask one question (not a list)

Ask **only** about the **first** missing required field. If all required fields are set but optional fields might help and the buyer seems undecided, you may ask **one** optional question — then search even if they skip it.

### Question templates

| Field | Template |
|-------|----------|
| `query` | "What kind of Nike shoe are you shopping for today?" |
| `max_price` | "What's your budget for this purchase?" |
| `category` | "Are you looking for running, basketball, lifestyle, or another category?" |
| `style` | "Any style preference — cushioned, lightweight, or stability?" |
| `size` | "What size do you need?" |

Keep `response_message` to **one short sentence**.

---

## Step 4 — Agent 1 ↔ Agent 2 loop

When Agent 2 returns `needs_clarification`:

1. Agent 1 reads `missing_fields` and `agentMessage` from the seller response.
2. Agent 1 checks its **buyer goal** (user constraints) for the missing value.
3. If known → Agent 1 sends another `session/prompt` with that answer (no human needed).
4. If unknown → Agent 1 asks the human user, then forwards the answer.
5. Repeat until `stopReason: "end_turn"` with `offers[]` or max clarification rounds (default **6**).

### Stop conditions

| Condition | Action |
|-----------|--------|
| `missing_fields` empty | Proceed to `database_calling` |
| `offers[]` non-empty | Goal phase: evaluate match (Agent 1) |
| 6 clarification rounds with same missing field | Escalate to user with explicit ask |
| Buyer cancels | `session/cancel`, end loop |

---

## Response contract (seller → buyer)

### Still clarifying

```json
{
  "stopReason": "needs_clarification",
  "agentMessage": "What's your budget for this purchase?",
  "parsedIntent": {
    "query": "basketball shoe",
    "max_price": null,
    "category": "basketball"
  },
  "requirements": {
    "query": "basketball shoe",
    "max_price": null,
    "category": "basketball",
    "style": null,
    "size": null
  },
  "missing_fields": ["max_price"],
  "awaitingClarification": true,
  "offers": []
}
```

### Ready — search ran

```json
{
  "stopReason": "end_turn",
  "agentMessage": "Found 3 matches. Best fit: …",
  "parsedIntent": { "query": "…", "max_price": 120 },
  "requirements": { "query": "…", "max_price": 120, "category": "basketball" },
  "missing_fields": [],
  "offers": [ "... top 3 ..." ]
}
```

---

## Worked examples

### Example 1 — Budget missing (2 turns)

**Turn 1 — Buyer:** "Something for basketball"

```json
{ "requirements": { "query": "basketball shoe", "category": "basketball" }, "missing_fields": ["max_price"] }
```

**Seller:** "What's your budget for this purchase?"

**Turn 2 — Buyer:** "Under $120"

```json
{ "requirements": { "query": "basketball shoe", "max_price": 120, "category": "basketball" }, "missing_fields": [] }
```

→ `database_calling` → top 3 offers.

---

### Example 2 — Agent 1 auto-answers from user goal

**User goal (Agent 1):** "Buy cushioned running shoes, max $150, size 10"

**Turn 1 — Agent 1 → Seller:** "I need cushioned running shoes"

Seller asks for budget.

**Agent 1** (knows goal) → Seller: "My budget is $150"

Seller may ask size (optional).

**Agent 1** → Seller: "Size 10"

→ Search → offers.

---

### Example 3 — Vague query

**Turn 1:** "I need new shoes"

Missing: `query` (too vague) and `max_price`

Ask about **query** first (priority 1): "What kind of Nike shoe are you shopping for today?"

---

## Guardrails

1. **One question per turn** — do not bombard the buyer with a checklist.
2. **Never search** while `max_price` or `query` is missing.
3. **Never invent** budget or product preferences — only use stated or merged values.
4. **Preserve context** across turns; seller session must remember turn 1 intent.
5. **Max 6 clarification rounds** — then escalate or end with a clear message.
6. After requirements satisfied, **hand off to `database_calling`** — do not pick products in the clarification phase.

---

## Skill chain

```text
clarification  →  (requirements satisfied)  →  database_calling  →  offers[]
```

Load `agents/skills/clarification/SKILL.md` first when intent is incomplete.
Load `agents/skills/database_calling/SKILL.md` only after `missing_fields` is empty.

---

## Related files

| File | Role |
|------|------|
| `agents/shared/requirements.py` | `merge_requirements`, `missing_fields`, question templates |
| `agents/README.md` | Package layout and run instructions |
| `agents/seller/AGENT.md` | Agent 2 mission — sell + match requirements |
| `agents/buyer/AGENT.md` | Agent 1 mission — satisfy user goal |
| `agents/buyer/orchestrator.py` | Agent 1 ↔ Agent 2 conversation loop |
| `seller_agent.py` | `session/prompt` handler |
