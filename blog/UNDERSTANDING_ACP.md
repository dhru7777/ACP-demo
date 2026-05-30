# Understanding Agent Client Protocol

Imagine you are coordinating a project with a remote team of specialists. You do not re-introduce yourself on every call. You pick up where you left off: what was decided, what is pending, what you are still waiting on.

Your specialists come from different companies. One uses Slack, one uses email, one has their own system. You need a shared language before any real work can happen. Before you assign anything, you ask what they can actually do. Some tasks take hours or days, so you do not block on every reply. When priorities shift, you send **stop** on an existing thread, not a brand-new conversation. Handoffs must stay visible, and access must match trust — not everyone sees everything.

Agentic communication on the internet has the same shape of problems:


| Problem          | Question                                               |
| ---------------- | ------------------------------------------------------ |
| State            | Do agents remember what was said before?               |
| Interoperability | Can my agent talk to yours in a shared format?         |
| Discovery        | Is my agent talking to the right agent?                |
| Async work       | What happens when a task runs for a long time?         |
| Control          | Who can say stop, and will the other side listen?      |
| Trust            | Should every agent trust every other agent by default? |


**Agent Client Protocol (ACP)** is the JSON-RPC layer that addresses these points: handshake, optional auth, named sessions, prompt turns, progress updates, permissions, and cancellation.

---

## What ACP is

ACP is a set of **JSON-RPC 2.0** messages between:


| Role       | Reference in the diagram | Responsibility                                  |
| ---------- | ------------------------ | ----------------------------------------------- |
| **Client** | Buyer-side agent         | Initiates requests                              |
| **Agent**  | Seller-side agent        | Holds session state, runs work, returns results |


The client role is structural, not necessarily human. One agent acting for a user can be the client; another agent’s endpoint can be the agent. The protocol defines **requester and responder**.

Typical stack for a single conversation:

1. **Initialize** — agree version and capabilities
2. **Authenticate** (if required)
3. **Session setup** — create or restore a thread
4. **Prompt turns** — user messages, updates, permissions, cancel

---

## Initialization

Initialization is how every connection starts. The buyer-side agent sends `initialize` with a protocol version and capabilities; the seller-side agent replies with the agreed version and what it supports. **No session exists yet** — only after this handshake can the buyer call `session/new`.

Initialization sequence diagram

**Figure 1 — Initialization.** [Download image](./assets/initialization.png)


| Step | Stage      | Buyer-side agent       | Seller-side agent                  | Meaning                                                                        |
| ---- | ---------- | ---------------------- | ---------------------------------- | ------------------------------------------------------------------------------ |
| 1    | Connection | Opens transport        | Accepts transport                  | HTTP (or similar) to a JSON-RPC endpoint. ACP defines messages, not transport. |
| 2    | Request    | Sends `initialize`     | Receives request                   | First ACP message. Not a session yet.                                          |
| 3    | Check      | Waits                  | Validates version and capabilities | Seller-side internal step; not a separate wire message.                        |
| 4    | Response   | Receives result        | Sends `initialize` response        | Buyer must finish this before any session method.                              |
| 5    | Ready      | May call `session/new` | Ready for sessions                 | Handshake complete. No user prompts exchanged yet.                             |


#### Wire format


|                                                                                                                                                                                                                                                                                                                    |                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Request — `initialize`{ "jsonrpc": "2.0", "id": 0, "method": "initialize", "params": { "protocolVersion": 1, "clientCapabilities": { "fs": { "readTextFile": true, "writeTextFile": true }, "terminal": true }, "clientInfo": { "name": "buyer-side-agent", "title": "Buyer-side Agent", "version": "1.0.0" } } } | Response{ "jsonrpc": "2.0", "id": 0, "result": { "protocolVersion": 1, "agentCapabilities": { "loadSession": true, "promptCapabilities": { "image": true, "audio": true, "embeddedContext": true }, "mcpCapabilities": { "http": true, "sse": true } }, "agentInfo": { "name": "seller-side-agent", "title": "Seller-side Agent", "version": "1.0.0" }, "authMethods": [] } } |


The spec uses `clientCapabilities` / `clientInfo` on the request and `agentCapabilities` / `agentInfo` on the response. Those names map to **buyer** and **seller** roles in the handshake.

### Key rules — initialization


| Rule         | Requirement                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| Version      | `protocolVersion` is a major integer; both sides must agree.                                                 |
| Capabilities | Omitted capability means unsupported.                                                                        |
| Baseline     | After init, the seller must support `session/new`, `session/prompt`, `session/cancel`, and `session/update`. |
| Scope        | Initialization does not create a session or carry user prompts.                                              |


---

## Authentication

Authentication establishes trust **after** initialization. The seller advertises methods in `authMethods` on the initialize response. If required, the buyer calls `authenticate` with a matching `methodId` before session work continues.

Authentication sequence diagram

**Figure 2 — Authentication.** [Download image](./assets/authentication.png)


| Step | Stage         | Buyer-side agent                            | Seller-side agent       | Meaning                                         |
| ---- | ------------- | ------------------------------------------- | ----------------------- | ----------------------------------------------- |
| 1–2  | Handshake     | `initialize`                                | `initialize` response   | Seller returns `authMethods`.                   |
| 3    | Auth request  | `authenticate` with `methodId`              | Validates method        | Buyer picks one advertised method.              |
| 4    | Auth response | Receives empty `result` on success          | Sends response          | Link is authenticated.                          |
| 5    | Proceed       | May call `session/new`, `session/prompt`, … | Accepts protected calls | Session and prompt work allowed.                |
| 6    | Re-auth       | `authenticate` again if needed              | May require it          | New connection or seller policy may reset auth. |


#### Wire format


|                                                                                                                                                                                                                                                                                                                            |                                                                                                                                                           |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Advertised at init + request — `authenticate`{ "authMethods": [{ "id": "agent-login", "name": "Agent login", "description": "Sign in using the agent login flow" }], "agentCapabilities": { "auth": { "logout": {} } } }{ "jsonrpc": "2.0", "id": 1, "method": "authenticate", "params": { "methodId": "agent-login" } } | Response — `authenticate`{ "jsonrpc": "2.0", "id": 1, "result": {} }Optional — `logout`{ "jsonrpc": "2.0", "id": 2, "method": "logout", "params": {} } |


### Key rules — authentication


| Rule         | Requirement                                                                          |
| ------------ | ------------------------------------------------------------------------------------ |
| Methods      | `methodId` in `authenticate` must match an `id` from `authMethods`.                  |
| Optional     | Empty `authMethods` means the seller may not require `authenticate`.                 |
| Logout       | Buyer must not call `logout` unless `agentCapabilities.auth.logout` was advertised.  |
| After logout | Handle possible `auth_required` errors; re-authenticate when the seller requires it. |


---

## Session setup

A **session** is a named conversation with its own `sessionId`, history, and working state. Multi-step flows (ask → clarify → answer) stay on one thread instead of resending the full transcript every time.

**Example:** Turn 1 — buyer says “running shoes.” Turn 2 — seller asks for budget. Both turns use the same `sessionId` so the seller can rely on stored context.

Session setup sequence diagram

**Figure 3 — Session setup.** MCP Servers are seller-side backends, not a third ACP peer. [Download image](./assets/session-setup.png)

All paths below assume **Initialized** (and **authenticated**, if required).

### Create a new session


| Step | Buyer-side agent   | Seller-side agent                | Meaning                      |
| ---- | ------------------ | -------------------------------- | ---------------------------- |
| 1    | `session/new`      | Creates session (may attach MCP) | New thread.                  |
| 2    | Stores `sessionId` | Returns `sessionId`              | ID used on every later turn. |



|                                                                                                              |                                                       |
| ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| Request — `session/new`{ "method": "session/new", "params": { "cwd": "/absolute/path", "mcpServers": [] } } | Response{ "result": { "sessionId": "sess_abc123" } } |


Use when starting a fresh conversation.

### Load vs resume


| Method           | Buyer gets                               | When to use                                        |
| ---------------- | ---------------------------------------- | -------------------------------------------------- |
| `session/load`   | Full history replay via `session/update` | Reconnect after restart; UI needs the full thread. |
| `session/resume` | Quiet reconnect, no full replay          | Short disconnect; seller still has context.        |



|                                                                                                                          |                                                                                                                              |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| Request — `session/load`{ "method": "session/load", "params": { "sessionId": "sess_abc123", "cwd": "/absolute/path" } } | Request — `session/resume`{ "method": "session/resume", "params": { "sessionId": "sess_abc123", "cwd": "/absolute/path" } } |


During load, the seller streams past messages as `session/update` notifications until load completes.

### List sessions


| Step | Buyer-side agent | Seller-side agent       | Meaning                                                   |
| ---- | ---------------- | ----------------------- | --------------------------------------------------------- |
| 1    | `session/list`   | Queries stored sessions | Discovery only; does not open a session.                  |
| 2    | Receives list    | Returns metadata        | Buyer picks a `sessionId`, then calls `load` or `resume`. |



|                                                                     |                                                                                                                                      |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Request — `session/list`{ "method": "session/list", "params": {} } | Response (example){ "result": { "sessions": [{ "sessionId": "sess_abc123", "title": "Running shoes", "cwd": "/absolute/path" }] } } |


### Key rules — session setup


| Rule             | Requirement                                                            |
| ---------------- | ---------------------------------------------------------------------- |
| Order            | Complete `initialize` (and `authenticate` if required) first.          |
| ID               | Every `session/prompt` and `session/cancel` uses the same `sessionId`. |
| `session/new`    | Creates a new thread; returns a new `sessionId`.                       |
| `session/load`   | Requires `loadSession` capability; replays history.                    |
| `session/resume` | Requires `sessionCapabilities.resume`.                                 |
| `session/list`   | Requires `sessionCapabilities.list`; discovery only.                   |
| `cwd`            | Absolute path for the session working context.                         |
| `mcpServers`     | Tells the seller which tool or data backends to attach.                |


---

## Prompt turn

A **prompt turn** is one cycle from a user message to a final `stopReason` on the same `session/prompt` request. The seller may use an LLM, push `session/update` progress, request permission for tools, and the buyer may cancel mid-turn. Requires init and a **ready** session.

**Prompt content:** Each item in `params.prompt` is a content block with a `type` (for example `text`, `image`, or `resource`). The buyer must only send types the two sides agreed at `initialize` under `promptCapabilities`.

Prompt turn sequence diagram

**Figure 4 — Prompt turn.** Solid lines = requests; dashed = seller notifications. LLM work is seller-internal. [Download image](./assets/prompt-turn.png)


| Step | Phase      | Buyer-side agent      | Seller-side agent              | Method                                  |
| ---- | ---------- | --------------------- | ------------------------------ | --------------------------------------- |
| 0    | Ready      | Active session        | Active session                 | —                                       |
| 1    | Prompt     | Sends user message    | Receives, runs LLM             | `session/prompt`                        |
| 2    | Progress   | Renders updates       | Streams plan, text, tool calls | `session/update`                        |
| 3    | Permission | User grants or denies | Runs tool if allowed           | `session/request_permission` + response |
| 4    | Cancel     | User aborts           | Stops LLM and tools            | `session/cancel`                        |
| 5    | End        | Receives outcome      | Completes turn                 | `session/prompt` result (`stopReason`)  |



|                                                                                                                                                                                                                                                                  |                                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Request — `session/prompt`{ "method": "session/prompt", "params": { "sessionId": "sess_abc", "prompt": [{ "type": "text", "text": "Running shoes under $150" }] } }Cancel (notification){ "method": "session/cancel", "params": { "sessionId": "sess_abc" } } | Notification — `session/update`{ "method": "session/update", "params": { "sessionId": "sess_abc", "update": { "sessionUpdate": "agent_message_chunk", "content": { "type": "text", "text": "…" } } } }Turn complete — `stopReason`{ "id": 2, "result": { "stopReason": "end_turn" } } |


{ "result": { "stopReason": "cancelled" } }

{
  "result": {
    "stopReason": "needs_clarification",
    "message": "What is your budget?"
  }
}



### Key rules — prompt turn


| Rule                | Requirement                                                 |
| ------------------- | ----------------------------------------------------------- |
| Order               | Initialize, session ready, then `session/prompt`.           |
| Content             | Block `type` must match negotiated `promptCapabilities`.    |
| Updates             | `session/update` is progress; `stopReason` closes the turn. |
| Permission          | Seller may ask; buyer responds before sensitive tools.      |
| Cancel              | Aborts the turn; session may stay open.                     |
| Cancel + permission | Pending permissions get outcome `cancelled`.                |
| Next message        | New user input = new `session/prompt`, same `sessionId`.    |


Spec: [Prompt turn](https://agentclientprotocol.com/protocol/prompt-turn.md)

---

## Protocol map (quick reference)


| Phase        | Primary methods                                                                    |
| ------------ | ---------------------------------------------------------------------------------- |
| Handshake    | `initialize`                                                                       |
| Trust        | `authenticate`, `logout`                                                           |
| Thread       | `session/new`, `session/load`, `session/resume`, `session/list`, `session/close`   |
| Conversation | `session/prompt`, `session/update`, `session/request_permission`, `session/cancel` |


---

