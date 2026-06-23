---
layout: post
title: "Understanding x402 — Agent Payments on Chain"
date: 2026-06-08
excerpt: "x402 turns the long-reserved HTTP 402 Payment Required status into real machine payments — quote, sign, verify, and settle USDC through a facilitator on a Layer 2 chain."
---

Say you want running shoes. You tell your **buyer-side agent** your size, budget, and style. It already knows your preferences from past conversations. It finds a seller, negotiates an offer, and decides to buy on your behalf.

Your agent also has **wallet access** — a balance of **USDC** you set aside for purchases like this. It does not ask you to open a browser, copy a wallet address, or paste a transaction hash. It is supposed to complete the purchase as one coordinated flow: agree on the item, pay, get proof, move on.

---

## The problems

Agent payments hit the same friction points:


| Problem          | Question                |
| ---------------- | ----------------------- |
| **Payment gate** | Who says pay first?     |
| **Units**        | Dollars or chain atoms? |
| **Proof**        | Paid or just claimed?   |
| **Chain ops**    | Who runs the RPC?       |
| **Settlement**   | Who broadcasts the tx?  |
| **Cost**         | L1 for every purchase?  |


**x402** is the protocol layer built to answer these  for agents paying over standard request/response flows.

---

## From HTTP 402 to x402

In 1991, HTTP reserved status code **402 Payment Required**. The idea was simple: before serving a resource, the server tells the client what payment is needed. The client pays, retries, and gets the response.

For thirty years, 402 stayed mostly unused. Browsers did not know what to do with it. There was no standard way for a client to **sign** a payment and **replay** the request with proof attached. The status code existed; the **client half of the protocol** did not.

I wrote about that history and the gap it left in **[From HTTP 402 to x402](/from-http-402-to-x402)**. 


|     |
| --- |


---

## What x402 is

**x402** is an open payment protocol built for the web and for autonomous clients. A typical settlement path looks like this:

1. The **seller** publishes payment requirements (scheme, network, asset, amount, `payTo`).
2. The **buyer** signs a payment payload that matches those requirements exactly.
3. An **x402 facilitator** **verifies** the payload, then **settles** by submitting the on-chain transfer.
4. Both sides receive a **receipt**  transaction hash, payer, payee, amounts verifiable on a block explorer.  
  
iNSERT THE DAIGRAM HERE

---

## Who is in the diagram




| Role                           | Responsibility                                                                               |
| ------------------------------ | -------------------------------------------------------------------------------------------- |
| **Buyer-side agent (client)**  | Requests the offer, signs the payment payload, receives the receipt                          |
| **Seller-side agent (server)** | Returns payment requirements, forwards verify/settle to the facilitator, returns paid status |
| **x402 facilitator**           | Validates the signed payload; broadcasts and confirms the USDC transfer                      |
| **Layer 2 (e.g. Base)**        | Executes the transfer quickly and cheaply; where the receipt’s `txHash` lives                |
| **Layer 1 (Ethereum)**         | Security anchor for the rollup — batches many L2 txs and posts proofs periodically           |


The buyer does **not** usually call the facilitator directly. The buyer proves payment intent through cryptography; the **seller’s side** drives verify and settle. That keeps one clear commerce endpoint for the client.

---

## Protocol breakdown

**Prerequisite:** buyer and seller have already agreed on the offer (item, price, terms) through whatever negotiation layer they use — for example [Agent Client Protocol](./UNDERSTANDING_ACP.md) sessions and prompts. x402 begins when payment is due.

**Figure 1 — x402 settlement (verify → settle → receipt).**

x402 protocol breakdown — buyer, seller, facilitator, Base L2, Ethereum L1

### Step-by-step


| Step   | Buyer-side agent                              | Seller-side agent                                      | x402 facilitator                    | Chain       | Meaning                                                                            |
| ------ | --------------------------------------------- | ------------------------------------------------------ | ----------------------------------- | ----------- | ---------------------------------------------------------------------------------- |
| **1**  | Sends request (e.g. commerce / pay quote)     | Receives request                                       | —                                   | —           | Client asks what payment is required for this offer.                               |
| **2**  | Receives **payment required**                 | Returns requirements (amount, asset, network, `payTo`) | —                                   | —           | Seller publishes the x402 terms. Same *idea* as HTTP 402.                          |
| **3**  | Signs payload; sends request **with payment** | Receives signed payload                                | —                                   | —           | Buyer attaches cryptographic proof of willingness to pay under those terms.        |
| **4**  | Waits                                         | Sends **verify** request                               | Verifies signature, amount, network | —           | Facilitator checks the payload before any chain write.                             |
| **5**  | —                                             | Receives **verified**                                  | Returns valid                       | —           | Seller may proceed to settlement.                                                  |
| **6**  | Waits                                         | Sends **settle** request                               | Submits USDC transfer               | **L2**      | Facilitator broadcasts the payment on the Layer 2 network.                         |
| **7**  | —                                             | —                                                      | **Rollup batching**                 | L2          | Multiple settlements may be grouped by the sequencer (normal L2 operation).        |
| **8**  | —                                             | —                                                      | Posts batch proof                   | L2 → **L1** | Rollup anchors compressed state to Ethereum for security.                          |
| **9**  | —                                             | —                                                      | —                                   | L1 confirms | Ethereum records the rollup’s commitment (not each agent’s tx individually on L1). |
| **10** | —                                             | Receives **settled** + `txHash`                        | Confirms on L2                      | L2          | Payment is final on the layer agents use for receipts.                             |
| **11** | Receives **transaction receipt**              | Sends paid response                                    | —                                   | —           | Both sides can store hash, amounts, and explorer links.                            |


Steps **7–9** are how optimistic rollups work. Agents and wallets reason about **step 10 on L2** — the receipt points at the L2 transaction, not an L1 entry per purchase.

---

## Wire format

### Request — quote (payment not attached yet)

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "commerce/pay",
  "params": {
    "sessionId": "sess_abc123",
    "offerId": "nike-air-max-90",
    "offer": {
      "id": "nike-air-max-90",
      "name": "Nike Air Max 90",
      "price": 90,
      "currency": "USD"
    }
  }
}
```

### Response — payment required

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "status": "payment_required",
    "offerId": "nike-air-max-90",
    "fx": {
      "catalogUsd": 90,
      "usdc": "0.009",
      "usdcAtomic": "9000"
    },
    "x402": {
      "scheme": "exact",
      "network": "eip155:84532",
      "facilitator": "https://x402.org/facilitator",
      "payTo": "0x29A1…b5A0",
      "usdcContract": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
      "paymentRequired": { }
    },
    "balanceCheck": {
      "sufficient": true
    }
  }
}
```

### Request — execute (signed payment attached)

```json
{
  "jsonrpc": "2.0",
  "id": 43,
  "method": "commerce/pay",
  "params": {
    "sessionId": "sess_abc123",
    "offerId": "nike-air-max-90",
    "execute": true,
    "payment": { }
  }
}
```

The `payment` object carries the x402 **PaymentPayload** (signed authorization). Shape comes from the x402 SDK for the chosen scheme and network.

### Response — paid

```json
{
  "jsonrpc": "2.0",
  "id": 43,
  "result": {
    "status": "paid",
    "offerId": "nike-air-max-90",
    "receipt": {
      "catalogUsd": 90,
      "usdcPaid": "0.009",
      "payTo": "0x29A1…b5A0",
      "payer": "0x4299…e111",
      "txHash": "0xabc…def",
      "explorer": "https://sepolia.basescan.org/tx/0xabc…def",
      "ethGas": "0.000012",
      "network": "eip155:84532"
    }
  }
}
```

---

## Key rules


| Rule                     | Requirement                                                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Exact terms**          | The signed payload must match the published requirements (amount, asset, network, `payTo`).                                            |
| **Verify before settle** | Facilitator validates the payload before broadcasting.                                                                                 |
| **Receipt**              | Success means a verifiable on-chain `txHash` plus payer/payee metadata.                                                                |
| **Facilitator role**     | Seller coordinates verify/settle; buyer proves payment through signing, not by sending raw funds to an unverified address out of band. |
| **Scheme**               | `exact` is common for fixed-price commerce; other schemes exist for metered or capped spend.                                           |
| **Timeout**              | Requirements include a maximum window; stale payloads are rejected.                                                                    |


---

  
  
Why Layer 2 instead of paying directly on Layer 1?

Ethereum **Layer 1** is the shared security layer for the ecosystem. Every transaction competes for limited block space. That is the right tradeoff for high-value settlement and protocol-level guarantees — but it is expensive and slow for **frequent, small agent payments** (shoe purchases, API calls, per-request API fees).

**Layer 2** networks such as Base run on top of Ethereum with a different cost model:


|                    | Layer 1 (Ethereum)               | Layer 2 (e.g. Base)                                  |
| ------------------ | -------------------------------- | ---------------------------------------------------- |
| **Fees**           | Higher — global security premium | Lower — execution off the main auction               |
| **Latency**        | Block times suited to settlement | Faster confirmation for everyday transfers           |
| **Throughput**     | Limited base-layer capacity      | Many txs batched inside the rollup                   |
| **Security model** | Native chain finality            | Inherits Ethereum security via periodic L1 anchoring |


Depending on the type of payment, facilator may or may not use L1 directly here. the settlement duration is function of the chain you will be using. 

---

