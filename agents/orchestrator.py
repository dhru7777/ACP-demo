"""Backward-compatible shim — use `agents.buyer.orchestrator`."""

from agents.buyer.orchestrator import main, run_conversation

if __name__ == "__main__":
    main()
