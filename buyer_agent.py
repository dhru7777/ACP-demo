"""
BUYER AGENT — runs as a script
================================
This is the Buyer side of your thesis diagram.
Think: Personal Agent acting on behalf of a human user.

ACP Flow this agent follows:
  Step 1 → initialize     : handshake with seller, learn capabilities
  Step 2 → commerce/request: send intent (what I want + max price)
  Step 3 → (Phase 2)      : pay → receive goods
"""

import requests
import json

SELLER_URL = "http://localhost:8002"

# --------------------------------------------------------------------------
# Core JSON-RPC sender
# Every message we send follows this exact ACP format
# --------------------------------------------------------------------------
def send_jsonrpc(method: str, params: dict, request_id: int = 1):
    payload = {
        "jsonrpc": "2.0",       # Always this version
        "id":      request_id,  # So we can match requests to responses
        "method":  method,      # What we want the agent to do
        "params":  params       # The data for that method
    }

    print(f"\n📤 Sending → method: '{method}'")
    print(f"   Payload: {json.dumps(params, indent=6)}")

    response = requests.post(SELLER_URL + "/", json=payload)
    result   = response.json()

    print(f"📥 Response received:")
    print(f"   {json.dumps(result, indent=6)}")

    return result


# --------------------------------------------------------------------------
# STEP 1: Initialize
# Before ANY commerce, we must shake hands.
# We tell the seller: who we are + what we support.
# Seller tells us: who they are + what THEY support.
# --------------------------------------------------------------------------
def initialize():
    print("\n" + "="*60)
    print("STEP 1: INITIALIZATION (ACP Handshake)")
    print("="*60)

    response = send_jsonrpc(
        method     = "initialize",
        params     = {
            "protocolVersion": 2,       # The ACP version we speak
            "clientInfo": {
                "name":    "buyer-agent",
                "title":   "Buyer Agent (Personal Side)",
                "version": "2.0.0"
            },
            "clientCapabilities": {
                "payment": {
                    "stripe": False,    # Phase 2 will enable
                    "x402":   False,    # Phase 3 will enable
                },
                "commerce": {
                    "canBuy":             True,
                    "preferredCurrencies": ["USD"]
                }
            }
        },
        request_id = 0
    )

    if "error" in response:
        print(f"\n❌ Initialization failed: {response['error']['message']}")
        return None

    result     = response["result"]
    agent_info = result["agentInfo"]
    caps       = result["agentCapabilities"]

    print(f"\n✅ Handshake complete!")
    print(f"   Connected to : {agent_info['title']} v{agent_info['version']}")
    print(f"   Can sell     : {caps['commerce']['items']}")
    print(f"   Currencies   : {caps['commerce']['acceptedCurrencies']}")
    print(f"   Stripe ready : {caps['payment']['stripe']}")
    print(f"   x402 ready   : {caps['payment']['x402']}")

    return caps  # Return seller capabilities so we can use them next


# --------------------------------------------------------------------------
# STEP 2: Request an item
# Now that we've initialized, we send our buying intent.
# "I want X, and I'll pay up to Y"
# --------------------------------------------------------------------------
def request_item(item: str, max_price: float, seller_capabilities: dict):
    print("\n" + "="*60)
    print("STEP 2: COMMERCE REQUEST (Sending Intent)")
    print("="*60)

    # Check if seller even has this item before requesting
    available = seller_capabilities["commerce"]["items"]
    if item not in available:
        print(f"\n❌ Item '{item}' not available. Seller has: {available}")
        return None

    response = send_jsonrpc(
        method     = "commerce/request",
        params     = {
            "item":      item,
            "max_price": max_price,
            "buyer_id":  "buyer-agent-001"
        },
        request_id = 1
    )

    if "error" in response:
        print(f"\n❌ Request failed: {response['error']['message']}")
        return None

    offer = response["result"]["offer"]
    print(f"\n✅ Offer received!")
    print(f"   Item        : {offer['item']}")
    print(f"   Description : {offer['description']}")
    print(f"   Price       : ${offer['price']} {offer['currency']}")
    print(f"   Status      : {offer['status']}")

    return offer


# --------------------------------------------------------------------------
# STEP 3: Payment placeholder
# Phase 1 ends here. Phase 2 will replace this with real Stripe.
# --------------------------------------------------------------------------
def pay(offer: dict):
    print("\n" + "="*60)
    print("STEP 3: PAYMENT (Phase 2 — not yet implemented)")
    print("="*60)
    print(f"\n Would pay ${offer['price']} {offer['currency']} for '{offer['item']}'")
    print(f"   → Stripe integration comes in Phase 2")
    print(f"   → x402 crypto payment comes in Phase 3")


# --------------------------------------------------------------------------
# Main flow — runs all steps in sequence
# --------------------------------------------------------------------------
def run():
    print("👟 BUYER AGENT STARTING")
    print("   Mapping to thesis: Personal Agent on Buyer Side")
    print("   Connecting to Seller Agent at:", SELLER_URL)

    # Step 1: Handshake
    seller_capabilities = initialize()
    if not seller_capabilities:
        return

    # Step 2: Send intent
    offer = request_item(
        item               = "air_max_270",
        max_price          = 200.00,
        seller_capabilities = seller_capabilities
    )
    if not offer:
        return

    # Step 3: Pay (placeholder)
    pay(offer)

    print("\n" + "="*60)
    print(" PHASE 1 COMPLETE — Two agents communicated via ACP!")
    print("   Next: Add Stripe payment in Phase 2")
    print("="*60)


if __name__ == "__main__":
    run()