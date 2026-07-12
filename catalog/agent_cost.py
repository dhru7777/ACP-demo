"""
Persist per-session LLM cost snapshots to Postgres.

Table: agent_session_costs — keyed by session_id with full cost_structure JSON.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from catalog.db import get_database_url

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_session_costs (
    session_id        TEXT PRIMARY KEY,
    buyer_id          TEXT,
    seller_cost_usd   NUMERIC(14, 8) NOT NULL DEFAULT 0,
    buyer_cost_usd    NUMERIC(14, 8) NOT NULL DEFAULT 0,
    total_cost_usd    NUMERIC(14, 8) NOT NULL DEFAULT 0,
    cost_structure    JSONB NOT NULL DEFAULT '{}',
    turn_log          JSONB NOT NULL DEFAULT '[]',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_session_costs_updated_idx
    ON agent_session_costs (updated_at DESC);
"""

_schema_ready = False


def _connect():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL not configured")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def ensure_schema() -> bool:
    """Create agent_session_costs table if missing. Returns True when Postgres is ready."""
    global _schema_ready
    if _schema_ready:
        return True
    if not get_database_url():
        return False
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    _schema_ready = True
    print("  [AgentCost] Postgres table agent_session_costs ready")
    return True


def _cost_totals(session: dict[str, Any]) -> tuple[float, float, float]:
    seller = float((session.get("seller") or {}).get("cost_usd") or 0)
    buyer = float((session.get("buyer") or {}).get("cost_usd") or 0)
    total = float(session.get("total_cost_usd") or (seller + buyer))
    return seller, buyer, total


def _turn_entry(turn: dict[str, Any] | None) -> dict[str, Any] | None:
    if not turn:
        return None
    entry = dict(turn)
    entry["recorded_at"] = datetime.now(timezone.utc).isoformat()
    return entry


def save_session_cost(
    session_id: str,
    usage_payload: dict[str, Any],
    *,
    buyer_id: str | None = None,
) -> bool:
    """
    Upsert session cost row and append the latest turn to turn_log.
    usage_payload: {turn, session} from record_turn / token_usage helpers.
    """
    if not session_id or not usage_payload:
        return False
    if not get_database_url():
        return False

    ensure_schema()

    session = usage_payload.get("session") or usage_payload
    turn = _turn_entry(usage_payload.get("turn"))
    seller_usd, buyer_usd, total_usd = _cost_totals(session)
    turn_batch = json.dumps([turn] if turn else [])

    sql = """
        INSERT INTO agent_session_costs (
            session_id, buyer_id,
            seller_cost_usd, buyer_cost_usd, total_cost_usd,
            cost_structure, turn_log
        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (session_id) DO UPDATE SET
            buyer_id = COALESCE(EXCLUDED.buyer_id, agent_session_costs.buyer_id),
            seller_cost_usd = EXCLUDED.seller_cost_usd,
            buyer_cost_usd = EXCLUDED.buyer_cost_usd,
            total_cost_usd = EXCLUDED.total_cost_usd,
            cost_structure = EXCLUDED.cost_structure,
            turn_log = agent_session_costs.turn_log || EXCLUDED.turn_log,
            updated_at = now()
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    session_id,
                    buyer_id,
                    seller_usd,
                    buyer_usd,
                    total_usd,
                    json.dumps(session),
                    turn_batch,
                ),
            )
        conn.commit()

    agent = (turn or {}).get("agent", "?")
    phase = (turn or {}).get("phase", "?")
    print(
        f"  [AgentCost] saved {session_id} — {agent}/{phase} "
        f"seller=${seller_usd:.6f} total=${total_usd:.6f}"
    )
    return True


def get_session_cost(session_id: str) -> dict[str, Any] | None:
    if not session_id or not get_database_url():
        return None
    ensure_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, buyer_id,
                       seller_cost_usd, buyer_cost_usd, total_cost_usd,
                       cost_structure, turn_log, created_at, updated_at
                FROM agent_session_costs
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "sessionId": row["session_id"],
        "buyerId": row["buyer_id"],
        "sellerCostUsd": float(row["seller_cost_usd"] or 0),
        "buyerCostUsd": float(row["buyer_cost_usd"] or 0),
        "totalCostUsd": float(row["total_cost_usd"] or 0),
        "costStructure": row["cost_structure"] or {},
        "turnLog": row["turn_log"] or [],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
