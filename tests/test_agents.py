"""
Basic tests for PrivAgent agents
Run with: uv run python tests/test_agents.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.privacy_agent import calculate_address_reuse_ratio, calculate_timing_variance
from agents.execution_agent import execution_agent
from agents.monitoring_agent import get_severity
from agents.coordinator import coordinator


def test_coordinator_initialization():
    """Test that coordinator agent initializes correctly"""
    assert coordinator.name == "PrivAgent_Coordinator"
    assert coordinator.address is not None
    print(f"✅ Coordinator initialized with address: {coordinator.address}")


def test_execution_agent_initialization():
    """Test that execution agent initializes correctly"""
    assert execution_agent.name == "PrivAgent_Execution"
    assert execution_agent.address is not None
    print(f"✅ Execution agent initialized with address: {execution_agent.address}")


def test_privacy_score_calculation():
    """Test privacy score helper functions"""
    # Test address reuse calculation
    mock_txs = [type('obj', (object,), {'signature': f'sig_{i}'})() for i in range(10)]
    reuse_ratio = calculate_address_reuse_ratio(mock_txs)
    assert 0 <= reuse_ratio <= 1
    print(f"✅ Address reuse ratio calculated: {reuse_ratio}")

    # Test timing variance with mock data
    mock_tx_times = [
        type('obj', (object,), {'block_time': 1000 + i*10})()
        for i in range(5)
    ]
    variance = calculate_timing_variance(mock_tx_times)
    assert variance >= 0
    print(f"✅ Timing variance calculated: {variance}")


def test_monitoring_severity_levels():
    """Test severity level calculation"""
    assert get_severity(90) == "LOW"
    assert get_severity(50) == "MEDIUM"
    assert get_severity(30) == "HIGH"
    print("✅ Severity levels working correctly")


def test_unique_agent_addresses():
    """Test that all agents have unique addresses"""
    from agents.privacy_agent import privacy_agent
    from agents.monitoring_agent import monitoring_agent

    addresses = {
        coordinator.address,
        privacy_agent.address,
        execution_agent.address,
        monitoring_agent.address
    }

    assert len(addresses) == 4, "All agents should have unique addresses"
    print(f"✅ All 4 agents have unique addresses")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Running PrivAgent Tests")
    print("="*60 + "\n")

    test_coordinator_initialization()
    test_execution_agent_initialization()
    test_privacy_score_calculation()
    test_monitoring_severity_levels()
    test_unique_agent_addresses()

    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60 + "\n")
