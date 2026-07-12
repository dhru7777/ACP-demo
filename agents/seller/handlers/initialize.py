"""ACP JSON-RPC handlers — initialize handshake."""

from __future__ import annotations

from catalog import catalog_search


def handle_initialize(id_, params: dict, connected_clients: dict, stripe_connect_enabled: bool) -> dict:
    client_info = params.get("clientInfo", {})
    client_caps = params.get("clientCapabilities", {})
    client_name = client_info.get("name", "unknown-client")

    connected_clients[client_name] = {
        "protocolVersion": params.get("protocolVersion", 1),
        "capabilities": client_caps,
    }

    print(f"  Initialized with: '{client_name}' v{client_info.get('version', '?')}")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {
            "protocolVersion": 1,
            "agentInfo": {
                "name":    "nike-seller-agent",
                "title":   "Nike Seller Agent",
                "version": "2.0.0",
            },
            "agentCapabilities": {
                "loadSession": True,
                "sessionCapabilities": {
                    "resume": {},
                    "close":  {},
                },
                "commerce": {
                    "canSell":            True,
                    "itemCount":          catalog_search.count(),
                    "categories":         list(catalog_search.summary()["categories"].keys()),
                    "acceptedCurrencies": ["USD"],
                    "negotiation":        False,
                },
                "payment": {
                    "stripe":        True,
                    "stripeConnect": bool(stripe_connect_enabled()),
                    "x402":          True,
                },
                "mcpCapabilities": {
                    "http": False,
                    "sse":  False,
                },
            },
            "authMethods": [],
        },
    }
