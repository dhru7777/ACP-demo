"""
Seller session/prompt handler — clarification skill → database_calling → offers.
"""

from __future__ import annotations

from acp import session_manager
from agents.seller.intent import parse_buyer_message
from agents.shared.requirements import empty_requirements, requirements_for_intent
from catalog.db import get_database_url, search_products
from intent import service as intent_service
from agents.shared.token_usage import format_terminal_line, record_turn, split_for_ui


def _catalog_source() -> str:
    return "postgres" if get_database_url() else "in_memory"


def cancelled_prompt_response(id_, session_id: str) -> dict:
    session_manager.add_history(session_id, "seller", "session/prompt.cancelled", {})
    return {
        "jsonrpc": "2.0", "id": id_,
        "result": {
            "stopReason":   "cancelled",
            "agentMessage": "Turn cancelled — session still active.",
            "offers":       [],
        },
    }


def _attach_usage(result: dict, usage_payload: dict | None, *, catalog_searched: bool) -> dict:
    if usage_payload:
        result["tokenUsage"] = usage_payload
        result["tokenSplit"] = split_for_ui(usage_payload.get("session", {}))
        print(format_terminal_line(usage_payload))
    result["catalogSearched"] = catalog_searched
    source = _catalog_source() if catalog_searched else None
    result["catalogSource"] = source
    if catalog_searched:
        print(f"  [Catalog] {source} DB search — top 3 shoe details from database_calling skill")
    else:
        print("  [Catalog] skipped — clarification phase (no DB/catalog query yet)")
    return result


def _accumulate_session_usage(session_id: str, turn_usage: dict | None) -> dict | None:
    if not turn_usage:
        return None
    session = session_manager.get(session_id)
    prior = (session.get("context") or {}).get("token_usage_session")
    merged = record_turn(
        prior,
        provider=turn_usage["turn"]["provider"],
        model=turn_usage["turn"]["model"],
        input_tokens=turn_usage["turn"]["input"],
        output_tokens=turn_usage["turn"]["output"],
        phase=turn_usage["turn"].get("phase", "intent_parse"),
        agent=turn_usage["turn"].get("agent"),
    )
    ctx = session.get("context") or {}
    ctx["token_usage_session"] = merged["session"]
    session_manager.update_context(session_id, ctx)
    return merged


def clarification_response(
    id_,
    session_id: str,
    requirements: dict,
    missing: list[str],
    message: str,
    turn_num: int,
    llm_provider: str = "regex",
    usage_payload: dict | None = None,
) -> dict:
    session = session_manager.get(session_id)
    ctx = session.get("context") or {}
    ctx.update({
        "awaiting_clarification": True,
        "awaiting_budget": True,
        "requirements": requirements,
        "pending_query": requirements.get("query", ""),
        "missing_fields": missing,
        "turn": turn_num + 1,
    })
    if usage_payload:
        ctx["token_usage_session"] = usage_payload.get("session")
    session_manager.update_context(session_id, ctx)
    session_manager.add_history(
        session_id, "seller", "session/prompt.clarification",
        {"question": message, "missing_fields": missing},
    )
    parsed = requirements_for_intent(requirements)
    result = {
        "jsonrpc": "2.0", "id": id_,
        "result": {
            "stopReason":            "needs_clarification",
            "agentMessage":          message,
            "parsedIntent":          parsed,
            "requirements":          parsed,
            "missing_fields":        missing,
            "awaitingClarification": True,
            "awaitingBudget":        "max_price" in missing,
            "usedClaude":            llm_provider == "anthropic",
            "usedOpenAI":            llm_provider == "openai",
            "llmProvider":           llm_provider,
            "offers":                [],
        },
    }
    accumulated = usage_payload
    _attach_usage(result["result"], accumulated, catalog_searched=False)
    return result


def build_offers_response(
    id_,
    session_id: str,
    query: str,
    max_price: float,
    raw_text: str,
    used_claude: bool = False,
    usage_payload: dict | None = None,
) -> dict:
    # database_calling skill — query Postgres for exact shoe rows (no category filter)
    try:
        results = search_products(query=query, max_price=max_price, top_k=3)
    except Exception as e:
        print(f"  [DB] search_products failed: {e}")
        msg = "Catalog database is temporarily unavailable. Check DATABASE_URL and try again."
        session_manager.add_history(session_id, "seller", "session/prompt.response", {"message": msg})
        out = {
            "jsonrpc": "2.0", "id": id_,
            "result": {
                "stopReason": "end_turn",
                "agentMessage": msg,
                "parsedIntent": {"query": query, "max_price": max_price},
                "usedClaude": used_claude,
                "offers": [],
                "dbError": str(e),
            },
        }
        _attach_usage(out["result"], usage_payload, catalog_searched=False)
        return out

    print(f"  [DB] search_products '{query[:50]}' (≤${max_price}): {len(results)} row(s)")

    if not results:
        msg = (
            f"No Nike shoes found for '{query}' within ${max_price}. "
            "Try a higher budget or a different style."
        )
        session_manager.add_history(session_id, "seller", "session/prompt.response", {"message": msg})
        result_payload = {
            "stopReason":   "end_turn",
            "agentMessage": msg,
            "parsedIntent": {"query": query, "max_price": max_price},
            "usedClaude":   used_claude,
            "offers":       [],
        }
        accumulated = usage_payload
        out = {"jsonrpc": "2.0", "id": id_, "result": result_payload}
        _attach_usage(out["result"], accumulated, catalog_searched=True)
        return out

    offers = [
        {
            "id":               r["id"],
            "name":             r["name"],
            "description":      r["description"],
            "price":            r["price"],
            "currency":         r["currency"],
            "category":         r.get("category"),
            "score":            r.get("score", 0),
            "sub_title":        r.get("sub_title"),
            "image_url":        r.get("image_url"),
            "product_url":      r.get("product_url"),
            "availability":     r.get("availability"),
            "available_sizes":  r.get("available_sizes"),
            "brand":            r.get("brand"),
            "keywords":         r.get("keywords"),
            "payment_required": True,
            "status":           "offer_ready",
            "seller_agent":     "nike-seller-agent-v2.0.0",
        }
        for r in results
    ]

    session_manager.add_history(session_id, "seller", "session/prompt.response", {"offers": offers})

    intent_info = None
    try:
        intent_info = intent_service.capture_intent(
            session_id=session_id,
            prompt=raw_text or query,
            budget_usd=max_price,
            prompt_summary=query,
        )
        session_manager.add_history(session_id, "buyer", "intent/capture.auto", {
            "intentHash": intent_info["intentHash"],
            "promptSummary": query,
            "budgetUsd": max_price,
        })
    except ValueError as e:
        print(f"  [Intent] capture skipped: {e}")

    top = offers[0]
    rest = len(offers) - 1
    if rest > 0:
        msg = (
            f"Found {len(offers)} matches. "
            f"Best fit: {top['name']} — ${top['price']}. "
            f"({rest} more option{'s' if rest > 1 else ''} included)"
        )
    else:
        msg = f"Found it: {top['name']} — ${top['price']} {top['currency']}. {top['description']}"

    print(f"  Offers: {[o['id'] for o in offers]}")

    result_payload = {
        "stopReason":   "end_turn",
        "agentMessage": msg,
        "parsedIntent": {"query": query, "max_price": max_price},
        "usedClaude":   used_claude,
        "offers":       offers,
    }
    if intent_info:
        result_payload["intentHash"] = intent_info["intentHash"]
        result_payload["intentCapturedAt"] = intent_info["capturedAt"]

    out = {"jsonrpc": "2.0", "id": id_, "result": result_payload}
    _attach_usage(out["result"], usage_payload, catalog_searched=True)
    return out


def handle_session_prompt(id_, params: dict) -> dict:
    session_id = params.get("sessionId")
    prompt = params.get("prompt", [])

    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32000, "message": "Valid sessionId required."},
        }

    text = " ".join(
        block.get("text", "")
        for block in prompt
        if block.get("type") == "text"
    ).strip()

    if not text:
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {"code": -32000, "message": "Empty prompt — send a text message."},
        }

    session_manager.clear_cancelled(session_id)
    session_manager.start_processing(session_id)

    try:
        session = session_manager.get(session_id)
        ctx = session.get("context", {})
        turn_num = ctx.get("turn", 1)
        history = session.get("history", [])

        print(f"  Prompt (turn {turn_num}): \"{text[:100]}\"")

        session_manager.add_history(session_id, "buyer", "session/prompt", {"text": text, "turn": turn_num})

        if session_manager.is_cancelled(session_id):
            return cancelled_prompt_response(id_, session_id)

        prior_req = ctx.get("requirements") or empty_requirements()
        if ctx.get("pending_query") and not prior_req.get("query"):
            prior_req = {**prior_req, "query": ctx["pending_query"]}

        parsed = parse_buyer_message(text, history, prior_requirements=prior_req)
        if session_manager.is_cancelled(session_id):
            return cancelled_prompt_response(id_, session_id)

        requirements = parsed["requirements"]
        missing = parsed["missing_fields"]
        llm_provider = parsed.get("llm_provider", "regex")

        turn_usage = parsed.get("token_usage")
        usage_payload = _accumulate_session_usage(session_id, turn_usage)

        if parsed.get("needs_clarification") or missing:
            return clarification_response(
                id_, session_id, requirements, missing,
                parsed.get("response_message", ""),
                turn_num, llm_provider=llm_provider,
                usage_payload=usage_payload,
            )

        session_manager.update_context(session_id, {
            "token_usage_session": (usage_payload or {}).get("session"),
        })
        query = requirements.get("query") or text
        budget = float(requirements["max_price"])
        print(f"  Requirements satisfied — search: \"{query[:60]}\" ≤ ${budget}")
        return build_offers_response(
            id_, session_id, query, budget, text,
            used_claude=(llm_provider == "anthropic"),
            usage_payload=usage_payload,
        )

    finally:
        session_manager.finish_processing(session_id)
