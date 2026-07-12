"""ACP JSON-RPC handlers — commerce request and pay."""

from __future__ import annotations

from acp import session_manager
from catalog import catalog_search
from payments.commerce_pay import handle_commerce_pay


def handle_commerce_request(id_, params: dict) -> dict:
    session_id = params.get("sessionId")
    item = params.get("item")
    max_price = params.get("max_price", 0)
    buyer_id = params.get("buyer_id", "unknown")

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": "Valid sessionId required. Call session/new first.",
            },
        }

    print(f"  Buyer '{buyer_id}' [session: {session_id}] wants: '{item}' (max: ${max_price})")

    product = catalog_search.get(item)
    if product is None:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Item '{item}' not in catalog. Use session/prompt to discover available items.",
            },
        }

    our_price = product["price"]
    if max_price < our_price:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32001,
                "message": f"Budget too low. '{item}' costs ${our_price}, you offered ${max_price}",
            },
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
        "seller_agent":     "nike-seller-agent-v2.0.0",
    }

    session_manager.add_history(session_id, "buyer", "commerce/request", {
        "item": item, "max_price": max_price,
    })
    session_manager.add_history(session_id, "seller", "commerce/request.response", offer)
    print(f"  Offer sent: ${our_price} for '{item}' | session: {session_id}")

    return {"jsonrpc": "2.0", "id": id_, "result": {"offer": offer}}


async def handle_commerce_pay_rpc(id_, params: dict) -> dict:
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
