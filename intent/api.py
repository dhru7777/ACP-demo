"""HTTP handlers for auditable intent endpoints."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from intent.constraints import public_constraints_doc
from intent import service
from search import catalog_search
from session_manager import session_manager


def constraints_response():
    return JSONResponse(public_constraints_doc())


async def capture_body(body: dict) -> JSONResponse:
    session_id = body.get("sessionId")
    prompt = (body.get("prompt") or "").strip()
    budget = body.get("budgetUsd") or body.get("budget")
    if not session_id or not session_manager.exists(session_id):
        return JSONResponse({"error": "Valid sessionId required"}, status_code=400)
    if not prompt:
        return JSONResponse({"error": "prompt required"}, status_code=400)
    if budget is None:
        return JSONResponse({"error": "budgetUsd required"}, status_code=400)
    try:
        result = service.capture_intent(
            session_id=session_id,
            prompt=prompt,
            budget_usd=float(budget),
            prompt_summary=(body.get("promptSummary") or body.get("intentSummary") or prompt).strip(),
            payment_rail=body.get("paymentRail") or "stripe_fiat",
        )
        session_manager.add_history(session_id, "buyer", "intent/capture", {
            "intentHash": result["intentHash"],
            "prompt": prompt,
            "budgetUsd": float(budget),
        })
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def manifest_response(session_id: str) -> JSONResponse:
    if not session_manager.exists(session_id):
        return JSONResponse({"error": "Unknown session"}, status_code=404)
    audit = service.buyer_audit(session_id)
    if not audit.get("found"):
        return JSONResponse({"error": "No intent for session"}, status_code=404)
    return JSONResponse(audit)


def merchant_response(session_id: str) -> JSONResponse:
    audit = service.merchant_audit(session_id)
    if not audit.get("found"):
        return JSONResponse({"error": "No intent for session"}, status_code=404)
    return JSONResponse(audit)


def audit_response(session_id: str) -> JSONResponse:
    return JSONResponse(service.full_audit(session_id))


async def check_body(body: dict) -> JSONResponse:
    session_id = body.get("sessionId")
    offer_id = body.get("offerId")
    if not session_id or not offer_id:
        return JSONResponse({"error": "sessionId and offerId required"}, status_code=400)
    product = catalog_search.get(offer_id)
    if product is None:
        return JSONResponse({"error": f"Unknown offer: {offer_id}"}, status_code=404)
    offer = body.get("offer") or {}
    merged = {
        "id": offer_id,
        "name": offer.get("name") or product.get("name"),
        "price": float(offer.get("price") or product.get("price")),
        "currency": offer.get("currency") or product.get("currency", "USD"),
        "category": offer.get("category") or product.get("category"),
    }
    try:
        result = service.check_offer(session_id, merged, product)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
