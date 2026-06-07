# ACP Demo — Day 7

## ERC-8004 Trust Layer + Agent Profile UI

**Date:** June 7, 2026  
**Author:** Dheeraj Maske  
**Builds on:**

- [Day 1 — Handshake + Commerce Intent](./Readme_Day1.md)
- [Day 2 — Session Layer](./README_DAY2.md)
- [Day 3 — Prompt Turn + NLP Intent](./README_DAY3.md)
- [Day 4 — Catalog Search + Multi-Turn Agentic Conversation](./README_DAY4.md)
- [Day 5 — x402 USDC Payment Settlement](./README_DAY5.md)
- [Day 6 — Stripe Fiat + Dual-Rail Payment Selection](./README_DAY6.md)

---

## What we implemented today

Day 7 adds a **trust and identity layer** alongside ACP negotiation and dual-rail payment — the seller is no longer anonymous server code; it is a registered ERC-8004 agent on 8004scan.

1. **`trust/` package** — modular ERC-8004 + 8004scan integration on the seller
2. **`GET /agent/erc8004`** — public identity, ranking, feedback, and verify links
3. **Auto-discovery** — agent ID resolved from public service URL via 8004scan (no hardcoded `ERC8004_AGENT_ID` required)
4. **◎ Profile panel** — seller header popover with four tabs: ID · Rank · Feedback · Verify
5. **ⓘ field help** — click-to-toggle tooltips on each label (hover preview when not dismissed)
6. **8004scan + IPFS fixes** — profile URLs use chain slug (`base-sepolia/6832`); `agentURI` opens via IPFS gateway
7. **Post-x402 ERC-8004 feedback** — after crypto settle, buyer submits `giveFeedback()` on Reputation Registry; rank before/after shown on receipt

**Registered agent:** [Attention Agent #6832 on Base Sepolia](https://testnet.8004scan.io/agents/base-sepolia/6832)

---

## Progress arc (Day 1 → Day 7)


| Day       | Focus                                 | Key additions                                                    |
| --------- | ------------------------------------- | ---------------------------------------------------------------- |
| **Day 1** | Handshake + hardcoded commerce        | `initialize`, `commerce/request`                                 |
| **Day 2** | Session context + history             | `session/new`, `session/load`, `session/resume`, `session/close` |
| **Day 3** | Natural language prompt turn          | `session/prompt`, `stopReason: end_turn`                         |
| **Day 4** | Agentic negotiation + catalog search  | Multi-turn, offer selection, Claude Haiku                        |
| **Day 5** | x402 USDC settlement                  | `commerce/pay`, x402 facilitator, wallet APIs                    |
| **Day 6** | Fiat payments + payment method choice | Stripe, dual wallets, buyer/seller accounts                      |
| **Day 7** | ERC-8004 trust + agent profile        | `GET /agent/erc8004`, 8004scan, ◎ profile, post-pay feedback     |


---

## ACP Flow — Day 7 (trust alongside payment)

```
Buyer Agent / demo.html          Seller Agent                 8004scan / chain
     │  initialize                    │                              │
     │ ──────────────────────────────►│                              │
     │  ◄── payment: x402 & Stripe ───│                              │
     │  ◄── erc8004 in GET / health ──│                              │
     │                                │                              │
     │  [session + prompt + offers — same as Day 6]                  │
     │  [commerce/pay — crypto or fiat — same as Day 6]              │
     │                                │                              │
     │  GET /agent/erc8004            │  discover agent by URL       │
     │ ──────────────────────────────►│ ────────────────────────────►│
     │                                │  on-chain ownerOf, tokenURI  │
     │                                │  fetch IPFS registration     │
     │  ◄── identity + rank + verify ─│                              │
     │                                │                              │
     │  commerce/pay (x402) settle    │                              │
     │ ──────────────────────────────►│  giveFeedback (buyer wallet) │
     │                                │ ──► Reputation Registry      │
     │                                │  poll 8004scan for new scores│
     │  ◄── receipt + trust rank delta│                              │
     │                                │                              │
     │  [◎ Profile panel in UI]       │                              │
```

**Four layers in the stack:**


| Layer          | Question it answers                          | Where in demo                          |
| -------------- | -------------------------------------------- | -------------------------------------- |
| **ACP**        | Can agents negotiate and agree on an offer?  | Center column · handshake/session      |
| **x402**       | Did USDC payment settle on-chain?            | Center column · crypto path            |
| **Stripe**     | Did fiat payment complete?                   | Center column · fiat path              |
| **ERC-8004**   | Who is this agent — verifiable identity?     | Seller **◎ Profile** popover           |


---

## Files Created / Modified

### New: `trust/` package


| File                     | Purpose                                                                 |
| ------------------------ | ----------------------------------------------------------------------- |
| `trust/config.py`        | Chain ID (from `X402_NETWORK`), registry addresses, 8004scan API/web URLs |
| `trust/scan8004.py`      | 8004scan API client + `discover_agent_by_service_url()`                 |
| `trust/registry_chain.py`| On-chain reads: `ownerOf`, `tokenURI`, `getAgentWallet`                 |
| `trust/metadata.py`      | Fetch registration JSON (IPFS / HTTPS / data URI); gateway URL builder  |
| `trust/identity_api.py`  | Builds `GET /agent/erc8004` response with `sections` + verify links     |
| `trust/reputation_chain.py` | On-chain `giveFeedback()` via buyer wallet + Base Sepolia RPC        |
| `trust/feedback_service.py` | Post-x402 feedback orchestration + 8004scan rank polling               |


**Auto-discovery flow:**

```
Request.base_url or ERC8004_SERVICE_URL
  → 8004scan search by endpoint
  → optional narrow by SELLER_PAYTO / owner wallet
  → agent ID + ranking + feedback merged into response
```

Chain defaults from `X402_NETWORK=eip155:84532`. Override with `ERC8004_AGENT_ID` or `ERC8004_CHAIN_ID` when needed.

---

### Updated: `seller_agent.py`


| Feature               | Details                                                              |
| --------------------- | -------------------------------------------------------------------- |
| `GET /agent/erc8004`  | Full profile JSON — identity, ranking, feedback, verify links        |
| `GET /` health check  | Adds `erc8004` block via `identity_status()` (no external API calls) |
| `Request` injection   | Passes `request.base_url` into discovery for Railway/local URL match   |


---

### Updated: `payments/x402_service.py`

After successful x402 settle (crypto only), calls `trust.feedback_service.submit_payment_feedback_async()` and attaches `receipt.trust` with rank before/after. Payment never fails if feedback fails.

---

### Updated: `payments/receipt_pdf.py`

Crypto PDF receipts include **ERC-8004 Trust** block: feedback tx, score, rank delta, 8004scan indexer status.

---

### Updated: `demo.html`


| Feature              | Details                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| **◎ Profile button** | Seller header — opens profile popover beside **$** wallet               |
| **Four tabs**        | ID · Rank · Feedback · Verify — equal-width 4-column grid               |
| **Rank scores**      | Displayed as `30 / 100` via `profileScore()`                            |
| **ⓘ info icons**     | Click toggles tip open/close; hover preview when not dismissed          |
| **Profile header**   | Title only — "Profile" (no agent name or config source note)            |
| **Trust on receipt** | Wallet bubble + PDF show feedback tx and rank delta after crypto pay    |
| **Profile refresh**  | Open ◎ Profile auto-refetches after crypto payment                      |
| **Build stamp**      | Footer shows `build 2026-06-07j` (or later) — hard refresh after deploy |


---

### Updated: `local.env.example`

Documented optional ERC-8004 overrides:

```bash
# ERC8004_AGENT_ID=6832
# ERC8004_CHAIN_ID=84532
# ERC8004_SERVICE_URL=https://your-app.up.railway.app
SCAN8004_API_KEY=
```

---

## ERC-8004 Architecture

**Attention Agent** on Base Sepolia:

| Field            | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| Agent ID         | `6832`                                                       |
| Chain            | Base Sepolia (`84532`)                                       |
| Service URL      | `https://acp-demo-production.up.railway.app/`              |
| 8004scan profile | `https://testnet.8004scan.io/agents/base-sepolia/6832`       |
| Registration     | IPFS `agentURI` — canonical JSON (name, services, x402 flag) |

[EIP-8004](https://eips.ethereum.org/EIPS/eip-8004) separates **identity** (on-chain NFT) from **reputation** (indexer scores, feedback). It does not replace ACP or payment rails — it answers *who am I paying?*

---

## Owner vs agent wallet vs payTo


| Field                    | Meaning                                                       |
| ------------------------ | ------------------------------------------------------------- |
| **Owner**                | Wallet that controls the identity NFT                         |
| **Agent wallet**         | Wallet ERC-8004 declares for commerce / x402 payTo            |
| **SELLER_PAYTO_ADDRESS** | What the Railway seller actually uses in `commerce/pay`       |

All three can match; in the demo they often differ until `setAgentWallet()` on-chain is aligned with env. Operator task — not shown to buyers in the payment flow.

---

## Bug fixed: 8004scan profile URL uses chain slug

The 8004scan web UI expects a **chain slug**, not a numeric chain ID:

```
✅ https://testnet.8004scan.io/agents/base-sepolia/6832
❌ https://testnet.8004scan.io/agents/84532/6832   → "Agent Not Found"
```

`trust/config.py` → `scan8004_chain_slug()` maps `84532` → `base-sepolia` for verify links.

---

## Bug fixed: IPFS `agentURI` in browser

Raw `ipfs://Qm…` does not open in a browser. `trust/metadata.py` → `agent_uri_browser_url()` probes public gateways (`dweb.link`, Cloudflare, `ipfs.io`) and returns the first working HTTPS URL for the Verify tab.

---

## Environment Variables

Add to `local.env` (and Railway):

```bash
# Required for profile + ranking from 8004scan testnet API
SCAN8004_API_KEY=...

# Chain defaults from X402_NETWORK — usually no override needed
X402_NETWORK=eip155:84532

# Optional — skip auto-discovery
# ERC8004_AGENT_ID=6832
# ERC8004_SERVICE_URL=https://acp-demo-production.up.railway.app
# ERC8004_OWNER_ADDRESS=0x...

# Post-x402 feedback (buyer wallet — must differ from agent owner; needs ETH for gas)
ERC8004_FEEDBACK_ON_PAY=true
# Random 0–100 per payment by default; pin with ERC8004_FEEDBACK_VALUE=95
```

Day 5–6 vars (`BUYER_WALLET_PRIVATE_KEY`, `SELLER_PAYTO_ADDRESS`, `DEMO_SERVER_SIGN`, Stripe keys) stay as-is.

**Reputation Registry (Base Sepolia):** `0x8004B663056A597Dffe9eCcC1965A193B7388713`

**Indexer lag:** 8004scan has no write API. Rank updates come from indexing on-chain `giveFeedback` events — receipt may show `indexerStatus: pending` for up to ~30s.

**Profile locally:** 8004scan registers the **Railway** URL, not `localhost:8002`. For ◎ on local dev, set `ERC8004_SERVICE_URL` to your Railway URL or uncomment `ERC8004_AGENT_ID=6832`.

---

## What to add to Railway

In the Railway project → **Variables**, add:


| Variable           | Notes                                              |
| ------------------ | -------------------------------------------------- |
| `SCAN8004_API_KEY` | 8004scan testnet API key for ranking + discovery   |

Redeploy seller after adding the key. Existing Day 5–6 variables unchanged.

---

## ACP Spec Compliance — Day 7 Status


| ACP Requirement                     | Day 6 | Day 7 |
| ----------------------------------- | ----- | ----- |
| `initialize` handshake              | ✅     | ✅     |
| Session layer                       | ✅     | ✅     |
| `session/prompt` + multi-turn       | ✅     | ✅     |
| Catalog search + agent pick         | ✅     | ✅     |
| `commerce/pay` — crypto (x402)      | ✅     | ✅     |
| `commerce/pay` — fiat (Stripe)      | ✅     | ✅     |
| Payment method selection at runtime | ✅     | ✅     |
| Seller identity endpoint            | ❌     | ✅     |
| ERC-8004 profile in UI              | ❌     | ✅     |
| 8004scan ranking + verify links     | ❌     | ✅     |
| Buyer-side trust check before pay   | ❌     | ❌     |
| Post-payment ERC-8004 feedback      | ❌     | ✅ (crypto) |
| Separate buyer payment service      | ❌     | ❌     |
| SSE streaming                       | ❌     | ❌     |


---

## Production vs Demo Gap — Day 7


| What we built                          | What production would use                               |
| -------------------------------------- | ------------------------------------------------------- |
| Full `/agent/erc8004` on seller        | Public buyer view vs operator-only fields               |
| Profile loaded on demand in UI         | Buyer agent reads profile before `commerce/pay`         |
| Feedback signed on seller (demo)         | Buyer service signs giveFeedback client-side only       |
| Single Railway service                 | Split buyer (:8001) + seller (:8002)                    |
| `DEMO_SERVER_SIGN` on seller           | Buyer signs x402 client-side only                       |


---

## How to Run Locally

```bash
source venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — seller (ACP + x402 + Stripe + ERC-8004)
uvicorn seller_agent:app --host 0.0.0.0 --port 8002 --reload

# Terminal 2 — demo UI
python3 -m http.server 8080
# Open http://localhost:8080/demo.html
```

**Trust flow:** Start → Handshake → click seller **◎** → Profile loads → browse ID / Rank / Feedback / Verify tabs → click ⓘ on any field for context → open 8004scan link from Verify tab.

**Crypto + rank flow:** Day 6 crypto path → after settle, receipt wallet bubble shows **◎ ERC-8004 trust** (feedback tx, rank before → after) → re-open ◎ Profile to see updated Rank tab.

**Hard refresh** after UI changes (`Cmd+Shift+R`). Check build stamp in footer (`build 2026-06-07j` or later).

---

## Where to Start Day 8


| Priority | Task                                      | File                    | Notes                                      |
| -------- | ----------------------------------------- | ----------------------- | ------------------------------------------ |
| 1        | Buyer-side trust check before pay         | `buyer_agent.py`, UI    | Fetch `/agent/erc8004` before `commerce/pay` |
| 2        | Split buyer server on :8001               | `buyer_server.py` (new) | Proxy ACP; buyer owns signing keys         |
| 3        | Public vs operator profile views          | `trust/identity_api.py` | Split sensitive fields from buyer JSON     |
| 4        | SSE payment + session updates             | `seller_agent.py`       | Stream verify/settle steps live in UI      |
| 5        | Fiat post-payment feedback                | `trust/feedback_service.py` | Stripe path reputation (optional)      |


---

## Live Links

- **Frontend:** `demo.html` (Netlify or local `http.server`)
- **Backend:** `https://acp-demo-production.up.railway.app`
- **Health check:** `GET /` → includes `erc8004.configured`, `agentId`, `chainId`
- **Profile API:** `GET /agent/erc8004`
- **8004scan:** [testnet.8004scan.io/agents/base-sepolia/6832](https://testnet.8004scan.io/agents/base-sepolia/6832)
- **Explorer:** [sepolia.basescan.org](https://sepolia.basescan.org)

---

## Quick reference — all README files


| File                               | What it covers                                |
| ---------------------------------- | --------------------------------------------- |
| [README.md](./README.md)           | Project overview + quick start                |
| [Readme_Day1.md](./Readme_Day1.md) | Handshake, commerce/request                   |
| [README_DAY2.md](./README_DAY2.md) | Session layer                                 |
| [README_DAY3.md](./README_DAY3.md) | session/prompt, NLP intent                    |
| [README_DAY4.md](./README_DAY4.md) | Catalog, multi-turn, Claude, agent pick       |
| [README_DAY5.md](./README_DAY5.md) | x402 USDC, wallets, receipt PDF               |
| [README_DAY6.md](./README_DAY6.md) | Fiat via Stripe, dual wallets, payment picker |
| [README_DAY7.md](./README_DAY7.md) | ERC-8004 trust, 8004scan, ◎ profile UI        |

