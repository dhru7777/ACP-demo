"""
SESSION MANAGER
===============
Owns all session state on the Seller side.

A session is a named, persistent conversation context between two agents.
It answers: "Who is talking, about what, and where did we leave off?"

Responsibilities:
  - create()      : generate a unique sessionId, store initial state
  - exists()      : check if a sessionId is known
  - get()         : retrieve full session state
  - close()       : remove session and free memory
  - add_history() : record each message for session/load replay
  - list_all()    : debug view of all active sessions

Storage: in-memory Python dict (lost on server restart).
Production equivalent: Redis or PostgreSQL with TTL expiry.  This is out of scope for the demo.
"""

import uuid
from datetime import datetime


class SessionManager:

    def __init__(self):
        # { sessionId: session_dict }
        self._sessions: dict = {}

    # ------------------------------------------------------------------
    # CREATE
    # Called when buyer sends session/new.
    # Generates a unique ID, stores the session context.
    # ------------------------------------------------------------------
    def create(self, buyer_id: str, cwd: str = "/") -> str:
        session_id = "sess_" + uuid.uuid4().hex[:12]
        self._sessions[session_id] = {
            "sessionId":  session_id,
            "buyerId":    buyer_id,
            "cwd":        cwd,
            "status":     "active",
            "createdAt":  datetime.utcnow().isoformat(),
            "history":    []   # each commerce exchange stored here for replay
        }
        print(f"  [SessionManager] Created session: {session_id} for buyer: {buyer_id}")
        return session_id

    # ------------------------------------------------------------------
    # EXISTS
    # Check before any session operation — buyer must verify before calling
    # session/load, session/resume, or session/close.
    # ------------------------------------------------------------------
    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    # ------------------------------------------------------------------
    # GET
    # Returns full session state dict or None if not found.
    # ------------------------------------------------------------------
    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    # ------------------------------------------------------------------
    # CLOSE
    # Called when buyer sends session/close.
    # Spec: seller MUST cancel ongoing work and free resources.
    # In our demo: just remove from dict.
    # ------------------------------------------------------------------
    def close(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            print(f"  [SessionManager] Closed session: {session_id}")
            return True
        return False

    # ------------------------------------------------------------------
    # UPDATE CONTEXT
    # Store arbitrary working state for the current conversation turn.
    # Used by multi-turn session/prompt flows (e.g. pending intent while
    # waiting for the buyer to supply a budget).
    #
    # Pass an empty dict {} to clear context between turns.
    # ------------------------------------------------------------------
    def update_context(self, session_id: str, context: dict):
        if session_id in self._sessions:
            self._sessions[session_id]["context"] = context

    # ------------------------------------------------------------------
    # ADD HISTORY
    # Store each meaningful message in the session so we can replay
    # it later via session/load.
    #
    # role    : "buyer" or "seller"
    # method  : the ACP method name (e.g. "commerce/request")
    # content : the params or result dict
    # ------------------------------------------------------------------
    def add_history(self, session_id: str, role: str, method: str, content: dict):
        if session_id not in self._sessions:
            return
        self._sessions[session_id]["history"].append({
            "role":      role,
            "method":    method,
            "content":   content,
            "timestamp": datetime.utcnow().isoformat()
        })

    # ------------------------------------------------------------------
    # LIST ALL
    # Debug helper — shows all active sessions and their size.
    # ------------------------------------------------------------------
    def list_all(self) -> list:
        return [
            {
                "sessionId": sid,
                "buyerId":   s["buyerId"],
                "status":    s["status"],
                "createdAt": s["createdAt"],
                "messages":  len(s["history"])
            }
            for sid, s in self._sessions.items()
        ]


# Singleton — seller_agent.py imports this instance directly
session_manager = SessionManager()
