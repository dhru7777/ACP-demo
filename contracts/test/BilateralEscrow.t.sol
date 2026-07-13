// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {BilateralEscrow} from "../src/BilateralEscrow.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";

contract BilateralEscrowTest is Test {
    MockUSDC internal usdc;
    BilateralEscrow internal escrow;

    address internal buyer = makeAddr("buyer");
    address internal seller = makeAddr("seller");
    uint256 internal constant AMOUNT = 1_000_000; // 1 mUSDC
    uint256 internal constant DURATION = 1 days;

    function setUp() public {
        usdc = new MockUSDC();
        usdc.mint(buyer, AMOUNT * 10);

        escrow = new BilateralEscrow(buyer, seller, address(usdc), AMOUNT, DURATION);
    }

    function test_deposit_confirm_releasesToSeller() public {
        vm.startPrank(buyer);
        usdc.approve(address(escrow), AMOUNT);
        escrow.deposit();
        assertEq(uint256(escrow.state()), uint256(BilateralEscrow.State.Funded));
        assertEq(usdc.balanceOf(address(escrow)), AMOUNT);

        escrow.confirm();
        vm.stopPrank();

        assertEq(uint256(escrow.state()), uint256(BilateralEscrow.State.Released));
        assertEq(usdc.balanceOf(seller), AMOUNT);
        assertEq(usdc.balanceOf(address(escrow)), 0);
    }

    function test_refund_afterDeadline() public {
        vm.startPrank(buyer);
        usdc.approve(address(escrow), AMOUNT);
        escrow.deposit();
        vm.stopPrank();

        vm.warp(block.timestamp + DURATION + 1);

        // Anyone may call refund after deadline
        vm.prank(address(0xDEAD));
        escrow.refund();

        assertEq(uint256(escrow.state()), uint256(BilateralEscrow.State.Refunded));
        assertEq(usdc.balanceOf(buyer), AMOUNT * 10); // full balance restored
        assertEq(usdc.balanceOf(address(escrow)), 0);
    }

    function test_refund_revertsBeforeDeadline() public {
        vm.startPrank(buyer);
        usdc.approve(address(escrow), AMOUNT);
        escrow.deposit();
        vm.stopPrank();

        vm.expectRevert(bytes("too early"));
        escrow.refund();
    }

    function test_onlyBuyerCanDepositAndConfirm() public {
        vm.prank(seller);
        vm.expectRevert(bytes("only buyer"));
        escrow.deposit();

        vm.startPrank(buyer);
        usdc.approve(address(escrow), AMOUNT);
        escrow.deposit();
        vm.stopPrank();

        vm.prank(seller);
        vm.expectRevert(bytes("only buyer"));
        escrow.confirm();
    }
}
