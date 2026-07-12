"""
Agent 1 ↔ Agent 2 orchestrator — agentic conversation until buyer goal is met.

The buyer agent (Anthropic) decides satisfaction by cross-checking offers against
constraints — no score thresholds or deterministic early exits.

Usage:
  python -m agents.buyer.orchestrator "cushioned running shoes under $150"
  python -m agents.orchestrator "..."   # backward-compatible shim
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / "local.env")
except ImportError:
    pass

from agents.buyer.acp_client import post, seller_url, session_prompt
from agents.buyer.evaluator import evaluate_turn, regex_reply_from_goal
from agents.shared.requirements import empty_requirements, merge_requirements, regex_extract

MAX_CLARIFICATION_ROUNDS = 6
MAX_SEARCH_RETRIES = 3


def _apply_plan_message(plan: dict, user_goal: str, missing: list[str]) -> str:
    message = (plan.get("reply_to_seller") or "").strip()
    if not message:
        message = regex_reply_from_goal(user_goal, missing)
    return message


def run_conversation(user_goal: str, verbose: bool = True) -> dict:
    if verbose:
        print("=" * 60)
        print(" AGENT 1 ↔ AGENT 2 — Agentic conversation")
        print(f" Goal: {user_goal}")
        print("=" * 60)

    init = post("initialize", {
        "protocolVersion": 1,
        "clientInfo": {"name": "buyer-agent", "title": "Nike Buyer Agent", "version": "1.0.0"},
        "clientCapabilities": {"fs": {"readTextFile": True}, "terminal": False},
    })
    if "error" in init:
        raise RuntimeError(init["error"]["message"])

    sess = post("session/new", {"buyerId": "buyer-agent-orchestrator", "cwd": str(_REPO_ROOT)})
    if "error" in sess:
        raise RuntimeError(sess["error"]["message"])
    session_id = sess["result"]["sessionId"]
    if verbose:
        print(f"\n  Session: {session_id}")

    buyer_req = merge_requirements(empty_requirements(), regex_extract(user_goal))
    if not buyer_req.get("query"):
        buyer_req["query"] = user_goal.strip()
    message = user_goal
    last_result: dict = {}
    last_plan: dict = {}
    clarification_rounds = 0
    search_retries = 0
    round_num = 0

    while True:
        round_num += 1
        if verbose:
            print(f"\n[Agent 1 → Seller] {message[:120]}")

        last_result = session_prompt(session_id, message)
        stop = last_result.get("stopReason", "")
        if verbose:
            print(f"[Seller → Agent 1] {stop}: {last_result.get('agentMessage', '')[:120]}")
            if last_result.get("offers"):
                print(f"  Offers: {len(last_result['offers'])} item(s)")

        if stop == "needs_clarification":
            clarification_rounds += 1
            if clarification_rounds > MAX_CLARIFICATION_ROUNDS:
                if verbose:
                    print("\n  Max clarification rounds reached.")
                break

            missing = last_result.get("missing_fields") or ["max_price"]
            try:
                last_plan = evaluate_turn(user_goal, last_result, buyer_req, round_num)
                message = _apply_plan_message(last_plan, user_goal, missing)
                buyer_req = merge_requirements(buyer_req, last_plan.get("requirements_update") or {})
            except Exception as e:
                if verbose:
                    print(f"  [Agent 1 LLM fallback] {e}")
                message = regex_reply_from_goal(user_goal, missing)

            if message.startswith("NEED_USER:"):
                need = message[len("NEED_USER:"):].strip()
                if verbose:
                    print(f"\n  Seller needs: {need}")
                try:
                    message = input("  Your answer: ").strip()
                except EOFError:
                    break
                if not message:
                    break
            continue

        if stop == "end_turn":
            try:
                last_plan = evaluate_turn(user_goal, last_result, buyer_req, round_num)
                buyer_req = merge_requirements(buyer_req, last_plan.get("requirements_update") or {})
            except Exception as e:
                if verbose:
                    print(f"  [Agent 1 eval error] {e}")
                break

            if last_plan.get("goal_satisfied"):
                if verbose:
                    print("\n  Agent 1: goal satisfied — offers pass constraint checks.")
                break

            if not last_plan.get("needs_more_search"):
                if verbose:
                    print(f"\n  Agent 1: stopping — {last_plan.get('reason', 'not satisfied')}")
                break

            search_retries += 1
            if search_retries >= MAX_SEARCH_RETRIES:
                if verbose:
                    print("\n  Max search retries reached.")
                break

            message = _apply_plan_message(
                last_plan,
                user_goal,
                last_result.get("missing_fields") or [],
            )
            if not message or message.startswith("NEED_USER:"):
                if verbose:
                    print(f"\n  Agent 1 needs user input: {message}")
                break
            if verbose:
                print(f"  Agent 1 re-search: {message[:120]}")
            continue

        break

    if verbose:
        print("\n" + "=" * 60)
        print(" CONVERSATION COMPLETE")
        if last_plan.get("constraint_checks"):
            for check in last_plan["constraint_checks"][:5]:
                status = "PASS" if check.get("pass") else "FAIL"
                print(f"  {check.get('rule')}: {status} — {check.get('detail', '')}")
        if last_result.get("offers"):
            top = last_result["offers"][0]
            print(f" Best match: {top.get('name')} — ${top.get('price')} (score {top.get('score')})")
        print("=" * 60)

    return {
        "session_id": session_id,
        "user_goal": user_goal,
        "final_result": last_result,
        "final_plan": last_plan,
        "clarification_rounds": clarification_rounds,
        "search_retries": search_retries,
    }


def main():
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
    else:
        print("Nike Buyer Agent — enter your shopping goal:")
        goal = sys.stdin.readline().strip()
        if not goal:
            goal = "comfortable running shoes under $150"

    try:
        run_conversation(goal)
    except requests.ConnectionError:
        print(f"Cannot reach seller at {seller_url()} — start with: python seller_agent.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
