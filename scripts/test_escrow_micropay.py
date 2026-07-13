#!/usr/bin/env python3
"""
Terminal E2E: escrow micropayment on Base Sepolia.

  deploy BilateralEscrow → approve → deposit → print held balance → confirm

Usage (from repo root, with local.env loaded):

  python scripts/test_escrow_micropay.py
  python scripts/test_escrow_micropay.py --catalog-usd 50
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load local.env via payments.config side effect
from payments import config as _config  # noqa: F401
from payments import escrow_service
from payments.chain import fetch_usdc_balance
from payments.demo_fx import quote_catalog_price
from payments.wallets import get_buyer_address, get_seller_address


async def main() -> int:
    parser = argparse.ArgumentParser(description="Escrow micropayment E2E on Base Sepolia")
    parser.add_argument("--catalog-usd", type=float, default=100.0, help="Catalog USD (demo rate → tiny USDC)")
    parser.add_argument("--skip-confirm", action="store_true", help="Stop after deposit (leave funded)")
    args = parser.parse_args()

    buyer = get_buyer_address()
    seller = get_seller_address()
    fx = quote_catalog_price(args.catalog_usd)

    print("=== Escrow micropayment test ===")
    print(f"buyer:  {buyer}")
    print(f"seller: {seller}")
    print(f"catalog ${args.catalog_usd:.2f} → {fx.usdc_atomic} atomic USDC ({fx.to_dict()['usdc']} USDC)")
    print(f"buyer USDC before: {fetch_usdc_balance(buyer).get('formatted')}")
    print(f"seller USDC before: {fetch_usdc_balance(seller).get('formatted')}")
    print()

    print("1) deploy + approve + deposit…")
    funded = await escrow_service.execute_deposit(
        args.catalog_usd,
        offer_id="micropay-terminal",
        offer_name="Terminal micropay escrow test",
        session_id="terminal-escrow",
    )
    rcpt = funded["receipt"]
    escrow = rcpt["escrow"]
    print(f"   status: {funded['status']}")
    print(f"   escrow: {escrow}")
    print(f"   held:   {rcpt['usdcHeld']} USDC (raw {rcpt.get('usdcAtomic')})")
    print(f"   state:  {rcpt['state']} (1=Funded)")
    print(f"   deposit tx: {rcpt['txHash']}")
    print(f"   explorer:   {rcpt['explorer']}")
    print()

    held = escrow_service.escrow_usdc_balance(escrow)
    print(f"2) escrow contract USDC balance (on-chain): {held} atomic")
    assert held == fx.usdc_atomic, f"expected {fx.usdc_atomic} held, got {held}"
    print("   OK — full micropayment amount is held (no USDC skimmed for gas)")
    print()

    if args.skip_confirm:
        print("3) skip confirm (--skip-confirm)")
        return 0

    print("3) confirm() — release to seller…")
    released = await escrow_service.execute_confirm(session_id="terminal-escrow", escrow=escrow)
    r2 = released["receipt"]
    print(f"   status: {released['status']}")
    print(f"   released: {r2['usdcReleased']} USDC")
    print(f"   escrow after: {r2['usdcHeldAfter']} USDC")
    print(f"   state: {r2['state']} (2=Released)")
    print(f"   tx: {r2['txHash']}")
    print(f"   explorer: {r2['explorer']}")
    print()
    print(f"buyer USDC after:  {fetch_usdc_balance(buyer).get('formatted')}")
    print(f"seller USDC after: {fetch_usdc_balance(seller).get('formatted')}")
    print("=== DONE ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
