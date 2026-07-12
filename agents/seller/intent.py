"""
Seller-side intent parsing (Agent 2) — Anthropic preferred, OpenAI fallback.

Returns structured requirements + missing_fields per clarification skill.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agents.shared.token_usage import (
    record_turn,
    usage_from_anthropic,
    usage_from_openai,
)
from agents.shared.requirements import (
    clarification_question,
    empty_requirements,
    extract_budget,
    merge_requirements,
    missing_fields,
    regex_extract,
    requirements_for_intent,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_OPENAI_CLIENT = None
_ANTHROPIC_CLIENT = None

_SYSTEM = """You parse buyer messages for a Nike shoe seller agent.

Respond ONLY with a single JSON object (no markdown):
{
  "query": "brief product intent or empty if only answering budget",
  "max_price": null or number,
  "category": null or one of: running, lifestyle, training, basketball, trail, soccer, golf, sandals, kids, apparel, accessories,
  "style": null or short style hint,
  "size": null or string,
  "response_message": "one short sentence — clarification question OR acknowledgment"
}

Rules:
- Extract budget from $ amounts, "under X", "budget of X"
- If message is ONLY a budget reply, keep query empty (session has prior query)
- If query or budget still unknown, response_message must ask for the most important missing piece
- One sentence only for response_message
- Raw JSON only"""


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO_ROOT / "local.env")
    except ImportError:
        pass


def _openai_key() -> str | None:
    _load_env()
    return (os.environ.get("OPENAI_API_KEY") or os.environ.get("OpenAI_API_KEY") or "").strip() or None


def _anthropic_key() -> str | None:
    _load_env()
    return (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("Intent_Parsing_Anthropic") or "").strip() or None


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


def _history_messages(history: list) -> list[dict]:
    messages = []
    for entry in history[-4:]:
        role = entry.get("role", "")
        content = entry.get("content", {})
        if role == "buyer" and "text" in content:
            messages.append({"role": "user", "content": content["text"]})
        elif role == "seller":
            q = content.get("question") or content.get("message")
            if q:
                messages.append({"role": "assistant", "content": q})
    return messages


def parse_buyer_message(
    text: str,
    history: list,
    prior_requirements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Parse latest buyer message and merge with prior session requirements.
    Returns requirements, missing_fields, needs_clarification, response_message, llm provider used.
    """
    prior = prior_requirements or empty_requirements()
    provider = "regex"

    parsed: dict[str, Any] = {}
    usage_payload: dict[str, Any] | None = None
    okey = _openai_key()
    akey = _anthropic_key()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

    if akey:
        try:
            parsed, usage_payload = _call_anthropic(text, history, akey, model)
            provider = "anthropic"
        except Exception as e:
            print(f"  [Anthropic] Error: {e}")

    if not parsed and okey:
        try:
            openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            parsed, usage_payload = _call_openai(text, history, okey, openai_model)
            provider = "openai"
            model = openai_model
        except Exception as e:
            print(f"  [OpenAI] Error: {e}")

    if not parsed:
        parsed = regex_extract(text)
        provider = "regex"
        usage_payload = record_turn(
            None, provider="regex", model="regex", input_tokens=0, output_tokens=0, agent="seller",
        )

    # Regex budget override
    budget = extract_budget(text)
    if budget is not None:
        parsed["max_price"] = budget

    if not (parsed.get("query") or "").strip() and prior.get("query"):
        parsed["query"] = prior["query"]

    requirements = merge_requirements(prior, parsed)
    missing = missing_fields(requirements)
    needs = len(missing) > 0

    msg = parsed.get("response_message") or ""
    if needs:
        msg = clarification_question(missing, msg)

    return {
        "requirements": requirements,
        "missing_fields": missing,
        "needs_clarification": needs,
        "response_message": msg,
        "llm_provider": provider,
        "llm_model": model,
        "parsed_intent": requirements_for_intent(requirements),
        "token_usage": usage_payload,
    }


def _call_openai(text: str, history: list, api_key: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        from openai import OpenAI
        _OPENAI_CLIENT = OpenAI(api_key=api_key)

    messages = [{"role": "system", "content": _SYSTEM}]
    messages.extend(_history_messages(history))
    messages.append({"role": "user", "content": text})

    resp = _OPENAI_CLIENT.chat.completions.create(
        model=model,
        max_tokens=300,
        messages=messages,
        temperature=0.2,
    )
    raw = _strip_json(resp.choices[0].message.content or "")
    inp, out = usage_from_openai(resp, model)
    usage = record_turn(
        None, provider="openai", model=model, input_tokens=inp, output_tokens=out, agent="seller",
    )
    return json.loads(raw), usage


def _call_anthropic(text: str, history: list, api_key: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    global _ANTHROPIC_CLIENT
    if _ANTHROPIC_CLIENT is None:
        import anthropic
        _ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=api_key)

    messages = _history_messages(history)
    messages.append({"role": "user", "content": text})

    resp = _ANTHROPIC_CLIENT.messages.create(
        model=model,
        max_tokens=300,
        system=_SYSTEM,
        messages=messages,
    )
    raw = _strip_json(resp.content[0].text)
    inp, out = usage_from_anthropic(resp)
    usage = record_turn(
        None, provider="anthropic", model=model, input_tokens=inp, output_tokens=out, agent="seller",
    )
    return json.loads(raw), usage
