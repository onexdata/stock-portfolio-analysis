#!/usr/bin/env python3
"""Demo WebSocket client for the portfolio analysis service.

Usage:
    python scripts/demo_client.py

Demonstrates:
  1. Connect to a session
  2. Request analysis on AAPL and stream results
  3. Mid-analysis, switch to GOOGL (triggers cancel-on-switch)
  4. Stream all GOOGL results
"""

import asyncio
import json
import sys

import websockets


SERVER_URL = "ws://localhost:8000/ws/demo-session-1"


async def main():
    print(f"Connecting to {SERVER_URL} ...")
    async with websockets.connect(SERVER_URL) as ws:
        print("Connected!\n")

        # ── Step 1: Request AAPL analysis ────────────────────────────────
        print(">>> Sending: analyze AAPL")
        await ws.send(json.dumps({"action": "analyze", "ticker": "AAPL"}))

        # Collect a couple results then switch
        results_before_switch = 0
        target_before_switch = 2

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
            except asyncio.TimeoutError:
                print("  (timeout waiting for message)")
                break

            data = json.loads(raw)
            if data.get("type") == "error":
                print(f"  ERROR: {data['detail']}")
                break

            print(
                f"  <- {data['ticker']} | {data['metric']:>20s} = {data['value']}"
            )
            results_before_switch += 1

            if results_before_switch >= target_before_switch:
                # ── Step 2: Switch to GOOGL mid-analysis ─────────────────
                print(f"\n>>> Switching: analyze GOOGL (cancel-on-switch)")
                await ws.send(
                    json.dumps({"action": "analyze", "ticker": "GOOGL"})
                )
                break

        # ── Step 3: Collect all GOOGL results ────────────────────────────
        googl_count = 0
        while googl_count < 5:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
            except asyncio.TimeoutError:
                print("  (timeout waiting for message)")
                break

            data = json.loads(raw)

            # Might still receive a trailing AAPL result
            ticker = data.get("ticker", "?")
            metric = data.get("metric", "?")
            value = data.get("value", "?")
            print(f"  <- {ticker} | {metric:>20s} = {value}")

            if ticker == "GOOGL":
                googl_count += 1

        print(f"\nDone — received {googl_count} GOOGL results.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
