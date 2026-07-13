// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

/// @title BilateralEscrow (V1.1)
/// @notice Buyer locks ERC-20; confirm → seller; cancel (buyer) or refund (after deadline) → buyer.
/// @dev No dispute module. Seller is receive-only.
contract BilateralEscrow {
    enum State {
        Created,
        Funded,
        Released,
        Refunded
    }

    address public immutable buyer;
    address public immutable seller;
    IERC20 public immutable token;
    uint256 public immutable amount;
    uint256 public immutable deadline;

    State public state;

    event Deposited(address indexed buyer, uint256 amount);
    event Released(address indexed seller, uint256 amount);
    event Refunded(address indexed buyer, uint256 amount);
    event Cancelled(address indexed buyer, uint256 amount);

    constructor(
        address buyer_,
        address seller_,
        address token_,
        uint256 amount_,
        uint256 durationSeconds_
    ) {
        require(buyer_ != address(0), "buyer=0");
        require(seller_ != address(0), "seller=0");
        require(token_ != address(0), "token=0");
        require(buyer_ != seller_, "buyer=seller");
        require(amount_ > 0, "amount=0");
        require(durationSeconds_ > 0, "duration=0");

        buyer = buyer_;
        seller = seller_;
        token = IERC20(token_);
        amount = amount_;
        deadline = block.timestamp + durationSeconds_;
        state = State.Created;
    }

    function deposit() external {
        require(msg.sender == buyer, "only buyer");
        require(state == State.Created, "not Created");

        bool ok = token.transferFrom(buyer, address(this), amount);
        require(ok, "transferFrom failed");

        state = State.Funded;
        emit Deposited(buyer, amount);
    }

    function confirm() external {
        require(msg.sender == buyer, "only buyer");
        require(state == State.Funded, "not Funded");

        state = State.Released;

        bool ok = token.transfer(seller, amount);
        require(ok, "transfer failed");

        emit Released(seller, amount);
    }

    /// @notice Buyer aborts while Funded — immediate refund (demo "No" / cancel).
    function cancel() external {
        require(msg.sender == buyer, "only buyer");
        require(state == State.Funded, "not Funded");

        state = State.Refunded;

        bool ok = token.transfer(buyer, amount);
        require(ok, "transfer failed");

        emit Cancelled(buyer, amount);
        emit Refunded(buyer, amount);
    }

    /// @notice Anyone after deadline if still Funded — timeout refund to buyer.
    function refund() external {
        require(state == State.Funded, "not Funded");
        require(block.timestamp > deadline, "too early");

        state = State.Refunded;

        bool ok = token.transfer(buyer, amount);
        require(ok, "transfer failed");

        emit Refunded(buyer, amount);
    }
}
