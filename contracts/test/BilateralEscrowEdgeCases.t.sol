// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {BilateralEscrow} from "../src/BilateralEscrow.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";

/// @notice Edge cases — contract correctly rejects bad paths; cancel solves early refund.
contract BilateralEscrowEdgeCasesTest is Test {
    MockUSDC internal usdc;
    address internal buyer = makeAddr("buyer");
    address internal seller = makeAddr("seller");
    address internal stranger = makeAddr("stranger");
    uint256 internal constant AMOUNT = 1_000_000;
    uint256 internal constant DURATION = 1 days;

    function _deploy() internal returns (BilateralEscrow) {
        return new BilateralEscrow(buyer, seller, address(usdc), AMOUNT, DURATION);
    }

    function _fund(BilateralEscrow escrow) internal {
        vm.startPrank(buyer);
        usdc.approve(address(escrow), AMOUNT);
        escrow.deposit();
        vm.stopPrank();
    }

    function setUp() public {
        usdc = new MockUSDC();
        usdc.mint(buyer, AMOUNT * 100);
        usdc.mint(stranger, AMOUNT * 100);
    }

    function test_edge01_sellerCannotDeposit() public {
        BilateralEscrow escrow = _deploy();
        vm.startPrank(seller);
        usdc.mint(seller, AMOUNT);
        usdc.approve(address(escrow), AMOUNT);
        vm.expectRevert(bytes("only buyer"));
        escrow.deposit();
        vm.stopPrank();
    }

    function test_edge02_doubleDepositFails() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        vm.startPrank(buyer);
        usdc.approve(address(escrow), AMOUNT);
        vm.expectRevert(bytes("not Created"));
        escrow.deposit();
        vm.stopPrank();
    }

    function test_edge03_confirmBeforeDepositFails() public {
        BilateralEscrow escrow = _deploy();
        vm.prank(buyer);
        vm.expectRevert(bytes("not Funded"));
        escrow.confirm();
    }

    function test_edge04_sellerCannotConfirm() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        vm.prank(seller);
        vm.expectRevert(bytes("only buyer"));
        escrow.confirm();
    }

    function test_edge05_doubleConfirmFails() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        vm.startPrank(buyer);
        escrow.confirm();
        vm.expectRevert(bytes("not Funded"));
        escrow.confirm();
        vm.stopPrank();
    }

    /// Edge #6 FIXED: buyer cancel() refunds immediately (demo No).
    function test_edge06_buyerCancelRefundsImmediately() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        uint256 before = usdc.balanceOf(buyer);
        vm.prank(buyer);
        escrow.cancel();

        assertEq(uint256(escrow.state()), uint256(BilateralEscrow.State.Refunded));
        assertEq(usdc.balanceOf(address(escrow)), 0);
        assertEq(usdc.balanceOf(buyer), before + AMOUNT);
    }

    /// Timeout refund still blocked before deadline; cancel is the early path.
    function test_edge06b_refundBeforeDeadlineStillFails() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        vm.prank(buyer);
        vm.expectRevert(bytes("too early"));
        escrow.refund();
    }

    function test_edge07_refundAfterReleaseFails() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        vm.prank(buyer);
        escrow.confirm();

        vm.warp(block.timestamp + DURATION + 1);
        vm.expectRevert(bytes("not Funded"));
        escrow.refund();
    }

    function test_edge07b_cancelAfterReleaseFails() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);

        vm.prank(buyer);
        escrow.confirm();

        vm.prank(buyer);
        vm.expectRevert(bytes("not Funded"));
        escrow.cancel();
    }

    function test_edge08_depositWithoutApproveFails() public {
        BilateralEscrow escrow = _deploy();
        vm.prank(buyer);
        vm.expectRevert(bytes("allowance"));
        escrow.deposit();
    }

    function test_edge09_insufficientBalanceFails() public {
        address broke = makeAddr("brokeBuyer");
        BilateralEscrow escrow =
            new BilateralEscrow(broke, seller, address(usdc), AMOUNT, DURATION);

        usdc.mint(broke, AMOUNT - 1);
        vm.startPrank(broke);
        usdc.approve(address(escrow), AMOUNT);
        vm.expectRevert(bytes("balance"));
        escrow.deposit();
        vm.stopPrank();
    }

    function test_edge10_badConstructorArgsFail() public {
        vm.expectRevert(bytes("buyer=0"));
        new BilateralEscrow(address(0), seller, address(usdc), AMOUNT, DURATION);

        vm.expectRevert(bytes("seller=0"));
        new BilateralEscrow(buyer, address(0), address(usdc), AMOUNT, DURATION);

        vm.expectRevert(bytes("token=0"));
        new BilateralEscrow(buyer, seller, address(0), AMOUNT, DURATION);

        vm.expectRevert(bytes("buyer=seller"));
        new BilateralEscrow(buyer, buyer, address(usdc), AMOUNT, DURATION);

        vm.expectRevert(bytes("amount=0"));
        new BilateralEscrow(buyer, seller, address(usdc), 0, DURATION);

        vm.expectRevert(bytes("duration=0"));
        new BilateralEscrow(buyer, seller, address(usdc), AMOUNT, 0);
    }

    function test_edge_sellerCannotCancel() public {
        BilateralEscrow escrow = _deploy();
        _fund(escrow);
        vm.prank(seller);
        vm.expectRevert(bytes("only buyer"));
        escrow.cancel();
    }
}
