"""
LLM token usage tracking and cost estimates per provider.

Costs are approximate list prices (USD per 1M tokens) — update as pricing changes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# USD per 1M tokens (input, output)
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "claude-haiku-4-5":  {"input": 0.25,  "output": 1.25},
    "claude-haiku-3-5":  {"input": 0.25,  "output": 1.25},
}

PROVIDER_LABELS = {
    "openai":     "OpenAI",
    "anthropic":  "Anthropic",
    "regex":      "Regex (free)",
}


def _empty_bucket() -> dict[str, Any]:
    return {"input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}


AGENT_KEYS = ("buyer", "seller")


def _resolve_agent(*, phase: str, agent: str | None) -> str:
    if agent in AGENT_KEYS:
        return agent
    return "buyer" if phase == "buyer_eval" else "seller"


def empty_session_usage() -> dict[str, Any]:
    return {
        "buyer":     _empty_bucket(),
        "seller":    _empty_bucket(),
        "openai":    _empty_bucket(),
        "anthropic": _empty_bucket(),
        "regex":     _empty_bucket(),
        "total_cost_usd": 0.0,
        "total_tokens": 0,
    }


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, {"input": 0.25, "output": 1.25})
    return (
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"]
    )


def record_turn(
    session_usage: dict[str, Any] | None,
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    phase: str = "intent_parse",
    agent: str | None = None,
) -> dict[str, Any]:
    """Accumulate usage into session totals; return turn + session snapshot."""
    session = deepcopy(session_usage) if session_usage else empty_session_usage()
    agent_key = _resolve_agent(phase=phase, agent=agent)

    for key in AGENT_KEYS:
        session.setdefault(key, _empty_bucket())
    bucket = session.setdefault(provider, _empty_bucket())
    agent_bucket = session[agent_key]

    cost = estimate_cost(model, input_tokens, output_tokens) if provider != "regex" else 0.0

    bucket["input"] += input_tokens
    bucket["output"] += output_tokens
    bucket["cost_usd"] = round(bucket["cost_usd"] + cost, 8)
    bucket["calls"] = bucket.get("calls", 0) + 1

    agent_bucket["input"] += input_tokens
    agent_bucket["output"] += output_tokens
    agent_bucket["cost_usd"] = round(agent_bucket["cost_usd"] + cost, 8)
    agent_bucket["calls"] = agent_bucket.get("calls", 0) + 1

    session["total_cost_usd"] = round(
        sum(session[a]["cost_usd"] for a in AGENT_KEYS),
        8,
    )
    session["total_tokens"] = sum(
        session[a]["input"] + session[a]["output"]
        for a in AGENT_KEYS
    )

    turn = {
        "agent": agent_key,
        "provider": provider,
        "model": model,
        "phase": phase,
        "input": input_tokens,
        "output": output_tokens,
        "cost_usd": round(cost, 8),
    }
    return {"turn": turn, "session": session}


def usage_from_openai(resp, model: str) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0
    return int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)


def usage_from_anthropic(resp) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0
    return int(getattr(u, "input_tokens", 0) or 0), int(getattr(u, "output_tokens", 0) or 0)


def format_terminal_line(usage_payload: dict[str, Any]) -> str:
    turn = usage_payload.get("turn", {})
    session = usage_payload.get("session", {})
    agent = turn.get("agent", "?")
    return (
        f"  [Tokens] {agent}: in={turn.get('input', 0)} out={turn.get('output', 0)} "
        f"${turn.get('cost_usd', 0):.6f} | session total ${session.get('total_cost_usd', 0):.6f}"
    )


def _legacy_agent_buckets(session_usage: dict[str, Any]) -> dict[str, Any]:
    """Map old provider-only sessions to buyer/seller for UI."""
    buyer = deepcopy(session_usage.get("buyer") or _empty_bucket())
    seller = deepcopy(session_usage.get("seller") or _empty_bucket())
    if buyer["cost_usd"] or seller["cost_usd"]:
        return {"buyer": buyer, "seller": seller}

    anthropic = session_usage.get("anthropic", _empty_bucket())
    openai = session_usage.get("openai", _empty_bucket())
    regex = session_usage.get("regex", _empty_bucket())
    buyer = deepcopy(anthropic)
    seller = {
        "input": openai.get("input", 0) + regex.get("input", 0),
        "output": openai.get("output", 0) + regex.get("output", 0),
        "cost_usd": openai.get("cost_usd", 0.0) + regex.get("cost_usd", 0.0),
        "calls": openai.get("calls", 0) + regex.get("calls", 0),
    }
    return {"buyer": buyer, "seller": seller}


def split_for_ui(session_usage: dict[str, Any]) -> list[dict[str, Any]]:
    """Bar segments for demo UI — Agent 1 (buyer) vs Seller, no provider names."""
    buckets = _legacy_agent_buckets(session_usage)
    total = session_usage.get("total_cost_usd") or 0.0
    if not total:
        total = buckets["buyer"]["cost_usd"] + buckets["seller"]["cost_usd"]

    segments = []
    for key, label, color in (
        ("buyer", "Buyer", "#e53935"),
        ("seller", "Seller", "#2e9e6e"),
    ):
        bucket = buckets[key]
        cost = bucket.get("cost_usd", 0.0)
        tokens = bucket.get("input", 0) + bucket.get("output", 0)
        if tokens == 0 and cost == 0:
            continue
        pct = (cost / total * 100) if total > 0 else 0
        segments.append({
            "agent": key,
            "label": label,
            "color": color,
            "input": bucket.get("input", 0),
            "output": bucket.get("output", 0),
            "cost_usd": cost,
            "pct": round(pct, 1),
            "calls": bucket.get("calls", 0),
        })
    return segments
