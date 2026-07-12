"""ACP JSON-RPC handler registry for the seller agent."""

from __future__ import annotations

from agents.seller.handlers.commerce import handle_commerce_pay_rpc, handle_commerce_request
from agents.seller.handlers.initialize import handle_initialize
from agents.seller.handlers.session import (
    handle_session_cancel,
    handle_session_close,
    handle_session_load,
    handle_session_new,
    handle_session_resume,
)
from agents.seller.prompt import handle_session_prompt

__all__ = [
    "handle_initialize",
    "handle_session_new",
    "handle_session_load",
    "handle_session_resume",
    "handle_session_cancel",
    "handle_session_close",
    "handle_session_prompt",
    "handle_commerce_request",
    "handle_commerce_pay_rpc",
]
