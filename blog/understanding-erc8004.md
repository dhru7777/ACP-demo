---
layout: post
title: "Understanding ERC-8004: Identity, Reputation, and Validation for Agents"
date: 2026-06-22
excerpt: "ERC-8004 is a global on-chain registry for agents: identity via ERC-721, buyer feedback on the Reputation Registry, and third-party attestation on the Validation Registry. This post walks through KYA, a Nike commerce demo on Base Sepolia, and where the model breaks in the real world."
---

## What is ERC-8004?

**ERC-8004** is a protocol to build a **global registry for agents**, giving them **identity**, **reputation**, and **validation** on-chain.

There are roughly eight billion people on this planet. If every human eventually runs one agent to achieve a particular task, we need a way to keep those agents accountable. A global registry with a history of each agent’s activity, promoted or demoted based on what it actually did, and a record that cannot be tampered with or manipulated because it lives on a blockchain.

As the population of agents grows, we need a **decentralized directory**. These agents are borderless and internet-native. They can transact on behalf of a user and disrupt cross-border payments. That enables **KYA (Know Your Agent)**, the same way finance uses KYC for people.

This solves **discovery** (global identity), which builds **trust**.

---

## How does it work?

ERC-8004 combines **three registries**:


| Registry       | Question it answers                         | Analogy                                  |
| -------------- | ------------------------------------------- | ---------------------------------------- |
| **Identity**   | Who is this agent?                          | A business license with a public listing |
| **Reputation** | How did buyers rate it?                     | Customers reviewing a restaurant         |
| **Validation** | Did an independent party verify its claims? | A food inspector certifying the kitchen  |


---

## 1) Identity Registry

Agents register on the **Identity Registry** using **ERC-721**. Each agent is an **NFT (Non-Fungible Token)**. That makes every agent immediately **browsable and transferable** across NFT-compliant apps.

In this demo, the seller is **Nike Seller Agent** (`vendor · nike.com`), registered as agent `**#6832`** on **Base Sepolia**.

**Figure 1: Identity (ID tab).** Agent ID, chain, global ID (`eip155:84532:…:6832`), owner, agent wallet, and x402 support. [View on 8004scan](https://testnet.8004scan.io/agents/base-sepolia/6832).

The on-chain NFT points to an off-chain **registration file** (`agentURI`). Ours looks like this:

```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "Attention Agent",
  "description": "ACP commerce agent that turns buyer intent into catalog offers and real payments.",
  "image": "https://blob.8004scan.app/30aefe5a...fcb3d869.jpg",
  "services": [
    {
      "name": "custom",
      "endpoint": "https://acp-demo-production.up.railway.app/"
    }
  ],
  "registrations": [
    {
      "agentId": 6832,
      "agentRegistry": "eip155:84532:0x8004A818...A494BD9e"
    }
  ],
  "supportedTrusts": ["reputation", "tee-attestation"],
  "active": true,
  "x402support": true
}
```


| Field                 | Meaning                                                                                               |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| `services[].endpoint` | Live seller URL (Railway in this demo)                                                                |
| `registrations[]`     | Links this file back to on-chain agent ID + registry contract                                         |
| `x402support`         | Agent accepts x402 machine payments                                                                   |
| `supportedTrusts`     | Declared trust models (`reputation`; `tee-attestation` is metadata until Validation Registry is used) |


---

## 2) Reputation Registry

Once an agent is registered and publicly visible, its credibility grows over time through **on-chain feedback**. In this demo, after the buyer agent purchases shoes, it gives feedback to the seller agent.

That feedback can measure quality of service (star rating), whether the agent is reachable, whether the owner is verified, uptime, success rate, response time, revenue, yield, and more. The better an agent performs, the faster it climbs discoverability rankings.

Feedback is structured in an **off-chain file**; a **hash** (or inline URI) is submitted **on-chain** via `giveFeedback()`.

After the transaction completes, the buyer agent sends **4 stars**, which equals **80 points** (`stars × 20`).

**Figure 2: Rating UI.** Four filled stars map to **80 / 100**. The demo auto-submits after 3 seconds unless the user adjusts stars.

**Figure 3: Submitting feedback.** The buyer wallet signs and broadcasts `giveFeedback()` on the Reputation Registry (8004).

That feedback is averaged with previous feedback. For agent `#6832` on [8004scan](https://testnet.8004scan.io/agents/base-sepolia/6832):


| Metric                    | Value                |
| ------------------------- | -------------------- |
| Average score             | **4.2 / 5** (85/100) |
| Total feedback            | **16**               |
| Overall leaderboard score | **20.83**            |


**Figure 4: Feedback on 8004scan.** Each row links to a wallet, tags (`x402`, `acp-commerce`), endpoint, and an explorer tx. The **overall score (20.83)** is a composite leaderboard rank, not the same as the star average alone.

The demo profile surfaces the same numbers on the **Feedback** tab:

**Figure 5: Profile Feedback tab.** On-chain feedback count, average score, your x402 payment history, and publisher.

8004scan blends multiple dimensions when computing rank: engagement, service, compliance, momentum.

**Figure 6: Score breakdown.** Weighted dimensions produce the leaderboard score. **Avg validation score: 0** because there are no Validation Registry attestations in this demo yet.

The **Rank** tab in the demo shows indexer-derived health, popularity, freshness, and related signals:

**Figure 7: Profile Rank tab.** Indexer-computed dimensions that drive discoverability beyond raw star averages.

### Why fake feedback is harder

Every `giveFeedback` call costs **gas**. Bots are usually not willing to pay for every review, so each feedback carries a real cost. Tags (`x402`, `acp-commerce`) let indexers filter agents the way you filter restaurants on Google Maps: by rating, context, and endpoint. That improves **discoverability** and **fosters trust**.

It is similar to looking for the best restaurant in your city: public scores, many reviewers, and filters, except here the reviews are on-chain and portable across apps.

### Code: submit feedback

After the buyer taps 4★ in the demo, the backend calls `submit_give_feedback()` (`trust/reputation_chain.py`):

```python
def submit_give_feedback(*, chain_id, agent_id, value, tag1, tag2, endpoint, feedback_uri):
    wallet = load_buyer_wallet()
    registry = reputation_registry_for_chain(chain_id)
    calldata = encode_give_feedback(agent_id, value, 0, tag1, tag2, endpoint, feedback_uri, b"\x00" * 32)

    tx = {"chainId": chain_id, "to": registry, "data": calldata, "from": wallet.address}
    signed = Account.sign_transaction(tx, wallet.private_key)
    return {"txHash": rpc("eth_sendRawTransaction", [signed.raw_transaction.hex()])}


submit_give_feedback(
    chain_id=84532,
    agent_id=6832,
    value=80,
    tag1="x402",
    tag2="acp-commerce",
    endpoint="https://acp-demo-production.up.railway.app",
    feedback_uri=_build_feedback_uri(payment_receipt),
)
```

On-chain each feedback carries:


| Field          | Example in demo                    | Purpose                    |
| -------------- | ---------------------------------- | -------------------------- |
| `value`        | `80`                               | Score 0–100 (4 stars × 20) |
| `tag1`         | `x402`                             | Payment rail used          |
| `tag2`         | `acp-commerce`                     | Commerce context           |
| `feedback_uri` | `data:application/json;base64,...` | Off-chain payment proof    |


---

## 3) Validation Registry

The **Validation Registry** is the on-chain contract where **trusted validators** attest that an agent’s claimed capabilities, identity, or runtime behavior (TEE proofs, audits, service checks) are genuine. This is **separate from buyer ratings** in the Reputation Registry.


|                    | Reputation Registry               | Validation Registry           |
| ------------------ | --------------------------------- | ----------------------------- |
| **Who submits**    | Buyer / client after use          | Named validator address       |
| **What it proves** | “I paid and rate this experience” | “I tested and attest claim X” |


---

## Advantages


| Parameter                   | Explanation                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Public trust record**     | Ratings live on-chain; anyone can verify them, not just trust a platform’s database                    |
| **Portable reputation**     | An agent’s score follows its ERC-8004 identity across apps and indexers, not locked to one marketplace |
| **Spam is costly**          | Gas makes mass fake reviews more expensive than free web ratings                                       |
| **Tied to real wallets**    | Each review links to an address, so accountability is stronger than anonymous forms                    |
| **Better discoverability**  | Indexers (e.g. 8004scan) turn feedback into rankings so good agents get found faster                   |
| **Richer context possible** | Off-chain proofs (payment receipt, test report) can back the on-chain score                            |
| **Independent validators**  | Validation Registry lets third parties attest quality, not only buyer opinions                         |


---

## Limitations


| Parameter                        | Explanation                                                                                    |
| -------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Gas kills participation**      | Unlike Google/Yelp, buyers must pay to rate; most won’t, so scores skew toward motivated users |
| **Off-chain storage cost & ops** | Detailed proofs need IPFS/hosting; someone pays and maintains that data                        |
| **Sybil attacks still possible** | Gas helps but doesn’t stop someone funding many wallets to inflate ratings                     |
| **Slow to show up**              | On-chain tx ≠ instant rank change; indexers lag, so UX feels broken to normal users            |
| **Wallet UX barrier**            | Mainstream buyers don’t want to sign crypto txs after buying shoes                             |
| **Rank is confusing**            | Leaderboard score ≠ simple star average; users misread trust signals                           |
| **No recourse for bad reviews**  | Mistaken or malicious on-chain feedback is hard to remove or dispute                           |


---

## How this demo fits together

```
ACP session     →  negotiate shoes
x402 payment    →  settle USDC on Base Sepolia
ERC-8004 ID     →  verify agent #6832 before / after pay
giveFeedback    →  buyer rates seller on Reputation Registry
8004scan        →  rank updates → better discoverability
```

**Live references**

- [Demo UI](https://dheeraj-agentic-communication-demo.netlify.app)
- [Seller API: ERC-8004 registration](https://acp-demo-production.up.railway.app/agent/erc8004)
- [8004scan: Agent 6832](https://testnet.8004scan.io/agents/base-sepolia/6832)
- [EIP-8004](https://eips.ethereum.org/EIPS/eip-8004)

---

