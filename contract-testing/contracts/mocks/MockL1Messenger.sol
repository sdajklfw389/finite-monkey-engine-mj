// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IL1Messenger} from "../interfaces/IL1Messenger.sol";

contract MockL1Messenger is IL1Messenger {
    bytes32 private _lastMessage;
    bytes32 private _lastL2ToL1Log;
    bytes32 private _lastL2ToL1Message;
    bytes32 private _lastL2ToL1LogHash;
    bytes32 private _lastL2ToL1MessageHash;
    uint256 private _lastLogIdInMerkleTree;

    function sendToL1(bytes memory _message) external returns (bytes32) {
        _lastMessage = keccak256(_message);
        return _lastMessage;
    }

    function sendL2ToL1Log(
        bool _isService,
        address _sender,
        bytes32 _key,
        bytes32 _value
    ) external returns (bytes32) {
        _lastL2ToL1Log = keccak256(abi.encode(_isService, _sender, _key, _value));
        return _lastL2ToL1Log;
    }

    function sendL2ToL1Message(
        bytes memory _message,
        uint256 _gasLimit
    ) external returns (bytes32) {
        _lastL2ToL1Message = keccak256(_message);
        return _lastL2ToL1Message;
    }

    function sendL2ToL1LogHash(
        bool _isService,
        address _sender,
        bytes32 _key,
        bytes32 _value
    ) external returns (bytes32) {
        _lastL2ToL1LogHash = keccak256(abi.encode(_isService, _sender, _key, _value));
        return _lastL2ToL1LogHash;
    }

    function sendL2ToL1MessageHash(
        bytes memory _message,
        uint256 _gasLimit
    ) external returns (bytes32) {
        _lastL2ToL1MessageHash = keccak256(_message);
        return _lastL2ToL1MessageHash;
    }

    // Implement missing interface functions
    function sendL2ToL1Log(
        bool _isService,
        bytes32 _key,
        bytes32 _value
    ) external returns (uint256 logIdInMerkleTree) {
        _lastL2ToL1Log = keccak256(abi.encode(_isService, _key, _value));
        _lastLogIdInMerkleTree = uint256(keccak256(abi.encodePacked(block.timestamp, _lastL2ToL1Log)));
        return _lastLogIdInMerkleTree;
    }

    function requestBytecodeL1Publication(bytes32 _bytecodeHash) external {
        // Mock implementation - just store the hash
        _lastMessage = _bytecodeHash;
    }

    // Mock functions for testing
    function getLastMessage() external view returns (bytes32) {
        return _lastMessage;
    }

    function getLastL2ToL1Log() external view returns (bytes32) {
        return _lastL2ToL1Log;
    }

    function getLastL2ToL1Message() external view returns (bytes32) {
        return _lastL2ToL1Message;
    }

    function getLastL2ToL1LogHash() external view returns (bytes32) {
        return _lastL2ToL1LogHash;
    }

    function getLastL2ToL1MessageHash() external view returns (bytes32) {
        return _lastL2ToL1MessageHash;
    }

    function getLastLogIdInMerkleTree() external view returns (uint256) {
        return _lastLogIdInMerkleTree;
    }
} 