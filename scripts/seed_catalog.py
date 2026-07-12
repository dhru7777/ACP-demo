#!/usr/bin/env python3
"""
Seed Railway Postgres from Nike Kaggle CSV.

Usage (from repo root):
  python scripts/seed_catalog.py scripts/nike_data_2022_09.csv

Requires in local.env:
  DATABASE_URL=postgresql://...@....railway.app:.../railway
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

# Repo root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent

# Load local.env
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / "local.env")
except ImportError:
    pass

import psycopg2
from psycopg2.extras import execute_values

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    sub_title       TEXT,
    price_usd       NUMERIC(10, 2) NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    category        TEXT,
    description     TEXT,
    keywords        TEXT[],
    image_url       TEXT,
    product_url     TEXT,
    availability    TEXT,
    available_sizes TEXT,
    brand           TEXT DEFAULT 'Nike',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

INSERT_SQL = """
INSERT INTO products (
    id, name, sub_title, price_usd, currency, category, description,
    keywords, image_url, product_url, availability, available_sizes, brand, active
) VALUES %s
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    sub_title = EXCLUDED.sub_title,
    price_usd = EXCLUDED.price_usd,
    currency = EXCLUDED.currency,
    category = EXCLUDED.category,
    description = EXCLUDED.description,
    keywords = EXCLUDED.keywords,
    image_url = EXCLUDED.image_url,
    product_url = EXCLUDED.product_url,
    availability = EXCLUDED.availability,
    available_sizes = EXCLUDED.available_sizes,
    brand = EXCLUDED.brand,
    active = EXCLUDED.active;
"""


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL missing — add it to local.env")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "railway.internal" in url:
        raise RuntimeError(
            "DATABASE_URL uses postgres.railway.internal — "
            "use the PUBLIC URL from Railway Connect tab for local seeding."
        )
    return url


def short_description(text: str, max_len: int = 220) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # First sentence-ish chunk
    chunk = re.split(r"[.!?]\s", text, maxsplit=1)[0].strip()
    if len(chunk) > max_len:
        return chunk[: max_len - 3].rstrip() + "..."
    return chunk


def first_image(images: str) -> str | None:
    if not images or not str(images).strip():
        return None
    return str(images).split("|")[0].strip() or None


def infer_category(name: str, sub_title: str, url: str) -> str:
    blob = f"{name} {sub_title} {url}".lower()
    if "basketball" in blob and "shoe" in blob:
        return "basketball"
    if any(w in blob for w in ("running", "runner", "pegasus", "vomero", "invincible")):
        return "running"
    if any(w in blob for w in ("soccer", "football boot", "cleat")):
        return "soccer"
    if "trail" in blob or "hike" in blob:
        return "trail"
    if "golf" in blob:
        return "golf"
    if "sandal" in blob:
        return "sandals"
    if any(w in blob for w in ("kid", "toddler", "big kids", "little kids")):
        return "kids"
    if "shoe" in blob or "sneaker" in blob:
        return "lifestyle"
    if any(w in blob for w in ("jersey", "shirt", "tee", "polo", "hoodie", "jacket", "shorts", "tights")):
        return "apparel"
    return "accessories"


def build_keywords(name: str, sub_title: str, category: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", f"{name} {sub_title}".lower())
    stop = {"nike", "men", "women", "s", "the", "and", "for", "with", "a", "an"}
    words = [t for t in tokens if t not in stop and len(t) > 2]
    if category and category not in words:
        words.append(category)
    # dedupe, keep order
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out[:12]


def is_shoe_row(row: dict) -> bool:
    sub = (row.get("sub_title") or "").lower()
    url = (row.get("url") or "").lower()
    name = (row.get("name") or "").lower()
    return (
        "shoe" in sub
        or "sneaker" in sub
        or "-shoes-" in url
        or "basketball shoes" in sub
    )


def clean_row(row: dict) -> dict | None:
    product_id = (row.get("uniq_id") or "").strip()
    name = (row.get("name") or "").strip()
    if not product_id or not name:
        return None

    try:
        price = float(row.get("price") or 0)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    sub_title = (row.get("sub_title") or "").strip() or None
    currency = (row.get("currency") or "USD").strip() or "USD"
    availability = (row.get("availability") or "").strip() or None
    available_sizes = (row.get("available_sizes") or "").strip() or None
    product_url = (row.get("url") or "").strip() or None
    brand = (row.get("brand") or "Nike").strip() or "Nike"

    category = infer_category(name, sub_title or "", product_url or "")
    description = short_description(row.get("description") or "")
    keywords = build_keywords(name, sub_title or "", category)
    image_url = first_image(row.get("images") or "")

    # Only sell in-stock items in the agent catalog
    active = availability == "InStock"

    return {
        "id": product_id,
        "name": name,
        "sub_title": sub_title,
        "price_usd": price,
        "currency": currency,
        "category": category,
        "description": description,
        "keywords": keywords,
        "image_url": image_url,
        "product_url": product_url,
        "availability": availability,
        "available_sizes": available_sizes,
        "brand": brand,
        "active": active,
    }


def read_csv(path: Path, *, shoes_only: bool = False) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if shoes_only and not is_shoe_row(row):
                continue
            cleaned = clean_row(row)
            if cleaned:
                rows.append(cleaned)
    return rows


def rows_to_tuples(rows: list[dict]) -> list[tuple]:
    return [
        (
            r["id"],
            r["name"],
            r["sub_title"],
            r["price_usd"],
            r["currency"],
            r["category"],
            r["description"],
            r["keywords"],
            r["image_url"],
            r["product_url"],
            r["availability"],
            r["available_sizes"],
            r["brand"],
            r["active"],
        )
        for r in rows
    ]


def seed(csv_path: Path, *, shoes_only: bool = False) -> None:
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    products = read_csv(csv_path, shoes_only=shoes_only)
    if not products:
        raise RuntimeError("No valid rows to insert — check CSV path and filters")

    url = get_database_url()
    conn = psycopg2.connect(url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
                execute_values(cur, INSERT_SQL, rows_to_tuples(products), page_size=100)
        print(f"Seeded {len(products)} products from {csv_path.name}")
        print(f"  shoes_only={shoes_only}")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products;")
            print(f"  total rows in DB: {cur.fetchone()[0]}")
    finally:
        conn.close()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_catalog.py <path-to.csv> [--shoes-only]")
        raise SystemExit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.is_absolute():
        csv_path = (REPO_ROOT / csv_path).resolve()

    shoes_only = "--shoes-only" in sys.argv[2:]
    seed(csv_path, shoes_only=shoes_only)


if __name__ == "__main__":
    main()