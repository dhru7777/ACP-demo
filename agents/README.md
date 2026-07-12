# Agents package — modular buyer/seller architecture

```
agents/
├── buyer/                    # Agent 1 — Anthropic, owns user goal
│   ├── AGENT.md              # Mission, skills map, ACP methods
│   ├── acp_client.py         # JSON-RPC client → seller :8002
│   ├── planner.py            # Anthropic: plan replies to clarifications
│   └── orchestrator.py       # Buyer ↔ seller conversation loop
├── seller/                   # Agent 2 — OpenAI, sells + matches requirements
│   ├── AGENT.md              # Mission, skill chain, offer shape
│   ├── intent.py             # Parse buyer messages → requirements
│   ├── prompt.py             # session/prompt, clarification, offers
│   └── handlers/             # ACP JSON-RPC handlers
│       ├── initialize.py
│       ├── session.py
│       ├── commerce.py
│       └── __init__.py
├── shared/
│   └── requirements.py       # Merge, missing fields, question templates
└── skills/
    ├── clarification/SKILL.md
    └── database_calling/SKILL.md

acp/
└── session_manager.py          # Session lifecycle (buyer/seller)

catalog/
├── data.py                     # In-memory Nike catalog
└── search.py                   # CatalogSearch — swap to Postgres later

# Root entry points (thin)
seller_agent.py                 # FastAPI app + HTTP routes → imports agents.seller.handlers
buyer_agent.py                  # Legacy scripted commerce demo
agents/orchestrator.py          # Shim → agents.buyer.orchestrator

# Root shims (backward compatible)
session_manager.py              # → acp.session_manager
catalog.py / search.py          # → catalog package
agents/requirements.py          # → agents.shared.requirements
agents/seller_intent.py         # → agents.seller.intent
```

## Run

```bash
# Seller (Agent 2)
python seller_agent.py

# Agentic buyer ↔ seller loop (Agent 1)
python -m agents.buyer.orchestrator "running shoes under $150"
python -m agents   # same
```

## Skill chain (Agent 2)

```text
clarification → database_calling → offers[]
```

## LLM split

| Agent | LLM | Module |
|-------|-----|--------|
| Agent 1 (buyer) | Anthropic | `agents/buyer/planner.py` |
| Agent 2 (seller) | OpenAI (fallback: Anthropic, regex) | `agents/seller/intent.py` |
