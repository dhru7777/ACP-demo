#!/usr/bin/env python3
"""
Payment rails smoke + integration checks.

Default target: http://127.0.0.1:8002 (local seller).
Override with SELLER_URL for Railway / staging.

  python scripts/test_payments.py
  SELLER_URL=https://acp-demo-production.up.railway.app python scripts/test_payments.py
  python scripts/test_payments.py --live-escrow   # on-chain deposit+cancel (needs local.env keys)
  python scripts/test_payments.py --live-stripe   # Stripe test charge (needs STRIPE_SECRET_KEY)

Exit 0 only if required route/module checks pass.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_SELLER = os.environ.get("SELLER_URL", "http://127.0.0.1:8002").rstrip("/")

DEMO_OFFER = {
    "id": "pay-test-offer-pegasus",
    "name": "Nike Air Pegasus 83 Premium",
    "price": 89.97,
    "currency": "USD",
    "category": "running",
}


def _req(method: str, path: str, body: dict | None = None, timeout: float = 60.0) -> tuple[int, dict | str]:
    url = f"{DEFAULT_SELLER}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": str(getattr(e, "reason", None) or e)}


def _ok(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def check_local_imports() -> bool:
    print("\n== Local Python imports ==")
    ok = True
    try:
        import stripe  # noqa: F401
        ok = _ok("import stripe", True, getattr(stripe, "VERSION", "?")) and ok
    except Exception as e:
        ok = _ok("import stripe", False, str(e)) and ok

    try:
        from payments import escrow_service, stripe_service, x402_service  # noqa: F401
        ok = _ok("import payments escrow/stripe/x402", True) and ok
    except Exception as e:
        ok = _ok("import payments escrow/stripe/x402", False, str(e)) and ok
    return ok


def check_seller_health() -> bool:
    print(f"\n== Seller health ({DEFAULT_SELLER}) ==")
    code, body = _req("GET", "/", timeout=15)
    if not _ok("GET /", code == 200, f"HTTP {code}"):
        print(f"       body={body!r}")
        return False
    if isinstance(body, dict):
        print(f"       agent={body.get('agent')} catalog={body.get('catalogCount')} source={body.get('catalogSource')}")
    return True


def check_payment_routes() -> bool:
    print("\n== Payment routes present ==")
    ok = True

    # Prefer dedicated health endpoint when deployed
    code, health = _req("GET", "/demo/payments/health", timeout=15)
    if code == 200 and isinstance(health, dict) and "rails" in health:
        rails = health["rails"]
        ok = _ok("GET /demo/payments/health", True) and ok
        escrow = rails.get("escrow") or {}
        stripe = rails.get("stripe") or {}
        ok = _ok("escrow routes registered", bool(escrow.get("ready")), str(escrow.get("routes"))) and ok
        ok = _ok("stripe module on server", bool(stripe.get("module")), stripe.get("error") or "") and ok
        return ok

    if code == 404:
        print("  [WARN] /demo/payments/health missing — probing execute endpoints")
    else:
        print(f"  [WARN] health HTTP {code}: {health!r}")

    # Probe: missing offerId → 400 means route exists; FastAPI detail Not Found → missing
    probes = [
        ("POST", "/demo/escrow/execute", {"offer": DEMO_OFFER, "offerId": DEMO_OFFER["id"], "requireIntent": False}),
        ("POST", "/demo/stripe/execute", {"offer": DEMO_OFFER, "offerId": DEMO_OFFER["id"], "requireIntent": False}),
        ("POST", "/demo/x402/execute", {"offer": DEMO_OFFER, "offerId": DEMO_OFFER["id"], "requireIntent": False}),
        ("POST", "/demo/escrow/confirm", {}),
        ("POST", "/demo/escrow/cancel", {}),
    ]
    for method, path, body in probes:
        code, resp = _req(method, path, body, timeout=30)
        missing = code == 404 and isinstance(resp, dict) and resp.get("detail") == "Not Found"
        # Escrow/stripe may 500 for chain/keys — that still proves the route exists
        exists = not missing and code != 0
        detail = f"HTTP {code}"
        if isinstance(resp, dict):
            detail += f" err={resp.get('error') or resp.get('detail') or resp.get('status')}"
        ok = _ok(f"{method} {path}", exists, detail) and ok
        if path == "/demo/stripe/execute" and isinstance(resp, dict):
            err = str(resp.get("error") or "")
            if "No module named 'stripe'" in err or "Stripe SDK missing" in err:
                ok = _ok("stripe package installed on server", False, err) and ok
    return ok


def check_escrow_quote_via_session() -> bool:
    print("\n== Escrow quote (session + commerce/pay) ==")
    code, init = _req("POST", "/", {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": 1, "clientInfo": {"name": "pay-test", "version": "1"}},
    }, timeout=30)
    if code != 200:
        return _ok("initialize", False, f"HTTP {code} {init!r}")

    code, sess = _req("POST", "/", {
        "jsonrpc": "2.0", "id": 2, "method": "session/new",
        "params": {"cwd": "/tmp", "mcpServers": []},
    }, timeout=30)
    if code != 200 or not isinstance(sess, dict) or "result" not in sess:
        return _ok("session/new", False, f"HTTP {code} {sess!r}")
    session_id = sess["result"].get("sessionId")
    if not session_id:
        return _ok("sessionId", False, str(sess))

    code, quote = _req("POST", "/", {
        "jsonrpc": "2.0", "id": 3, "method": "commerce/pay",
        "params": {
            "sessionId": session_id,
            "offerId": DEMO_OFFER["id"],
            "offer": DEMO_OFFER,
            "payment_method": "escrow",
        },
    }, timeout=60)
    if code != 200 or not isinstance(quote, dict):
        return _ok("commerce/pay escrow quote", False, f"HTTP {code} {quote!r}")
    if quote.get("error"):
        return _ok("commerce/pay escrow quote", False, str(quote["error"]))
    result = quote.get("result") or {}
    status = result.get("status")
    rail = result.get("rail")
    usdc = (result.get("fx") or {}).get("usdc")
    return _ok(
        "commerce/pay escrow quote",
        status == "payment_required" and rail == "escrow" and bool(usdc),
        f"status={status} rail={rail} usdc={usdc}",
    )


def live_escrow() -> bool:
    print("\n== Live escrow deposit → cancel (on-chain) ==")
    try:
        from payments import config as _config  # noqa: F401
        from payments import escrow_service
    except Exception as e:
        return _ok("load escrow_service", False, str(e))

    import asyncio

    async def _run() -> bool:
        funded = await escrow_service.execute_deposit(
            DEMO_OFFER["price"],
            offer_id=DEMO_OFFER["id"],
            offer_name=DEMO_OFFER["name"],
            session_id="pay-test-live-escrow",
        )
        if funded.get("status") != "escrow_funded":
            return _ok("deposit", False, str(funded))
        escrow = (funded.get("receipt") or {}).get("escrow")
        ok = _ok("deposit", True, f"escrow={escrow} held={(funded.get('receipt') or {}).get('usdcHeld')}")
        cancelled = await escrow_service.execute_cancel(
            session_id="pay-test-live-escrow",
            offer_id=DEMO_OFFER["id"],
            escrow=escrow,
        )
        ok = _ok("cancel/refund", cancelled.get("status") == "cancelled", str(cancelled.get("status"))) and ok
        return ok

    return asyncio.run(_run())


def live_stripe() -> bool:
    print("\n== Live Stripe test charge ==")
    try:
        from payments import stripe_service
    except Exception as e:
        return _ok("load stripe_service", False, str(e))

    import asyncio

    async def _run() -> bool:
        result = await stripe_service.execute_payment(
            DEMO_OFFER["price"], DEMO_OFFER["id"], DEMO_OFFER["name"]
        )
        return _ok(
            "stripe charge",
            result.get("status") == "paid",
            f"status={result.get('status')} pi={(result.get('receipt') or {}).get('paymentIntentId')}",
        )

    return asyncio.run(_run())


def main() -> int:
    parser = argparse.ArgumentParser(description="Payment rails smoke tests")
    parser.add_argument("--live-escrow", action="store_true", help="Run on-chain escrow deposit+cancel")
    parser.add_argument("--live-stripe", action="store_true", help="Run Stripe test PaymentIntent")
    parser.add_argument("--skip-imports", action="store_true", help="Skip local import checks")
    args = parser.parse_args()

    print(f"SELLER_URL={DEFAULT_SELLER}")
    failed = False

    if not args.skip_imports and not check_local_imports():
        failed = True

    if not check_seller_health():
        print("\nSeller not reachable. Start locally:\n  source venv/bin/activate && python seller_agent.py")
        return 1

    if not check_payment_routes():
        failed = True

    if not check_escrow_quote_via_session():
        failed = True

    if args.live_escrow and not live_escrow():
        failed = True
    if args.live_stripe and not live_stripe():
        failed = True

    print("\n" + ("ALL CHECKS PASSED" if not failed else "SOME CHECKS FAILED"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
