"""
SELLER AGENT — Port 8002
========================
This is the Seller side of your thesis diagram.
Think: Amazon's Vendor Agent — it exposes products, accepts intents, returns offers.

ACP Flow:
  1. Buyer Agent calls initialize → we shake hands, exchange capabilities
  2. Buyer Agent calls commerce/request → we return a price offer
  3. (Phase 2) Buyer pays → we deliver the goods
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Seller Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Product catalog — what this agent can sell
# --------------------------------------------------------------------------
CATALOG = {
    "air_max_270":      {"price": 150.00, "currency": "USD", "description": "Nike Air Max 270 — Men's Lifestyle Shoe"},
    "air_force_1":      {"price": 110.00, "currency": "USD", "description": "Nike Air Force 1 '07 — Classic Low-Top"},
    "react_infinity_4": {"price": 160.00, "currency": "USD", "description": "Nike React Infinity Run Flyknit 4 — Running Shoe"},
}

# --------------------------------------------------------------------------
# Track which clients have initialized with us
# --------------------------------------------------------------------------
connected_clients = {}


# --------------------------------------------------------------------------
# Single JSON-RPC endpoint — all ACP messages come here
# --------------------------------------------------------------------------
@app.post("/")
async def handle_jsonrpc(request: Request):
    body = await request.json()

    jsonrpc = body.get("jsonrpc")
    method  = body.get("method")
    id      = body.get("id")
    params  = body.get("params", {})

    print(f"\n📨 Received method: '{method}' (id={id})")

    # Route to the right handler
    if method == "initialize":
        return JSONResponse(handle_initialize(id, params))

    elif method == "commerce/request":
        return JSONResponse(handle_commerce_request(id, params))

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not supported by this agent"
            }
        })


# --------------------------------------------------------------------------
# HANDLER 1: initialize
# This is the ACP handshake — client tells us what it can do,
# we tell it what WE can do. No work happens yet.
# --------------------------------------------------------------------------
def handle_initialize(id, params):
    protocol_version = params.get("protocolVersion", 1)
    client_info      = params.get("clientInfo", {})
    client_caps      = params.get("clientCapabilities", {})

    # Store the client so we know who's connected
    client_name = client_info.get("name", "unknown-client")
    connected_clients[client_name] = {
        "protocolVersion": protocol_version,
        "capabilities": client_caps
    }

    print(f"  ✅ Initialized with client: '{client_name}' v{client_info.get('version', '?')}")
    print(f"  Client capabilities: {client_caps}")

    # Respond with OUR capabilities — what this seller agent supports
    return {
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "protocolVersion": 1,               # We agree on version 1
            "agentInfo": {
                "name":    "seller-agent",
                "title":   "Seller Agent (Vendor Side)",
                "version": "1.0.0"
            },
            "agentCapabilities": {
                "commerce": {
                    "canSell":             True,
                    "items":               list(CATALOG.keys()),
                    "acceptedCurrencies":  ["USD"],    # Phase 3 will add USDC
                    "negotiation":         False,      # Fixed prices for now
                },
                "payment": {
                    "stripe": False,   # Phase 2 will enable this
                    "x402":   False,   # Phase 3 will enable this
                },
                "mcpCapabilities": {
                    "http": False,     # Not connected to MCP tools yet
                    "sse":  False,
                }
            },
            "authMethods": []   # No auth required yet
        }
    }


# --------------------------------------------------------------------------
# HANDLER 2: commerce/request
# Buyer sends intent ("I want X, max price Y")
# We check our catalog and return an offer
# --------------------------------------------------------------------------
def handle_commerce_request(id, params):
    item      = params.get("item")
    max_price = params.get("max_price", 0)
    buyer_id  = params.get("buyer_id", "unknown")

    print(f"  🛒 Buyer '{buyer_id}' wants: '{item}' (max budget: ${max_price})")

    # Item doesn't exist in catalog
    if item not in CATALOG:
        return {
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": -32000,
                "message": f"Item '{item}' not in catalog. Available: {list(CATALOG.keys())}"
            }
        }

    product   = CATALOG[item]
    our_price = product["price"]

    # Buyer's budget is too low
    if max_price < our_price:
        return {
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": -32001,
                "message": f"Budget too low. '{item}' costs ${our_price}, you offered ${max_price}"
            }
        }

    # Return a valid offer — buyer now needs to pay to receive goods
    print(f"  ✅ Offer sent: ${our_price} for '{item}'")
    return {
        "jsonrpc": "2.0",
        "id": id,
        "result": {
            "offer": {
                "item":             item,
                "description":      product["description"],
                "price":            our_price,
                "currency":         product["currency"],
                "payment_required": True,       # Payment must happen before delivery
                "status":           "offer_ready",
                "seller_agent":     "seller-agent-v1.0.0"
            }
        }
    }


# --------------------------------------------------------------------------
# Run the server
# --------------------------------------------------------------------------
if __name__ == "__main__":
    print("👟 Nike Seller Agent starting on http://localhost:8002")
    print(f"   Catalog: {list(CATALOG.keys())}\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)