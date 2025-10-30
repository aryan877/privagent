"""
Authentication Module for PrivAgent - Two-Layer Security System

PROBLEM:
Without auth, anyone who discovers your agent address on ASI:One can:
- Transfer funds from ANY wallet
- Execute swaps using YOUR private key
- Drain your wallet

SOLUTION:
Layer 1: Agent-to-agent message verification (uAgents Identity)
Layer 2: Wallet ownership proof (Solana signature verification)

This ensures:
- Only verified agents can send requests
- Users can only control wallets they OWN
- Transactions require cryptographic proof from wallet's private key
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

# NaCl provides Ed25519 signatures (same as Solana uses)
import nacl.signing
# Solders provides Solana keypair/pubkey handling
from solders.pubkey import Pubkey
# uAgents Identity for inter-agent message verification
from uagents.crypto import Identity


@dataclass
class WalletAuthChallenge:
    """
    Challenge-response pattern for proving wallet ownership.

    How it works:
    1. User: "Transfer 100 USDC from wallet X"
    2. Agent generates challenge: random nonce + timestamp
    3. User signs challenge with wallet X's private key in their browser
    4. Agent verifies signature matches wallet X's public key
    5. If valid: execute. If not: reject.

    This prevents anyone from controlling wallets they don't own.
    """
    wallet_address: str  # Base58 Solana address (e.g., "Gx7UJ7...")
    challenge: str       # Random SHA256 hash used once
    timestamp: int       # Unix timestamp when challenge was created
    expires_in: int = 300  # Challenge valid for 5 minutes


@dataclass
class SignedRequest:
    """
    A request that's been cryptographically signed by user's wallet.

    Frontend example (JavaScript with Phantom wallet):
        const message = JSON.stringify({
            action: "transfer",
            wallet: userWalletAddress,
            amount: 100,
            timestamp: Math.floor(Date.now() / 1000)
        });
        const sig = await window.solana.signMessage(message, "utf8");

    Backend verifies the signature matches the wallet's public key.
    """
    wallet_address: str  # Wallet that signed this request
    message: str         # Operation details (JSON string)
    signature: bytes     # Ed25519 signature from wallet's private key
    timestamp: int       # When request was signed (prevents replay attacks)


class AuthenticationManager:
    """
    Manages cryptographic authentication for agent operations.

    Features:
    - Challenge generation for wallet verification
    - Ed25519 signature verification (Solana-compatible)
    - Timestamp validation (5 minute window)
    - Replay attack prevention (signature caching)

    Usage:
        auth_manager = AuthenticationManager()

        # Verify a signed request
        success, error = auth_manager.verify_signed_request(request)
        if not success:
            return f"❌ Auth failed: {error}"
    """

    def __init__(self, challenge_ttl: int = 300):
        """
        Initialize authentication manager.

        Args:
            challenge_ttl: How long challenges are valid (seconds).
                          Default 5 min - balance between security and UX.
        """
        self.challenge_ttl = challenge_ttl

        # Track active challenges per wallet
        # wallet_address -> WalletAuthChallenge
        self._active_challenges: dict[str, WalletAuthChallenge] = {}

        # Track used signatures to prevent replay attacks
        # If attacker intercepts a signed request, they can't reuse it
        self._used_signatures: set[str] = set()

    def generate_challenge(self, wallet_address: str) -> WalletAuthChallenge:
        """
        Generate a unique cryptographic challenge for wallet ownership proof.

        The challenge is a SHA256 hash of:
        - Wallet address
        - Current timestamp (seconds)
        - Nanosecond precision timestamp (ensures uniqueness)

        Args:
            wallet_address: Base58 Solana public key

        Returns:
            WalletAuthChallenge containing nonce and expiration
        """
        timestamp = int(time.time())

        # Create unique nonce by hashing wallet + timestamps
        nonce = hashlib.sha256(
            f"{wallet_address}:{timestamp}:{time.time_ns()}".encode()
        ).hexdigest()

        challenge = WalletAuthChallenge(
            wallet_address=wallet_address,
            challenge=nonce,
            timestamp=timestamp,
            expires_in=self.challenge_ttl
        )

        # Store for later verification
        self._active_challenges[wallet_address] = challenge
        return challenge

    def verify_wallet_signature(
        self,
        wallet_address: str,
        message: bytes,
        signature: bytes
    ) -> bool:
        """
        Verify that a signature was created by the wallet's private key.

        Uses Ed25519 elliptic curve cryptography (same as Solana):
        - Private key signs message → signature
        - Public key verifies signature matches message
        - If signature is valid, proves ownership of private key

        This is the CORE security mechanism that prevents unauthorized access.

        Args:
            wallet_address: Base58 Solana public key (e.g., "Gx7UJ...")
            message: The exact bytes that were signed
            signature: Ed25519 signature bytes (64 bytes)

        Returns:
            True if signature is valid for this wallet, False otherwise

        Example:
            # User signs in browser with Phantom
            sig = await window.solana.signMessage(message)

            # Backend verifies
            if verify_wallet_signature(userWallet, message, sig):
                # User owns this wallet ✅
                execute_transaction()
            else:
                # Reject - user doesn't own wallet ❌
                return "Unauthorized"
        """
        try:
            # Convert base58 string to Solana public key object
            pubkey = Pubkey.from_string(wallet_address)

            # Create NaCl verifier from public key bytes
            # NaCl is the crypto library Solana uses for Ed25519
            verify_key = nacl.signing.VerifyKey(pubkey.__bytes__())

            # Verify signature matches message
            # Raises exception if signature is invalid
            verify_key.verify(message, signature)

            return True

        except Exception:
            # Verification failed - could be:
            # - Invalid signature (tampered or wrong wallet)
            # - Malformed wallet address
            # - Wrong message (signed different content)
            return False

    def verify_signed_request(self, request: SignedRequest) -> tuple[bool, str]:
        """
        Comprehensive verification of a signed request with security checks.

        Validates:
        1. ✅ Signature is valid for the wallet (crypto verification)
        2. ✅ Request is fresh (timestamp within 5 min window)
        3. ✅ Signature hasn't been used before (replay protection)

        Args:
            request: SignedRequest with wallet_address, message, signature, timestamp

        Returns:
            (success: bool, error_message: str)
            - (True, "Request verified") if all checks pass
            - (False, "reason...") if any check fails

        Security Properties:
        - Prevents wallet theft (signature verification)
        - Prevents replay attacks (signature caching)
        - Prevents stale requests (timestamp validation)
        """
        current_time = int(time.time())
        age = current_time - request.timestamp

        # Check 1: Timestamp freshness
        # Reject requests older than challenge_ttl (default 5 min)
        if age > self.challenge_ttl:
            return False, f"Request expired ({age}s old, max {self.challenge_ttl}s)"

        # Allow 1 min clock skew for timestamp in future
        # (client/server clocks might not be perfectly synced)
        if age < -60:
            return False, "Request timestamp is in the future"

        # Check 2: Replay attack prevention
        # Hash the signature to create a unique ID
        sig_hash = hashlib.sha256(request.signature).hexdigest()

        if sig_hash in self._used_signatures:
            # Attacker intercepted a valid signed request and is trying to reuse it
            return False, "Signature already used (replay attack detected)"

        # Check 3: Cryptographic signature verification
        # This is where we verify the user actually owns the wallet
        message_bytes = request.message.encode('utf-8')

        if not self.verify_wallet_signature(
            request.wallet_address,
            message_bytes,
            request.signature
        ):
            return False, "Invalid signature for wallet"

        # All checks passed! ✅
        # Mark signature as used to prevent replay
        self._used_signatures.add(sig_hash)

        # Garbage collection: keep signature cache under 1000 entries
        # In production, use Redis or DB with TTL
        if len(self._used_signatures) > 1000:
            self._used_signatures.clear()

        return True, "Request verified"

    def verify_agent_message(
        self,
        sender_address: str,
        digest: bytes,
        signature: str
    ) -> bool:
        """
        Verify inter-agent message using uAgents Identity verification.

        This is Layer 1 security - ensures messages between agents are authentic.
        Uses uAgents' built-in cryptographic verification.

        Each agent has a private key that signs messages.
        Recipients verify using the sender's public key (address).

        Args:
            sender_address: uAgent address that sent the message
            digest: SHA-256 hash of the message
            signature: Cryptographic signature from sending agent

        Returns:
            True if message is authentic, False if tampered/forged

        Example:
            # Privacy agent sends to execution agent
            digest = hashlib.sha256(message.encode()).digest()
            signature = privacy_agent.sign_digest(digest)

            # Execution agent verifies
            if verify_agent_message(privacy_addr, digest, signature):
                # Message is authentic ✅
                process_request()
        """
        try:
            # Use uAgents built-in verification
            # This cryptographically proves the message came from sender_address
            return Identity.verify_digest(sender_address, digest, signature)
        except Exception:
            # Verification failed - message was tampered or forged
            return False


# Global singleton instance for easy import across modules
# Usage: from agents.auth import auth_manager
auth_manager = AuthenticationManager()


def create_message_digest(message: str) -> bytes:
    """
    Create SHA-256 hash of a message for cryptographic signing.

    SHA-256 is a one-way hash function:
    - Same message always produces same hash
    - Cannot reverse hash back to original message
    - Even tiny change in message produces completely different hash

    Used for:
    - Agent-to-agent message verification
    - Creating unique signature identifiers

    Args:
        message: Text message to hash

    Returns:
        32-byte SHA-256 digest

    Example:
        digest = create_message_digest("transfer 100 USDC")
        signature = agent.sign_digest(digest)
    """
    hasher = hashlib.sha256()
    hasher.update(message.encode('utf-8'))
    return hasher.digest()


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

# Example 1: Verify wallet signature
# ------------------------------------
# from agents.auth import auth_manager
# from solders.keypair import Keypair
#
# keypair = Keypair()  # User's wallet
# message = b"Transfer 100 USDC"
# signature = keypair.sign_message(message)
#
# if auth_manager.verify_wallet_signature(str(keypair.pubkey()), message, signature.__bytes__()):
#     print("✅ User owns this wallet")
#     execute_transfer()
# else:
#     print("❌ Invalid signature - reject")


# Example 2: Verify signed request with all security checks
# ----------------------------------------------------------
# from agents.auth import auth_manager, SignedRequest
# import time
#
# request = SignedRequest(
#     wallet_address="Gx7UJ7XNBFxRDehVQhZtKRhYHA1J1pkmvxAMUeF4CX",
#     message='{"action":"transfer","amount":100}',
#     signature=sig_bytes,
#     timestamp=int(time.time())
# )
#
# success, error = auth_manager.verify_signed_request(request)
# if success:
#     print("✅ Request verified")
#     process_transfer()
# else:
#     print(f"❌ Auth failed: {error}")


# Example 3: Agent-to-agent message verification
# -----------------------------------------------
# from agents.auth import create_message_digest, auth_manager
#
# # Sending agent
# message = "compress 1000 USDC"
# digest = create_message_digest(message)
# signature = sender_agent.sign_digest(digest)
#
# # Receiving agent
# if auth_manager.verify_agent_message(sender_address, digest, signature):
#     print("✅ Message is authentic")
#     process_compression()
# else:
#     print("❌ Message was tampered - reject")
