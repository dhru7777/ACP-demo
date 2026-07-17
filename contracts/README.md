# Bilateral Escrow (Base Sepolia)

V1 escrow: buyer deposits Circle USDC → buyer confirms → seller receives.  
Buyer can **cancel()** while Funded for an immediate refund (demo **No**).  
If nobody confirms/cancels before the deadline → anyone can `refund()` to buyer.  
No dispute module.

## Prerequisites

1. [Foundry](https://book.getfoundry.sh/getting-started/installation) (`forge`, `cast`) — local compile/test only
2. Buyer + deployer wallets funded with **Base Sepolia ETH** (gas)
3. Buyer funded with **test USDC** from [Circle faucet](https://faucet.circle.com/) (network: Base Sepolia)

Runtime deploy (seller agent / Railway) loads bytecode from
`contracts/artifacts/BilateralEscrow.json` (committed). After changing
`src/BilateralEscrow.sol`, refresh it:

```bash
cd contracts && forge build
cp out/BilateralEscrow.sol/BilateralEscrow.json /tmp/be.json
# or: python from repo root to rewrite contracts/artifacts/BilateralEscrow.json
```

Defaults baked into deploy script:

| Role | Address |
|------|---------|
| Buyer | `0x4299661b083f0920750BdFEc11EedeB49ee9e111` |
| Seller | `0x29A1885E5bE21263F840c20622E9D7ed6d35b5A0` |
| USDC | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` |
| Amount | `1000000` (1 USDC, 6 decimals) |
| Duration | 1 day |

The **escrow address does not exist until you deploy**. After deploy, that contract address holds the USDC.

## Setup

```bash
cd contracts
cp .env.example .env
# Edit .env: set PRIVATE_KEY (0x-prefixed) for the deploying wallet
```

## Test locally

```bash
cd contracts
forge test -vv
```

## Deploy to Base Sepolia

```bash
cd contracts
source .env   # or: set -a; source .env; set +a

forge script script/Deploy.s.sol:Deploy \
  --rpc-url "$BASE_SEPOLIA_RPC" \
  --broadcast \
  -vvvv
```

Copy the printed `BilateralEscrow deployed: 0x...` — that is your escrow address.

## Approve → deposit → confirm (buyer key)

Use the **buyer** private key as `PRIVATE_KEY` for these steps:

```bash
export ESCROW=0xYourEscrowAddress

ACTION=approve forge script script/Interact.s.sol:Interact \
  --rpc-url "$BASE_SEPOLIA_RPC" --broadcast -vvvv

ACTION=deposit forge script script/Interact.s.sol:Interact \
  --rpc-url "$BASE_SEPOLIA_RPC" --broadcast -vvvv

# After off-chain delivery / when ready to pay seller:
ACTION=confirm forge script script/Interact.s.sol:Interact \
  --rpc-url "$BASE_SEPOLIA_RPC" --broadcast -vvvv

# Or buyer aborts (instant refund while Funded):
ACTION=cancel forge script script/Interact.s.sol:Interact \
  --rpc-url "$BASE_SEPOLIA_RPC" --broadcast -vvvv
```

## Refund after deadline

Anyone can call (still needs a funded key for gas):

```bash
ACTION=refund forge script script/Interact.s.sol:Interact \
  --rpc-url "$BASE_SEPOLIA_RPC" --broadcast -vvvv
```

## States

`Created (0) → Funded (1) → Released (2)` or `Refunded (3)`
