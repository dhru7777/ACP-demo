#!/usr/bin/env python3
"""Local Playwright UI test: demo Escrow → Yes (confirm)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright, expect

OUT = Path("/tmp/escrow_ui_test")
OUT.mkdir(parents=True, exist_ok=True)
DEMO = "http://127.0.0.1:8765/demo.html"


async def dump(page, name: str) -> None:
    await page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print(f"  saved {OUT}/{name}.png")


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(120_000)

        print("1) open demo")
        await page.goto(DEMO, wait_until="networkidle")
        await expect(page.locator("#next-btn")).to_be_visible()
        await dump(page, "01_loaded")

        print("2) Start")
        await page.click("#next-btn")
        await page.wait_for_function(
            "() => (document.querySelector('#next-btn')?.textContent || '').includes('Handshake')"
        )
        await dump(page, "02_boot")

        print("3) Handshake")
        await page.click("#next-btn")
        await page.wait_for_function(
            "() => (document.querySelector('#next-btn')?.textContent || '').includes('Session')",
            timeout=90_000,
        )
        await dump(page, "03_handshake")

        print("4) Create session")
        await page.click("#next-btn")
        await page.wait_for_function(
            "() => !!(window.__ACP_DEMO__ && window.__ACP_DEMO__.activeSession)",
            timeout=90_000,
        )
        sess = await page.evaluate("() => window.__ACP_DEMO__.activeSession")
        print(f"   sessionId={sess}")
        await dump(page, "04_session")

        print("5) jump to payment (skip long LLM negotiation)")
        await page.evaluate(
            """() => {
              const d = window.__ACP_DEMO__;
              try { if (typeof abortPromptTurn === 'function') abortPromptTurn(); } catch (e) {}
              window._autonomousBuyerLoop = false;
              d.busy = false;
              d.pendingOffer = {
                id: 'd2c24bb4-3853-5caf-8620-734f771dd9ac',
                name: 'Nike Air Pegasus 83 Premium',
                price: 50,
                currency: 'USD',
                category: 'running',
              };
              d.step = 4;
              d.chosenPaymentMethod = null;
              if (typeof _paymentInProgress !== 'undefined') _paymentInProgress = false;
              const btn = document.getElementById('next-btn');
              btn.style.display = '';
              btn.disabled = false;
              btn.textContent = 'Next: Payment';
              if (typeof setStatus === 'function') setStatus('UI escrow test — payment ready');
            }"""
        )
        await dump(page, "05_ready_payment")

        print("6) payment picker")
        await page.click("#next-btn")
        await page.wait_for_selector(".pay-pick-card", timeout=60_000)
        await dump(page, "06_picker")

        print("7) click Crypto (escrow underneath)")
        card = page.locator(".pay-pick-card[data-method='crypto']")
        if await card.count() == 0:
            card = page.locator(".pay-pick-card", has_text="Crypto")
        await card.first.click()
        await dump(page, "07_crypto_clicked")

        print("8) wait for Yes (deposit on-chain)…")
        try:
            await page.wait_for_selector('.escrow-confirm-wrap .pay-pick-card[data-method="yes"]', timeout=180_000)
        except Exception:
            text = await page.inner_text("body")
            print("FAIL: no Yes picker\n", text[-2000:])
            await dump(page, "08_fail")
            await browser.close()
            return 1
        await dump(page, "08_yes_no")

        body = (await page.inner_text("body")).lower()
        print(f"   held signal: {'held' in body}")

        print("9) Yes → release")
        await page.locator('.escrow-confirm-wrap .pay-pick-card[data-method="yes"]').first.click()
        await page.wait_for_function(
            """() => {
              const t = document.body.innerText.toLowerCase();
              return t.includes('released') || t.includes('release failed');
            }""",
            timeout=180_000,
        )
        await dump(page, "09_after_yes")
        final = (await page.inner_text("body")).lower()
        for n in ("held", "released", "release failed"):
            print(f"   {n!r}: {n in final}")

        ok = "released" in final and "release failed" not in final
        await browser.close()
        print("=== UI CRYPTO+ESCROW YES PATH PASSED ===" if ok else "=== UI PATH FAILED ===")
        return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as e:
        print("FAILED:", e, file=sys.stderr)
        raise
