"""
Shared Message Models for PrivAgent Communication
All inter-agent messages use these models for consistency
"""
from uagents import Model
from typing import Optional, Dict, List


# Privacy Agent Messages
class PrivacyRequest(Model):
    """Request for privacy operations"""
    action: str  # "compress", "report", "score"
    wallet_address: str
    amount: Optional[float] = None
    recipient: Optional[str] = None
    request_id: str


class PrivacyResponse(Model):
    """Response from privacy operations"""
    request_id: str
    success: bool
    result: dict


# Execution Agent Messages
class ExecutionRequest(Model):
    """Request for execution operations"""
    action: str  # "transfer", "swap", "compress_transfer"
    from_wallet: str
    to_wallet: Optional[str] = None
    amount: float
    token_mint: str
    request_id: str
    # Swap specific
    input_token: Optional[str] = None
    output_token: Optional[str] = None
    slippage_bps: Optional[int] = 300
    # Privacy options
    privacy_level: Optional[str] = "standard"  # "standard", "max"


class ExecutionResponse(Model):
    """Response from execution operations"""
    request_id: str
    success: bool
    result: dict
    # Include transaction details
    signature: Optional[str] = None
    explorer_url: Optional[str] = None


# Monitoring Agent Messages
class MonitoringRequest(Model):
    """Request for monitoring operations"""
    action: str  # "monitor", "check", "alert"
    wallet_address: str
    threshold: Optional[int] = 70
    alert_types: Optional[List[str]] = None  # ["score", "pattern", "timing"]
    request_id: str


class MonitoringResponse(Model):
    """Response from monitoring operations"""
    request_id: str
    success: bool
    result: dict


# Alert Messages (sent from Monitoring to Coordinator/Privacy)
class PrivacyAlert(Model):
    """Privacy alert sent by monitoring agent"""
    alert_type: str  # "score_drop", "pattern_detected", "timing_correlation"
    wallet_address: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    data: dict
    timestamp: str