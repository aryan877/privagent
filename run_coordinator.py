#!/usr/bin/env python3
"""
Quick start script to run the Coordinator Agent
"""
import sys
import os

# Add agents directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agents'))

from agents.coordinator import coordinator

if __name__ == "__main__":
    print("=" * 60)
    print("PrivAgent Coordinator - Starting...")
    print("=" * 60)
    print(f"\nAgent Address: {coordinator.address}")
    print(f"Port: {os.getenv('AGENT_PORT_COORDINATOR', 8000)}")
    print("\nTo test via ASI:One:")
    print(f"1. Go to https://asi1.ai")
    print(f"2. Search for agent: {coordinator.address}")
    print(f"3. Send message: 'hello' or 'help'")
    print("\n" + "=" * 60)
    print("Press Ctrl+C to stop\n")

    coordinator.run()
