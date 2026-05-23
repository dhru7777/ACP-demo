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
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from session_manager import session_manager
from search import catalog_search   # modular search — swap backend here

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
    return JSONResponse({
        "status":  "ok",
        "agent":   "nike-seller-agent",
        "version": "2.0.0",
        "session": True
    })


# --------------------------------------------------------------------------
# Single JSON-RPC endpoint — all ACP messages arrive here
# --------------------------------------------------------------------------
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
    elif method == "session/prompt":   return JSONResponse(handle_session_prompt(id_, params))
    elif method == "commerce/request": return JSONResponse(handle_commerce_request(id_, params))
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
                # Payment capabilities (Phase 2 will enable stripe)
                "payment": {
                    "stripe": False,
                    "x402":   False,
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
# BUDGET EXTRACTOR — pull max price from natural language.
# In production: this becomes an LLM call: extract_intent(text) → JSON
# Kept as a pure function so it can be replaced without touching the handler.
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

    # Retrieve session context (tracks multi-turn state)
    session  = session_manager.get(session_id)
    ctx      = session.get("context", {})
    turn_num = ctx.get("turn", 1)

    print(f"  Prompt (turn {turn_num}): \"{text[:100]}\"")

    # Record this buyer turn in session history
    session_manager.add_history(session_id, "buyer", "session/prompt",
                                {"text": text, "turn": turn_num})

    # ── TURN 2+: buyer is responding to our clarification question ────────────
    if ctx.get("awaiting_budget"):
        budget = extract_budget(text)

        if budget is None:
            # Still no number — gently ask one more time with a concrete example
            msg = ("I need a specific budget to find the right shoe. "
                   "Try something like '$150' or 'under $200'. What's your limit?")
            session_manager.add_history(session_id, "seller", "session/prompt.clarification",
                                        {"question": msg})
            return {
                "jsonrpc": "2.0", "id": id_,
                "result": {
                    "stopReason":    "needs_clarification",
                    "agentMessage":  msg,
                    "parsedIntent":  {"query": ctx.get("pending_query", ""), "max_price": None},
                    "awaitingBudget": True,
                    "offers":        []
                }
            }

        # Budget received — combine with saved intent and search
        original_query = ctx.get("pending_query", text)
        session_manager.update_context(session_id, {})   # clear state after resolution
        print(f"  Budget resolved: ${budget} | original query: \"{original_query[:60]}\"")
        return _build_offers(id_, session_id, original_query, budget, text)

    # ── TURN 1: check if buyer included a budget ──────────────────────────────
    budget = extract_budget(text)

    if budget is None:
        # No budget — save the intent and ask for it
        session_manager.update_context(session_id, {
            "awaiting_budget": True,
            "pending_query":   text,
            "turn":            2
        })
        question = ("I can help you find the perfect Nike shoe. "
                    "What's your budget for this purchase?")
        session_manager.add_history(session_id, "seller", "session/prompt.clarification",
                                    {"question": question})
        print(f"  No budget detected — asking buyer for budget")
        return {
            "jsonrpc": "2.0", "id": id_,
            "result": {
                "stopReason":    "needs_clarification",
                "agentMessage":  question,
                "parsedIntent":  {"query": text, "max_price": None},
                "awaitingBudget": True,
                "offers":        []
            }
        }

    # Budget was included in the first message — skip clarification
    session_manager.update_context(session_id, {})   # ensure context clean
    return _build_offers(id_, session_id, text, budget, text)


# --------------------------------------------------------------------------
# HELPER: search catalog and build the offer response
# Extracted so both clarification-resolved and direct-budget paths use it.
# --------------------------------------------------------------------------
def _build_offers(id_, session_id: str, query: str, max_price: float, raw_text: str) -> dict:
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
            "offers":       offers
        }
    }


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
        "item":             item,
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
    print(f"  Session support: session/new, session/load, session/resume, session/close\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)
