"""
Agent 1 (OpenAI) — non-deterministic evaluation against user goal + constraints.

The buyer agent decides satisfaction; no score thresholds or regex shortcuts on the offer path.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agents.shared.token_usage import (
    format_terminal_line,
    record_turn,
    usage_from_openai,
)
from agents.shared.requirements import extract_budget, regex_extract, requirements_for_intent
from intent.constraints import build_session_constraints, public_constraints_doc

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OPENAI_CLIENT = None

_BUYER_EVAL_SYSTEM = """You are Agent 1 — the Nike buyer agent.

You cross-check seller responses and Postgres catalog offers against the user's goal and policy constraints.
You decide when to clarify, when to re-search the database, and when the goal is satisfied.
Do NOT use match score alone — judge holistically from offer details vs intent.

Policy constraints (verify each when offers are present):
- budget.max: every offer price must be <= buyer max_price / budget
- intent fit: name, description, keywords align with user_goal
- categories_allowed: from policy — flag mismatch only when clearly wrong
- size: if user_goal mentions size, check available_sizes when present
- merchant: offers must be Nike catalog items (seller is nike.com)

Respond ONLY with JSON (no markdown):
{
  "reply_to_seller": "next natural language message for session/prompt, or empty if done",
  "requirements_update": {
    "query": null or string,
    "max_price": null or number,
    "category": null or string,
    "style": null or string,
    "size": null or string
  },
  "goal_satisfied": true or false,
  "constraints_passed": true or false,
  "needs_more_search": true or false,
  "constraint_checks": [
    {"rule": "budget.max", "pass": true, "detail": "short note"}
  ],
  "reason": "brief explanation of your decision"
}

Decision rules:
- You are AUTONOMOUS: no human in the loop. Every reply_to_seller must be derived from user_goal and buyer_profile only.
- Never echo nonsense or unrelated requests (e.g. "cake") — rewrite query to valid Nike footwear matching user_goal.
- Seller needs_clarification: goal_satisfied=false, needs_more_search=false, reply_to_seller fully answers from user_goal
- Offers returned but weak/wrong/over budget/low match: goal_satisfied=false, needs_more_search=true, reply_to_seller refines search
- Offers fit goal and constraints: goal_satisfied=true, constraints_passed=true, needs_more_search=false
- If user_goal truly lacks required info: prefix reply_to_seller with NEED_USER:
- One message per turn; be conversational"""


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO_ROOT / "local.env")
    except ImportError:
        pass


def _openai_key() -> str:
    _load_env()
    key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("OpenAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing — required for Agent 1 (buyer)")
    return key


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip())
    if not raw.startswith("{"):
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)
    return raw


def _policy_for_goal(user_goal: str, buyer_requirements: dict) -> dict:
    budget = buyer_requirements.get("max_price")
    if budget is None:
        budget = extract_budget(user_goal) or regex_extract(user_goal).get("max_price") or 150.0
    return build_session_constraints(budget_usd=float(budget), intent_text=user_goal)


def regex_reply_from_goal(user_goal: str, missing: list[str]) -> str:
    """Fallback when OpenAI is unavailable — derive reply from goal text."""
    field = (missing or ["max_price"])[0]
    extracted = regex_extract(user_goal)
    if field == "max_price":
        budget = extracted.get("max_price") or extract_budget(user_goal)
        return f"My budget is ${int(budget)}" if budget else "My budget is around $150"
    if field == "query":
        return (extracted.get("query") or user_goal).strip() or "comfortable running shoes"
    if field == "category":
        cat = extracted.get("category")
        return f"I'm looking for {cat} shoes" if cat else user_goal
    if field == "style":
        style = extracted.get("style")
        return f"I prefer {style} shoes" if style else user_goal
    if field == "size":
        size = extracted.get("size")
        return f"Size {size}" if size else "Size 10"
    return user_goal.strip() or "comfortable running shoes"


def _parse_plan_json(raw: str) -> dict[str, Any]:
    text = _strip_json(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        end = text.rfind("}")
        if end > 0:
            return json.loads(text[: end + 1])
        raise


def evaluate_turn(
    user_goal: str,
    seller_result: dict,
    buyer_requirements: dict,
    round_num: int,
    *,
    session_usage: dict | None = None,
    conversation_history: list | None = None,
    buyer_profile: dict | None = None,
) -> dict[str, Any]:
    """
    Agent 1 evaluates seller turn — clarification or offers — against constraints.
    Returns plan with goal_satisfied, needs_more_search, reply_to_seller, etc.
    """
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        from openai import OpenAI
        _OPENAI_CLIENT = OpenAI(api_key=_openai_key())

    policy = _policy_for_goal(user_goal, buyer_requirements)
    user_payload = {
        "user_goal": user_goal,
        "buyer_profile": buyer_profile or {},
        "conversation_history": conversation_history or [],
        "buyer_requirements": requirements_for_intent(buyer_requirements),
        "policy_constraints": policy,
        "policy_reference": public_constraints_doc(),
        "seller_stop_reason": seller_result.get("stopReason"),
        "seller_message": seller_result.get("agentMessage"),
        "seller_missing_fields": seller_result.get("missing_fields", []),
        "seller_requirements": seller_result.get("requirements"),
        "offers": seller_result.get("offers", []),
        "catalog_source": seller_result.get("catalogSource"),
        "round": round_num,
    }

    model = os.environ.get("OPENAI_BUYER_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    resp = _OPENAI_CLIENT.chat.completions.create(
        model=model,
        max_tokens=700,
        temperature=0.2,
        messages=[
            {"role": "system", "content": _BUYER_EVAL_SYSTEM},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
    )
    inp, out = usage_from_openai(resp, model)
    usage = record_turn(
        session_usage,
        provider="openai",
        model=model,
        input_tokens=inp,
        output_tokens=out,
        phase="buyer_eval",
        agent="buyer",
    )
    print(format_terminal_line(usage))

    raw = resp.choices[0].message.content or ""
    plan = _parse_plan_json(raw)
    plan["_token_usage"] = usage
    plan["_policy"] = policy

    checks = plan.get("constraint_checks") or []
    if checks:
        summary = ", ".join(
            f"{c.get('rule')}:{'PASS' if c.get('pass') else 'FAIL'}"
            for c in checks[:4]
        )
        print(f"  [Agent 1] constraint checks — {summary}")
    print(f"  [Agent 1] goal_satisfied={plan.get('goal_satisfied')} "
          f"needs_more_search={plan.get('needs_more_search')} — {plan.get('reason', '')[:80]}")

    return plan


def plan_next_turn(
    user_goal: str,
    seller_result: dict,
    buyer_requirements: dict,
    round_num: int,
) -> dict:
    return evaluate_turn(user_goal, seller_result, buyer_requirements, round_num)
