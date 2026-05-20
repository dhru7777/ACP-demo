# ACP Demo — Day 2
## Session Layer Implementation

**Date:** May 20, 2026
**Author:** Dheeraj Maske
**Builds on:** Day 1 — ACP Handshake + Commerce Intent + Offer

---

## What we implemented today

The ACP session layer — the protocol's way of creating a named, persistent conversation
context between two agents. Sessions answer: *"Who is talking, about what, and where did we leave off?"*

---

## ACP Flow — Before vs After

### Day 1 (2 steps)
```
Buyer Agent                          Seller Agent
     │  initialize                        │
     │ ──────────────────────────────────►│
     │  ◄──────── capabilities ───────────│
     │                                    │
     │  commerce/request                  │
     │ ──────────────────────────────────►│
     │  ◄──────── offer: $150.00 ─────────│
```

### Day 2 (4 steps — session layer added)
```
Buyer Agent                          Seller Agent
     │  initialize                        │
     │ ──────────────────────────────────►│
     │  ◄──── capabilities                │
     │        canCreateSession: true       │
     │        sessionMethods: resume,close │
     │                                    │
     │  session/new                        │
     │  buyerId: buyer-agent-v2.0.0       │
     │ ──────────────────────────────────►│
     │  ◄──── sessionId: sess_abc123 ─────│
     │        stored in session_state.json │
     │                                    │
     │  commerce/request                  │
     │  sessionId: sess_abc123            │  ← NEW: session required
     │ ──────────────────────────────────►│
     │  ◄──── offer: $150.00 ─────────────│
     │        logged to session history    │
     │                                    │
     │  session/close                     │
     │ ──────────────────────────────────►│
     │  ◄──── {} (resources freed) ───────│
```

---

## Files Created / Modified

### New: `session_manager.py`
Singleton class that owns all session state on the seller side.

| Method | What it does |
|---|---|
| `create(buyer_id, cwd)` | Generates a UUID sessionId, stores context |
| `exists(session_id)` | Returns True/False — checked before any session operation |
| `get(session_id)` | Returns full session dict including history |
| `close(session_id)` | Removes session and frees memory |
| `add_history(session_id, role, method, content)` | Appends a message to session history for replay |
| `list_all()` | Debug view of all active sessions |

**Storage:** In-memory Python dict. Lost on server restart.
**Production equivalent:** Redis or PostgreSQL with TTL expiry.

---

### Updated: `seller_agent.py`
Four new JSON-RPC handlers added. `commerce/request` now requires a valid `sessionId`.

| New Method | ACP Spec Reference | What it does |
|---|---|---|
| `session/new` | Required by spec | Creates session, returns sessionId |
| `session/load` | `loadSession: true` capability | Replays session history (simplified: inline in response, not SSE stream) |
| `session/resume` | `sessionCapabilities.resume` | Silent reconnect, no history replay |
| `session/close` | `sessionCapabilities.close` | Cancels work, frees session resources |

Updated `initialize` response to declare:
```json
"agentCapabilities": {
  "loadSession": true,
  "sessionCapabilities": {
    "resume": {},
    "close": {}
  }
}
```

---

### Updated: `buyer_agent.py`
Full 4-step client now with session lifecycle management.

| Step | Function | What it does |
|---|---|---|
| 1 | `initialize()` | Handshake — reads `loadSession` and `sessionCapabilities` from seller |
| 2 | `setup_session(seller_caps)` | Checks `session_state.json` → tries `session/load` or `session/resume` → falls back to `session/new` |
| 3 | `request_item(session_id, item, max_price)` | Sends `sessionId` with every commerce request |
| 4 | `close_session(session_id)` | Sends `session/close`, removes `session_state.json` |

**Session persistence logic:**
```
Run buyer_agent.py
  └─ session_state.json exists?
       ├─ YES + seller supports loadSession → session/load (replay history)
       ├─ YES + seller supports resume      → session/resume (silent reconnect)
       └─ NO  (or above failed)             → session/new (fresh start)
```

---

### Updated: `demo.html`
Session is now a visible step in the UI — not hidden protocol detail.

**New flow in the browser (5 clicks):**

| Click | What you see |
|---|---|
| Start | Agents boot |
| Next: Handshake | `initialize` exchange — capabilities bubble now shows `canCreateSession: true` + `sessionMethods` |
| Next: Create Session | `session/new` exchange — both feeds show sessionId being created and stored |
| Next: Send Intent | `commerce/request` — bubble shows `sessionId: sess_...` being forwarded |
| Next: Payment | Phase 2 placeholder |

**Phase dots updated to 5:**
`01 · Handshake → 02 · Session → 03 · Intent → 04 · Offer → 05 · Payment`

---

## ACP Spec Compliance — Day 2 Status

| ACP Requirement | Day 1 | Day 2 |
|---|---|---|
| `initialize` handshake | ✅ | ✅ |
| `session/new` | ❌ | ✅ |
| `session/load` (with history replay) | ❌ | ✅ (simplified — inline, not SSE stream) |
| `session/resume` | ❌ | ✅ |
| `session/close` | ❌ | ✅ |
| `loadSession` in agentCapabilities | ❌ | ✅ |
| `sessionCapabilities` in agentCapabilities | ❌ | ✅ |
| `commerce/request` requires sessionId | ❌ | ✅ |
| Session history for replay | ❌ | ✅ |
| Session persistence across buyer runs | ❌ | ✅ (via `session_state.json`) |
| SSE streaming for `session/load` replay | ❌ | ❌ (HTTP demo limitation — Phase 3) |
| Payment execution | ❌ | ❌ (Phase 2) |

---

## Known Simplification vs Real ACP

The spec says `session/load` should stream history as `session/update` **notifications** (server-sent events) before responding. Our demo returns history inline in the HTTP response body instead.

This is a deliberate demo simplification. In production, you would use SSE or WebSockets for true streaming replay.

---

## How to Run Locally

```bash
# Terminal 1
source venv/bin/activate
uvicorn seller_agent:app --port 8002

# Terminal 2
source venv/bin/activate
python3 buyer_agent.py

# Run it again — second run will attempt session/load
python3 buyer_agent.py
```

**Note:** Remove the `close_session()` call in `buyer_agent.py` `run()` function to keep the session alive between runs and observe session/load working on the second run.

---

## Where to Start Day 3

| Priority | Task | File |
|---|---|---|
| 1 | Stripe payment execution — `commerce/pay` method | `seller_agent.py` |
| 2 | `pay()` function in buyer — real payment call instead of placeholder | `buyer_agent.py` |
| 3 | Payment visible in `demo.html` Step 4 — not just a placeholder | `demo.html` |
| 4 | Version enforcement — reject `protocolVersion != 1` in `initialize` | `seller_agent.py` |
| 5 | SSE streaming for `session/load` replay (replaces inline return) | `seller_agent.py` |

---

## Live Links

- **Frontend:** Netlify (static `demo.html`)
- **Backend:** `https://acp-demo-production.up.railway.app` — requires redeploy to pick up `session_manager.py`
