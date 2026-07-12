"""
Postgres catalog access — database_calling skill implementation.

Single entry point: search_products() / get_product()
Called only AFTER clarification requirements are satisfied.
"""

from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / "local.env")
except ImportError:
    pass


def get_database_url() -> str | None:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        return None
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "railway.internal" in url:
        return None
    return url


def _connect():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL not configured — cannot query Postgres catalog")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def _query_tokens(query: str) -> set[str]:
    stop = {"i", "want", "need", "a", "an", "the", "for", "my", "some", "shoe", "shoes", "nike"}
    return {t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in stop and len(t) > 2}


def _score_row(query_lower: str, query_tokens: set[str], row: dict) -> float:
    """Query-token search only — no category filter or category boost."""
    keywords = set(row.get("keywords") or [])
    name = (row.get("name") or "").lower()
    sub = (row.get("sub_title") or "").lower()
    desc = (row.get("description") or "").lower()

    searchable = keywords | set(re.findall(r"[a-z0-9]+", f"{name} {sub}"))
    overlap = len(query_tokens & searchable) / max(len(query_tokens), 1)
    name_sim = SequenceMatcher(None, query_lower, name).ratio()
    desc_hit = 0.10 if query_tokens and any(t in desc for t in query_tokens) else 0.0

    return (overlap * 0.65) + (name_sim * 0.25) + desc_hit


def _row_to_result(row: dict, score: float) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "sub_title": row.get("sub_title"),
        "price": float(row["price_usd"]),
        "currency": row.get("currency") or "USD",
        "category": row.get("category"),
        "description": row.get("description") or "",
        "keywords": row.get("keywords") or [],
        "image_url": row.get("image_url"),
        "product_url": row.get("product_url"),
        "availability": row.get("availability"),
        "available_sizes": row.get("available_sizes"),
        "brand": row.get("brand") or "Nike",
        "score": round(score, 3),
    }


def search_products(
    query: str,
    max_price: float,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """
    Query Postgres products table — ranked by relevance, no category hard-filter.
    Per agents/skills/database_calling/SKILL.md
    """
    query = (query or "").strip()
    if not query:
        return []
    if max_price is None or max_price <= 0:
        return []

    query_lower = query.lower()
    query_tokens = _query_tokens(query)
    if not query_tokens:
        query_tokens = set(re.findall(r"[a-z0-9]+", query_lower))

    sql = """
        SELECT id, name, sub_title, price_usd, currency, category, description,
               keywords, image_url, product_url, availability, available_sizes, brand
        FROM products
        WHERE active = true
          AND price_usd <= %s
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (max_price,))
            rows = cur.fetchall()

    scored: list[tuple[float, dict]] = []
    for row in rows:
        score = _score_row(query_lower, query_tokens, dict(row))
        if score > 0.05:
            scored.append((score, dict(row)))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_row_to_result(row, score) for score, row in scored[:top_k]]


def get_product(product_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, sub_title, price_usd, currency, category, description,
                       keywords, image_url, product_url, availability, available_sizes, brand
                FROM products
                WHERE id = %s AND active = true
                """,
                (product_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return _row_to_result(dict(row), 1.0)


def catalog_stats() -> dict[str, Any]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM products WHERE active = true")
            total = int(cur.fetchone()["n"])
            cur.execute(
                """
                SELECT COALESCE(category, 'unknown') AS cat, COUNT(*) AS n
                FROM products WHERE active = true
                GROUP BY category ORDER BY n DESC
                """
            )
            cats = {r["cat"]: int(r["n"]) for r in cur.fetchall()}
            cur.execute(
                "SELECT MIN(price_usd) AS lo, MAX(price_usd) AS hi FROM products WHERE active = true"
            )
            pr = cur.fetchone()
    return {
        "total_items": total,
        "categories": cats,
        "price_range": {"min": float(pr["lo"] or 0), "max": float(pr["hi"] or 0)},
        "source": "postgres",
    }
