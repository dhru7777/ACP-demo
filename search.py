"""Backward-compatible shim — use `from catalog import catalog_search`."""

from catalog.search import CatalogSearch, catalog_search

__all__ = ["CatalogSearch", "catalog_search"]
