# ACP Demo — Agentic Commerce on Nike

**Capturing Intent Over Attention in Agentic Payments** — a seven-day build that takes two AI agents from handshake to real money movement to on-chain identity.

| Layer | Protocol | Question it answers |
|-------|----------|---------------------|
| Negotiation | **ACP** (Agent Client Protocol) | Can these agents agree on an offer? |
| Settlement | **x402** (USDC) + **Stripe** (fiat) | Did payment complete on the chosen rail? |
| Trust | **ERC-8004** + [8004scan](https://testnet.8004scan.io) | Who is this agent, and can I verify it? |

**Live seller:** [acp-demo-production.up.railway.app](https://acp-demo-production.up.railway.app)  
**Registered identity:** [Attention Agent #6832 on Base Sepolia](https://testnet.8004scan.io/agents/base-sepolia/6832)

---

## What this repo is

A Nike-themed **buyer ↔ seller** demo:

1. **Handshake** — `initialize` exchanges capabilities (ACP + x402 + Stripe).
2. **Session** — multi-turn conversation with history (`session/new`, `session/prompt`, …).
3. **Catalog** — 100 Nike items; fuzzy search + optional Claude Haiku intent parsing.
4. **Payment** — buyer picks **Crypto (USDC on Base Sepolia)** or **Fiat (Stripe test card ···4242)**.
5. **Profile** — seller **◎** panel shows ERC-8004 identity, 8004scan rank, feedback, and verify links.

Open `demo.html` for the three-column stage: **Buyer** | **Protocols (ACP · x402 · Stripe)** | **Seller**.

---

## Quick start (local)

```bash
cd acp-demo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp local.env.example local.env
# Fill keys: ANTHROPIC_API_KEY (optional), wallets, SCAN8004_API_KEY, Stripe (fiat)

# Terminal 1 — seller (ACP + x402 + Stripe + ERC-8004)
uvicorn seller_agent:app --host 0.0.0.0 --port 8002 --reload

# Terminal 2 — demo UI
python3 -m http.server 8080
# → http://localhost:8080/demo.html
```

**Profile locally:** 8004scan registers your Railway URL, not `localhost`. Set `ERC8004_SERVICE_URL=https://acp-demo-production.up.railway.app` or `ERC8004_AGENT_ID=6832` in `local.env`.

**Smoke test:** Start → Handshake → Session → *"running shoes at $150"* → pick offer → Payment → Crypto or Fiat → seller **◎ Profile** → Verify tab → 8004scan link.

Hard refresh after UI changes (`Cmd+Shift+R`). Footer shows build stamp (e.g. `build 2026-06-07g`).

---

## Seven-day arc

| Day | README | You shipped |
|-----|--------|-------------|
| **1** | [Readme_Day1.md](./Readme_Day1.md) | Handshake, first priced offer |
| **2** | [README_DAY2.md](./README_DAY2.md) | Sessions + conversation history |
| **3** | [README_DAY3.md](./README_DAY3.md) | Natural language `session/prompt` |
| **4** | [README_DAY4.md](./README_DAY4.md) | 100-item catalog, multi-turn negotiation |
| **5** | [README_DAY5.md](./README_DAY5.md) | x402 USDC, live wallets, PDF receipts |
| **6** | [README_DAY6.md](./README_DAY6.md) | Stripe fiat + buyer payment rail choice |
| **7** | [README_DAY7.md](./README_DAY7.md) | ERC-8004 trust layer + ◎ profile UI |

**Start here after a break:** [README_DAY7.md](./README_DAY7.md) — narrative map of Acts I–IV, env cheatsheet, file map, and production gaps.

---

## Project layout

```
acp-demo/
├── demo.html              # Buyer/seller UI, wallets, ◎ profile
├── seller_agent.py        # ACP + payments + GET /agent/erc8004
├── buyer_agent.py         # Terminal buyer script
├── session_manager.py     # Session history + payment receipts
├── search.py              # Catalog search (100 Nike items)
├── payments/              # x402, Stripe, wallets, chain reads
├── trust/                 # ERC-8004 + 8004scan (Day 7)
├── local.env.example      # Env var reference
└── README_DAY*.md         # One chapter per build day
```

---

## Key env vars

See `local.env.example` for the full list. Minimum for a full demo:

```bash
X402_NETWORK=eip155:84532
BUYER_WALLET_PRIVATE_KEY=0x...
SELLER_PAYTO_ADDRESS=0x...
DEMO_SERVER_SIGN=true          # single-service demo: seller signs buyer USDC
SCAN8004_API_KEY=...           # 8004scan profile + ranking
```

Stripe keys (Day 6) for fiat. `ANTHROPIC_API_KEY` optional — regex fallback for intent.

ERC-8004 agent ID is **auto-discovered** from the seller's public URL when `ERC8004_AGENT_ID` is omitted.

---

## Thesis

Commerce between AI agents needs **intent** (what the buyer wants), **session** (a real conversation), **payment** (money that moves), and **trust** (verifiable identity). This repo implements that stack in public — one day at a time.

---

*One-liner: **Nike agentic commerce demo — ACP for negotiation, x402 and Stripe for payment, ERC-8004 for who the seller is.** Open ◎ and show Attention Agent on Base Sepolia.*
