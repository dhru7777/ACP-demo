"""Nike product catalog — in-memory data + search layer."""

from catalog.data import CATALOG, get_catalog_summary
from catalog.search import CatalogSearch, catalog_search
from catalog.db import search_products, get_product

__all__ = [
    "CATALOG", "get_catalog_summary", "CatalogSearch", "catalog_search",
    "search_products", "get_product",
]
