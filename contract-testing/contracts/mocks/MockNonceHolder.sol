// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {INonceHolder} from "../interfaces/INonceHolder.sol";

contract MockNonceHolder is INonceHolder {
    mapping(address => uint256) private _minNonces;
    mapping(address => mapping(uint256 => bool)) private _usedNonces;
    mapping(address => mapping(uint256 => uint256)) private _valuesUnderNonce;

    function getMinNonce(address _address) external view returns (uint256) {
        return _minNonces[_address];
    }

    function getRawNonce(address _address) external view returns (uint256) {
        return _minNonces[_address];
    }

    function increaseMinNonce(uint256 _value) external returns (uint256) {
        _minNonces[msg.sender] += _value;
        return _minNonces[msg.sender];
    }

    function setValue(uint256 _key, uint256 _value) external {
        _minNonces[msg.sender] = _value;
    }

    function getValue(uint256 _key) external view returns (uint256) {
        return _minNonces[msg.sender];
    }

    function getValue(uint256 _key, uint256 _index) external view returns (uint256) {
        return _minNonces[msg.sender];
    }

    function getValue(uint256 _key, uint256 _index, bool _isSystem) external view returns (uint256) {
        return _minNonces[msg.sender];
    }

    function getValue(uint256 _key, bool _isSystem) external view returns (uint256) {
        return _minNonces[msg.sender];
    }

    function setValueUnderNonce(uint256 _key, uint256 _value) external {
        _valuesUnderNonce[msg.sender][_key] = _value;
    }

    function getValueUnderNonce(uint256 _key) external view returns (uint256) {
        return _valuesUnderNonce[msg.sender][_key];
    }

    function incrementMinNonceIfEquals(uint256 _expectedNonce) external {
        if (_minNonces[msg.sender] == _expectedNonce) {
            _minNonces[msg.sender]++;
        }
    }

    function validateNonceUsage(address _address, uint256 _key, bool _shouldBeUsed) external view {
        require(_usedNonces[_address][_key] == _shouldBeUsed, "Invalid nonce usage");
    }

    function appendRawNonce(address _address, uint256 _key) external {
        _usedNonces[_address][_key] = true;
    }

    function incrementDeploymentNonce(address _address) external returns (uint256) {
        _minNonces[_address]++;
        return _minNonces[_address];
    }

    function getDeploymentNonce(address _address) external view returns (uint256) {
        return _minNonces[_address];
    }

    // Mock functions for testing
    function setMinNonce(address _address, uint256 _nonce) external {
        _minNonces[_address] = _nonce;
    }

    function isNonceUsed(address _address, uint256 _nonce) external view returns (bool) {
        return _usedNonces[_address][_nonce];
    }
} 