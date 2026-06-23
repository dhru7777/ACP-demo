"""In-memory intent and audit store (per session)."""

from __future__ import annotations

from datetime import datetime, timezone

_records: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def save_intent(session_id: str, manifest: dict, intent_hash: str) -> dict:
    _records[session_id] = {
        "manifest": manifest,
        "intent_hash": intent_hash,
        "captured_at": manifest.get("captured_at") or _now(),
        "constraint_checks": [],
        "payments": [],
    }
    return _records[session_id]


def get_record(session_id: str) -> dict | None:
    return _records.get(session_id)


def get_manifest(session_id: str) -> dict | None:
    rec = get_record(session_id)
    return rec["manifest"] if rec else None


def get_intent_hash(session_id: str) -> str | None:
    rec = get_record(session_id)
    return rec["intent_hash"] if rec else None


def has_paid(session_id: str) -> bool:
    rec = get_record(session_id)
    return bool(rec and rec.get("payments"))


def add_check(session_id: str, entry: dict) -> None:
    rec = get_record(session_id)
    if not rec:
        return
    rec["constraint_checks"].append({**entry, "at": _now()})


def add_payment(session_id: str, entry: dict) -> None:
    rec = get_record(session_id)
    if not rec:
        return
    rec["payments"].append({**entry, "at": _now()})
