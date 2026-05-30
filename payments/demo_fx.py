"""
Demo catalog USD → on-chain USDC conversion.

Catalog prices stay in display dollars ($100 shoe). Settlement uses real USDC
at a configurable demo rate so test wallets last for many runs.

Default: 1 USDC = $10,000 catalog  →  $100 = 0.01 USDC (10_000 base units).
"""

from __future__ import annotations

from dataclasses import dataclass

from payments.config import env

USDC_DECIMALS = 6


def catalog_usd_per_usdc() -> float:
    raw = env("DEMO_CATALOG_USD_PER_USDC", "10000")
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        rate = 10_000.0
    return max(rate, 1.0)


def catalog_usd_to_usdc_decimal(catalog_usd: float) -> float:
    """Human-readable USDC amount for chain (e.g. 0.01)."""
    return round(float(catalog_usd) / catalog_usd_per_usdc(), USDC_DECIMALS)


def catalog_usd_to_usdc_atomic(catalog_usd: float) -> int:
    """USDC base units (6 decimals) for x402 exact scheme."""
    dec = catalog_usd_to_usdc_decimal(catalog_usd)
    return int(round(dec * (10**USDC_DECIMALS)))


def format_usdc_atomic(raw: int) -> str:
    if raw == 0:
        return "0"
    whole, frac = divmod(raw, 10**USDC_DECIMALS)
    frac_s = str(frac).zfill(USDC_DECIMALS).rstrip("0")
    return f"{whole}.{frac_s}" if frac_s else str(whole)


@dataclass(frozen=True)
class DemoPriceQuote:
    catalog_usd: float
    usdc_decimal: float
    usdc_atomic: int
    catalog_usd_per_usdc: float

    def to_dict(self) -> dict:
        return {
            "catalogUsd": self.catalog_usd,
            "usdc": format_usdc_atomic(self.usdc_atomic),
            "usdcAtomic": str(self.usdc_atomic),
            "usdcDecimals": USDC_DECIMALS,
            "demoRate": f"1 USDC = ${self.catalog_usd_per_usdc:,.0f} catalog (demo)",
            "catalogUsdPerUsdc": self.catalog_usd_per_usdc,
        }


def quote_catalog_price(catalog_usd: float) -> DemoPriceQuote:
    rate = catalog_usd_per_usdc()
    atomic = catalog_usd_to_usdc_atomic(catalog_usd)
    return DemoPriceQuote(
        catalog_usd=float(catalog_usd),
        usdc_decimal=atomic / (10**USDC_DECIMALS),
        usdc_atomic=atomic,
        catalog_usd_per_usdc=rate,
    )
