# ACP Demo — Phase 1
## Two Agents Communicating Locally

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
        │  "I want market_data_report, max $2"   │
        │ ──────────────────────────────────────►│
        │  ◄────── offer: $1.00, payment needed ─│
        │                                        │
        │  Step 3: [payment — Phase 2]           │
```

---

## Setup

```bash
pip install fastapi uvicorn requests
```

---

## Run

**Terminal 1 — Start the Seller Agent:**
```bash
python seller_agent.py
```

**Terminal 2 — Run the Buyer Agent:**
```bash
python buyer_agent.py
```

---

## Phases

| Phase | What gets added       | File to modify         |
|-------|-----------------------|------------------------|
| 1     | ACP handshake + intent | seller_agent.py, buyer_agent.py |
| 2     | Stripe fiat payment    | Add stripe to seller, pay() in buyer |
| 3     | x402 crypto (USDC)     | Add x402 to seller_agent.py |
| 4     | Trust + audit layer   | New trust_layer.py service |

---

## How this maps to your thesis diagram

| Thesis Diagram         | This code              |
|------------------------|------------------------|
| Human/User             | You (running buyer_agent.py) |
| Personal Agent         | buyer_agent.py         |
| Vendor Agent           | seller_agent.py        |
| Intent Request (arrow d) | commerce/request method |
| Verified Offer (arrow e) | offer in response      |
| Intent + Trust Layer   | Phase 4                |
| Payments               | Phase 2 (Stripe) / Phase 3 (x402) |