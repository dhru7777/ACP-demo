"""
CATALOG SEARCH — Modular Search Layer
======================================
Current backend: in-memory keyword overlap + difflib fuzzy matching.

How to swap to Vector DB (Phase 4+):
  1. Add a new class: `PineconeSearch(CatalogSearch)`
  2. Override `_search_impl()` with a Pinecone/pgvector query
  3. In seller_agent.py: `catalog_search = PineconeSearch(CATALOG)`
  
  The rest of the codebase (seller_agent.py, session/prompt handler)
  stays identical — it only calls `catalog_search.search(...)`.

How to add MCP tool access (Phase 4+):
  - Wrap `_search_impl()` to call an MCP tool: `search_inventory(query)`
  - MCP server connects to a cloud vector DB and returns ranked results

Public interface (never changes):
  catalog_search.search(query, max_price, top_k) → list[dict]
  catalog_search.get(item_id)                     → dict | None
  catalog_search.count()                           → int
  catalog_search.summary()                         → dict
"""

import re
from difflib import SequenceMatcher
from catalog.data import CATALOG, get_catalog_summary


class CatalogSearch:
    """
    In-memory fuzzy search over the Nike catalog.
    Designed as a drop-in interface for future vector DB or MCP replacement.
    """

    def __init__(self, catalog: dict):
        self._catalog = catalog

    # ------------------------------------------------------------------
    # PUBLIC INTERFACE — these signatures stay stable across backends
    # ------------------------------------------------------------------

    def search(self, query: str, max_price: float | None = None, top_k: int = 3) -> list[dict]:
        """
        Find the best matching items for a natural-language query.

        Args:
            query:     Natural language string, e.g. "comfortable running shoe"
            max_price: Optional budget ceiling in USD. Items above this are excluded.
            top_k:     Maximum number of results to return (default 3).

        Returns:
            List of matched item dicts, sorted by relevance score descending.
            Each item includes an added 'id' and 'score' field.
        """
        return self._search_impl(query, max_price, top_k)

    def get(self, item_id: str) -> dict | None:
        """Look up a specific item by its catalog ID."""
        return self._catalog.get(item_id)

    def count(self) -> int:
        """Total number of items in the catalog."""
        return len(self._catalog)

    def summary(self) -> dict:
        """Stats summary — safe to expose to clients (no item list)."""
        return get_catalog_summary()

    # ------------------------------------------------------------------
    # CURRENT BACKEND — replace this method to swap search engines
    # ------------------------------------------------------------------

    def _search_impl(self, query: str, max_price: float | None, top_k: int) -> list[dict]:
        """
        In-memory search using:
          - Keyword token overlap  (weight: 0.65) — catches exact term matches
          - Difflib name similarity (weight: 0.25) — catches partial name matches
          - Category boost          (weight: 0.10) — if query contains category name
          
        Future: replace this body with a Pinecone/pgvector API call.
        The return format must stay the same.
        """
        query_lower = query.lower()
        query_tokens = set(re.findall(r'\w+', query_lower))

        scored = []
        for item_id, item in self._catalog.items():

            # Hard filter — skip items over budget
            if max_price is not None and item["price"] > max_price:
                continue

            keywords    = set(item["keywords"])
            item_name   = item["name"].lower()
            item_cat    = item["category"].lower()

            # 1. Keyword overlap — what fraction of query tokens match keywords
            overlap = len(query_tokens & keywords) / max(len(query_tokens), 1)

            # 2. Name similarity — fuzzy string match on display name
            name_sim = SequenceMatcher(None, query_lower, item_name).ratio()

            # 3. Category boost — if the user mentions the category explicitly
            cat_boost = 0.10 if item_cat in query_lower else 0.0

            score = (overlap * 0.65) + (name_sim * 0.25) + cat_boost

            # Only include items with at least some relevance
            if score > 0.05:
                scored.append((score, item_id, item))

        # Sort by score descending, return top_k
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id":          item_id,
                "name":        item["name"],
                "price":       item["price"],
                "currency":    item["currency"],
                "category":    item["category"],
                "description": item["description"],
                "score":       round(score, 3)
            }
            for score, item_id, item in scored[:top_k]
        ]


# Singleton — Postgres when DATABASE_URL is set, else in-memory fallback
def _make_catalog_search():
    import os
    from pathlib import Path
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / "local.env")
    except ImportError:
        pass
    if os.environ.get("DATABASE_URL", "").strip():
        try:
            from catalog.postgres_search import PostgresCatalogSearch
            ps = PostgresCatalogSearch()
            n = ps.count()
            print(f"  [Catalog] Postgres backend — {n} active products")
            return ps
        except Exception as e:
            print(f"  [Catalog] Postgres unavailable ({e}) — falling back to in-memory")
    return CatalogSearch(CATALOG)


catalog_search = _make_catalog_search()
