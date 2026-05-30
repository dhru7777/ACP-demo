# Understanding Agent Client Protocol

## The Problem

Imagine you're coordinating a project with a remote team of specialists.

You don't re-introduce yourself on every call. You pick up where you left off, what was decided, what's pending, what you're still waiting on. That's just how conversation works.

But your specialists come from different companies. One uses Slack, one uses email, one has their own system. You need a shared language before any real work can happen.

Before you assign anything, you ask what they can actually do. Can this person run financial models? Do they handle legal review? You don't assume. You check.

Some tasks don't come back in five minutes. You send a request, they say they'll have it by Thursday, and you move on. You don't stand by the phone waiting.

But priorities shift. You need to call back and say stop, we're going a different direction. That's not a new conversation. It's a signal on an existing one.

Sometimes your specialist loops in someone else and hands off the work. Now you need to know who owns the deadline and who you call if something breaks. The chain has to stay visible.

And not everyone gets access to everything. The legal specialist doesn't see the financials. The external vendor doesn't get your internal notes. Every handoff carries a level of trust, and the channel has to respect that.

A similar thing is true for agentic communication on the internet. Going ahead with agentic infrastructure, we face the following difficulties.

| Problem | Question |
|---|---|
| State Management | Do agents even remember what was said before? |
| Interoperability | Can my agent actually talk to your agent, or are they just shouting into a void? |
| Discovery | Is my agent talking to the right agent, the one that will actually get the work done? |
| Async & Long-Running Tasks | What happens to my task when the agent goes quiet for an hour? |
| Interruption & Control | Who gets to say stop, and will the agent actually listen? |
| Multi-Agent Orchestration | When things break across a chain of agents, who is responsible? |
| Trust & Auth | Should my agent trust every other agent by default? |

That is why we need ACP. To reduce the friction at every one of these points in agentic communication.

---

## What ACP Is

Agent Client Protocol (ACP) is a set of JSON-RPC messages between two roles:

- A **buyer-side agent** — the one that initiates requests
- A **seller-side agent** — the one that receives requests, holds session state, and returns results

The client role is structural, not necessarily human. One agent acting on behalf of a user can be the buyer. Another agent's server endpoint can be the seller. The protocol defines who is the requester and who is the responder.

---

## How ACP Works

Every ACP connection follows a strict order. You cannot skip steps.

```
Initialize → Authenticate → Session Setup → Prompt Turn
```

---

### 1. Initialization

Before any session or prompt can happen, both agents need to agree on what they support and what version of the protocol they are speaking.

The buyer sends `initialize`. The seller checks the version, reads the capabilities, and responds. No session exists yet.

<!-- Insert Image: Initialization Diagram -->

| Step | Buyer-side Agent | Seller-side Agent | What it means |
|---|---|---|---|
| 1 | Opens transport connection | Accepts connection | Transport is ready. ACP defines message format, not the transport layer. |
| 2 | Sends `initialize` with `protocolVersion`, `clientCapabilities`, `clientInfo` | Receives request | First ACP message. Not a session yet. |
| 3 | Waits | Checks version and capabilities | Internal seller logic. Not a wire message. |
| 4 | Receives `protocolVersion`, `agentCapabilities`, `authMethods` | Sends response | Buyer must process this before any session call. |
| 5 | Can now call `session/new` | Ready to receive `session/new` | Handshake complete. No prompts exchanged yet. |

<table>
<tr>
<th>Request</th>
<th>Response</th>
</tr>
<tr>
<td>

```json
{
  "jsonrpc": "2.0",
  "id": 0,
  "method": "initialize",
  "params": {
    "protocolVersion": 1,
    "clientCapabilities": {
      "fs": {
        "readTextFile": true,
        "writeTextFile": true
      },
      "terminal": true
    },
    "clientInfo": {
      "name": "buyer-side-agent",
      "version": "1.0.0"
    }
  }
}
```

</td>
<td>

```json
{
  "jsonrpc": "2.0",
  "id": 0,
  "result": {
    "protocolVersion": 1,
    "agentCapabilities": {
      "loadSession": true,
      "promptCapabilities": {
        "image": true,
        "audio": true
      },
      "mcpCapabilities": {
        "http": true,
        "sse": true
      }
    },
    "agentInfo": {
      "name": "seller-side-agent",
      "version": "1.0.0"
    },
    "authMethods": []
  }
}
```

</td>
</tr>
</table>

**Key rules**

- `protocolVersion` is a major version integer. Both sides must agree.
- Omitted capabilities are treated as unsupported.
- After init, the seller must support `session/new`, `session/prompt`, `session/cancel`, and `session/update`.
- Initialization does not create a session or carry user prompts.

---

### 2. Authentication

After initialization, the seller advertises which authentication methods it supports inside `authMethods`. If the seller requires authentication, the buyer calls `authenticate` before any session work can continue.

<!-- Insert Image: Authentication Diagram -->

| Step | Buyer-side Agent | Seller-side Agent | What it means |
|---|---|---|---|
| 1–2 | Sends `initialize` | Responds with `authMethods` | Seller advertises available auth methods. |
| 3 | Sends `authenticate` with `methodId` | Receives request | Buyer picks one method from `authMethods`. |
| 4 | Receives empty result on success | Sends response | Connection is now authenticated. |
| 5+ | May call `session/new`, etc. | Accepts authenticated requests | Session setup can continue. |

<table>
<tr>
<th>Request</th>
<th>Response</th>
</tr>
<tr>
<td>

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "authenticate",
  "params": {
    "methodId": "agent-login"
  }
}
```

</td>
<td>

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {}
}
```

</td>
</tr>
</table>

**Key rules**

- `methodId` must match an `id` from `authMethods`.
- If `authMethods` is empty, no separate `authenticate` call is needed.
- Auth state does not last forever. A new connection or session may require `authenticate` again.
- `logout` is optional and only available if `agentCapabilities.auth.logout` was advertised.

---

### 3. Session Setup

A session is a named conversation between buyer and seller. It has its own `sessionId`, history, and working state. This keeps a multi-step flow on one thread instead of starting from zero on every message.

If the buyer says "running shoes" on turn one and the seller asks for a budget on turn two, both turns belong to the same `sessionId`. Without sessions, the seller would have no memory of turn one.

<!-- Insert Image: Session Setup Diagram -->

| Method | When to use |
|---|---|
| `session/new` | Start a fresh conversation thread |
| `session/load` | Reopen an existing session and replay full history |
| `session/resume` | Reconnect quietly without replaying history |
| `session/list` | See all available past sessions before opening one |

<table>
<tr>
<th>session/new Request</th>
<th>session/new Response</th>
</tr>
<tr>
<td>

```json
{
  "method": "session/new",
  "params": {
    "cwd": "/absolute/path",
    "mcpServers": []
  }
}
```

</td>
<td>

```json
{
  "result": {
    "sessionId": "sess_abc123"
  }
}
```

</td>
</tr>
</table>

<table>
<tr>
<th>session/load Request</th>
<th>session/resume Request</th>
</tr>
<tr>
<td>

```json
{
  "method": "session/load",
  "params": {
    "sessionId": "sess_abc123",
    "cwd": "/absolute/path"
  }
}
```

</td>
<td>

```json
{
  "method": "session/resume",
  "params": {
    "sessionId": "sess_abc123",
    "cwd": "/absolute/path"
  }
}
```

</td>
</tr>
</table>

**Key rules**

- Initialize and authenticate before calling any session method.
- Every `session/prompt` and `session/cancel` uses the same `sessionId`.
- `session/load` requires the `loadSession` capability.
- `session/resume` requires `sessionCapabilities.resume`.
- `session/list` discovers sessions but does not open one.
- `cwd` must be an absolute path.

---

### 4. Prompt Turn

A prompt turn is one cycle from a user message to a final `stopReason` on the same `session/prompt` request. The seller may stream progress, request permissions for tools, and the buyer may cancel mid-turn.

<!-- Insert Image: Prompt Turn Diagram -->

| Step | Phase | Buyer-side Agent | Seller-side Agent |
|---|---|---|---|
| 1 | Prompt | Sends user message | Receives, runs LLM |
| 2 | Progress | Renders updates | Streams plan, text, tool calls via `session/update` |
| 3 | Permission | User grants or denies | Runs tool if allowed |
| 4 | Cancel | User aborts | Stops LLM and tools |
| 5 | End | Receives outcome | Sends `stopReason` |

<table>
<tr>
<th>Prompt Request</th>
<th>Possible Responses</th>
</tr>
<tr>
<td>

```json
{
  "method": "session/prompt",
  "params": {
    "sessionId": "sess_abc",
    "prompt": [{
      "type": "text",
      "text": "Running shoes under $150"
    }]
  }
}
```

</td>
<td>

```json
{ "result": { "stopReason": "end_turn" } }

{ "result": { "stopReason": "cancelled" } }

{
  "result": {
    "stopReason": "needs_clarification",
    "message": "What is your budget?"
  }
}
```

</td>
</tr>
</table>

**Key rules**

| Rule | Requirement |
|---|---|
| Order | Initialize, then session ready, then `session/prompt` |
| Prompt content | Only types allowed by negotiated prompt capabilities |
| Updates | `session/update` is progress, not the final response |
| End of turn | The same `session/prompt` request receives the `stopReason` |
| Cancel | Aborts the turn. Session may stay open. |
| Next message | New user input uses another `session/prompt` on the same `sessionId` |

---

## What ACP Does Not Cover

ACP handles the conversation layer cleanly. It does not pretend to solve everything.

Multi-agent orchestration, meaning one agent calling another, tracking a chain of agents, or owning a failure across that chain, sits outside this spec. That is a separate and harder problem.

ACP is not oversold. It solves what it says it solves.
