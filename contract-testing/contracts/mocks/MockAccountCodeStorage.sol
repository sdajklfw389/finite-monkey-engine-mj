// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IAccountCodeStorage} from "../interfaces/IAccountCodeStorage.sol";

contract MockAccountCodeStorage is IAccountCodeStorage {
    mapping(address => bytes32) private _codeHashes;
    mapping(address => bytes32) private _codeHashesHistory;
    mapping(address => uint256) private _codeSizes;
    mapping(address => uint256) private _codeSizesHistory;
    mapping(address => bool) private _isConstructed;
    mapping(address => bool) private _isEVM;

    function storeAccountConstructingCodeHash(address _address, bytes32 _hash) external {
        _codeHashes[_address] = _hash;
        _isConstructed[_address] = false;
    }

    function storeAccountConstructedCodeHash(address _address, bytes32 _hash) external {
        _codeHashes[_address] = _hash;
        _isConstructed[_address] = true;
    }

    function markAccountCodeHashAsConstructed(address _address) external {
        _isConstructed[_address] = true;
    }

    function getCodeHash(uint256 _input) external view returns (bytes32 codeHash) {
        return _codeHashes[address(uint160(_input))];
    }

    function getCodeSize(uint256 _input) external view returns (uint256 codeSize) {
        return _codeSizes[address(uint160(_input))];
    }

    function isAccountEVM(address _addr) external view returns (bool) {
        return _isEVM[_addr];
    }

    function storeCodeHash(address _address, bytes32 _hash) external {
        _codeHashes[_address] = _hash;
    }

    function storeCodeHashHistory(address _address, bytes32 _hash) external {
        _codeHashesHistory[_address] = _hash;
    }

    function storeCodeSize(address _address, uint256 _size) external {
        _codeSizes[_address] = _size;
    }

    function storeCodeSizeHistory(address _address, uint256 _size) external {
        _codeSizesHistory[_address] = _size;
    }

    function getCodeHash(address _address) external view returns (bytes32) {
        return _codeHashes[_address];
    }

    function getCodeHashHistory(address _address) external view returns (bytes32) {
        return _codeHashesHistory[_address];
    }

    function getCodeSize(address _address) external view returns (uint256) {
        return _codeSizes[_address];
    }

    function getCodeSizeHistory(address _address) external view returns (uint256) {
        return _codeSizesHistory[_address];
    }

    function getRawCodeHash(address _address) external view returns (bytes32) {
        return _codeHashes[_address];
    }

    // Mock functions for testing
    function setAccountEVM(address _addr, bool _isEVMAccount) external {
        _isEVM[_addr] = _isEVMAccount;
    }

    function isConstructed(address _addr) external view returns (bool) {
        return _isConstructed[_addr];
    }
} 