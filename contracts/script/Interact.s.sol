// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console2} from "forge-std/Script.sol";
import {BilateralEscrow} from "../src/BilateralEscrow.sol";

interface IERC20Approve {
    function approve(address spender, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/// @notice Buyer-side helpers. Set ESCROW and use BUYER private key as PRIVATE_KEY.
///   ACTION=approve|deposit|confirm|cancel|refund
contract Interact is Script {
    function run() external {
        address escrowAddr = vm.envAddress("ESCROW");
        string memory action = vm.envString("ACTION");
        uint256 pk = vm.envUint("PRIVATE_KEY");

        BilateralEscrow escrow = BilateralEscrow(escrowAddr);
        IERC20Approve token = IERC20Approve(address(escrow.token()));
        uint256 amount = escrow.amount();

        vm.startBroadcast(pk);

        if (_eq(action, "approve")) {
            bool ok = token.approve(escrowAddr, amount);
            require(ok, "approve failed");
            console2.log("approved escrow for amount", amount);
        } else if (_eq(action, "deposit")) {
            escrow.deposit();
            console2.log("deposited; state", uint256(escrow.state()));
        } else if (_eq(action, "confirm")) {
            escrow.confirm();
            console2.log("confirmed; state", uint256(escrow.state()));
        } else if (_eq(action, "cancel")) {
            escrow.cancel();
            console2.log("cancelled; state", uint256(escrow.state()));
        } else if (_eq(action, "refund")) {
            escrow.refund();
            console2.log("refunded; state", uint256(escrow.state()));
        } else {
            revert("ACTION must be approve|deposit|confirm|cancel|refund");
        }

        vm.stopBroadcast();

        console2.log("buyer USDC", token.balanceOf(escrow.buyer()));
        console2.log("seller USDC", token.balanceOf(escrow.seller()));
        console2.log("escrow USDC", token.balanceOf(escrowAddr));
    }

    function _eq(string memory a, string memory b) internal pure returns (bool) {
        return keccak256(bytes(a)) == keccak256(bytes(b));
    }
}
