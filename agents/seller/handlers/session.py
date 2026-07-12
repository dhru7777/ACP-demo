"""ACP JSON-RPC handlers — session lifecycle."""

from __future__ import annotations

from acp import session_manager


def handle_session_new(id_, params: dict) -> dict:
    buyer_id = params.get("buyerId", "unknown-buyer")
    cwd = params.get("cwd", "/")
    session_id = session_manager.create(buyer_id=buyer_id, cwd=cwd)
    print(f"  Session created: {session_id} | buyer: {buyer_id} | cwd: {cwd}")
    print(f"  Active sessions: {len(session_manager.list_all())}")
    return {"jsonrpc": "2.0", "id": id_, "result": {"sessionId": session_id}}


def handle_session_load(id_, params: dict) -> dict:
    session_id = params.get("sessionId")
    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' not found. Create a new one with session/new.",
            },
        }

    session = session_manager.get(session_id)
    history = session["history"]
    print(f"  Loading session: {session_id} | {len(history)} history entries")

    return {
        "jsonrpc": "2.0",
        "id": id_,
        "result": {
            "sessionId": session_id,
            "buyerId":   session["buyerId"],
            "cwd":       session["cwd"],
            "createdAt": session["createdAt"],
            "history":   history,
        },
    }


def handle_session_resume(id_, params: dict) -> dict:
    session_id = params.get("sessionId")
    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' not found or expired.",
            },
        }

    session = session_manager.get(session_id)
    print(f"  Session resumed: {session_id} | buyer: {session['buyerId']}")
    return {"jsonrpc": "2.0", "id": id_, "result": {}}


def handle_session_cancel(id_, params: dict) -> dict:
    session_id = params.get("sessionId")
    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' does not exist or is not active.",
            },
        }

    session_manager.cancel(session_id)
    session_manager.add_history(session_id, "buyer", "session/cancel", {})
    print(f"  Session cancel: {session_id} — in-flight work stopped, session still active")
    return {"jsonrpc": "2.0", "id": id_, "result": {}}


def handle_session_close(id_, params: dict) -> dict:
    session_id = params.get("sessionId")
    if not session_id or not session_manager.exists(session_id):
        return {
            "jsonrpc": "2.0", "id": id_,
            "error": {
                "code": -32000,
                "message": f"Session '{session_id}' does not exist or is not active.",
            },
        }

    session_manager.close(session_id)
    print(f"  Session closed: {session_id}")
    print(f"  Active sessions remaining: {len(session_manager.list_all())}")
    return {"jsonrpc": "2.0", "id": id_, "result": {}}
