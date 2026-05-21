# ACP Demo — Phase 1
## Simulating Agentic Payments with ACP (Agent Client Protocol)

Based on thesis: "Capturing Intent Over Attention in Agentic Payments" by Dheeraj Maske

---

## What this builds

```
Buyer Agent (buyer_agent.py)        Seller Agent (seller_agent.py)
        │                                        │
        │  Step 1: initialize                    │
        │ ──────────────────────────────────────►│
        │  ◄────── capabilities + agentInfo ─────│
        │                                        │
        │  Step 2: commerce/request              │
        │  "I want air_max_270, max $200"        │
        │ ──────────────────────────────────────►│
        │  ◄────── offer: $150.00, payment needed│
        │                                        │
        │  Step 3: [payment — Phase 2]           │
```

---

## Live Demo

- **Frontend (Netlify):** demo.html served on Netlify
- **Backend (Railway):** seller_agent.py running at `https://acp-demo-production.up.railway.app`

---

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn requests
```

**Terminal 1 — Start the Seller Agent:**
```bash
uvicorn seller_agent:app --port 8002
```

**Terminal 2 — Run the Buyer Agent:**
```bash
python3 buyer_agent.py
```

---

## Phase Roadmap

| Phase | Status | What it does | File(s) |
|-------|--------|--------------|---------|
| 1 | ✅ Done | ACP handshake + commerce intent + offer | `seller_agent.py`, `buyer_agent.py`, `demo.html` |
| 2 | 🔜 Tomorrow | Stripe fiat payment execution | `seller_agent.py`, `buyer_agent.py` |
| 3 | ⏳ Pending | x402 crypto payment (USDC) | `seller_agent.py` |
| 4 | ⏳ Pending | Trust + audit layer | New `trust_layer.py` |

---

## Phase 1 — What's Done vs What's Missing

### Done ✅

| ACP Component | Implementation |
|---|---|
| JSON-RPC 2.0 message envelope | `jsonrpc: "2.0"`, `id`, `method`, `params` on every message |
| `initialize` handshake | Both agents send/receive and store capabilities |
| `clientInfo` / `agentInfo` exchange | Name + version sent both ways |
| `clientCapabilities` / `agentCapabilities` | `commerce`, `payment`, `mcpCapabilities` fields |
| `authMethods` field | Returned as `[]` |
| Custom commerce method | `commerce/request` — intent + offer pattern |
| CORS | `allow_origins=["*"]` on seller for browser access |
| Live UI wired to backend | `demo.html` makes real fetch() calls to Railway |

### Missing / Phase 2+ 🔜

| Gap | What's needed | Phase |
|---|---|---|
| Payment never executes | Stripe API integration in `seller_agent.py` + `pay()` in buyer | 2 |
| No session layer | `session/new`, `session/prompt`, `session/cancel` methods | 2 |
| Version negotiation not enforced | Seller must reject unsupported `protocolVersion` | 2 |
| No authentication | Validate bearer token or API key in seller | 2 |
| Buyer not deployed | Buyer is a local script — needs to be a running service | 3 |
| Crypto payment | x402 / USDC integration | 3 |
| Trust + audit | Log all agent transactions with signatures | 4 |

---

## Where to Start Tomorrow (Phase 2)

1. **Stripe payment** — add `stripe` to `requirements.txt`, create a payment intent in `handle_commerce_pay()` in `seller_agent.py`
2. **`commerce/pay` method** — add a new handler in `seller_agent.py` that calls Stripe and returns a receipt
3. **`pay()` function in buyer** — send a real `commerce/pay` JSON-RPC call instead of the placeholder
4. **Version check** — add `if protocol_version != SUPPORTED_VERSION: return error(...)` in `handle_initialize()`
5. **Session ID** — generate a UUID in `initialize` response and require it on all subsequent calls

---

## How this maps to the thesis diagram

| Thesis Diagram | This code |
|---|---|
| Human / User | You (triggering buyer_agent.py) |
| Personal Agent | `buyer_agent.py` |
| Vendor Agent | `seller_agent.py` |
| Intent Request (arrow d) | `commerce/request` method |
| Verified Offer (arrow e) | `offer` in response |
| Payment | Phase 2 (Stripe) / Phase 3 (x402) |
| Intent + Trust Layer | Phase 4 (`trust_layer.py`) |
