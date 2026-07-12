"""
Postgres-backed catalog search — drop-in replacement for CatalogSearch.
"""

from __future__ import annotations

from catalog import db as catalog_db


class PostgresCatalogSearch:
    """Queries Railway Postgres per database_calling skill."""

    def search(self, query: str, max_price: float | None = None, top_k: int = 3) -> list[dict]:
        if max_price is None:
            return []
        return catalog_db.search_products(query=query, max_price=float(max_price), top_k=top_k)

    def get(self, item_id: str) -> dict | None:
        row = catalog_db.get_product(item_id)
        if row is None:
            return None
        return {
            "name": row["name"],
            "price": row["price"],
            "currency": row["currency"],
            "category": row.get("category"),
            "description": row["description"],
            "image_url": row.get("image_url"),
            "product_url": row.get("product_url"),
            "available_sizes": row.get("available_sizes"),
        }

    def count(self) -> int:
        return catalog_db.catalog_stats()["total_items"]

    def summary(self) -> dict:
        return catalog_db.catalog_stats()
