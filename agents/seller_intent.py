"""Backward-compatible shim — use `agents.seller.intent`."""

from agents.seller.intent import parse_buyer_message

__all__ = ["parse_buyer_message"]
