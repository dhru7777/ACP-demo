"""Backward-compatible shim — use `from catalog import catalog_search`."""

from catalog.data import CATALOG, get_catalog_summary
from catalog.search import CatalogSearch, catalog_search

__all__ = ["CATALOG", "get_catalog_summary", "CatalogSearch", "catalog_search"]
