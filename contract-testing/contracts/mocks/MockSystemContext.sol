// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ISystemContext} from "../interfaces/ISystemContext.sol";

contract MockSystemContext is ISystemContext {
    uint256 private _chainId;
    address private _origin;
    uint256 private _gasPrice;
    uint256 private _blockGasLimit;
    address private _coinbase;
    uint256 private _difficulty;
    uint256 private _baseFee;
    uint16 private _txNumberInBlock;
    uint256 private _gasPerPubdataByte;
    uint256 private _currentPubdataSpent;
    uint128 private _blockNumber;
    uint128 private _blockTimestamp;
    uint128 private _l2BlockNumber;
    uint128 private _l2BlockTimestamp;
    mapping(uint256 => bytes32) private _blockHashes;
    mapping(uint256 => bytes32) private _batchHashes;

    function chainId() external view override returns (uint256) {
        return _chainId;
    }

    function origin() external view override returns (address) {
        return _origin;
    }

    function gasPrice() external view override returns (uint256) {
        return _gasPrice;
    }

    function blockGasLimit() external view override returns (uint256) {
        return _blockGasLimit;
    }

    function coinbase() external view override returns (address) {
        return _coinbase;
    }

    function difficulty() external view override returns (uint256) {
        return _difficulty;
    }

    function baseFee() external view override returns (uint256) {
        return _baseFee;
    }

    function txNumberInBlock() external view override returns (uint16) {
        return _txNumberInBlock;
    }

    function gasPerPubdataByte() external view override returns (uint256) {
        return _gasPerPubdataByte;
    }

    function getCurrentPubdataSpent() external view override returns (uint256) {
        return _currentPubdataSpent;
    }

    function getBlockHashEVM(uint256 _block) external view override returns (bytes32) {
        return _blockHashes[_block];
    }

    function getBatchHash(uint256 _batchNumber) external view override returns (bytes32) {
        return _batchHashes[_batchNumber];
    }

    function getBlockNumber() external view override returns (uint128) {
        return _blockNumber;
    }

    function getBlockTimestamp() external view override returns (uint128) {
        return _blockTimestamp;
    }

    function getBatchNumberAndTimestamp() external view override returns (uint128 blockNumber, uint128 blockTimestamp) {
        return (_blockNumber, _blockTimestamp);
    }

    function getL2BlockNumberAndTimestamp() external view override returns (uint128 blockNumber, uint128 blockTimestamp) {
        return (_l2BlockNumber, _l2BlockTimestamp);
    }

    // Mock functions to set values for testing
    function setChainId(uint256 _value) external {
        _chainId = _value;
    }

    function setOrigin(address _value) external {
        _origin = _value;
    }

    function setGasPrice(uint256 _value) external {
        _gasPrice = _value;
    }

    function setBlockGasLimit(uint256 _value) external {
        _blockGasLimit = _value;
    }

    function setCoinbase(address _value) external {
        _coinbase = _value;
    }

    function setDifficulty(uint256 _value) external {
        _difficulty = _value;
    }

    function setBaseFee(uint256 _value) external {
        _baseFee = _value;
    }

    function setTxNumberInBlock(uint16 _value) external {
        _txNumberInBlock = _value;
    }

    function setGasPerPubdataByte(uint256 _value) external {
        _gasPerPubdataByte = _value;
    }

    function setCurrentPubdataSpent(uint256 _value) external {
        _currentPubdataSpent = _value;
    }

    function setBlockHash(uint256 _block, bytes32 _hash) external {
        _blockHashes[_block] = _hash;
    }

    function setBatchHash(uint256 _batchNumber, bytes32 _hash) external {
        _batchHashes[_batchNumber] = _hash;
    }

    function setBlockNumber(uint128 _value) external {
        _blockNumber = _value;
    }

    function setBlockTimestamp(uint128 _value) external {
        _blockTimestamp = _value;
    }

    function setL2BlockNumber(uint128 _value) external {
        _l2BlockNumber = _value;
    }

    function setL2BlockTimestamp(uint128 _value) external {
        _l2BlockTimestamp = _value;
    }
} 