#!/usr/bin/env python3
"""
Authentication tests for PrivAgent hackathon submission.

Tests wallet signature verification and security guarantees.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.auth import auth_manager, SignedRequest
from solders.keypair import Keypair
import time

print("🔐 Testing PrivAgent Authentication System")
print("=" * 60)

# Test 1: Wallet Signature Verification
print("\n[Test 1] Wallet Signature Verification")
print("-" * 60)

# Generate test wallet
test_wallet = Keypair()
wallet_address = str(test_wallet.pubkey())
print(f"Test wallet: {wallet_address[:16]}...")

# Sign a message
message = b"Transfer 100 USDC to recipient"
signature = test_wallet.sign_message(message)
sig_bytes = signature.__bytes__()
print(f"Message: {message.decode()}")
print(f"Signature: {sig_bytes[:16].hex()}...")

# Verify signature
is_valid = auth_manager.verify_wallet_signature(
    wallet_address,
    message,
    sig_bytes
)

if is_valid:
    print("✅ PASS: Wallet signature verified successfully!")
else:
    print("❌ FAIL: Wallet signature verification failed")
    exit(1)

# Test 2: Invalid signature should fail
print("\n[Test 2] Invalid Signature Detection")
print("-" * 60)

wrong_wallet = Keypair()
wrong_signature = wrong_wallet.sign_message(message)

is_invalid = auth_manager.verify_wallet_signature(
    wallet_address,  # Real wallet
    message,
    wrong_signature.__bytes__()  # Wrong signature
)

if not is_invalid:
    print("✅ PASS: Invalid signature correctly rejected!")
else:
    print("❌ FAIL: Invalid signature was accepted (security issue!)")
    exit(1)

# Test 3: Signed Request with Full Validation
print("\n[Test 3] Signed Request Validation")
print("-" * 60)

request_message = '{"action":"transfer","amount":100,"timestamp":' + str(int(time.time())) + '}'
request_sig = test_wallet.sign_message(request_message.encode())

signed_request = SignedRequest(
    wallet_address=wallet_address,
    message=request_message,
    signature=request_sig.__bytes__(),
    timestamp=int(time.time())
)

success, error_msg = auth_manager.verify_signed_request(signed_request)

if success:
    print(f"✅ PASS: Request verified: {error_msg}")
else:
    print(f"❌ FAIL: Request rejected: {error_msg}")
    exit(1)

# Test 4: Expired Request Detection
print("\n[Test 4] Expired Request Detection")
print("-" * 60)

old_timestamp = int(time.time()) - 400  # 400 seconds ago (> 5 min)
old_request = SignedRequest(
    wallet_address=wallet_address,
    message='{"action":"transfer","old":true}',
    signature=test_wallet.sign_message(b"old").__bytes__(),
    timestamp=old_timestamp
)

success, error_msg = auth_manager.verify_signed_request(old_request)

if not success and "expired" in error_msg.lower():
    print(f"✅ PASS: Expired request correctly rejected: {error_msg}")
else:
    print(f"❌ FAIL: Expired request was accepted (security issue!)")
    exit(1)

# Test 5: Replay Attack Prevention
print("\n[Test 5] Replay Attack Prevention")
print("-" * 60)

# First request
replay_message = '{"action":"transfer","amount":999}'
replay_sig = test_wallet.sign_message(replay_message.encode())

request1 = SignedRequest(
    wallet_address=wallet_address,
    message=replay_message,
    signature=replay_sig.__bytes__(),
    timestamp=int(time.time())
)

# Accept first request
success1, _ = auth_manager.verify_signed_request(request1)
print(f"First request: {'✅ Accepted' if success1 else '❌ Rejected'}")

# Try to replay same signature
request2 = SignedRequest(
    wallet_address=wallet_address,
    message=replay_message,
    signature=replay_sig.__bytes__(),  # Same signature!
    timestamp=int(time.time())
)

success2, error_msg2 = auth_manager.verify_signed_request(request2)

if not success2 and "replay" in error_msg2.lower():
    print(f"✅ PASS: Replay attack detected and blocked!")
else:
    print(f"❌ FAIL: Replay attack succeeded (security issue!)")
    exit(1)

# Summary
print("\n" + "=" * 60)
print("🎉 ALL TESTS PASSED!")
print("=" * 60)
print("\nSecurity guarantees verified:")
print("  ✅ Wallet ownership verification")
print("  ✅ Invalid signature detection")
print("  ✅ Timestamp validation")
print("  ✅ Replay attack prevention")
print("\nYour authentication system is ready for production! 🔒")
