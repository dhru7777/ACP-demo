#!/usr/bin/env python3
"""
Escrow payment failure matrix — 10 ways the rail should fail (plus one soft-pass).

Default: http://127.0.0.1:8002
  SELLER_URL=https://acp-demo-production.up.railway.app python scripts/test_escrow_failures.py

Exit 0 if all expected failures behave correctly.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SELLER = os.environ.get("SELLER_URL", "http://127.0.0.1:8002").rstrip("/")

OFFER = {
    "id": "escrow-fail-matrix-pegasus",
    "name": "Nike Air Pegasus 83 Premium",
    "price": 89.97,
    "currency": "USD",
    "category": "running",
}


def _req(method: str, path: str, body: dict | None = None, timeout: float = 90.0) -> tuple[int, dict]:
    url = f"{SELLER}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {"error": raw}
    except Exception as e:
        return 0, {"error": str(e)}


def _rpc(method: str, params: dict, id_: int = 1) -> tuple[int, dict]:
    return _req("POST", "/", {"jsonrpc": "2.0", "id": id_, "method": method, "params": params})


def _new_session() -> str:
    _rpc("initialize", {"protocolVersion": 1, "clientInfo": {"name": "escrow-fail", "version": "1"}})
    code, sess = _rpc("session/new", {"cwd": "/tmp", "mcpServers": []}, id_=2)
    if code != 200 or not isinstance(sess.get("result"), dict):
        raise RuntimeError(f"session/new failed: {code} {sess}")
    sid = sess["result"].get("sessionId")
    if not sid:
        raise RuntimeError(f"no sessionId: {sess}")
    return sid


def _capture_intent(session_id: str, budget_usd: float = 150.0, prompt: str = "comfortable running shoes") -> dict:
    code, body = _req("POST", "/intent/capture", {
        "sessionId": session_id,
        "prompt": prompt,
        "budgetUsd": budget_usd,
        "promptSummary": prompt,
    })
    if code != 200:
        raise RuntimeError(f"intent capture failed: {code} {body}")
    return body


def expect(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def main() -> int:
    print(f"SELLER_URL={SELLER}")
    code, health = _req("GET", "/", timeout=20)
    if code != 200:
        print(f"Seller not reachable (HTTP {code}): {health}")
        print("Start local: source venv/bin/activate && python seller_agent.py")
        return 1
    print(f"agent={health.get('agent')} catalog={health.get('catalogCount')}\n")

    ok = True
    cases_run = 0

    # ── 1. Missing offerId ────────────────────────────────────────────────
    cases_run += 1
    code, body = _req("POST", "/demo/escrow/execute", {"offer": {"name": "x", "price": 10}, "requireIntent": False})
    ok = expect("1 missing offerId → 400", code == 400 and "offerid" in str(body.get("error", "")).lower(),
                f"HTTP {code} {body.get('error')}") and ok

    # ── 2. Unknown offer, no inline price/name ────────────────────────────
    cases_run += 1
    code, body = _req("POST", "/demo/escrow/execute", {
        "offerId": "does-not-exist-zzzz",
        "offer": {"id": "does-not-exist-zzzz"},
        "requireIntent": False,
    })
    ok = expect("2 unknown offer → 404", code == 404, f"HTTP {code} {body.get('error')}") and ok

    # ── 3. Confirm with nothing pending ───────────────────────────────────
    cases_run += 1
    code, body = _req("POST", "/demo/escrow/confirm", {
        "sessionId": "no-deal",
        "offerId": "no-deal",
    })
    err = str(body.get("error") or "")
    ok = expect(
        "3 confirm without deposit → error",
        code >= 400 and ("pending" in err.lower() or "deposit" in err.lower() or "escrow" in err.lower()),
        f"HTTP {code} {err[:120]}",
    ) and ok

    # ── 4. Cancel with nothing pending ────────────────────────────────────
    cases_run += 1
    code, body = _req("POST", "/demo/escrow/cancel", {
        "sessionId": "no-deal-cancel",
        "offerId": "no-deal-cancel",
    })
    err = str(body.get("error") or "")
    ok = expect(
        "4 cancel without deposit → error",
        code >= 400 and ("pending" in err.lower() or "cancel" in err.lower() or "deposit" in err.lower()),
        f"HTTP {code} {err[:120]}",
    ) and ok

    # ── 5. requireIntent:true, no intent captured ─────────────────────────
    cases_run += 1
    sid = _new_session()
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": OFFER["id"],
        "offer": OFFER,
        "requireIntent": True,
    })
    err = str(body.get("error") or "")
    ok = expect(
        "5 requireIntent true, no capture → 400",
        code == 400 and "intent" in err.lower(),
        f"HTTP {code} {err[:140]}",
    ) and ok

    # ── 6. Category mismatch with requireIntent:true → 403 ────────────────
    cases_run += 1
    sid = _new_session()
    _capture_intent(sid, budget_usd=150, prompt="comfortable running shoes")
    bad = {**OFFER, "id": OFFER["id"] + "-bball", "category": "basketball", "name": "Basketball shoe"}
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": bad["id"],
        "offer": bad,
        "requireIntent": True,
    })
    err = str(body.get("error") or "")
    ok = expect(
        "6 category mismatch + requireIntent → 403",
        code == 403 and "constraint" in err.lower(),
        f"HTTP {code} {err[:160]}",
    ) and ok

    # ── 7. Over budget with requireIntent:true → 403 ──────────────────────
    cases_run += 1
    sid = _new_session()
    _capture_intent(sid, budget_usd=50, prompt="running shoes under 50")
    pricey = {**OFFER, "id": OFFER["id"] + "-pricey", "price": 120.0}
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": pricey["id"],
        "offer": pricey,
        "requireIntent": True,
    })
    err = str(body.get("error") or "")
    ok = expect(
        "7 over budget + requireIntent → 403",
        code == 403 and ("constraint" in err.lower() or "budget" in err.lower()),
        f"HTTP {code} {err[:160]}",
    ) and ok

    # ── 8. Same constraint FAIL but requireIntent:false must NOT 403 ──────
    #    (this was the production demo bug)
    cases_run += 1
    sid = _new_session()
    _capture_intent(sid, budget_usd=50, prompt="running shoes under 50")
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": pricey["id"],
        "offer": pricey,
        "requireIntent": False,
    }, timeout=180)
    # May proceed to chain and fail on gas/USDC — must not be constraint 403
    not_constraint_block = code != 403
    ok = expect(
        "8 constraint fail + requireIntent false → not 403",
        not_constraint_block,
        f"HTTP {code} err={str(body.get('error') or body.get('status'))[:140]}",
    ) and ok

    # ── 9. Catalog price that rounds to 0 USDC ────────────────────────────
    cases_run += 1
    sid = _new_session()
    tiny = {**OFFER, "id": OFFER["id"] + "-tiny", "price": 0.0001}
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": tiny["id"],
        "offer": tiny,
        "requireIntent": False,
    }, timeout=60)
    err = str(body.get("error") or "")
    ok = expect(
        "9 near-zero catalog → rounded USDC error",
        code >= 400 and ("0" in err or "round" in err.lower() or "usdc" in err.lower() or "amount" in err.lower()),
        f"HTTP {code} {err[:140]}",
    ) and ok

    # ── 10. Absurd catalog price → insufficient USDC (or gas) ─────────────
    cases_run += 1
    sid = _new_session()
    huge = {**OFFER, "id": OFFER["id"] + "-huge", "price": 50_000_000.0}
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": huge["id"],
        "offer": huge,
        "requireIntent": False,
    }, timeout=90)
    err = str(body.get("error") or "").lower()
    ok = expect(
        "10 huge amount → insufficient funds error",
        code >= 400 and ("insufficient" in err or "usdc" in err or "fund" in err or "gas" in err),
        f"HTTP {code} {str(body.get('error'))[:140]}",
    ) and ok

    # ── Soft success path: micropay deposit + cancel (optional, may skip) ─
    print("\n== Soft live path (deposit→cancel micropay) ==")
    sid = _new_session()
    micro = {**OFFER, "id": f"escrow-micro-{sid[-8:]}", "price": 25.0}
    code, body = _req("POST", "/demo/escrow/execute", {
        "sessionId": sid,
        "offerId": micro["id"],
        "offer": micro,
        "requireIntent": False,
    }, timeout=180)
    if body.get("status") == "escrow_funded":
        escrow = (body.get("receipt") or {}).get("escrow")
        print(f"  [PASS] deposit held — escrow={escrow} usdc={(body.get('receipt') or {}).get('usdcHeld')}")
        ccode, cbody = _req("POST", "/demo/escrow/cancel", {
            "sessionId": sid,
            "offerId": micro["id"],
            "escrow": escrow,
        }, timeout=120)
        ok = expect(
            "cancel after fund → cancelled",
            ccode == 200 and cbody.get("status") == "cancelled",
            f"HTTP {ccode} {cbody.get('status')} {cbody.get('error')}",
        ) and ok

        # ── bonus: confirm after cancel must fail ─────────────────────────
        cases_run += 1
        rcode, rbody = _req("POST", "/demo/escrow/confirm", {
            "sessionId": sid,
            "offerId": micro["id"],
            "escrow": escrow,
        }, timeout=60)
        ok = expect(
            "11 confirm after cancel → error",
            rcode >= 400,
            f"HTTP {rcode} {rbody.get('error')}",
        ) and ok
    else:
        print(f"  [SKIP] live deposit unavailable — HTTP {code} {body.get('error') or body.get('status')}")
        print("         (fund buyer ETH/USDC on Base Sepolia to exercise on-chain path)")

    print(f"\n{cases_run} failure cases exercised")
    print("ALL ESCROW FAILURE CHECKS PASSED" if ok else "SOME ESCROW FAILURE CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
