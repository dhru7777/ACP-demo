"""
SELLER AGENT — Port 8002
========================
Vendor side of the ACP demo.

ACP Flow:
  1. initialize          → handshake, agree capabilities
  2. session/new         → create a session, return sessionId
  3. commerce/request    → buyer sends intent + sessionId, we return offer
  4. session/close       → buyer ends session, we free resources

Session methods supported:
  - session/new          : create a fresh session
  - session/load         : replay history of a previous session
  - session/resume       : reconnect silently (no replay)
  - session/close        : end and free session

Note on session/load in this demo:
  The spec calls for streaming session/update notifications over SSE.
  Since we use plain HTTP, we return the full history in the response body
  instead. Production would use SSE or WebSockets for true streaming replay.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from session_manager import session_manager

app = FastAPI(title="Nike Seller Agent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Product catalog
# --------------------------------------------------------------------------
CATALOG = {
    "air_max_270":      {"price": 150.00, "currency": "USD", "description": "Nike Air Max 270 — Men's Lifestyle Shoe"},
    "air_force_1":      {"price": 110.00, "currency": "USD", "description": "Nike Air Force 1 '07 — Classic Low-Top"},
    "react_infinity_4": {"price": 160.00, "currency": "USD", "description": "Nike React Infinity Run Flyknit 4 — Running Shoe"},
}

# Track initialized clients (from handshake)
connected_clients = {}


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
                # Commerce capabilities
                "commerce": {
                    "canSell":            True,
                    "items":              list(CATALOG.keys()),
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

    if item not in CATALOG:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Item '{item}' not in catalog. Available: {list(CATALOG.keys())}"
            }
        }

    product   = CATALOG[item]
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
    print("Nike Seller Agent v2.0.0 starting on http://localhost:8002")
    print(f"  Catalog: {list(CATALOG.keys())}")
    print(f"  Session support: session/new, session/load, session/resume, session/close\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)
