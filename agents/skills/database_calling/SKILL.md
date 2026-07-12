---
name: database-calling
description: >-
  Queries the Nike product catalog from Postgres or the seller HTTP API.
  Extracts structured search params from buyer chat, runs ranked DB/API lookups,
  and returns the top 3 matching products by confidence score. Use when the agent
  needs inventory search, product recommendations, offers, catalog lookup, budget
  filtering, or any task that must ground answers in real database rows — never
  invented SKUs.
---

# Database Calling — Product Search Skill

## Purpose

Turn unstructured buyer messages into **structured search parameters**, call the **database or catalog API**, and return **exactly 3 ranked matches** (or fewer if none qualify). Product facts must come from DB/API rows only — never from LLM memory.

## When to use this skill

Use this skill when:

- A buyer asks for shoes, styles, categories, or products ("comfortable running shoe under $150")
- You need to build `offers[]` for ACP `session/prompt`
- You need to verify a product exists before `commerce/request`
- You have partial info (query only, budget only) and must combine session context

Do **not** use this skill for payment, wallet, or ERC-8004 flows — those use other handlers.

---

## Architecture (read once)

```text
Buyer message (NL)
    ↓
Step 1: Extract { query, max_price, category? }
    ↓
Step 2: Validate — ask clarification if budget missing (demo default)
    ↓
Step 3: DB/API call — ranked search, top_k = 3
    ↓
Step 4: Map rows → offers[] with score
    ↓
Step 5: Return agentMessage + offers (or "no matches")
```

**Ranking source of truth:** search layer / Postgres — **not** the LLM. The LLM only extracts parameters and formats the reply.

**Current repo state:**
- Postgres `products` table seeded via `scripts/seed_catalog.py`
- After clarification: `search_products()` queries Postgres (`catalog/db.py`)
- Seller `session/prompt` and `GET /products` use database_calling — no category hard-filter
- In-memory `catalog/data.py` is fallback only when `DATABASE_URL` is unset

---

## Step 1 — Extract structured parameters

From the latest buyer message **plus** up to 4 prior session turns, produce:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | string | yes | Natural-language product intent, e.g. `"cushioned running shoe"` |
| `max_price` | number (USD) | yes* | Budget ceiling. *Demo requires budget; if missing → clarification |
| `category` | string | no | `running`, `lifestyle`, `basketball`, `trail`, `soccer`, `golf`, `sandals`, `kids`, `apparel`, `accessories` |
| `top_k` | int | no | Default **3** — always request 3 unless caller specifies otherwise |

### Extraction rules

1. **Budget patterns** (regex fallback is fine):
   - `$200`, `under 150`, `budget of 200`, `max $180`, `250 dollars`
2. **Query** = product intent **without** price tokens. Keep category words (`running`, `basketball`) in `query`.
3. **Category** = set only if buyer explicitly names a category; otherwise leave `null` and let search infer.
4. If `max_price` is missing and session has no stored budget → set `needs_clarification: true` and ask:
   > "What's your budget for this purchase?"
5. On turn 2, merge stored `query` from session context with new budget from the latest message.

### Extraction output (internal JSON)

```json
{
  "query": "cushioned running shoe",
  "max_price": 150,
  "category": "running",
  "needs_clarification": false,
  "top_k": 3
}
```

---

## Step 2 — Choose call path (priority order)

### Path A — HTTP API (preferred once implemented)

Call the seller catalog endpoint:

```http
GET {SELLER_BASE_URL}/products?query={query}&max_price={max_price}&top_k=3&category={category}
```

| Env var | Default |
|---------|---------|
| `SELLER_BASE_URL` | `http://localhost:8002` (local) or Railway seller URL (prod) |

**Expected response shape:**

```json
{
  "count": 3,
  "query": "cushioned running shoe",
  "max_price": 150,
  "results": [
    {
      "id": "abc123",
      "name": "Nike Air Zoom Pegasus 41",
      "price": 130.00,
      "currency": "USD",
      "category": "running",
      "description": "The everyday workhorse — responsive zoom, smooth ride",
      "score": 0.742
    }
  ]
}
```

**Single product lookup:**

```http
GET {SELLER_BASE_URL}/products/{id}
```

### Path B — ACP session (current demo flow)

If you are the seller agent handling `session/prompt`, call the search layer directly (same contract as `_build_offers` in `seller_agent.py`):

```python
from search import catalog_search

results = catalog_search.search(
    query=query,
    max_price=max_price,
    top_k=3,
)
```

Future swap (no handler changes):

```python
# from catalog_db import postgres_search
# results = postgres_search.search(query=query, max_price=max_price, top_k=3)
```

### Path C — Direct Postgres (scripts / MCP / offline agent)

Use when HTTP is unavailable but `DATABASE_URL` is set (from `local.env`).

**Connection:** load `DATABASE_URL` from repo root `local.env`. Normalize `postgres://` → `postgresql://`. **Local dev must use Railway public host**, not `postgres.railway.internal`.

**Table:** `products`

| Column | Type | Search use |
|--------|------|------------|
| `id` | TEXT PK | offer id |
| `name` | TEXT | name similarity |
| `sub_title` | TEXT | extra tokens |
| `price_usd` | NUMERIC | budget filter |
| `currency` | TEXT | offer currency |
| `category` | TEXT | category boost / filter |
| `description` | TEXT | offer description |
| `keywords` | TEXT[] | token overlap (primary signal) |
| `image_url` | TEXT | optional UI |
| `product_url` | TEXT | optional link |
| `availability` | TEXT | informational |
| `available_sizes` | TEXT | informational |
| `brand` | TEXT | default Nike |
| `active` | BOOLEAN | **must be true** for sellable items |

**Scoring (mirror `search.py` in-memory logic):**

- Keyword overlap: **0.65** — fraction of query tokens found in `keywords`
- Name similarity: **0.25** — fuzzy match on `lower(name)`
- Category boost: **0.10** — if query contains `lower(category)`
- Minimum score threshold: **> 0.05**
- Hard filter: `active = true`, `price_usd <= max_price`
- Optional hard filter: `category = $category` when provided
- Sort: `score DESC`, `LIMIT 3`

**Reference SQL** (requires `pg_trgm` for `similarity()`; if unavailable, use Path B or Python `search_products`):

```sql
WITH params AS (
  SELECT
    lower(:query) AS q,
    regexp_split_to_array(lower(:query), '\W+') AS q_tokens,
    :max_price::numeric AS max_p,
    :category AS cat
),
scored AS (
  SELECT
    p.id,
    p.name,
    p.price_usd,
    p.currency,
    p.category,
    p.description,
    p.keywords,
    p.image_url,
    (
      (
        SELECT COUNT(*)::float
        FROM unnest(p.keywords) kw
        WHERE kw = ANY (SELECT unnest(q_tokens) FROM params)
      ) / GREATEST(cardinality((SELECT q_tokens FROM params)), 1)
      * 0.65
      + similarity(lower(p.name), (SELECT q FROM params)) * 0.25
      + CASE
          WHEN (SELECT q FROM params) LIKE '%' || lower(p.category) || '%' THEN 0.10
          ELSE 0
        END
    ) AS score
  FROM products p, params
  WHERE p.active = true
    AND p.price_usd <= (SELECT max_p FROM params)
    AND (
      (SELECT cat FROM params) IS NULL
      OR p.category = (SELECT cat FROM params)
    )
)
SELECT id, name, price_usd AS price, currency, category, description,
       round(score::numeric, 3) AS score
FROM scored
WHERE score > 0.05
ORDER BY score DESC
LIMIT 3;
```

**Python entry point** (agent tool implementation target):

```python
def search_products(query: str, max_price: float, top_k: int = 3, category: str | None = None) -> list[dict]:
    """Single entry point for HTTP route, ACP handler, and MCP tool."""
    ...
```

---

## Step 3 — Map DB/API results to offers

Every result must include a **confidence `score`** from the search layer (0–1). Map fields as follows:

| DB / API field | Offer field |
|----------------|-------------|
| `id` | `id` |
| `name` | `name` |
| `description` | `description` |
| `price` / `price_usd` | `price` |
| `currency` | `currency` |
| `category` | `category` |
| `score` | `score` |

Add ACP commerce fields:

```json
{
  "id": "…",
  "name": "…",
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

Return **at most 3** offers, sorted by `score` descending.

---

## Step 4 — Agent response templates

### 3 matches

```text
Found 3 matches. Best fit: {offers[0].name} — ${offers[0].price}. (2 more options included)
```

### 1 match

```text
Found it: {name} — ${price} {currency}. {description}
```

### 0 matches

```text
No Nike shoes found for '{query}' within ${max_price}. Try a higher budget or a different style.
```

Return empty `offers: []` — do not fabricate alternatives.

### Missing budget

```text
I can help you find the perfect Nike shoe. What's your budget for this purchase?
```

Set `stopReason: "end_turn"`, no offers, store `pending_intent` in session for turn 2.

---

## Guardrails (mandatory)

1. **Never invent products.** Every `id`, `name`, and `price` must trace to a DB row or `catalog_search` result.
2. **Never skip the search call** when the buyer asked for recommendations — even if the LLM "knows" Nike models.
3. **Always pass `top_k=3`** unless the user explicitly asks for fewer.
4. **Filter inactive rows:** `active = true` / `availability = InStock` in Postgres.
5. **Respect budget:** exclude items where `price > max_price`.
6. **Id lookup:** for `commerce/request`, verify with `GET /products/{id}` or `catalog_search.get(id)` before accepting.
7. **Secrets:** never log or echo `DATABASE_URL` or API keys.
8. **Errors:** if DB/API fails, say search is temporarily unavailable — do not guess catalog items.

---

## Worked examples

### Example 1 — Full intent in one message

**Buyer:** "I need a cushioned running shoe, budget $150"

**Extracted:**

```json
{ "query": "cushioned running shoe", "max_price": 150, "category": "running", "top_k": 3 }
```

**Call:**

```http
GET /products?query=cushioned%20running%20shoe&max_price=150&top_k=3&category=running
```

**Action:** Return top 3 `offers[]` with scores; highlight highest-score item in `agentMessage`.

---

### Example 2 — Two-turn clarification

**Turn 1 — Buyer:** "Something for basketball"

Extract → `max_price: null`, `needs_clarification: true`
**Response:** Ask for budget. Store `query: "basketball shoe"` in session.

**Turn 2 — Buyer:** "Under $120"

Extract → `max_price: 120`, merge `query` from session
**Call:** `search(query="basketball shoe", max_price=120, top_k=3)`
**Response:** 3 ranked offers or no-match message.

---

### Example 3 — Direct id verification

**Buyer:** "I'll take product id `f3a8c2…`"

**Call:**

```http
GET /products/f3a8c2…
```

If 404 → tell buyer the id is not in catalog; suggest `session/prompt` search.
If 200 → proceed to `commerce/request` with that id and listed price.

---

## Tool definition (for Agent 2 LLM tool loop)

When exposing this as an LLM tool:

```json
{
  "name": "search_products",
  "description": "Search Nike catalog in Postgres/API. Returns top 3 products ranked by relevance score. Use for any product discovery or recommendation request.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language product search, e.g. 'lightweight trail runner'"
      },
      "max_price": {
        "type": "number",
        "description": "Maximum price in USD"
      },
      "category": {
        "type": "string",
        "description": "Optional category filter"
      },
      "top_k": {
        "type": "integer",
        "description": "Number of results; default 3"
      }
    },
    "required": ["query", "max_price"]
  }
}
```

**Tool handler pseudocode:**

```python
def handle_search_products(args: dict) -> dict:
    results = search_products(
        query=args["query"],
        max_price=args["max_price"],
        top_k=args.get("top_k", 3),
        category=args.get("category"),
    )
    return {"results": results, "count": len(results)}
```

---

## Checklist before returning to buyer

- [ ] Extracted `query` and `max_price` (or asked for budget)
- [ ] Called DB/API — did not hallucinate catalog
- [ ] Returned ≤ 3 items, sorted by `score` DESC
- [ ] Each offer has `id`, `name`, `price`, `currency`, `category`, `description`, `score`
- [ ] `agentMessage` summarizes best match and count
- [ ] Empty results → helpful no-match message, not fake products

---

## Related files in this repo

| File | Role |
|------|------|
| `search.py` | `CatalogSearch.search(query, max_price, top_k=3)` — interface to preserve |
| `seller_agent.py` | `_build_offers()`, `session/prompt`, clarification + search |
| `agents/skills/clarification/SKILL.md` | Multi-turn requirements before search |
| `agents/buyer/orchestrator.py` | Agent 1 ↔ Agent 2 conversation loop |
| `scripts/seed_catalog.py` | Postgres schema + CSV seed |
| `catalog.py` | Legacy in-memory catalog (being replaced) |
| `local.env` | `DATABASE_URL` for Path C |
