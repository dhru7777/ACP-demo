// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console2} from "forge-std/Script.sol";
import {BilateralEscrow} from "../src/BilateralEscrow.sol";

/// @notice Deploy BilateralEscrow to Base Sepolia (or any RPC).
/// Env (optional overrides):
///   BUYER, SELLER, TOKEN, AMOUNT, DURATION_SECONDS
contract Deploy is Script {
    // Defaults from acp-demo Base Sepolia setup
    address constant DEFAULT_BUYER = 0x4299661b083f0920750BdFEc11EedeB49ee9e111;
    address constant DEFAULT_SELLER = 0x29A1885E5bE21263F840c20622E9D7ed6d35b5A0;
    address constant DEFAULT_USDC = 0x036CbD53842c5426634e7929541eC2318f3dCF7e;
    uint256 constant DEFAULT_AMOUNT = 1_000_000; // 1 USDC (6 decimals)
    uint256 constant DEFAULT_DURATION = 1 days;

    function run() external {
        address buyer = vm.envOr("BUYER", DEFAULT_BUYER);
        address seller = vm.envOr("SELLER", DEFAULT_SELLER);
        address token = vm.envOr("TOKEN", DEFAULT_USDC);
        uint256 amount = vm.envOr("AMOUNT", DEFAULT_AMOUNT);
        uint256 duration = vm.envOr("DURATION_SECONDS", DEFAULT_DURATION);

        uint256 pk = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(pk);
        BilateralEscrow escrow = new BilateralEscrow(buyer, seller, token, amount, duration);
        vm.stopBroadcast();

        console2.log("BilateralEscrow deployed:", address(escrow));
        console2.log("buyer:", buyer);
        console2.log("seller:", seller);
        console2.log("token:", token);
        console2.log("amount:", amount);
        console2.log("deadline:", escrow.deadline());
    }
}
