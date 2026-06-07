"""
SELLER AGENT — Port 8002
========================
Vendor side of the ACP demo.

ACP Flow:
  1. initialize          → handshake, agree capabilities
  2. session/new         → create a session, return sessionId
  3. session/prompt      → buyer sends NL intent, we search & return top offers
  4. session/close       → buyer ends session, we free resources

Session methods supported:
  - session/new          : create a fresh session
  - session/load         : replay history of a previous session
  - session/resume       : reconnect silently (no replay)
  - session/close        : end and free session

Search layer (search.py):
  - Current: in-memory keyword + difflib fuzzy matching
  - Future:  swap CatalogSearch for PineconeSearch / MCPSearch — no other changes needed

Note on session/load in this demo:
  The spec calls for streaming session/update notifications over SSE.
  Since we use plain HTTP, we return the full history in the response body
  instead. Production would use SSE or WebSockets for true streaming replay.
"""

import re
import os
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from session_manager import session_manager
from search import catalog_search   # modular search — swap backend here
from payments.commerce_pay import handle_commerce_pay
from payments.wallets import AgentRole, wallet_status
from payments.config import get_stripe_seller_account_id
from payments.wallet_api import (
    build_fiat_seller_wallet_response,
    build_fiat_wallet_response,
    build_wallet_response,
)


def _stripe_connect_enabled() -> bool:
    return get_stripe_seller_account_id() is not None
from payments import x402_service
from payments.chain import fetch_tx_fee_eth
from payments.receipt_pdf import build_receipt_pdf
from trust.identity_api import build_agent_identity_response, identity_status
# --------------------------------------------------------------------------
# Anthropic client — used for natural language intent parsing.
# Falls back silently to regex if the key is missing or the call fails.
# Key: set ANTHROPIC_API_KEY in Railway env vars (or local.env locally).
# --------------------------------------------------------------------------
_anthropic_client = None
try:
    import anthropic as _anthropic_lib
    _api_key = (os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("Intent_Parsing_Anthropic"))
    if _api_key:
        _anthropic_client = _anthropic_lib.Anthropic(api_key=_api_key)
        print("  [Claude] Anthropic client ready — using LLM for intent parsing")
    else:
        print("  [Claude] No API key found — falling back to regex intent parser")
except ImportError:
    print("  [Claude] anthropic package not installed — falling back to regex")

app = FastAPI(title="Nike Seller Agent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracks connected clients (from handshake)
connected_clients: dict = {}


# --------------------------------------------------------------------------
# Health check — Railway pings GET / to verify the container is alive
# --------------------------------------------------------------------------
@app.get("/")
async def health():
    summary = catalog_search.summary()
    return JSONResponse({
        "status":        "ok",
        "agent":           "nike-seller-agent",
        "version":         "2.0.0",
        "session":         True,
        "catalogCount":    catalog_search.count(),
        "catalogCategories": list(summary["categories"].keys()),
        "wallets": {
            "buyer":  wallet_status(AgentRole.BUYER),
            "seller": wallet_status(AgentRole.SELLER),
        },
        "erc8004": identity_status(),
    })


# --------------------------------------------------------------------------
# Wallet info — live Base Sepolia balances + Basescan history (no private keys)
# --------------------------------------------------------------------------
@app.get("/wallet/buyer")
async def wallet_buyer():
    try:
        return JSONResponse(build_wallet_response(AgentRole.BUYER))
    except Exception as e:
        return JSONResponse({"role": "buyer", "error": str(e)}, status_code=503)


@app.get("/wallet/buyer/fiat")
async def wallet_buyer_fiat():
    try:
        return JSONResponse(await build_fiat_wallet_response())
    except Exception as e:
        return JSONResponse({"role": "buyer", "provider": "stripe", "error": str(e)}, status_code=503)


@app.get("/wallet/seller/fiat")
async def wallet_seller_fiat():
    try:
        return JSONResponse(await build_fiat_seller_wallet_response())
    except Exception as e:
        return JSONResponse({"role": "seller", "provider": "stripe", "error": str(e)}, status_code=503)


@app.get("/wallet/seller")
async def wallet_seller():
    try:
        return JSONResponse(build_wallet_response(AgentRole.SELLER))
    except Exception as e:
        return JSONResponse({"role": "seller", "error": str(e)}, status_code=503)


# --------------------------------------------------------------------------
# ERC-8004 agent identity — live 8004scan + on-chain verification links
# --------------------------------------------------------------------------
@app.get("/agent/erc8004")
async def agent_erc8004(request: Request):
    try:
        service_url = str(request.base_url).rstrip("/")
        data = await asyncio.to_thread(build_agent_identity_response, service_url)
        if not data.get("configured"):
            return JSONResponse(data, status_code=503)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"configured": False, "error": str(e)}, status_code=503)


# --------------------------------------------------------------------------
# Single JSON-RPC endpoint — all ACP messages arrive here
# --------------------------------------------------------------------------
@app.get("/demo/tx-fee")
async def demo_tx_fee(tx: str = ""):
    """Settlement tx fee (facilitator gas) — polled after settle if receipt not ready yet."""
    if not tx or not tx.startswith("0x"):
        return JSONResponse({"error": "tx query param required"}, status_code=400)
    gas = await asyncio.to_thread(fetch_tx_fee_eth, tx)
    if not gas:
        return JSONResponse({"error": "fee unavailable"}, status_code=404)
    return JSONResponse(gas)


async def _build_receipt_pdf_response(body: dict) -> Response:
    try:
        pdf_bytes = await asyncio.to_thread(build_receipt_pdf, body)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    offer_id = (body.get("offer") or {}).get("id") or "payment"
    filename = f"acp-receipt-{offer_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/demo/receipt.pdf")
@app.post("/demo/receipt")
async def demo_receipt_pdf(request: Request):
    """Downloadable PDF receipt for demo UI."""
    body = await request.json()
    return await _build_receipt_pdf_response(body)


@app.post("/demo/erc8004/feedback")
async def demo_erc8004_feedback(request: Request):
    """Buyer agent submits ERC-8004 giveFeedback after payment (manual demo step)."""
    from trust.feedback_service import submit_agent_feedback_async

    body = await request.json()
    score = body.get("score")
    if score is None:
        return JSONResponse({"error": "score required (0-100)"}, status_code=400)
    try:
        score_int = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        return JSONResponse({"error": "invalid score"}, status_code=400)

    payment = body.get("payment") or body.get("receipt") or {}
    result = await submit_agent_feedback_async(
        score=score_int,
        comment=str(body.get("comment") or ""),
        stars=body.get("stars"),
        payment_receipt=payment if isinstance(payment, dict) else None,
    )
    session_id = body.get("sessionId")
    if session_id and session_manager.exists(session_id):
        session_manager.add_history(session_id, "buyer", "erc8004/feedback", body)
        session_manager.add_history(session_id, "seller", "erc8004/feedback.result", result)
    return JSONResponse(result)


@app.post("/demo/x402/execute")
async def demo_x402_execute(request: Request):
    """Demo UI: quote + sign + settle in one call when DEMO_SERVER_SIGN=true."""
    body = await request.json()
    session_id = body.get("sessionId")
    offer = body.get("offer") or {}
    offer_id = body.get("offerId") or offer.get("id")
    if not offer_id:
        return JSONResponse({"error": "offerId required"}, status_code=400)
    product = catalog_search.get(offer_id)
    if product is None:
        return JSONResponse({"error": f"Unknown offer: {offer_id}"}, status_code=404)
    catalog_usd = float(offer.get("price") or product["price"])
    offer_name = offer.get("name") or product.get("name", "")
    try:
        result = await x402_service.execute_payment(catalog_usd, offer_id, offer_name)
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.receipt", result)
            sess = session_manager.get(session_id)
            if sess is not None:
                paid = sess.setdefault("context", {}).setdefault("paidOffers", {})
                paid[offer_id] = result
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/demo/stripe/verify-connect")
async def demo_stripe_verify_connect():
    """Diagnose whether STRIPE_SELLER_ACCOUNT_ID belongs to this platform key."""
    import stripe as _stripe_lib
    from payments.config import get_stripe_secret_key, get_stripe_seller_account_id
    key = get_stripe_secret_key()
    seller_id = get_stripe_seller_account_id()
    if not key:
        return JSONResponse({"ok": False, "error": "STRIPE_SECRET_KEY not set"}, status_code=400)
    _stripe_lib.api_key = key
    if not seller_id:
        return JSONResponse({"ok": False, "error": "STRIPE_SELLER_ACCOUNT_ID not set"}, status_code=400)
    try:
        acct = await asyncio.to_thread(lambda: _stripe_lib.Account.retrieve(seller_id))
        return JSONResponse({
            "ok": True,
            "accountId": acct.id,
            "type": acct.type,
            "chargesEnabled": acct.charges_enabled,
            "payoutsEnabled": acct.payouts_enabled,
            "country": acct.country,
        })
    except Exception as e:
        return JSONResponse({"ok": False, "accountId": seller_id, "error": str(e)}, status_code=400)


@app.post("/demo/stripe/execute")
async def demo_stripe_execute(request: Request):
    """Demo UI: charge test card via Stripe in one call."""
    from payments import stripe_service

    body = await request.json()
    session_id = body.get("sessionId")
    offer = body.get("offer") or {}
    offer_id = body.get("offerId") or offer.get("id")
    if not offer_id:
        return JSONResponse({"error": "offerId required"}, status_code=400)
    product = catalog_search.get(offer_id)
    if product is None:
        return JSONResponse({"error": f"Unknown offer: {offer_id}"}, status_code=404)
    catalog_usd = float(offer.get("price") or product["price"])
    offer_name = offer.get("name") or product.get("name", "")
    try:
        result = await stripe_service.execute_payment(catalog_usd, offer_id, offer_name)
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay.fiat", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.fiat.receipt", result)
            sess = session_manager.get(session_id)
            if sess is not None:
                paid = sess.setdefault("context", {}).setdefault("paidOffers", {})
                paid[offer_id] = result
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/")
async def handle_jsonrpc(request: Request):
    body   = await request.json()
    method = body.get("method")
    id_    = body.get("id")
    params = body.get("params", {})

    print(f"\n  Received: '{method}' (id={id_})")

    if   method == "initialize":       return JSONResponse(handle_initialize(id_, params))
    elif method == "session/new":      return JSONResponse(handle_session_new(id_, params))
    elif method == "session/load":     return JSONResponse(handle_session_load(id_, params))
    elif method == "session/resume":   return JSONResponse(handle_session_resume(id_, params))
    elif method == "session/close":    return JSONResponse(handle_session_close(id_, params))
    elif method == "session/cancel":   return JSONResponse(handle_session_cancel(id_, params))
    elif method == "session/prompt":   return JSONResponse(handle_session_prompt(id_, params))
    elif method == "commerce/request": return JSONResponse(handle_commerce_request(id_, params))
    elif method == "commerce/pay":     return JSONResponse(await _handle_commerce_pay_rpc(id_, params))
    else:
        return JSONResponse({
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32601, "message": f"Method '{method}' not supported"}
        })


# --------------------------------------------------------------------------
# HANDLER: initialize
# Handshake — we now declare full session capabilities so buyer knows
# what session methods it's allowed to call.
# --------------------------------------------------------------------------
def handle_initialize(id_, params):
    client_info = params.get("clientInfo", {})
    client_caps = params.get("clientCapabilities", {})
    client_name = client_info.get("name", "unknown-client")

    connected_clients[client_name] = {
        "protocolVersion": params.get("protocolVersion", 1),
        "capabilities": client_caps
    }

    print(f"  Initialized with: '{client_name}' v{client_info.get('version', '?')}")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {
            "protocolVersion": 1,
            "agentInfo": {
                "name":    "nike-seller-agent",
                "title":   "Nike Seller Agent",
                "version": "2.0.0"
            },
            "agentCapabilities": {
                # Session capabilities — buyer MUST check these before calling session methods
                "loadSession": True,               # supports session/load
                "sessionCapabilities": {
                    "resume": {},                  # supports session/resume
                    "close":  {}                   # supports session/close
                },
                # Commerce capabilities — expose count/categories only, not full catalog
                "commerce": {
                    "canSell":            True,
                    "itemCount":          catalog_search.count(),
                    "categories":         list(catalog_search.summary()["categories"].keys()),
                    "acceptedCurrencies": ["USD"],
                    "negotiation":        False,
                },
                "payment": {
                    "stripe":        True,
                    "stripeConnect": bool(_stripe_connect_enabled()),
                    "x402":          True,
                },
                # MCP tool connections (Phase 3+)
                "mcpCapabilities": {
                    "http": False,
                    "sse":  False,
                }
            },
            "authMethods": []
        }
    }


# --------------------------------------------------------------------------
# HANDLER: session/new
# Buyer creates a new session after a successful handshake.
# We generate a unique sessionId and store the context.
# --------------------------------------------------------------------------
def handle_session_new(id_, params):
    buyer_id = params.get("buyerId", "unknown-buyer")
    cwd      = params.get("cwd", "/")

    session_id = session_manager.create(buyer_id=buyer_id, cwd=cwd)

    print(f"  Session created: {session_id} | buyer: {buyer_id} | cwd: {cwd}")
    print(f"  Active sessions: {len(session_manager.list_all())}")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {
            "sessionId": session_id
        }
    }


# --------------------------------------------------------------------------
# HANDLER: session/load
# Buyer wants to reload a previous session and see its history.
#
# Spec: stream history as session/update notifications (SSE).
# Demo simplification: return history inline in the response body.
# --------------------------------------------------------------------------
def handle_session_load(id_, params):
    session_id = params.get("sessionId")

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' not found. Create a new one with session/new."
            }
        }

    session = session_manager.get(session_id)
    history = session["history"]

    print(f"  Loading session: {session_id} | {len(history)} history entries")

    # In production: stream each entry as a session/update notification via SSE.
    # In this demo: return history inline so the buyer can display it.
    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {
            "sessionId": session_id,
            "buyerId":   session["buyerId"],
            "cwd":       session["cwd"],
            "createdAt": session["createdAt"],
            "history":   history       # Full replay — production would stream these
        }
    }


# --------------------------------------------------------------------------
# HANDLER: session/resume
# Silent reconnect — no history replay, just confirm session is ready.
# --------------------------------------------------------------------------
def handle_session_resume(id_, params):
    session_id = params.get("sessionId")

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' not found or expired."
            }
        }

    session = session_manager.get(session_id)
    print(f"  Session resumed: {session_id} | buyer: {session['buyerId']}")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {}   # Spec: empty result on success
    }


# --------------------------------------------------------------------------
# HANDLER: session/cancel
# Buyer aborts in-flight work (Claude call, catalog search) but keeps the
# session open. The buyer can send a new session/prompt immediately after.
# Spec: all Agents MUST support session/cancel as a baseline session method.
# --------------------------------------------------------------------------
def handle_session_cancel(id_, params):
    session_id = params.get("sessionId")

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' does not exist or is not active."
            }
        }

    session_manager.cancel(session_id)
    session_manager.add_history(session_id, "buyer", "session/cancel", {})

    print(f"  Session cancel: {session_id} — in-flight work stopped, session still active")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {}
    }


# --------------------------------------------------------------------------
# HANDLER: session/close
# Buyer ends the session. We free resources (remove from memory).
# Spec: MUST also cancel any ongoing work (none in our demo).
# --------------------------------------------------------------------------
def handle_session_close(id_, params):
    session_id = params.get("sessionId")

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' does not exist or is not active."
            }
        }

    session_manager.close(session_id)
    print(f"  Session closed: {session_id}")
    print(f"  Active sessions remaining: {len(session_manager.list_all())}")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {}   # Spec: empty result on success
    }


# --------------------------------------------------------------------------
# CLAUDE INTENT PARSER
# Uses Claude to understand the buyer's message and decide:
#   - What shoe are they looking for? (intent)
#   - Did they mention a budget? (max_price)
#   - Do we need to ask back? (needs_clarification)
#   - What should the seller say? (response_message)
#
# If Claude is unavailable → falls back to extract_budget() + hardcoded text.
# Architecture: Claude handles language, Python/difflib handles catalog search.
# --------------------------------------------------------------------------
_CLAUDE_SYSTEM = """You are a friendly Nike shoe store agent helping buyers find the right shoe.

Catalog: 100 Nike shoes. Categories: running, lifestyle, training, basketball, trail, soccer, golf, sandals.
Price range: $18 (slides) to $285 (elite soccer boots). Most popular range: $65-$200.

Parse the buyer's message and respond ONLY with a single valid JSON object — no markdown, no code fences, no extra text:
{"intent": "brief description of what they want", "max_price": null or a number, "needs_clarification": true or false, "response_message": "your short natural reply"}

Rules:
- If ANY budget is mentioned (e.g. '$150', 'under 200', 'around a hundred', 'budget is 120'): set max_price to that number AND set needs_clarification=false
- If NO budget is mentioned at all: set max_price=null AND set needs_clarification=true, ask for budget in response_message
- If buyer is just giving you a budget number (turn 2 reply like 'my budget is $150'): set needs_clarification=false, intent can be empty string
- Keep response_message short (1 sentence), conversational, not robotic
- IMPORTANT: respond with raw JSON only — no ```json fences, no explanation"""


def claude_parse_intent(text: str, history: list) -> dict:
    """
    Call Claude to parse buyer intent. Returns a dict with:
      intent, max_price, needs_clarification, response_message, used_claude (bool)

    Falls back to regex if Claude is unavailable or errors.
    """
    if _anthropic_client is None:
        return _regex_fallback(text)

    # Build conversation context from last 4 session turns
    messages = []
    for entry in history[-4:]:
        role    = entry.get("role", "")
        content = entry.get("content", {})
        if role == "buyer" and "text" in content:
            messages.append({"role": "user", "content": content["text"]})
        elif role == "seller":
            q = content.get("question") or content.get("message")
            if q:
                messages.append({"role": "assistant", "content": q})

    messages.append({"role": "user", "content": text})

    try:
        response = _anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=250,
            system=_CLAUDE_SYSTEM,
            messages=messages
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if Claude wraps the JSON (e.g. ```json {...} ```)
        if raw.startswith("```"):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw.strip())

        # Fallback: extract the JSON object even if there's surrounding text
        if not raw.startswith("{"):
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            raw = m.group(0) if m else raw

        parsed = json.loads(raw)
        parsed["used_claude"] = True
        parsed = _apply_regex_budget_override(text, parsed)
        print(f"  [Claude] intent='{parsed.get('intent','')[:50]}' "
              f"max_price={parsed.get('max_price')} "
              f"needs_clarification={parsed.get('needs_clarification')}")
        return parsed
    except Exception as e:
        print(f"  [Claude] Error: {e} — falling back to regex")
        return _regex_fallback(text)


def _apply_regex_budget_override(text: str, parsed: dict) -> dict:
    """If the message contains a dollar amount, use it (Claude sometimes omits max_price)."""
    budget = extract_budget(text)
    if budget is not None:
        parsed["max_price"] = budget
        parsed["needs_clarification"] = False
    return parsed


def _regex_fallback(text: str) -> dict:
    """Pure regex fallback when Claude is unavailable."""
    budget = extract_budget(text)
    return {
        "intent":             text,
        "max_price":          budget,
        "needs_clarification": budget is None,
        "response_message":   (
            "I can help you find the perfect Nike shoe. What's your budget for this purchase?"
            if budget is None
            else f"Got it — searching for options within ${budget:.0f} for you now."
        ),
        "used_claude":        False
    }


# --------------------------------------------------------------------------
# BUDGET EXTRACTOR — pull max price from natural language.
# Used by the regex fallback path and as a standalone utility.
# --------------------------------------------------------------------------
def extract_budget(text: str) -> float | None:
    """
    Extract buyer's budget ceiling from a natural-language string.
    Returns None if no budget is mentioned (search will include all prices).

    Examples matched:
      "$200", "$ 200", "max $150", "budget of 200", "under 300", "250 dollars"
    """
    t = text.lower()
    patterns = [
        r'\$\s*(\d+(?:\.\d+)?)',               # $200 or $ 200
        r'budget\s+(?:of\s+)?(\d+(?:\.\d+)?)', # budget of 200
        r'under\s+\$?\s*(\d+(?:\.\d+)?)',       # under $200
        r'at\s+\$?\s*(\d+(?:\.\d+)?)',           # at 250 dollars
        r'max\s+\$?\s*(\d+(?:\.\d+)?)',         # max $200
        r'(\d+(?:\.\d+)?)\s*dollars?',          # 200 dollars
        r'spend\s+(?:up\s+to\s+)?\$?\s*(\d+)', # spend up to $200
    ]
    for pattern in patterns:
        m = re.search(pattern, t)
        if m:
            return float(m.group(1))
    return None


# --------------------------------------------------------------------------
# HANDLER: session/prompt  —  MULTI-TURN CONVERSATION
#
# The buyer agent sends a natural-language message. We respond differently
# depending on conversation state stored in the session context:
#
#   Turn 1 (no budget in message):
#     → Save the intent in session context
#     → Return stopReason: "needs_clarification" + ask for budget
#     → Client must send another session/prompt with the budget
#
#   Turn 2 (budget provided):
#     → Combine stored intent + new budget signal
#     → Search catalog, return top 3 offers
#     → Clear session context (conversation complete)
#
#   Turn 1 (budget already in message):
#     → Skip clarification, search immediately
#
# Why multi-turn?
#   The session keeps context between turns — the seller remembers what the
#   buyer asked on turn 1 so it doesn't ask again.  This is the core value
#   of session/prompt over stateless HTTP.
#
# Swap guide: replace catalog_search in search.py with a Pinecone/MCP
# backend — this handler stays identical.
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
def _cancelled_prompt_response(id_, session_id: str) -> dict:
    """Return when session/cancel interrupted this prompt turn."""
    session_manager.add_history(session_id, "seller", "session/prompt.cancelled", {})
    return {
        "jsonrpc": "2.0", "id": id_,
        "result": {
            "stopReason":   "cancelled",
            "agentMessage": "Turn cancelled — session still active.",
            "offers":       []
        }
    }


def handle_session_prompt(id_, params):
    session_id = params.get("sessionId")
    prompt     = params.get("prompt", [])

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32000, "message": "Valid sessionId required."}
        }

    # Extract plain text from ACP content blocks
    text = " ".join(
        block.get("text", "")
        for block in prompt
        if block.get("type") == "text"
    ).strip()

    if not text:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32000, "message": "Empty prompt — send a text message."}
        }

    session_manager.clear_cancelled(session_id)
    session_manager.start_processing(session_id)

    try:
        # Retrieve session context (tracks multi-turn state)
        session  = session_manager.get(session_id)
        ctx      = session.get("context", {})
        turn_num = ctx.get("turn", 1)
        history  = session.get("history", [])

        print(f"  Prompt (turn {turn_num}): \"{text[:100]}\"")

        # Record this buyer turn in session history
        session_manager.add_history(session_id, "buyer", "session/prompt",
                                    {"text": text, "turn": turn_num})

        if session_manager.is_cancelled(session_id):
            return _cancelled_prompt_response(id_, session_id)

        # ── TURN 2+: buyer is responding to our clarification question ────────────
        if ctx.get("awaiting_budget"):
            parsed   = claude_parse_intent(text, history)
            if session_manager.is_cancelled(session_id):
                return _cancelled_prompt_response(id_, session_id)

            budget   = parsed.get("max_price")
            used_llm = parsed.get("used_claude", False)

            if budget is None:
                msg = parsed.get("response_message",
                                 "I still need a specific amount to search for you. "
                                 "Try something like '$150' or 'under $200'.")
                session_manager.add_history(session_id, "seller", "session/prompt.clarification",
                                            {"question": msg})
                return {
                    "jsonrpc": "2.0", "id": id_,
                    "result": {
                        "stopReason":    "needs_clarification",
                        "agentMessage":  msg,
                        "parsedIntent":  {"query": ctx.get("pending_query", ""), "max_price": None},
                        "awaitingBudget": True,
                        "usedClaude":    used_llm,
                        "offers":        []
                    }
                }

            original_query = ctx.get("pending_query", text)
            session_manager.update_context(session_id, {})
            print(f"  Budget resolved: ${budget} | original: \"{original_query[:60]}\"")
            return _build_offers(id_, session_id, original_query, budget, text,
                                 used_claude=used_llm)

        # ── TURN 1: parse the full message with Claude ────────────────────────────
        parsed   = claude_parse_intent(text, history)
        if session_manager.is_cancelled(session_id):
            return _cancelled_prompt_response(id_, session_id)

        intent   = parsed.get("intent", text)
        budget   = parsed.get("max_price")
        used_llm = parsed.get("used_claude", False)

        if parsed.get("needs_clarification") or budget is None:
            question = parsed.get("response_message",
                                  "I can help you find the perfect Nike shoe. "
                                  "What's your budget for this purchase?")
            session_manager.update_context(session_id, {
                "awaiting_budget": True,
                "pending_query":   intent,
                "turn":            2
            })
            session_manager.add_history(session_id, "seller", "session/prompt.clarification",
                                        {"question": question})
            print(f"  Needs budget — asking: \"{question[:80]}\"")
            return {
                "jsonrpc": "2.0", "id": id_,
                "result": {
                    "stopReason":    "needs_clarification",
                    "agentMessage":  question,
                    "parsedIntent":  {"query": intent, "max_price": None},
                    "awaitingBudget": True,
                    "usedClaude":    used_llm,
                    "offers":        []
                }
            }

        print(f"  Budget in first message: ${budget}")
        session_manager.update_context(session_id, {})
        return _build_offers(id_, session_id, intent, budget, text,
                             used_claude=used_llm)

    finally:
        session_manager.finish_processing(session_id)


# --------------------------------------------------------------------------
# HELPER: search catalog and build the offer response
# Extracted so both clarification-resolved and direct-budget paths use it.
# --------------------------------------------------------------------------
def _build_offers(id_, session_id: str, query: str, max_price: float, raw_text: str,
                  used_claude: bool = False, confirm_msg: str = "") -> dict:
    results = catalog_search.search(query=query, max_price=max_price, top_k=3)
    print(f"  Search '{query[:50]}' (≤${max_price}): {len(results)} result(s)")

    if not results:
        msg = (f"No Nike shoes found for '{query}' within ${max_price}. "
               "Try a higher budget or a different style.")
        session_manager.add_history(session_id, "seller", "session/prompt.response",
                                    {"message": msg})
        return {
            "jsonrpc": "2.0", "id": id_,
            "result": {
                "stopReason":   "end_turn",
                "agentMessage": msg,
                "parsedIntent": {"query": query, "max_price": max_price},
                "usedClaude":   used_claude,
                "offers":       []
            }
        }

    offers = [
        {
            "id":               r["id"],
            "name":             r["name"],
            "description":      r["description"],
            "price":            r["price"],
            "currency":         r["currency"],
            "category":         r["category"],
            "score":            r.get("score", 0),   # intent relevance — buyer agent uses this
            "payment_required": True,
            "status":           "offer_ready",
            "seller_agent":     "nike-seller-agent-v2.0.0"
        }
        for r in results
    ]

    session_manager.add_history(session_id, "seller", "session/prompt.response",
                                {"offers": offers})

    top  = offers[0]
    rest = len(offers) - 1
    if rest > 0:
        msg = (f"Found {len(offers)} matches. "
               f"Best fit: {top['name']} — ${top['price']}. "
               f"({rest} more option{'s' if rest > 1 else ''} included)")
    else:
        msg = f"Found it: {top['name']} — ${top['price']} {top['currency']}. {top['description']}"

    print(f"  Offers: {[o['id'] for o in offers]}")

    return {
        "jsonrpc": "2.0", "id": id_,
        "result": {
            "stopReason":   "end_turn",
            "agentMessage": msg,
            "parsedIntent": {"query": query, "max_price": max_price},
            "usedClaude":   used_claude,
            "offers":       offers
        }
    }


# --------------------------------------------------------------------------
# HANDLER: commerce/pay — x402 USDC settlement (quote or pay+settle)
# --------------------------------------------------------------------------
async def _handle_commerce_pay_rpc(id_, params):
    session_id = params.get("sessionId")
    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32000, "message": "Valid sessionId required."},
        }

    out = await handle_commerce_pay(params, catalog_search.get)
    if "error" in out:
        return {"jsonrpc": "2.0", "id": id_, "error": out["error"]}

    result = out["result"]
    role = "buyer" if params.get("payment") else "seller"
    session_manager.add_history(session_id, role, "commerce/pay", params)
    session_manager.add_history(session_id, "seller", "commerce/pay.response", result)
    if result.get("status") == "paid":
        sess = session_manager.get(session_id)
        if sess is not None:
            paid = sess.setdefault("context", {}).setdefault("paidOffers", {})
            paid[result.get("offerId", "")] = result

    return {"jsonrpc": "2.0", "id": id_, "result": result}


# --------------------------------------------------------------------------
# HANDLER: commerce/request
# Buyer sends intent — now requires a valid sessionId.
# We store the exchange in session history for future replay.
# --------------------------------------------------------------------------
def handle_commerce_request(id_, params):
    session_id = params.get("sessionId")
    item       = params.get("item")
    max_price  = params.get("max_price", 0)
    buyer_id   = params.get("buyer_id", "unknown")

    # Validate session exists
    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": "Valid sessionId required. Call session/new first."
            }
        }

    print(f"  Buyer '{buyer_id}' [session: {session_id}] wants: '{item}' (max: ${max_price})")

    product = catalog_search.get(item)
    if product is None:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Item '{item}' not in catalog. Use session/prompt to discover available items."
            }
        }

    our_price = product["price"]

    if max_price < our_price:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32001,
                "message": f"Budget too low. '{item}' costs ${our_price}, you offered ${max_price}"
            }
        }

    offer = {
        "id":               item,
        "item":             item,
        "name":             product.get("name", item),
        "description":      product["description"],
        "price":            our_price,
        "currency":         product["currency"],
        "payment_required": True,
        "status":           "offer_ready",
        "seller_agent":     "nike-seller-agent-v2.0.0"
    }

    # Store in session history so session/load can replay this exchange
    session_manager.add_history(session_id, "buyer", "commerce/request", {
        "item": item, "max_price": max_price
    })
    session_manager.add_history(session_id, "seller", "commerce/request.response", offer)

    print(f"  Offer sent: ${our_price} for '{item}' | session: {session_id}")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {"offer": offer}
    }


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------
if __name__ == "__main__":
    summary = catalog_search.summary()
    print("Nike Seller Agent v2.0.0 starting on http://localhost:8002")
    print(f"  Catalog: {summary['total_items']} items across {len(summary['categories'])} categories")
    print(f"  Price range: ${summary['price_range']['min']} – ${summary['price_range']['max']}")
    print(f"  Session support: session/new, session/load, session/resume, session/cancel, session/close\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)
