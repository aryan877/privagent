from __future__ import annotations

from typing import Dict, List, Optional

from uagents import Model


class PrivacyRequest(Model):
    action: str  # "compress", "report", "score"
    wallet_address: str
    amount: Optional[float] = None
    recipient: Optional[str] = None
    token_symbol: Optional[str] = None
    privacy_level: Optional[str] = None
    request_id: str
    # Authentication (optional for read-only operations like "report")
    wallet_signature: Optional[str] = None  # Base64 encoded signature
    signed_message: Optional[str] = None  # Message that was signed
    timestamp: Optional[int] = None  # Unix timestamp


class PrivacyResponse(Model):
    request_id: str
    success: bool
    result: Dict
    execution_time: Optional[float] = None
    method_used: Optional[str] = None


class TransferRequest(Model):
    from_wallet: str
    to_wallet: str
    amount: float
    token_mint: str
    use_compression: bool = False
    privacy_level: str = "standard"
    request_id: str
    # Authentication (required for transfers)
    wallet_signature: Optional[str] = None  # Base64 encoded signature
    signed_message: Optional[str] = None  # Message that was signed
    timestamp: Optional[int] = None  # Unix timestamp


class SwapRequest(Model):
    wallet: str
    input_token: str
    output_token: str
    amount: float
    slippage_bps: int = 50
    protect_mev: bool = True
    max_priority_fee: Optional[int] = None
    routing_preference: str = "best"
    request_id: str
    # Authentication (required for swaps)
    wallet_signature: Optional[str] = None  # Base64 encoded signature
    signed_message: Optional[str] = None  # Message that was signed
    timestamp: Optional[int] = None  # Unix timestamp


class ExecutionResponse(Model):
    request_id: str
    success: bool
    result: Dict
    execution_time: Optional[float] = None
    signature: Optional[str] = None
    explorer_url: Optional[str] = None
    mev_protected: bool = False


class MonitoringRequest(Model):
    action: str
    wallet_address: str
    threshold: Optional[int] = 70
    alert_types: Optional[List[str]] = None
    request_id: str


class MonitoringResponse(Model):
    request_id: str
    success: bool
    result: Dict


class PrivacyAlert(Model):
    alert_type: str
    wallet_address: str
    severity: str
    message: str
    data: Dict
    timestamp: str


# =============================================================================
# Zero-Knowledge Privacy Models
# =============================================================================

class ZKPrivacyRequest(Model):
    action: str  # "verify_snark", "generate_stealth", "homomorphic_analysis"
    wallet_address: str
    transaction_data: Optional[Dict] = None
    zk_proof: Optional[Dict] = None
    privacy_params: Optional[Dict] = None
    request_id: str


class ZKPrivacyResponse(Model):
    request_id: str
    success: bool
    zk_proof_valid: Optional[bool] = None
    stealth_addresses: Optional[List[str]] = None
    encrypted_metrics: Optional[Dict] = None
    privacy_score: Optional[float] = None
    verification_details: Dict = {}


# =============================================================================
# ML-Based MEV Detection Models
# =============================================================================

class MEVDetectionRequest(Model):
    wallet_address: str
    transaction_sequence: List[Dict] = []
    time_window_seconds: int = 60
    detection_models: List[str] = ["lstm", "gnn", "transformer", "isolation_forest"]
    real_time_analysis: bool = True
    request_id: str


class MEVDetectionResponse(Model):
    request_id: str
    success: bool
    mev_detected: bool
    mev_type: Optional[str] = None  # "sandwich", "frontrun", "backrun", "arbitrage"
    confidence: float = 0.0
    risk_score: float = 0.0
    temporal_analysis: Dict = {}
    graph_analysis: Dict = {}
    anomaly_score: float = 0.0
    recommendations: List[str] = []


class SandwichAttackData(Model):
    front_tx: Dict
    victim_tx: Dict
    back_tx: Dict
    profit_estimate: float
    confidence: float
    timestamp: str


# =============================================================================
# Advanced Privacy Analytics Models
# =============================================================================

class AdvancedPrivacyAnalysisRequest(Model):
    wallet_address: str
    analysis_depth: str = "comprehensive"  # "basic", "standard", "comprehensive"
    include_behavioral: bool = True
    include_cross_chain: bool = True
    include_ml_anomaly: bool = True
    historical_window_days: int = 30
    request_id: str


class AdvancedPrivacyAnalysisResponse(Model):
    request_id: str
    success: bool
    privacy_score: float = 0.0
    multi_dimensional_scores: Dict = {}
    behavioral_biometrics: Dict = {}
    cross_chain_analysis: Dict = {}
    anomaly_detection_results: Dict = {}
    privacy_recommendations: List[str] = []
    risk_factors: List[Dict] = []
    execution_time: Optional[float] = None
    error: Optional[str] = None


# =============================================================================
# Real-Time Monitoring Models
# =============================================================================

class RealTimeMonitoringRequest(Model):
    wallet_addresses: List[str]
    monitoring_types: List[str] = ["mev", "privacy", "anomaly", "cross_chain"]
    alert_threshold: float = 0.7
    continuous_learning: bool = True
    request_id: str


class RealTimeAlert(Model):
    alert_id: str
    alert_type: str
    severity: str  # "low", "medium", "high", "critical"
    wallet_address: str
    details: Dict
    confidence: float
    timestamp: str
    recommended_actions: List[str] = []
