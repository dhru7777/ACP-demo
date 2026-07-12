"""
Shared buyer requirements model for clarification + search.

Used by seller_agent (session/prompt) and agents/orchestrator (buyer loop).
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

REQUIRED_FIELDS = ("query", "max_price")
OPTIONAL_FIELDS = ("category", "style", "size")
FIELD_PRIORITY = ("query", "max_price", "category", "style", "size")

QUESTIONS: dict[str, str] = {
    "query": "What kind of Nike shoe are you shopping for today?",
    "max_price": "What's your budget for this purchase?",
    "category": "Are you looking for running, basketball, lifestyle, or another category?",
    "style": "Any style preference — cushioned, lightweight, or stability?",
    "size": "What size do you need?",
}

CATEGORIES = frozenset({
    "running", "lifestyle", "training", "basketball", "trail",
    "soccer", "golf", "sandals", "kids", "apparel", "accessories",
})


def empty_requirements() -> dict[str, Any]:
    return {
        "query": None,
        "max_price": None,
        "category": None,
        "style": None,
        "size": None,
    }


def extract_budget(text: str) -> float | None:
    """Pull max price from natural language."""
    t = text.lower()
    patterns = [
        r"\$\s*(\d+(?:\.\d+)?)",
        r"budget\s+(?:of\s+)?(\d+(?:\.\d+)?)",
        r"under\s+\$?\s*(\d+(?:\.\d+)?)",
        r"at\s+\$?\s*(\d+(?:\.\d+)?)",
        r"max\s+\$?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*dollars?",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            return float(m.group(1))
    return None


def extract_size(text: str) -> str | None:
    t = text.lower()
    if extract_budget(text) is not None and not re.search(r"size\s+\d", t):
        return None
    m = re.search(r"size\s+(?:us\s+)?(\d+(?:\.\d+)?)\b", t)
    if m:
        return m.group(1)
    return None


def _is_budget_only_message(text: str) -> bool:
    t = text.lower().strip()
    if extract_budget(text) is None:
        return False
    stripped = t
    for pat in (
        r"\$\s*\d+(?:\.\d+)?",
        r"under\s+\$?\s*\d+(?:\.\d+)?",
        r"budget\s+(?:of\s+)?\d+(?:\.\d+)?",
        r"max\s+\$?\s*\d+(?:\.\d+)?",
        r"\d+(?:\.\d+)?\s*dollars?",
        r"my\s+budget\s+is",
    ):
        stripped = re.sub(pat, "", stripped, flags=re.I)
    stripped = re.sub(r"[^\w\s]", " ", stripped)
    return len(stripped.split()) <= 2


def extract_category(text: str) -> str | None:
    t = text.lower()
    for cat in CATEGORIES:
        if cat in t:
            return cat
    return None


def extract_style(text: str) -> str | None:
    styles = ("cushioned", "lightweight", "stability", "neutral", "plush", "support")
    t = text.lower()
    for s in styles:
        if s in t:
            return s
    return None


def regex_extract(text: str) -> dict[str, Any]:
    """Lightweight extraction without LLM."""
    budget = extract_budget(text)
    category = extract_category(text)
    size = extract_size(text)
    style = extract_style(text)

    if _is_budget_only_message(text):
        return {
            "query": None,
            "max_price": budget,
            "category": category,
            "style": style,
            "size": size,
        }

    query = text.strip()
    if budget is not None:
        query = re.sub(r"\$\s*\d+(?:\.\d+)?", "", query, flags=re.I)
        query = re.sub(r"under\s+\$?\s*\d+(?:\.\d+)?", "", query, flags=re.I)
        query = re.sub(r"budget\s+(?:of\s+)?\d+(?:\.\d+)?", "", query, flags=re.I)
    query = " ".join(query.split()).strip() or None
    return {
        "query": query,
        "max_price": budget,
        "category": category,
        "style": style,
        "size": size,
    }


def merge_requirements(base: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch into base; non-null patch values win."""
    out = deepcopy(base) if base else empty_requirements()
    for key in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
        val = patch.get(key)
        if val is None:
            continue
        if key == "query" and isinstance(val, str) and not val.strip():
            continue
        if key == "max_price":
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if val <= 0:
                continue
        out[key] = val
    return out


def missing_fields(req: dict[str, Any]) -> list[str]:
    """Required fields only — search blocked until these are set."""
    out: list[str] = []
    if not (req.get("query") or "").strip():
        out.append("query")
    price = req.get("max_price")
    if price is None:
        out.append("max_price")
    else:
        try:
            if float(price) <= 0:
                out.append("max_price")
        except (TypeError, ValueError):
            out.append("max_price")
    return [f for f in FIELD_PRIORITY if f in out]


def clarification_question(missing: list[str], parsed_message: str | None = None) -> str:
    if parsed_message and parsed_message.strip():
        return parsed_message.strip()
    if not missing:
        return "Could you tell me a bit more about what you're looking for?"
    return QUESTIONS.get(missing[0], QUESTIONS["query"])


def requirements_satisfied(req: dict[str, Any]) -> bool:
    return len(missing_fields(req)) == 0


def requirements_for_intent(req: dict[str, Any]) -> dict[str, Any]:
    """Public subset for parsedIntent / API responses."""
    return {
        "query": req.get("query"),
        "max_price": req.get("max_price"),
        "category": req.get("category"),
        "style": req.get("style"),
        "size": req.get("size"),
    }
