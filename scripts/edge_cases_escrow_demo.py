#!/usr/bin/env python3
"""How we solved the 10 escrow demo edge cases."""

from __future__ import annotations

SOLVED = [
    {
        "id": 1,
        "name": "Seller deposits",
        "fix": "Contract: only buyer. Service: _require_buyer_signer() before txs.",
    },
    {
        "id": 2,
        "name": "Double deposit / Retry",
        "fix": "Service reuses Funded escrow for same session+amount; else cancel then redeploy.",
    },
    {
        "id": 3,
        "name": "Confirm before deposit",
        "fix": "execute_confirm requires Funded; clear error if missing pending.",
    },
    {
        "id": 4,
        "name": "Seller confirms",
        "fix": "Contract only buyer + service always signs with buyer key.",
    },
    {
        "id": 5,
        "name": "Double Yes",
        "fix": "Idempotent confirm: if already Released, return success without 2nd tx.",
    },
    {
        "id": 6,
        "name": "No = stuck until deadline",
        "fix": "NEW cancel() — buyer refunds immediately. Demo No → POST /demo/escrow/cancel.",
    },
    {
        "id": 7,
        "name": "Refund after release",
        "fix": "Still rejected on-chain; cancel also blocked after Released.",
    },
    {
        "id": 8,
        "name": "Missing approve",
        "fix": "Approve then poll allowance before deposit; fail loudly if allowance missing.",
    },
    {
        "id": 9,
        "name": "Insufficient USDC",
        "fix": "Balance check BEFORE deploy (no orphan Created contract).",
    },
    {
        "id": 10,
        "name": "Bad constructor / zero amount",
        "fix": "Pre-validate amount/buyer/seller; constructor also rejects buyer=seller.",
    },
]


def main() -> None:
    print("Escrow edge cases — fixes applied\n")
    for c in SOLVED:
        print(f"{c['id']}. {c['name']}")
        print(f"   → {c['fix']}\n")


if __name__ == "__main__":
    main()
