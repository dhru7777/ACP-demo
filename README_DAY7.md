# ACP Demo — Day 7

## Trust, Identity, and the Story So Far

**Date:** June 7, 2026  
**Author:** Dheeraj Maske  
**Thesis:** *Capturing Intent Over Attention in Agentic Payments*

*Read this when you come back after a week. It is the map, not the manual.*

---

## The story in one paragraph

You set out to prove that commerce between AI agents needs more than a checkout button — it needs **intent** (what the buyer wants), **session** (a real conversation), **payment** (money that actually moves), and eventually **trust** (proof that the agent on the other side is who it claims to be). Over seven days you built that arc in public: handshake → session → natural-language prompts → a 100-item Nike catalog → real USDC on Base Sepolia → real Stripe test charges → and finally **ERC-8004 identity** on 8004scan with a live profile panel in the demo. The seller is no longer just a Python server on Railway. It is **Attention Agent** — agent `#6832` on Base Sepolia, discoverable, scored, and verifiable.

---

## Act I — Two agents learn to talk (Days 1–2)

**Day 1** was the spark. A buyer agent and a seller agent spoke JSON-RPC over HTTP. `initialize` exchanged capabilities. `commerce/request` turned *"I want Air Max 270 under $200"* into a priced offer. The UI on Netlify called Railway. Nothing was fake except the payment step — and that gap was the whole point.

**Day 2** gave the conversation a memory. ACP sessions (`session/new`, `session/load`, `session/resume`, `session/close`) meant every prompt and offer belonged to a `sessionId`. History landed in `session_state.json`. The protocol started to feel like a *relationship*, not a one-shot API call.

→ [Readme_Day1.md](./Readme_Day1.md) · [README_DAY2.md](./README_DAY2.md)

---

## Act II — The buyer finds their voice (Days 3–4)

**Day 3** replaced hardcoded SKUs with **`session/prompt`**. The buyer typed English. The seller parsed intent, searched a catalog, returned an offer card with a shoe image. The boot sequence in `demo.html` was reordered so the story read top-to-bottom: Start → Handshake → Session → Prompt → Payment.

**Day 4** scaled the shop. One hundred Nike items. Fuzzy search in `search.py` (vector-ready). Claude Haiku parsed intent when `ANTHROPIC_API_KEY` was set; regex held the line otherwise. Multi-turn negotiation arrived: *"What's your budget?"* → buyer auto-reply → offer. The buyer agent picked by **relevance**, not cheapest price. You were no longer demoing a protocol — you were demoing **agentic commerce**.

→ [README_DAY3.md](./README_DAY3.md) · [README_DAY4.md](./README_DAY4.md)

---

## Act III — Money moves (Days 5–6)

**Day 5** closed the loop with **x402**. `commerce/pay` quoted USDC on Base Sepolia. The x402.org facilitator verified and settled on-chain. Wallet popovers showed live ETH/USDC balances and Basescan links. PDF receipts appeared in chat. The center column gained a second protocol box: **ACP** for handshake/session, **x402** for settlement. Session history stored quote, proof, and receipt.

**Day 6** added **choice**. The buyer agent paused before pay and offered two rails: **Crypto (USDC)** or **Fiat (Stripe test card ···4242)**. Wallets split into Crypto and Fiat tabs. Two Stripe accounts (buyer charges, seller receives) proved dual-rail was real, not a label. The center column gained a third box: **Stripe** when fiat won.

→ [README_DAY5.md](./README_DAY5.md) · [README_DAY6.md](./README_DAY6.md)

---

## Act IV — Who is this agent? (Day 7)

Payments answer *"did money move?"* Trust answers *"who am I paying, and can I verify that without trusting the UI?"*

### ERC-8004 enters the stage

[EIP-8004](https://eips.ethereum.org/EIPS/eip-8004) separates **identity** (on-chain NFT on the Identity Registry) from **reputation** (indexers, feedback, scores). It does not replace ACP or x402 — it sits beside them:

| Layer | Question it answers |
|--------|---------------------|
| **ACP** | Can these agents negotiate and agree on an offer? |
| **x402 / Stripe** | Did payment complete on the chosen rail? |
| **ERC-8004** | Is this agent a registered identity with a verifiable profile? |

You registered **Attention Agent** on [8004scan testnet](https://testnet.8004scan.io/agents/base-sepolia/6832):

- **Base Sepolia** — agent ID `6832`
- **Service** — `https://acp-demo-production.up.railway.app/`
- **x402** — supported
- **Registration file** — on IPFS (`agentURI`), the canonical JSON behind the name, description, and services

### What we built in code

A modular **`trust/`** package on the seller:

| File | Role |
|------|------|
| `trust/config.py` | Chain, 8004scan API/web URLs, registry addresses |
| `trust/scan8004.py` | 8004scan API + **auto-discovery** by service URL |
| `trust/registry_chain.py` | On-chain `ownerOf`, `tokenURI`, `getAgentWallet` |
| `trust/metadata.py` | Fetch registration JSON (IPFS / HTTPS / data URI) |
| `trust/identity_api.py` | Builds `GET /agent/erc8004` response |

**Auto-discovery:** You no longer need `ERC8004_AGENT_ID` in env for the happy path. The seller matches its public URL against 8004scan (seller wallet narrows the search). Chain defaults from `X402_NETWORK=eip155:84532`.

**Endpoint:** `GET /agent/erc8004` — identity, ranking, feedback, verify links. Health check `GET /` includes a small `erc8004` block.

### The ◎ profile panel (seller header)

Next to the **$** wallet button on the seller panel, **◎** opens **Profile** — four equal tabs:

| Tab | What you see |
|-----|----------------|
| **ID** | Agent ID, chain, global ID, owner, agent wallet, x402 |
| **Rank** | 8004scan scores (0–100): health, popularity, freshness, metadata, … |
| **Feedback** | Stars, watchers, verified, publisher |
| **Verify** | Links to 8004scan, Basescan NFT, registry contract, IPFS JSON, live service |

Each label has a small **ⓘ** icon — hover or tap for a one-line explanation. No wall of text until you ask for it.

**Fixes worth remembering:**

- 8004scan profile URL uses **chain slug** (`base-sepolia/6832`), not numeric `84532/6832` — otherwise you get "Agent Not Found"
- IPFS `agentURI` opens via a public gateway (`dweb.link`), not raw `ipfs://` in the browser

### Owner vs agent wallet (the confusion you hit)

| Field | Meaning |
|-------|---------|
| **Owner** | Wallet that controls the identity NFT (registered on 8004scan) |
| **Agent wallet** | Wallet ERC-8004 declares for commerce / x402 payTo |
| **SELLER_PAYTO_ADDRESS** | What your Railway seller actually uses in `commerce/pay` |

All three *can* match; in the demo they often **don't** until you align `setAgentWallet()` on-chain with env. That's an operator task, not a buyer-facing field.

### Why IPFS shows up at all

On-chain storage only holds a pointer: **`agentURI` → ipfs://Qm…** The JSON file holds name, services, x402 flag, image. IPFS is **content-addressed** — the link is tied to the file hash, not your server hostname. 8004scan indexes it; Basescan shows the NFT; the Verify tab lets anyone audit the same JSON.

---

## The demo as a stage play

Open `demo.html`. Three columns: **Buyer** | **Protocols** | **Seller**.

```
Buyer Agent          Center gutter              Seller Agent
     │                 ACP · handshake              │
     │                 x402 · USDC                  │  ◎ Profile
     │                 Stripe · fiat                │  $ Wallet
     │                                            Attention Agent
     │  session/prompt ──────────────────────────►│  catalog search
     │  commerce/pay   ──────────────────────────►│  x402 or Stripe
```

**Build stamp** in the footer (e.g. `build 2026-06-07g`) — hard refresh after UI changes (`Cmd+Shift+R`).

---

## Progress arc (Day 1 → Day 7)

| Day | You shipped | Emotional beat |
|-----|-------------|----------------|
| **1** | Handshake + offer | *They can talk.* |
| **2** | Sessions + history | *They remember.* |
| **3** | `session/prompt` + NLP | *They understand English.* |
| **4** | 100 items + multi-turn + Claude | *They negotiate.* |
| **5** | x402 USDC + wallets + PDF | *Crypto money moves.* |
| **6** | Stripe fiat + payment picker | *Buyer chooses the rail.* |
| **7** | ERC-8004 + profile + 8004scan | *The agent has a name and a passport.* |

---

## How to run (when you return)

```bash
cd acp-demo
source venv/bin/activate
pip install -r requirements.txt   # if fresh clone

# Terminal 1 — seller (ACP + x402 + Stripe + wallets + ERC-8004)
uvicorn seller_agent:app --host 0.0.0.0 --port 8002 --reload

# Terminal 2 — demo UI
python3 -m http.server 8080
# open http://localhost:8080/demo.html
```

Copy `local.env.example` → `local.env`. Minimum for a full run:

- `ANTHROPIC_API_KEY` — Claude intent (optional; regex fallback)
- `BUYER_WALLET_PRIVATE_KEY` + `SELLER_PAYTO_ADDRESS` — x402
- `DEMO_SERVER_SIGN=true` — demo signs buyer USDC on seller (single-service only)
- `SCAN8004_API_KEY` — 8004scan testnet API for profile/ranking
- Stripe keys — fiat path (Day 6)

**Profile locally:** 8004scan registers your **Railway** URL, not `localhost:8002`. For ◎ on local dev, set `ERC8004_SERVICE_URL=https://acp-demo-production.up.railway.app` or uncomment `ERC8004_AGENT_ID=6832`.

**Smoke test:** Start → Handshake → Session → *"running shoes at $150"* → pick offer → Payment → Crypto or Fiat → ◎ Profile → Verify → 8004scan link.

---

## Env cheatsheet (ERC-8004)

```bash
# Usually enough — chain from X402, agent ID from 8004scan match
X402_NETWORK=eip155:84532
SCAN8004_API_KEY=...

# Optional overrides
# ERC8004_AGENT_ID=6832
# ERC8004_SERVICE_URL=https://your-app.up.railway.app
```

---

## Production gaps (honest ledger)

| Demo today | Production later |
|------------|------------------|
| One Railway service | Split buyer (:8001) + seller (:8002) |
| `DEMO_SERVER_SIGN` on seller | Buyer signs client-side only |
| Full `/agent/erc8004` on seller | Public vs operator-only profile views |
| Post-pay feedback to ERC-8004 | Reputation registry + indexer feedback |
| In-memory sessions | Redis / DB + SSE replay |

---

## File map (where the bodies are buried)

```
acp-demo/
├── demo.html              # The stage — buyer/seller UI, wallets, profile ◎
├── seller_agent.py        # ACP + payments + GET /agent/erc8004
├── buyer_agent.py         # Terminal buyer script
├── session_manager.py     # Session history + payment receipts
├── search.py              # 100-item catalog search
├── payments/              # x402, Stripe, wallets, chain reads
├── trust/                 # ERC-8004 + 8004scan (Day 7)
├── local.env.example      # All env vars documented
└── README_DAY*.md         # One chapter per day — this file is Day 7
```

---

## All chapters

| File | Story beat |
|------|------------|
| [Readme_Day1.md](./Readme_Day1.md) | Handshake, first offer |
| [README_DAY2.md](./README_DAY2.md) | Sessions |
| [README_DAY3.md](./README_DAY3.md) | Natural language |
| [README_DAY4.md](./README_DAY4.md) | Catalog + negotiation |
| [README_DAY5.md](./README_DAY5.md) | USDC on-chain |
| [README_DAY6.md](./README_DAY6.md) | Stripe + payment choice |
| **README_DAY7.md** | **Trust + Attention Agent profile** |

---

## Where Act V might go

You have **intent**, **session**, **dual payment**, and **identity**. The next scenes write themselves:

1. **Buyer-side trust** — buyer agent reads public profile before `commerce/pay`
2. **Post-payment feedback** — ERC-8004 reputation after settle
3. **Split deploy** — buyer server owns keys; seller owns catalog + x402 receive
4. **README on Railway** — env vars for `SCAN8004_API_KEY`, redeploy after Day 7 push

---

*When someone asks what this repo is, say: **"It's a Nike agentic commerce demo — ACP for negotiation, x402 and Stripe for payment, ERC-8004 for who the seller is."** Then open ◎ and show them Attention Agent on Base Sepolia.*
