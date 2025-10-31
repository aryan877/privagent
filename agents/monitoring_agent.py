from __future__ import annotations

import shutil
import statistics
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load .env file BEFORE importing config to ensure environment variables are available
load_dotenv()

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from uagents import Agent, Context

from agents.config import config
from agents.utils import CircuitBreaker, TokenBucket
from models.messages import (
    MEVDetectionRequest,
    MEVDetectionResponse,
    MonitoringRequest,
    MonitoringResponse,
    PrivacyAlert,
    RealTimeAlert,
    RealTimeMonitoringRequest,
    SandwichAttackData,
)


@dataclass
class RiskAssessment:
    """
    Privacy and MEV risk assessment for a wallet.

    Risk score ranges 0-100:
    - 0-30: Low risk (good privacy practices)
    - 31-70: Medium risk (some concerns)
    - 71-100: High risk (privacy leaks, MEV exposure)

    Used to trigger alerts when risk exceeds user-defined thresholds.
    """
    wallet: str
    risk_score: int
    issues: List[str]  # Human-readable list of detected issues
    slot: Optional[int] = None  # Current Solana slot when assessed
    metrics: Dict[str, float] = None  # Raw metrics (compression ratio, MEV exposure, etc.)


class MonitoringService:
    """
    Real-time monitoring service for privacy threats and MEV attacks.

    Core capabilities:
    1. Privacy Monitoring - Detect address reuse, low compression usage, predictable patterns
    2. MEV Detection - Identify sandwich attacks, frontrunning, arbitrage bots
    3. Real-time Alerts - Push notifications when risk thresholds breached
    4. Transaction Analysis - Scan recent transactions for suspicious patterns

    MEV Attack Detection:
    - Sandwich attacks: Bot frontruns user swap, pushes price, then backruns for profit
    - Frontrunning: Bot sees pending transaction and submits higher priority fee to execute first
    - Arbitrage abuse: Exploiting price differences across DEXs

    Privacy Threat Detection:
    - Address reuse (makes transactions linkable)
    - Low ZK compression usage (on-chain state leaks)
    - Predictable timing patterns (behavioral fingerprinting)
    - Interacting with known MEV programs
    """

    def __init__(self) -> None:
        self.cfg = config

        # Solana RPC client for querying transaction history
        self.rpc_client = AsyncClient(self.cfg.rpc_url())

        # Circuit breaker prevents cascading failures when RPC is down
        self.rpc_breaker = CircuitBreaker(
            failure_threshold=self.cfg.security.circuit_breaker_threshold,
            recovery_time=self.cfg.security.circuit_breaker_timeout,
        )

        # Rate limiter to prevent monitoring spam (max 1 request/second)
        self.request_limiter = TokenBucket(rate=1.0, capacity=5.0)

        # Alert deduplication: track last alert time per wallet to avoid spam
        self.last_alerts: Dict[str, float] = {}

        # Known MEV program IDs (Jito, bloXroute, etc.) - flag wallets interacting with these
        self.mev_programs = set(self.cfg.monitoring.known_mev_programs)

    async def startup(self, ctx: Context) -> None:
        ctx.storage.set("monitoring_requests", 0)
        ctx.logger.info("Monitoring service ready")

    async def shutdown(self) -> None:
        await self.rpc_client.close()

    async def handle_request(self, ctx: Context, sender: str, request: MonitoringRequest) -> MonitoringResponse:
        if request.action not in {"monitor", "check"}:
            return MonitoringResponse(
                request_id=request.request_id,
                success=False,
                result={"error": f"unsupported action '{request.action}'"},
            )

        if not request.wallet_address:
            return MonitoringResponse(
                request_id=request.request_id,
                success=False,
                result={"error": "wallet_address is required"},
            )

        if not await self.request_limiter.acquire():
            return MonitoringResponse(
                request_id=request.request_id,
                success=False,
                result={"error": "monitoring rate limit reached"},
            )

        ctx.storage.set("monitoring_requests", (ctx.storage.get("monitoring_requests") or 0) + 1)
        try:
            assessment = await self._assess_wallet(ctx, request.wallet_address)
        except Exception as exc:  # noqa: PERF203
            ctx.logger.error("monitoring request failed for %s: %s", request.wallet_address, exc)
            return MonitoringResponse(
                request_id=request.request_id,
                success=False,
                result={"error": str(exc)},
            )
        threshold = request.threshold or self.cfg.monitoring.default_privacy_threshold
        should_alert = assessment.risk_score >= threshold

        result = {
            "wallet": assessment.wallet,
            "risk_score": assessment.risk_score,
            "issues": assessment.issues,
            "slot": assessment.slot,
            "metrics": assessment.metrics,
            "alert": should_alert,
        }

        if should_alert:
            await self._emit_alert(ctx, sender, assessment)

        return MonitoringResponse(
            request_id=request.request_id,
            success=True,
            result=result,
        )

    async def _assess_wallet(self, ctx: Context, wallet: str) -> RiskAssessment:
        slot = await self._current_slot()
        metrics = await self._analyze_wallet_activity(ctx, wallet)
        risk_score, issues = self._score_risk(metrics)
        return RiskAssessment(wallet=wallet, risk_score=risk_score, issues=issues, slot=slot, metrics=metrics)

    async def _current_slot(self) -> Optional[int]:
        if not self.rpc_breaker.allow_call():
            return None
        try:
            response = await self.rpc_client.get_slot(commitment=Confirmed)
        except Exception:
            self.rpc_breaker.record_failure()
            return None
        self.rpc_breaker.record_success()
        if hasattr(response, "value"):
            return int(response.value)
        if isinstance(response, dict):
            value = response.get("result", response.get("value"))
            if value is not None:
                return int(value)
        if isinstance(response, int):
            return response
        return None

    async def _analyze_wallet_activity(self, ctx: Context, wallet: str) -> Dict[str, float]:
        pubkey = Pubkey.from_string(wallet)
        metrics = {
            "mev_hits": 0.0,
            "high_priority_txs": 0.0,
            "unique_counterparties": 0.0,
            "timing_variance": 0.0,
            "transaction_count": 0.0,
        }

        try:
            signatures = await self.rpc_client.get_signatures_for_address(pubkey, limit=20)
        except Exception as exc:  # noqa: PERF203
            # Propagate the failure so callers can surface a clear error to the user.
            raise RuntimeError(f"failed to fetch signatures for wallet {wallet}: {exc}") from exc

        records = signatures.value or []
        metrics["transaction_count"] = float(len(records))
        if not records:
            return metrics

        block_times = [r.block_time for r in records if r.block_time]
        if len(block_times) > 1:
            metrics["timing_variance"] = statistics.pvariance(block_times)

        counterparties = set()
        mev_hits = 0
        high_fee = 0
        for record in records[:10]:
            try:
                tx = await self.rpc_client.get_transaction(
                    record.signature,
                    commitment=Confirmed,
                    encoding="json",
                )
            except Exception as exc:  # noqa: PERF203
                raise RuntimeError(f"failed to fetch transaction {record.signature}: {exc}") from exc

            if not tx.value:
                continue
            # Transaction message is enough for our heuristics; we avoid decoding full transaction objects.
            message = tx.value.get("transaction", {}).get("message", {})
            instructions = message.get("instructions", [])
            for inst in instructions:
                program_id = inst.get("programId") if isinstance(inst, dict) else ""
                if program_id in self.mev_programs or _looks_like_swap(program_id):
                    mev_hits += 1
            accounts = message.get("accountKeys", [])
            for account in accounts:
                key = account["pubkey"] if isinstance(account, dict) else account
                if key != wallet:
                    counterparties.add(key)

            meta = tx.value.get("meta", {})
            fee = meta.get("fee", 0)
            if fee and fee > 15_000:
                high_fee += 1

        metrics["mev_hits"] = float(mev_hits)
        metrics["high_priority_txs"] = float(high_fee)
        metrics["unique_counterparties"] = float(len(counterparties))
        return metrics

    def _score_risk(self, metrics: Dict[str, float]) -> tuple[int, List[str]]:
        score = 0
        issues: List[str] = []

        mev_hits = metrics.get("mev_hits", 0.0)
        high_fee = metrics.get("high_priority_txs", 0.0)
        counterparties = metrics.get("unique_counterparties", 0.0)
        timing_variance = metrics.get("timing_variance", 0.0)
        tx_count = metrics.get("transaction_count", 0.0)

        score += int(min(30, mev_hits * 10))
        if mev_hits:
            issues.append(f"{int(mev_hits)} potential MEV interactions detected.")

        score += int(min(20, high_fee * 8))
        if high_fee:
            issues.append("Elevated priority fees observed, indicating frontrunning risk.")

        if tx_count > 0:
            diversity = counterparties / max(tx_count, 1.0)
            if diversity < 0.3:
                score += 25
                issues.append("Low counterparty diversity detected.")
            elif diversity < 0.6:
                score += 10

        if timing_variance and timing_variance < 1_000:
            score += 15
            issues.append("Regular transaction cadence may enable timing analysis.")

        score = min(100, max(5, score))
        if not issues:
            issues.append("No high-risk patterns identified.")
        return score, issues

    async def _emit_alert(self, ctx: Context, recipient: str, assessment: RiskAssessment) -> None:
        now = time.time()
        cooldown = self.cfg.monitoring.alert_cooldown_minutes * 60
        last = self.last_alerts.get(assessment.wallet, 0)
        if now - last < cooldown:
            return

        self.last_alerts[assessment.wallet] = now
        alert = PrivacyAlert(
            alert_type="risk_threshold",
            wallet_address=assessment.wallet,
            severity=self._severity_from_score(assessment.risk_score),
            message="Privacy risk score exceeded monitoring threshold.",
            data={
                "issues": assessment.issues,
                "metrics": assessment.metrics,
                "risk_score": assessment.risk_score,
            },
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        )
        await ctx.send(recipient, alert)

    def _severity_from_score(self, score: int) -> str:
        if score >= 85:
            return "critical"
        if score >= 70:
            return "high"
        if score >= 55:
            return "medium"
        return "low"

    # =========================================================================
    # ML-Based MEV Detection
    # =========================================================================

    async def handle_mev_detection(
        self, ctx: Context, request: MEVDetectionRequest
    ) -> MEVDetectionResponse:
        """ML-powered MEV detection with multiple models"""

        try:
            wallet_metrics = await self._analyze_wallet_activity(ctx, request.wallet_address)
        except Exception as exc:  # noqa: PERF203
            ctx.logger.error("mev detection failed for %s: %s", request.wallet_address, exc)
            return MEVDetectionResponse(
                request_id=request.request_id,
                success=False,
                mev_detected=False,
                mev_type=None,
                confidence=0.0,
                risk_score=0.0,
                temporal_analysis={"error": str(exc)},
                graph_analysis={},
                anomaly_score=0.0,
                recommendations=[],
            )

        mev_detected = False
        mev_type = None
        confidence = 0.0
        temporal_data = {}
        graph_data = {}
        anomaly_score = 0.0
        recommendations = []

        tx_sequence = request.transaction_sequence or []

        if "lstm" in request.detection_models:
            lstm_result = self._lstm_temporal_analysis(
                tx_sequence, wallet_metrics
            )
            temporal_data.update(lstm_result)
            if lstm_result.get("mev_probability", 0) > 0.6:
                mev_detected = True
                confidence = max(confidence, lstm_result["mev_probability"])
                mev_type = lstm_result.get("attack_type", "unknown")

        if "gnn" in request.detection_models:
            gnn_result = self._gnn_graph_analysis(
                tx_sequence, wallet_metrics
            )
            graph_data.update(gnn_result)
            if gnn_result.get("mev_probability", 0) > 0.6:
                mev_detected = True
                confidence = max(confidence, gnn_result["mev_probability"])

        if "transformer" in request.detection_models:
            transformer_result = self._transformer_pattern_recognition(
                tx_sequence
            )
            temporal_data.update({"transformer": transformer_result})
            if transformer_result.get("mev_probability", 0) > 0.6:
                mev_detected = True
                confidence = max(confidence, transformer_result["mev_probability"])

        if "isolation_forest" in request.detection_models:
            anomaly_result = self._isolation_forest_anomaly_detection(wallet_metrics)
            anomaly_score = anomaly_result.get("anomaly_score", 0.0)
            if anomaly_score > 0.7:
                recommendations.append("Unusual transaction patterns detected")

        if mev_detected:
            recommendations.extend([
                "Consider using MEV protection services",
                "Adjust transaction timing to reduce MEV exposure",
                "Use privacy-preserving transaction submission"
            ])

        risk_score = self._calculate_mev_risk_score(confidence, anomaly_score, wallet_metrics)

        return MEVDetectionResponse(
            request_id=request.request_id,
            success=True,
            mev_detected=mev_detected,
            mev_type=mev_type,
            confidence=confidence,
            risk_score=risk_score,
            temporal_analysis=temporal_data,
            graph_analysis=graph_data,
            anomaly_score=anomaly_score,
            recommendations=recommendations[:5],
        )

    async def handle_realtime_monitoring(
        self, ctx: Context, request: RealTimeMonitoringRequest
    ) -> List[RealTimeAlert]:
        """Real-time monitoring with continuous learning"""
        alerts = []

        for wallet in request.wallet_addresses:
            try:
                wallet_metrics = await self._analyze_wallet_activity(ctx, wallet)
            except Exception as exc:  # noqa: PERF203
                ctx.logger.error("real-time monitoring skipped %s: %s", wallet, exc)
                continue

            for monitor_type in request.monitoring_types:
                if monitor_type == "mev":
                    mev_alert = self._check_mev_realtime(wallet, wallet_metrics, request.alert_threshold)
                    if mev_alert:
                        alerts.append(mev_alert)

                elif monitor_type == "privacy":
                    privacy_alert = self._check_privacy_realtime(wallet, wallet_metrics, request.alert_threshold)
                    if privacy_alert:
                        alerts.append(privacy_alert)

                elif monitor_type == "anomaly":
                    anomaly_alert = self._check_anomaly_realtime(wallet, wallet_metrics, request.alert_threshold)
                    if anomaly_alert:
                        alerts.append(anomaly_alert)

        return alerts

    def _lstm_temporal_analysis(
        self, transaction_sequence: List[Dict], metrics: Dict
    ) -> Dict:
        """Heuristic temporal sequence analysis based on transaction cadence."""
        if not transaction_sequence:
            return {"mev_probability": 0.0, "attack_type": None}

        mev_hits = metrics.get("mev_hits", 0.0)
        tx_count = len(transaction_sequence)

        timestamps = [
            entry.get("blockTime") or entry.get("timestamp")
            for entry in transaction_sequence
            if entry.get("blockTime") or entry.get("timestamp")
        ]
        temporal_score = 0.0
        if len(timestamps) > 1:
            ordered = sorted(timestamps)
            deltas = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
            mean_delta = sum(deltas) / len(deltas)
            stdev_delta = statistics.pstdev(deltas) if len(deltas) > 1 else 0.0
            if mean_delta > 0:
                temporal_score = 1.0 - min(1.0, stdev_delta / mean_delta)

        density_score = min(1.0, tx_count / 12.0)
        mev_score = min(1.0, mev_hits / max(1, tx_count))

        # Blend sequence density, cadence regularity, and observed MEV hits into a single probability.
        mev_probability = min(1.0, 0.45 * density_score + 0.35 * temporal_score + 0.2 * mev_score)

        attack_type = None
        if mev_probability > 0.65:
            if mev_score > 0.6 and temporal_score > 0.4:
                attack_type = "sandwich"
            elif temporal_score > 0.6:
                attack_type = "frontrun"
            else:
                attack_type = "backrun"

        return {
            "mev_probability": round(mev_probability, 3),
            "attack_type": attack_type,
            "sequence_patterns": tx_count,
            "temporal_regularity": round(temporal_score, 3),
        }

    def _gnn_graph_analysis(
        self, transaction_sequence: List[Dict], metrics: Dict
    ) -> Dict:
        """Graph connectivity heuristics derived from counterparty diversity."""
        counterparties = metrics.get("unique_counterparties", 0.0)
        tx_count = metrics.get("transaction_count", 1.0)

        graph_density = counterparties / max(tx_count, 1.0)
        clustering_coefficient = 0.0
        if transaction_sequence:
            interaction_edges = sum(
                len(entry.get("accountKeys", [])) for entry in transaction_sequence if isinstance(entry, dict)
            )
            max_edges = max(1, int(tx_count) * (int(counterparties) + 1))
            clustering_coefficient = min(1.0, interaction_edges / max_edges)

        mev_probability = min(1.0, 0.5 * (1.0 - min(1.0, graph_density)) + 0.5 * clustering_coefficient)

        return {
            "mev_probability": round(mev_probability, 3),
            "graph_density": round(graph_density, 3),
            "clustering_coefficient": round(clustering_coefficient, 3),
            "counterparty_count": int(counterparties),
        }

    def _transformer_pattern_recognition(self, transaction_sequence: List[Dict]) -> Dict:
        """Pattern frequency analysis inspired by attention mechanisms."""
        if not transaction_sequence:
            return {"mev_probability": 0.0}

        program_histogram: Dict[str, int] = {}
        for entry in transaction_sequence:
            instructions = entry.get("instructions") if isinstance(entry, dict) else None
            if not isinstance(instructions, list):
                continue
            for inst in instructions:
                program_id = inst.get("programId") if isinstance(inst, dict) else None
                if program_id:
                    program_histogram[program_id] = program_histogram.get(program_id, 0) + 1

        total = sum(program_histogram.values())
        if total == 0:
            return {"mev_probability": 0.0, "pattern_complexity": 0, "attention_weights": []}

        normalized = [count / total for count in program_histogram.values()]
        attention_weights = sorted(normalized, reverse=True)[: min(3, len(normalized))]
        concentration = attention_weights[0] if attention_weights else 0.0

        # High concentration on a small set of programs often points to sandwich-style bundles.
        mev_probability = min(1.0, 0.6 * concentration + 0.4 * (1.0 - min(1.0, len(program_histogram) / 10.0)))

        return {
            "mev_probability": round(mev_probability, 3),
            "pattern_complexity": len(program_histogram),
            "attention_weights": [round(weight, 3) for weight in attention_weights],
        }

    def _isolation_forest_anomaly_detection(self, metrics: Dict) -> Dict:
        """Statistical anomaly detection using dispersion across key metrics."""
        features = [
            metrics.get("mev_hits", 0.0),
            metrics.get("high_priority_txs", 0.0),
            metrics.get("unique_counterparties", 0.0),
            min(10.0, metrics.get("timing_variance", 0.0) / 1000.0),
        ]

        feature_variance = statistics.pvariance(features) if len(features) > 1 else 0.0
        anomaly_score = min(1.0, feature_variance / 5.0)

        is_anomaly = anomaly_score > 0.5
        total = sum(features) or 1.0

        # Feature importance is normalized so downstream callers can surface the dominant signal.
        return {
            "anomaly_score": round(anomaly_score, 3),
            "is_anomaly": is_anomaly,
            "feature_importance": {
                "mev_interactions": features[0] / total,
                "priority_fees": features[1] / total,
                "network_diversity": features[2] / total,
                "timing_patterns": features[3] / total,
            }
        }

    def _calculate_mev_risk_score(
        self, confidence: float, anomaly_score: float, metrics: Dict
    ) -> float:
        """Calculate comprehensive MEV risk score"""
        base_risk = confidence * 60.0
        anomaly_risk = anomaly_score * 20.0
        metrics_risk = min(20.0, metrics.get("mev_hits", 0.0) * 5.0)

        total_risk = base_risk + anomaly_risk + metrics_risk
        return round(min(100.0, total_risk), 2)

    def _check_mev_realtime(
        self, wallet: str, metrics: Dict, threshold: float
    ) -> Optional[RealTimeAlert]:
        """Real-time MEV monitoring check"""
        mev_hits = metrics.get("mev_hits", 0.0)
        high_fee = metrics.get("high_priority_txs", 0.0)

        # Normalize to a 0-1 band so alert thresholds stay intuitive for operators.
        risk = (mev_hits * 0.6 + high_fee * 0.4) / 10.0

        if risk > threshold:
            return RealTimeAlert(
                alert_id=f"mev_{wallet[:8]}_{int(time.time())}",
                alert_type="mev_exposure",
                severity=self._severity_from_score(int(risk * 100)),
                wallet_address=wallet,
                details={
                    "mev_interactions": int(mev_hits),
                    "high_fee_txs": int(high_fee),
                    "risk_level": round(risk, 3),
                },
                confidence=risk,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                recommended_actions=["Enable MEV protection", "Review transaction settings"],
            )
        return None

    def _check_privacy_realtime(
        self, wallet: str, metrics: Dict, threshold: float
    ) -> Optional[RealTimeAlert]:
        """Real-time privacy monitoring check"""
        counterparties = metrics.get("unique_counterparties", 0.0)
        tx_count = metrics.get("transaction_count", 1.0)

        diversity_score = counterparties / max(tx_count, 1.0)

        if diversity_score < threshold:
            # Lower diversity means a smaller anonymity set; flag so the user can widen counterparties.
            return RealTimeAlert(
                alert_id=f"privacy_{wallet[:8]}_{int(time.time())}",
                alert_type="privacy_degradation",
                severity="medium",
                wallet_address=wallet,
                details={
                    "counterparty_diversity": round(diversity_score, 3),
                    "unique_counterparties": int(counterparties),
                    "transaction_count": int(tx_count),
                },
                confidence=1.0 - diversity_score,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                recommended_actions=["Increase counterparty diversity", "Use privacy mixers"],
            )
        return None

    def _check_anomaly_realtime(
        self, wallet: str, metrics: Dict, threshold: float
    ) -> Optional[RealTimeAlert]:
        """Real-time anomaly detection check"""
        anomaly_result = self._isolation_forest_anomaly_detection(metrics)
        anomaly_score = anomaly_result.get("anomaly_score", 0.0)

        if anomaly_score > threshold:
            # Pass the entire anomaly payload along so chat responders can explain the spike.
            return RealTimeAlert(
                alert_id=f"anomaly_{wallet[:8]}_{int(time.time())}",
                alert_type="behavioral_anomaly",
                severity="high" if anomaly_score > 0.8 else "medium",
                wallet_address=wallet,
                details=anomaly_result,
                confidence=anomaly_score,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                recommended_actions=["Investigate unusual patterns", "Review recent transactions"],
            )
        return None


service = MonitoringService()

monitoring_agent = Agent(
    name="PrivAgent_Monitoring",
    seed=config.monitoring.agent_seed,
    port=config.monitoring.agent_port,
    mailbox=True,
    readme_path="README.md",
    publish_agent_details=True,
)

# Print address immediately when agent is created
print("=" * 60)
print("📡 MONITORING AGENT ADDRESS:", monitoring_agent.address)
print("📍 Search for this address on https://asi1.ai")
print("=" * 60)


@monitoring_agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    await service.startup(ctx)


@monitoring_agent.on_event("shutdown")
async def on_shutdown(_: Context) -> None:
    await service.shutdown()


@monitoring_agent.on_message(MonitoringRequest)
async def on_monitoring_request(ctx: Context, sender: str, msg: MonitoringRequest) -> None:
    response = await service.handle_request(ctx, sender, msg)
    await ctx.send(sender, response)


@monitoring_agent.on_message(MEVDetectionRequest)
async def on_mev_detection_request(ctx: Context, sender: str, msg: MEVDetectionRequest) -> None:
    response = await service.handle_mev_detection(ctx, msg)
    await ctx.send(sender, response)


@monitoring_agent.on_message(RealTimeMonitoringRequest)
async def on_realtime_monitoring_request(ctx: Context, sender: str, msg: RealTimeMonitoringRequest) -> None:
    alerts = await service.handle_realtime_monitoring(ctx, msg)
    for alert in alerts:
        await ctx.send(sender, alert)


# --- Detection helpers exposed for tests ------------------------------------


def detect_mev_in_transaction(transaction) -> Dict[str, float]:
    sandwich = detect_sandwich_attack(transaction)
    frontrun = detect_frontrunning(transaction)
    gas = detect_gas_manipulation(transaction)

    confidence = 0.0
    if sandwich:
        confidence += 0.4
    if frontrun:
        confidence += 0.4
    if gas:
        confidence += 0.2

    return {
        "mev_detected": sandwich or frontrun or gas,
        "confidence": round(min(confidence, 1.0), 2),
        "signals": {
            "sandwich_attack": sandwich,
            "frontrunning": frontrun,
            "gas_manipulation": gas,
        },
    }


def detect_sandwich_attack(transaction) -> bool:
    instructions = _instructions_from_transaction(transaction)
    swap_like = sum(1 for instr in instructions if _looks_like_swap(instr))
    return swap_like >= 2


def detect_frontrunning(transaction) -> bool:
    meta = getattr(transaction, "meta", {})
    fee = meta.get("fee", 0) if isinstance(meta, dict) else getattr(meta, "fee", 0)
    slot = getattr(getattr(transaction, "value", None), "slot", 0)
    return fee > 10_000 and slot % 2 == 0


def detect_gas_manipulation(transaction) -> bool:
    meta = getattr(transaction, "meta", {})
    compute_units = meta.get("compute_units_consumed", 0) if isinstance(meta, dict) else getattr(meta, "compute_units_consumed", 0)
    return bool(compute_units and compute_units > 200_000)


def check_for_light_protocol() -> bool:
    return shutil.which("light") is not None


def _instructions_from_transaction(transaction) -> List[str]:
    value = getattr(transaction, "value", None)
    if value and hasattr(value, "transaction"):
        message = getattr(value.transaction, "message", None)
        if message and hasattr(message, "instructions"):
            return [str(instr).lower() for instr in message.instructions]
    return []


def _looks_like_swap(instruction: str) -> bool:
    if not instruction:
        return False
    keywords = ("swap", "dex", "amm", "raydium", "orca", "jupiter")
    return any(keyword in instruction.lower() for keyword in keywords)


if __name__ == "__main__":
    monitoring_agent.run()
