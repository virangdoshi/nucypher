pragma solidity ^0.5.3;


import "zeppelin/math/SafeMath.sol";
import "contracts/NuCypherToken.sol";
import "contracts/MinersEscrow.sol";


/**
* @notice The WorkLock distribution contract
**/
contract WorkLock {
    using SafeMath for uint256;

    event Bid(address indexed miner, uint256 depositedETH, uint256 claimedTokens);
    event Claimed(address indexed miner, uint256 claimedTokens);
    event Refund(address indexed miner, uint256 refundETH, uint256 workDone);

    struct WorkInfo {
        uint256 depositedETH;
        uint256 workDone;
        bool claimed;
    }

    NuCypherToken public token;
    MinersEscrow public escrow;
    uint256 public startBidDate;
    uint256 public endBidDate;
    // ETH -> NU
    uint256 public depositRate;
    // Work (reward in NU) -> ETH
    uint256 public refundRate;
    uint256 public minAllowableLockedTokens;
    uint256 public maxAllowableLockedTokens;
    uint256 public allClaimedTokens;
    uint16 public lockedPeriods;
    mapping(address => WorkInfo) public workInfo;

    /**
    * @param _token Token contract
    * @param _escrow Escrow contract
    * @param _startBidDate Timestamp when bidding starts
    * @param _endBidDate Timestamp when bidding will end
    * @param _depositRate ETH -> NU rate
    * @param _refundRate Work -> ETH rate
    * @param _lockedPeriods Number of periods during which claimed tokens will be locked
    **/
    constructor(
        NuCypherToken _token,
        MinersEscrow _escrow,
        uint256 _startBidDate,
        uint256 _endBidDate,
        uint256 _depositRate,
        uint256 _refundRate,
        uint16 _lockedPeriods
    )
        public
    {
        require(_token.totalSupply() > 0 &&
            _escrow.secondsPerPeriod() > 0 &&
            _endBidDate > _startBidDate &&
            _endBidDate > block.timestamp &&
            _depositRate > 0 &&
            _refundRate > 0 &&
            _lockedPeriods >= _escrow.minLockedPeriods());
        token = _token;
        escrow = _escrow;
        startBidDate = _startBidDate;
        endBidDate = _endBidDate;
        minAllowableLockedTokens = _escrow.minAllowableLockedTokens();
        maxAllowableLockedTokens = _escrow.maxAllowableLockedTokens();
        depositRate = _depositRate;
        refundRate = _refundRate;
        lockedPeriods = _lockedPeriods;
    }

    /**
    * @notice Bid for tokens by transferring ETH
    **/
    function bid() public payable returns (uint256 newClaimedTokens) {
        require(block.timestamp >= startBidDate && block.timestamp <= endBidDate,
            "Bid is open during a certain period");
        WorkInfo storage info = workInfo[msg.sender];
        info.depositedETH = info.depositedETH.add(msg.value);
        uint256 claimedTokens = info.depositedETH.mul(depositRate);
        require(claimedTokens >= minAllowableLockedTokens && claimedTokens <= maxAllowableLockedTokens,
            "Claimed tokens must be within the allowed limits");
        newClaimedTokens = msg.value.mul(depositRate);
        allClaimedTokens = allClaimedTokens.add(newClaimedTokens);
        require(allClaimedTokens <= token.balanceOf(address(this)),
            "Not enough tokens in the contract");
        emit Bid(msg.sender, msg.value, newClaimedTokens);
    }

    /**
    * @notice Claimed tokens will be deposited and locked as stake in the MinersEscrow contract.
    **/
    function claim() public returns (uint256 claimedTokens) {
        require(block.timestamp >= endBidDate, "Claiming tokens allowed after bidding is over");
        WorkInfo storage info = workInfo[msg.sender];
        require(!info.claimed, "Tokens are already claimed");
        info.claimed = true;
        claimedTokens = info.depositedETH.mul(depositRate);
        info.workDone = escrow.setWorkMeasurement(msg.sender, true);
        token.approve(address(escrow), claimedTokens);
        escrow.deposit(msg.sender, claimedTokens, lockedPeriods);
        emit Claimed(msg.sender, claimedTokens);
    }

    /**
    * @notice Refund ETH for the work done
    **/
    function refund() public returns (uint256 refundETH) {
        WorkInfo storage info = workInfo[msg.sender];
        require(info.claimed, "Tokens are not claimed");
        require(info.depositedETH > 0, "Nothing deposited");
        uint256 currentWork = escrow.getWorkDone(msg.sender);
        uint256 workDone = currentWork.sub(info.workDone);
        require(workDone > 0, "No work has been done.");
        refundETH = workDone.div(refundRate);
        if (refundETH > info.depositedETH) {
            refundETH = info.depositedETH;
        }
        if (refundETH == info.depositedETH) {
            escrow.setWorkMeasurement(msg.sender, false);
        }
        info.depositedETH = info.depositedETH.sub(refundETH);
        workDone = refundETH.mul(refundRate);
        info.workDone = info.workDone.add(workDone);
        emit Refund(msg.sender, refundETH, workDone);
        msg.sender.transfer(refundETH);
    }

    /**
    * @notice Get remaining work to full refund
    **/
    function getRemainingWork(address _miner) public view returns (uint256) {
        WorkInfo storage info = workInfo[_miner];
        uint256 workDone = escrow.getWorkDone(_miner).sub(info.workDone);
        uint256 remainingWork = info.depositedETH.mul(refundRate);
        if (remainingWork <= workDone) {
            return 0;
        }
        return remainingWork.sub(workDone);
    }

}
