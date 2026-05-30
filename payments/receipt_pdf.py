"""Generate a simple PDF payment receipt for the demo UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fpdf import FPDF


def _line(pdf: FPDF, label: str, value: str) -> None:
    text = (value or "-").replace("\u2014", "-")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"{label}: {text}", ln=True)


def _wallet_block(pdf: FPDF, title: str, data: dict | None) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, title, ln=True)
    if not data:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "-", ln=True)
        return
    bal = data.get("balances") or {}
    eth = bal.get("ETH") or {}
    usdc = bal.get("USDC") or {}
    _line(pdf, "Address", data.get("address", ""))
    _line(pdf, "ETH", f"{eth.get('formatted', '-')} {eth.get('symbol', 'ETH')}")
    _line(pdf, "USDC", f"{usdc.get('formatted', '-')} {usdc.get('symbol', 'USDC')}")
    tx0 = (data.get("txs") or [None])[0]
    if tx0:
        sign = "+" if tx0.get("direction") == "in" else "−" if tx0.get("direction") == "out" else ""
        _line(
            pdf,
            "Latest tx",
            f"{sign}{tx0.get('amount', '')} {tx0.get('asset', '')} ({tx0.get('timestamp', '')})",
        )


def build_receipt_pdf(payload: dict[str, Any]) -> bytes:
    offer = payload.get("offer") or {}
    rcpt = payload.get("receipt") or {}
    gas = rcpt.get("ethGas") or {}
    wallets = payload.get("wallets") or {}
    before = wallets.get("before") or {}
    after = wallets.get("after") or {}

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ACP Demo - Payment Receipt", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        0,
        5,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        ln=True,
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Payment", ln=True)
    _line(pdf, "Item", offer.get("name") or offer.get("id") or "-")
    _line(pdf, "Catalog price", f"${offer.get('price', '-')} {offer.get('currency', 'USD')}")
    _line(pdf, "USDC paid", f"{rcpt.get('usdcPaid', '-')} USDC")
    _line(pdf, "Network", rcpt.get("network") or "base-sepolia")
    _line(pdf, "Facilitator gas", f"{gas.get('formatted', '-')} ETH")
    _line(pdf, "Settlement tx", rcpt.get("txHash") or "-")
    if rcpt.get("explorer"):
        _line(pdf, "Verify", rcpt["explorer"])

    pdf.ln(2)
    def _snap(role: str, phase: str) -> dict | None:
        bucket = before if phase == "before" else after
        entry = bucket.get(role) if isinstance(bucket, dict) else None
        if isinstance(entry, dict) and entry.get("full"):
            return entry["full"]
        return entry if isinstance(entry, dict) and entry.get("address") else None

    _wallet_block(pdf, "Buyer wallet (before)", _snap("buyer", "before"))
    _wallet_block(pdf, "Buyer wallet (after)", _snap("buyer", "after"))
    _wallet_block(pdf, "Seller wallet (before)", _snap("seller", "before"))
    _wallet_block(pdf, "Seller wallet (after)", _snap("seller", "after"))

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        4,
        "Gas is paid by the x402 facilitator relayer, not deducted from the buyer ETH balance shown above.",
    )

    out = pdf.output()
    return out if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")
