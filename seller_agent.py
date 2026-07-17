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
from fastapi.responses import JSONResponse, Response, FileResponse, RedirectResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from acp import session_manager
from catalog import catalog_search
from catalog.db import get_database_url, get_product, search_products
from agents.seller.handlers import (
    handle_commerce_pay_rpc,
    handle_commerce_request,
    handle_initialize,
    handle_session_cancel,
    handle_session_close,
    handle_session_load,
    handle_session_new,
    handle_session_prompt,
    handle_session_resume,
)
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
from payments import escrow_service, x402_service
from payments.chain import fetch_tx_fee_eth
from payments.receipt_pdf import build_receipt_pdf
from trust.identity_api import build_agent_identity_response, identity_status
from intent import api as intent_api
from intent import service as intent_service
from intent.payment_guard import check_offer_for_session, finalize_paid_receipt

app = FastAPI(title="Nike Seller Agent", version="2.0.0")


def _resolve_product(offer_id: str, offer: dict | None = None) -> dict | None:
    """Catalog lookup with inline-offer fallback for demo UI payments."""
    offer = offer or {}
    product = catalog_search.get(offer_id)
    if product is not None:
        return {**product, "id": offer_id}
    price = offer.get("price")
    name = offer.get("name")
    if price is None or not name:
        return None
    try:
        catalog_usd = float(price)
    except (TypeError, ValueError):
        return None
    return {
        "id": offer_id,
        "name": str(name),
        "price": catalog_usd,
        "currency": offer.get("currency") or "USD",
        "category": offer.get("category"),
        "description": offer.get("description") or "",
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracks connected clients (from handshake)
connected_clients: dict = {}

_ROOT = Path(__file__).resolve().parent


@app.get("/intent-demo")
async def intent_demo_redirect():
    return RedirectResponse(url="/intent-demo.html")


@app.get("/intent-demo.html")
async def serve_intent_demo():
    path = _ROOT / "intent" / "intent-demo.html"
    if not path.is_file():
        return JSONResponse({"error": "intent-demo.html not found"}, status_code=404)
    return FileResponse(path, media_type="text/html")


@app.get("/demo.html")
async def serve_demo_html():
    path = _ROOT / "demo.html"
    if not path.is_file():
        return JSONResponse({"error": "demo.html not found"}, status_code=404)
    return FileResponse(path, media_type="text/html")


# --------------------------------------------------------------------------
# Health check — Railway pings GET / to verify the container is alive
# --------------------------------------------------------------------------
def _x402_health() -> dict:
    from payments.config import get_facilitator_url, get_network
    from payments.x402_service import _demo_server_sign_enabled

    buyer = wallet_status(AgentRole.BUYER)
    seller = wallet_status(AgentRole.SELLER)
    ready = (
        buyer.get("configured")
        and seller.get("configured")
        and _demo_server_sign_enabled()
    )
    blockers: list[str] = []
    if not buyer.get("configured"):
        blockers.append(buyer.get("error") or "BUYER_WALLET_PRIVATE_KEY missing")
    if not seller.get("configured"):
        blockers.append(seller.get("error") or "SELLER_PAYTO_ADDRESS missing")
    if not _demo_server_sign_enabled():
        blockers.append("DEMO_SERVER_SIGN is off — demo UI cannot sign x402 payments")
    return {
        "ready": ready,
        "network": get_network(),
        "facilitator": get_facilitator_url(),
        "demoServerSign": _demo_server_sign_enabled(),
        "blockers": blockers,
    }


@app.get("/")
async def health():
    summary = catalog_search.summary()
    return JSONResponse({
        "status":        "ok",
        "agent":           "nike-seller-agent",
        "version":         "2.0.0",
        "session":         True,
        "catalogCount":    catalog_search.count(),
        "catalogSource":   catalog_search.summary().get("source", "in_memory"),
        "catalogCategories": list(summary["categories"].keys()),
        "wallets": {
            "buyer":  wallet_status(AgentRole.BUYER),
            "seller": wallet_status(AgentRole.SELLER),
        },
        "x402": _x402_health(),
        "erc8004": identity_status(),
    })


@app.get("/products")
async def list_products(query: str, max_price: float, top_k: int = 3):
    """database_calling skill — HTTP path after clarification requirements met."""
    try:
        results = search_products(query=query, max_price=max_price, top_k=min(top_k, 10))
        return JSONResponse({
            "count": len(results),
            "query": query,
            "max_price": max_price,
            "source": "postgres",
            "results": results,
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "source": get_database_url() and "postgres" or "unconfigured"}, status_code=503)


@app.get("/session/{session_id}/agent-cost")
async def session_agent_cost(session_id: str):
    """Return persisted LLM cost structure for a session (Postgres)."""
    try:
        from catalog.agent_cost import get_session_cost

        row = get_session_cost(session_id)
        if row is None:
            return JSONResponse(
                {"found": False, "sessionId": session_id, "message": "No cost record for this session"},
                status_code=404,
            )
        return JSONResponse({"found": True, **row})
    except Exception as e:
        return JSONResponse({"found": False, "sessionId": session_id, "error": str(e)}, status_code=503)


@app.get("/products/{product_id}")
async def product_detail(product_id: str):
    try:
        row = get_product(product_id)
        if row is None:
            return JSONResponse({"error": f"Product '{product_id}' not found"}, status_code=404)
        return JSONResponse({"source": "postgres", "product": row})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)


@app.post("/agent/buyer/evaluate")
async def buyer_evaluate(request: Request):
    """Agent 1 (OpenAI) — cross-check seller turn against goal + constraints."""
    body = await request.json()
    try:
        from agents.buyer.evaluator import evaluate_turn
        from agents.shared.token_usage import split_for_ui

        prior = body.get("token_usage")
        plan = evaluate_turn(
            user_goal=body.get("user_goal", ""),
            seller_result=body.get("seller_result", {}),
            buyer_requirements=body.get("buyer_requirements") or {},
            round_num=int(body.get("round", 1)),
            session_usage=prior,
            conversation_history=body.get("conversation_history"),
            buyer_profile=body.get("buyer_profile"),
        )
        usage = plan.pop("_token_usage", {})
        policy = plan.pop("_policy", None)
        session = usage.get("session", {})
        session_id = body.get("sessionId") or body.get("session_id")
        if session_id and usage:
            try:
                from catalog.agent_cost import save_session_cost
                from acp import session_manager as _sm

                buyer_id = None
                if _sm.exists(session_id):
                    buyer_id = (_sm.get(session_id) or {}).get("buyerId")
                save_session_cost(session_id, usage, buyer_id=buyer_id)
            except Exception as e:
                print(f"  [AgentCost] buyer evaluate persist failed: {e}")
        return JSONResponse({
            "result": plan,
            "tokenUsage": {"session": session, "turn": usage.get("turn")},
            "tokenSplit": split_for_ui(session),
            "policy": policy,
        })
    except RuntimeError as e:
        return JSONResponse({"error": {"message": str(e)}}, status_code=503)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": {"message": str(e)}}, status_code=500)


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
def _public_service_url(request: Request) -> str:
    """Prefer env override; behind Railway/proxies use X-Forwarded-* (not http:// base_url)."""
    from trust.config import get_service_url

    explicit = get_service_url()
    if explicit:
        return explicit.rstrip("/")
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https")
    if "," in proto:
        proto = proto.split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    if host and "," in host:
        host = host.split(",")[0].strip()
    # Railway internal routing often reports http while the public URL is https.
    if proto == "http" and host and (
        host.endswith(".railway.app") or host.endswith(".up.railway.app")
    ):
        proto = "https"
    return f"{proto}://{host}".rstrip("/")


@app.get("/agent/erc8004")
async def agent_erc8004(request: Request):
    try:
        service_url = _public_service_url(request)
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
    product = _resolve_product(offer_id, offer)
    if product is None:
        return JSONResponse({"error": f"Unknown offer: {offer_id}"}, status_code=404)
    catalog_usd = float(offer.get("price") or product["price"])
    offer_name = offer.get("name") or product.get("name", "")

    check_result = None
    if session_id:
        try:
            check_result = check_offer_for_session(
                session_id,
                offer_id=offer_id,
                offer_name=offer_name,
                catalog_usd=catalog_usd,
                product=product,
                offer=offer,
                payment_rail="x402",
                require_intent=body.get("requireIntent", True),
            )
        except ValueError as e:
            return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
        if check_result and not check_result.get("pass"):
            return JSONResponse({
                "status": "error",
                "error": "Constraint check failed",
                "constraintCheck": check_result,
            }, status_code=403)

    try:
        result = await x402_service.execute_payment(catalog_usd, offer_id, offer_name)
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.receipt", result)
            sess = session_manager.get(session_id)
            if sess is not None:
                paid = sess.setdefault("context", {}).setdefault("paidOffers", {})
                paid[offer_id] = result
            if check_result and result.get("status") == "paid":
                finalize_paid_receipt(
                    session_id,
                    offer_id=offer_id,
                    check_result=check_result,
                    receipt=result.get("receipt") or {},
                    provider="x402",
                )
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/demo/payments/health")
async def demo_payments_health():
    """Report which payment rails are importable / routable (for smoke tests)."""
    stripe_ok = False
    stripe_err = None
    try:
        import stripe as _stripe  # noqa: F401
        stripe_ok = True
    except Exception as e:
        stripe_err = str(e)

    escrow_ok = True
    escrow_err = None
    try:
        _ = escrow_service.build_quote
    except Exception as e:
        escrow_ok = False
        escrow_err = str(e)

    return JSONResponse({
        "status": "ok",
        "rails": {
            "x402": {"route": "/demo/x402/execute", "ready": True},
            "escrow": {
                "routes": [
                    "/demo/escrow/execute",
                    "/demo/escrow/confirm",
                    "/demo/escrow/cancel",
                    "/demo/escrow/pending",
                ],
                "ready": escrow_ok,
                "error": escrow_err,
            },
            "stripe": {
                "route": "/demo/stripe/execute",
                "module": stripe_ok,
                "error": stripe_err,
            },
        },
    })


@app.post("/demo/escrow/execute")
async def demo_escrow_execute(request: Request):
    """Demo UI: deploy BilateralEscrow + approve + deposit (funds held until confirm)."""
    body = await request.json()
    session_id = body.get("sessionId")
    offer = body.get("offer") or {}
    offer_id = body.get("offerId") or offer.get("id")
    if not offer_id:
        return JSONResponse({"error": "offerId required"}, status_code=400)
    product = _resolve_product(offer_id, offer)
    if product is None:
        return JSONResponse({"error": f"Unknown offer: {offer_id}"}, status_code=404)
    catalog_usd = float(offer.get("price") or product["price"])
    offer_name = offer.get("name") or product.get("name", "")

    check_result = None
    if session_id:
        try:
            check_result = check_offer_for_session(
                session_id,
                offer_id=offer_id,
                offer_name=offer_name,
                catalog_usd=catalog_usd,
                product=product,
                offer=offer,
                payment_rail="escrow",
                require_intent=body.get("requireIntent", False),
            )
        except ValueError as e:
            return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
        if check_result and not check_result.get("pass"):
            return JSONResponse({
                "status": "error",
                "error": "Constraint check failed",
                "constraintCheck": check_result,
            }, status_code=403)

    try:
        result = await escrow_service.execute_deposit(
            catalog_usd, offer_id, offer_name, session_id=session_id
        )
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay.escrow_deposit", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.escrow_funded", result)
            sess = session_manager.get(session_id)
            if sess is not None:
                held = sess.setdefault("context", {}).setdefault("escrowOffers", {})
                held[offer_id] = result
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/demo/escrow/confirm")
async def demo_escrow_confirm(request: Request):
    """Buyer Yes — release escrowed USDC to seller."""
    body = await request.json()
    session_id = body.get("sessionId")
    offer_id = body.get("offerId")
    escrow = body.get("escrow")
    try:
        result = await escrow_service.execute_confirm(
            session_id=session_id, offer_id=offer_id, escrow=escrow
        )
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay.escrow_confirm", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.escrow_released", result)
            sess = session_manager.get(session_id)
            if sess is not None:
                paid = sess.setdefault("context", {}).setdefault("paidOffers", {})
                oid = offer_id or (result.get("receipt") or {}).get("offerId")
                if oid:
                    paid[oid] = result
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/demo/escrow/cancel")
async def demo_escrow_cancel(request: Request):
    """Buyer No — cancel Funded escrow and refund USDC immediately."""
    body = await request.json()
    session_id = body.get("sessionId")
    offer_id = body.get("offerId")
    escrow = body.get("escrow")
    try:
        result = await escrow_service.execute_cancel(
            session_id=session_id, offer_id=offer_id, escrow=escrow
        )
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay.escrow_cancel", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.escrow_cancelled", result)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/demo/escrow/pending")
async def demo_escrow_pending(sessionId: str | None = None, offerId: str | None = None):
    deal = escrow_service.get_pending(session_id=sessionId, offer_id=offerId)
    if not deal:
        return JSONResponse({"status": "none"})
    held = escrow_service.escrow_usdc_balance(deal["escrow"])
    state = escrow_service.escrow_state(deal["escrow"])
    return JSONResponse({**deal, "heldAtomic": held, "state": state, "status": "pending"})


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


@app.get("/intent/constraints")
async def intent_constraints():
    return intent_api.constraints_response()


@app.post("/intent/capture")
async def intent_capture(request: Request):
    return await intent_api.capture_body(await request.json())


@app.get("/intent/manifest/{session_id}")
async def intent_manifest(session_id: str):
    return intent_api.manifest_response(session_id)


@app.get("/intent/merchant/{session_id}")
async def intent_merchant(session_id: str):
    return intent_api.merchant_response(session_id)


@app.get("/intent/audit/{session_id}")
async def intent_audit(session_id: str):
    return intent_api.audit_response(session_id)


@app.post("/intent/check")
async def intent_check(request: Request):
    return await intent_api.check_body(await request.json())


@app.post("/demo/stripe/execute")
async def demo_stripe_execute(request: Request):
    """Demo UI: charge test card via Stripe in one call."""
    try:
        from payments import stripe_service
    except ImportError as e:
        return JSONResponse(
            {"status": "error", "error": f"Stripe SDK missing: {e}. Add stripe to requirements."},
            status_code=500,
        )

    body = await request.json()
    session_id = body.get("sessionId")
    offer = body.get("offer") or {}
    offer_id = body.get("offerId") or offer.get("id")
    if not offer_id:
        return JSONResponse({"error": "offerId required"}, status_code=400)
    product = _resolve_product(offer_id, offer)
    if product is None:
        return JSONResponse({"error": f"Unknown offer: {offer_id}"}, status_code=404)
    catalog_usd = float(offer.get("price") or product["price"])
    offer_name = offer.get("name") or product.get("name", "")

    check_result = None
    if session_id:
        try:
            check_result = check_offer_for_session(
                session_id,
                offer_id=offer_id,
                offer_name=offer_name,
                catalog_usd=catalog_usd,
                product=product,
                offer=offer,
                payment_rail="stripe_fiat",
                require_intent=body.get("requireIntent", True),
            )
        except ValueError as e:
            return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
        if check_result and not check_result.get("pass"):
            return JSONResponse({
                "status": "error",
                "error": "Constraint check failed",
                "constraintCheck": check_result,
            }, status_code=403)

    metadata_extra = None
    if check_result:
        metadata_extra = {
            "intentHash": check_result.get("intentHash"),
            "checkoutHash": check_result.get("checkoutHash"),
            "constraintCheck": check_result.get("constraintCheck"),
        }

    try:
        result = await stripe_service.execute_payment(
            catalog_usd, offer_id, offer_name, metadata_extra=metadata_extra,
        )
        if session_id and session_manager.exists(session_id):
            session_manager.add_history(session_id, "buyer", "commerce/pay.fiat", body)
            session_manager.add_history(session_id, "seller", "commerce/pay.fiat.receipt", result)
            sess = session_manager.get(session_id)
            if sess is not None:
                paid = sess.setdefault("context", {}).setdefault("paidOffers", {})
                paid[offer_id] = result
            if check_result and result.get("status") == "paid":
                finalize_paid_receipt(
                    session_id,
                    offer_id=offer_id,
                    check_result=check_result,
                    receipt=result.get("receipt") or {},
                    provider="stripe",
                )
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

    if   method == "initialize":       return JSONResponse(handle_initialize(id_, params, connected_clients, _stripe_connect_enabled))
    elif method == "session/new":      return JSONResponse(handle_session_new(id_, params))
    elif method == "session/load":     return JSONResponse(handle_session_load(id_, params))
    elif method == "session/resume":   return JSONResponse(handle_session_resume(id_, params))
    elif method == "session/close":    return JSONResponse(handle_session_close(id_, params))
    elif method == "session/cancel":   return JSONResponse(handle_session_cancel(id_, params))
    elif method == "session/prompt":   return JSONResponse(handle_session_prompt(id_, params))
    elif method == "commerce/request": return JSONResponse(handle_commerce_request(id_, params))
    elif method == "commerce/pay":     return JSONResponse(await handle_commerce_pay_rpc(id_, params))
    else:
        return JSONResponse({
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32601, "message": f"Method '{method}' not supported"}
        })



# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        from catalog.agent_cost import ensure_schema
        ensure_schema()
    except Exception as e:
        print(f"  [AgentCost] schema ensure skipped: {e}")
    summary = catalog_search.summary()
    print("Nike Seller Agent v2.0.0 starting on http://localhost:8002")
    print(f"  Catalog: {summary['total_items']} items across {len(summary['categories'])} categories")
    print(f"  Price range: ${summary['price_range']['min']} – ${summary['price_range']['max']}")
    print(f"  Session support: session/new, session/load, session/resume, session/cancel, session/close\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)
