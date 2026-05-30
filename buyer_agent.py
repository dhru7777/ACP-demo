"""
BUYER AGENT
===========
Client side of the ACP demo. Simulates a buyer purchasing a Nike shoe
from the seller agent using the Agent Client Protocol (ACP).

Full ACP flow:
  1. initialize        — handshake, get seller capabilities
  2. session/new       — create (or reload) a session
     └─ session/load   — if a saved sessionId exists and seller supports it
  3. commerce/request  — send item + max_price, receive offer
  4. session/close     — end the session, free seller resources

Session persistence:
  sessionId is saved in session_state.json so the buyer can reload the
  same session across multiple runs (simulating a real persistent client).
"""
from payments.wallets import AgentRole, wallet_status
import requests
import json
import os
import sys

SELLER_URL       = "http://localhost:8002"
SESSION_FILE     = "session_state.json"
REQUEST_ID       = 0   # incrementing counter for JSON-RPC ids


def next_id() -> int:
    global REQUEST_ID
    REQUEST_ID += 1
    return REQUEST_ID


def post(method: str, params: dict) -> dict:
    """Send one JSON-RPC message to the seller and return the parsed response."""
    payload = {
        "jsonrpc": "2.0",
        "id":      next_id(),
        "method":  method,
        "params":  params
    }
    resp = requests.post(SELLER_URL, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------
# SESSION FILE HELPERS
# --------------------------------------------------------------------------
def load_saved_session_id() -> str | None:
    """Read the last sessionId we saved to disk."""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
                return data.get("sessionId")
        except Exception:
            return None
    return None


def save_session_id(session_id: str):
    """Persist sessionId to disk so we can resume it next run."""
    with open(SESSION_FILE, "w") as f:
        json.dump({"sessionId": session_id}, f, indent=2)
    print(f"  Session saved to {SESSION_FILE}")


def clear_saved_session():
    """Remove persisted session after a clean close."""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        print(f"  Session file removed — next run starts fresh")


# --------------------------------------------------------------------------
# STEP 1: INITIALIZE
# --------------------------------------------------------------------------
def initialize() -> dict:
    """
    Handshake — buyer announces itself and its capabilities.
    Seller responds with its own capabilities (including session support).
    We do NOT reveal budget here; only what's needed for protocol agreement.
    """
    print("\n[ STEP 1 ] INITIALIZE — Handshake")
    print("  Sending: initialize")

    resp = post("initialize", {
        "protocolVersion": 1,
        "clientInfo": {
            "name":    "buyer-agent",
            "title":   "Nike Buyer Agent",
            "version": "2.0.0"
        },
        "clientCapabilities": {
            "fs":       {"readTextFile": True, "writeTextFile": False},
            "terminal": False
        }
    })

    if "error" in resp:
        print(f"  ERROR: {resp['error']['message']}")
        sys.exit(1)

    result = resp["result"]
    seller_caps = result.get("agentCapabilities", {})

    seller_info = result.get("agentInfo", {})
    agreed_version = result.get("protocolVersion")

    print(f"  Agreed protocol version: {agreed_version}")
    print(f"  Seller: {seller_info.get('title', '?')} v{seller_info.get('version', '?')}")
    print(f"  Seller loadSession support: {seller_caps.get('loadSession', False)}")
    print(f"  Seller session capabilities: {list(seller_caps.get('sessionCapabilities', {}).keys())}")

    catalog = seller_caps.get("commerce", {}).get("items", [])
    print(f"  Catalog: {', '.join(catalog)}")
    print(f"  HANDSHAKE COMPLETE")
    return seller_caps


# --------------------------------------------------------------------------
# STEP 2: SESSION SETUP
# --------------------------------------------------------------------------
def setup_session(seller_caps: dict) -> str:
    """
    After a successful handshake, establish a session.

    Logic (follows ACP spec):
      - If we have a saved sessionId AND seller supports loadSession
        → try session/load (replay history) or session/resume (silent)
      - Otherwise → session/new (fresh start)

    Returns the active sessionId (used in all subsequent calls).
    """
    print("\n[ STEP 2 ] SESSION SETUP")

    saved_id           = load_saved_session_id()
    supports_load      = seller_caps.get("loadSession", False)
    session_caps       = seller_caps.get("sessionCapabilities", {})
    supports_resume    = "resume" in session_caps

    if saved_id and supports_load:
        print(f"  Found saved session: {saved_id}")
        print(f"  Attempting session/load (seller supports loadSession)...")

        resp = post("session/load", {
            "sessionId":  saved_id,
            "cwd":        os.getcwd(),
            "mcpServers": []
        })

        if "result" in resp:
            history = resp["result"].get("history", [])
            print(f"  Session reloaded! {len(history)} history entries replayed")
            if history:
                print(f"  Last entry: [{history[-1]['role']}] {history[-1]['method']}")
            return saved_id

        # session/load failed — session may have expired
        print(f"  Load failed ({resp.get('error', {}).get('message', '?')})")
        print(f"  Clearing stale session, creating new one...")
        clear_saved_session()

    elif saved_id and supports_resume:
        print(f"  Found saved session: {saved_id}")
        print(f"  Attempting session/resume (silent reconnect, no replay)...")

        resp = post("session/resume", {
            "sessionId":  saved_id,
            "cwd":        os.getcwd(),
            "mcpServers": []
        })

        if "result" in resp:
            print(f"  Session resumed silently (no history replay)")
            return saved_id

        print(f"  Resume failed — creating new session...")
        clear_saved_session()

    # Create fresh session
    print(f"  Creating new session via session/new...")
    resp = post("session/new", {
        "buyerId": "buyer-agent-v2.0.0",
        "cwd":     os.getcwd()
    })

    if "error" in resp:
        print(f"  ERROR: {resp['error']['message']}")
        sys.exit(1)

    session_id = resp["result"]["sessionId"]
    save_session_id(session_id)

    print(f"  Session created: {session_id}")
    print(f"  SESSION READY")
    return session_id


# --------------------------------------------------------------------------
# STEP 3: COMMERCE REQUEST
# --------------------------------------------------------------------------
def request_item(session_id: str, item: str, max_price: float) -> dict | None:
    """
    Send purchase intent to the seller.
    sessionId is now included — seller will reject requests without one.
    """
    print(f"\n[ STEP 3 ] COMMERCE REQUEST")
    print(f"  Requesting: '{item}' | Budget: ${max_price} | Session: {session_id}")

    resp = post("commerce/request", {
        "sessionId": session_id,
        "buyer_id":  "buyer-agent-v2.0.0",
        "item":      item,
        "max_price": max_price
    })

    if "error" in resp:
        print(f"  ERROR: {resp['error']['message']}")
        return None

    offer = resp["result"]["offer"]
    print(f"  Offer received!")
    print(f"    Item:        {offer['item']}")
    print(f"    Description: {offer['description']}")
    print(f"    Price:       ${offer['price']} {offer['currency']}")
    print(f"    Status:      {offer['status']}")
    return offer


# --------------------------------------------------------------------------
# STEP 4: CLOSE SESSION
# --------------------------------------------------------------------------
def close_session(session_id: str):
    """
    Politely end the session.
    Spec: seller MUST cancel any ongoing work and free resources.
    We also clean up our local session_state.json.
    """
    print(f"\n[ STEP 4 ] SESSION CLOSE")
    print(f"  Sending: session/close for {session_id}")

    resp = post("session/close", {"sessionId": session_id})

    if "error" in resp:
        print(f"  ERROR: {resp['error']['message']}")
    else:
        print(f"  Session closed cleanly on seller side")

    clear_saved_session()
    print(f"  SESSION CLOSED")


# --------------------------------------------------------------------------
# ACCEPT / REJECT OFFER
# --------------------------------------------------------------------------
def evaluate_offer(offer: dict, our_max: float) -> bool:
    print(f"\n[ DECISION ] Evaluating offer...")
    if offer["price"] <= our_max:
        print(f"  ACCEPTED — ${offer['price']} is within our budget of ${our_max}")
        return True
    print(f"  REJECTED — ${offer['price']} exceeds our budget of ${our_max}")
    return False


def _offer_id(offer: dict) -> str:
    """Catalog id — commerce/request uses item; session/prompt uses id."""
    return offer.get("id") or offer.get("item") or ""


def pay_for_offer(session_id: str, offer: dict) -> dict:
    """x402: quote then settle via commerce/pay (server signs if DEMO_SERVER_SIGN)."""
    offer_id = _offer_id(offer)
    if not offer_id:
        print("  ERROR: offer missing id/item")
        return {"error": {"message": "offer missing id/item"}}

    print(f"\n[ STEP 5 ] COMMERCE / PAY — x402 USDC")
    quote_resp = post("commerce/pay", {
        "sessionId": session_id,
        "offerId": offer_id,
        "offer": offer,
    })
    if "error" in quote_resp:
        print(f"  Quote error: {quote_resp['error']['message']}")
        return quote_resp

    quote = quote_resp.get("result", {})
    fx = quote.get("fx", {})
    print(f"  Catalog: ${fx.get('catalogUsd')} → {fx.get('usdc')} USDC ({fx.get('demoRate', '')})")
    bal = quote.get("balanceCheck", {})
    if bal and not bal.get("sufficient"):
        print("  Insufficient USDC on buyer wallet for this offer.")
        return quote_resp

    pay_resp = post("commerce/pay", {
        "sessionId": session_id,
        "offerId": offer_id,
        "offer": offer,
        "execute": True,
    })
    if "error" in pay_resp:
        print(f"  Pay error: {pay_resp['error']['message']}")
        return pay_resp

    result = pay_resp.get("result", {})
    if result.get("status") == "paid":
        rcpt = result.get("receipt", {})
        print(f"  PAID — {rcpt.get('usdcPaid')} USDC")
        print(f"  Tx: {rcpt.get('explorer') or rcpt.get('txHash')}")
        if rcpt.get("ethGas"):
            g = rcpt["ethGas"]
            print(f"  Facilitator gas (ETH): {g.get('formatted', '—')}")
    else:
        print(f"  Payment status: {result.get('status')} — {result.get('error', '')}")
    return pay_resp


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def run():
    print("=" * 60)
    print(" BUYER AGENT v2.0.0  — ACP Nike Demo")
    print(" Phase 1–2: Handshake + Session + Commerce + x402 Pay")
    print("=" * 60)

    item      = "air_max_270"
    max_price = 200.00

    # 1. Handshake
    seller_caps = initialize()

    # 2. Session
    session_id = setup_session(seller_caps)

    # 3. Commerce
    offer = request_item(session_id, item, max_price)

    # 4. Evaluate + pay
    if offer and evaluate_offer(offer, max_price):
        pay_for_offer(session_id, offer)

    # 5. Close
    close_session(session_id)

    print("\n" + "=" * 60)
    print(" COMPLETE — All 4 ACP steps executed")
    print("=" * 60)


if __name__ == "__main__":
    run()
