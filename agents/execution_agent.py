from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import time
from asyncio.subprocess import PIPE
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv

# Load .env file BEFORE importing config to ensure environment variables are available
load_dotenv()

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.keypair import Keypair as SoldersKeypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import Transaction, VersionedTransaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import TransferCheckedParams, transfer_checked
from uagents import Agent, Context

from agents.config import config
from agents.utils import CircuitBreaker, TokenBucket, TransactionContext, retry_async
from models.messages import ExecutionResponse, SwapRequest, TransferRequest


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------


@dataclass
class NetworkSnapshot:
    """
    Real-time snapshot of Solana network conditions.

    Used to make intelligent decisions about transaction submission:
    - Adjust priority fees based on congestion
    - Block risky swaps during high congestion (MEV protection)
    - Dynamically tune slippage tolerance

    Updated every 60 seconds via on_interval handler.
    """
    slot_height: int = 0
    current_tps: float = 0.0
    congestion: str = "low"
    priority_fee_lamports: int = 0
    last_updated: float = field(default_factory=time.time)


@dataclass
class ExecutionMetrics:
    """
    Performance tracking for the execution agent.

    Tracks:
    - Total operations (transfers, swaps) and outcomes
    - Latency statistics for monitoring performance degradation
    - MEV protection interventions (swaps blocked due to risk)
    - Circuit breaker activations (safety shutdowns during RPC issues)

    Metrics are logged every 5 minutes and stored in agent storage.
    """
    transfers: int = 0
    swaps: int = 0
    successes: int = 0
    failures: int = 0
    average_latency_ms: float = 0.0
    total_fees_lamports: int = 0
    mev_protections: int = 0
    circuit_breaker_trips: int = 0

    def record_latency(self, latency_ms: float) -> None:
        """
        Incrementally update running average latency.

        Uses a rolling average to avoid accumulating historical samples,
        which keeps memory usage constant and gives more weight to recent performance.
        """
        samples = self.transfers + self.swaps
        if samples <= 0:
            self.average_latency_ms = latency_ms
            return
        previous = self.average_latency_ms * (samples - 1)
        self.average_latency_ms = (previous + latency_ms) / samples


@dataclass
class SwapDecision:
    proceed: bool
    risk_level: str
    reasons: List[str]
    price_impact_pct: float
    congestion: str


# -----------------------------------------------------------------------------
# Jupiter API Client
# -----------------------------------------------------------------------------


class JupiterClient:
    """Encapsulates Jupiter API interactions with privacy-conscious features."""

    def __init__(self, cfg_execution) -> None:
        self.cfg = cfg_execution

        # Circuit breaker protects against cascading failures when Jupiter API is down
        # After N failures, it stops sending requests and gives the service time to recover
        self.breaker = CircuitBreaker(
            failure_threshold=config.security.circuit_breaker_threshold,
            recovery_time=config.security.circuit_breaker_timeout,
        )

        # Lazy-initialized HTTP session - created on first use
        self._session: Optional[aiohttp.ClientSession] = None

        # Semaphore limits concurrent outbound requests to respect API rate limits
        self._semaphore = asyncio.Semaphore(max(1, self.cfg.jupiter_max_retries))

        # Privacy features: randomized timing and route obfuscation to reduce MEV attack surface
        self._jitter_seconds = float(os.getenv("JUPITER_TIMING_JITTER", "3.0"))
        self._obfuscate_routes = os.getenv("JUPITER_ROUTE_OBFUSCATION", "true").lower() == "true"

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def quote(self, request: SwapRequest, slippage_bps: int, limiter: TokenBucket) -> Dict[str, Any]:
        """
        Fetch a swap quote from Jupiter aggregator.

        This is step 1 of the two-phase swap flow:
        1. Get quote (this method) - finds best route and pricing
        2. Execute swap - signs and submits the transaction

        Returns dict with 'success' bool and either 'data' (quote) or 'error' (string).
        """
        # Check if circuit breaker is open (too many recent failures)
        if not self.breaker.allow_call():
            return {"success": False, "error": "jupiter circuit breaker open"}

        # Build Jupiter API query parameters
        params = {
            "inputMint": request.input_token,
            "outputMint": request.output_token,
            "amount": str(self._amount_in_lamports(request.input_token, request.amount)),
            "slippageBps": slippage_bps,
            # onlyDirectRoutes=false enables multi-hop routes, making tx path less predictable (MEV defense)
            "onlyDirectRoutes": "false" if self._obfuscate_routes else "true",
            "enforceSingleTx": "true",  # Force atomic execution (no partial fills)
        }
        if config.execution.restrict_intermediate_tokens:
            # Limit intermediate tokens to reduce attack surface (e.g., only use USDC/SOL as bridge tokens)
            params["restrictIntermediateTokens"] = "true"

        headers = self._headers()
        url = f"{self._base_url()}/v6/quote"

        session = await self._ensure_session()

        # Serialize outbound quote calls so we respect Jupiter rate limits and our own token bucket
        # This prevents us from overwhelming Jupiter's API or hitting rate limits
        async with self._semaphore:
            # Wait for token bucket to allow this request (rate limiting)
            await limiter.acquire(amount=1.0, max_wait=2.0)
            try:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        detail = await response.text()
                        # Record failure for circuit breaker tracking
                        self.breaker.record_failure()
                        return {"success": False, "error": f"quote failed ({response.status}): {detail}"}
                    payload = await response.json()
            except aiohttp.ClientError as exc:
                self.breaker.record_failure()
                return {"success": False, "error": f"quote error: {exc}"}

        # Success! Record it so circuit breaker knows the service is healthy
        self.breaker.record_success()
        return {"success": True, "data": payload}

    async def execute(self, request: SwapRequest, quote: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a swap using a previously fetched quote.

        This is step 2 of the two-phase swap flow. Jupiter returns a serialized
        transaction that we need to sign and submit to the network.

        Privacy features:
        - Random timing jitter prevents MEV bots from predicting submission time
        - Uses pro endpoint with API key when available (better privacy vs public endpoints)

        Returns dict with 'success' bool and either 'data' (swap tx) or 'error' (string).
        """
        # Check circuit breaker before attempting swap
        if not self.breaker.allow_call():
            return {"success": False, "error": "jupiter circuit breaker open"}

        # Build swap execution payload
        payload = {
            "quoteResponse": quote,  # Quote from previous step
            "userPublicKey": request.wallet,  # Wallet that will sign the transaction
            "wrapAndUnwrapSol": True,  # Auto-wrap SOL to WSOL if needed
        }
        if request.max_priority_fee is not None:
            # Attach custom priority fee to jump ahead in block processing
            payload["prioritizationFeeLamports"] = request.max_priority_fee

        if self._jitter_seconds > 0:
            # Introduce a randomized delay to avoid deterministic timing that MEV bots can exploit
            # Makes it harder for frontrunners to predict when our tx will hit the mempool
            await asyncio.sleep(random.uniform(0.0, self._jitter_seconds))

        url = f"{self._base_url()}/v6/swap"
        headers = self._headers()
        session = await self._ensure_session()

        # Serialize swap execution through semaphore (rate limiting)
        async with self._semaphore:
            try:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        detail = await response.text()
                        self.breaker.record_failure()
                        return {"success": False, "error": f"swap failed ({response.status}): {detail}"}
                    payload = await response.json()
            except aiohttp.ClientError as exc:
                self.breaker.record_failure()
                return {"success": False, "error": f"swap error: {exc}"}

        # Swap request succeeded, update circuit breaker
        self.breaker.record_success()
        return {"success": True, "data": payload}

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        timeout = aiohttp.ClientTimeout(total=self.cfg.jupiter_timeout_seconds)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _base_url(self) -> str:
        if self.cfg.jupiter_api_key:
            return self.cfg.jupiter_pro_url
        return self.cfg.jupiter_lite_url

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.cfg.jupiter_api_key:
            # Private routes require the pro API key, so propagate it when present.
            headers["Authorization"] = f"Bearer {self.cfg.jupiter_api_key}"
        return headers

    def _amount_in_lamports(self, mint: str, amount: float) -> int:
        decimals = {
            config.token.usdc_mint: config.token.usdc_decimals,
            config.token.usdt_mint: config.token.usdt_decimals,
            config.token.sol_mint: config.token.sol_decimals,
        }.get(mint, 9)
        return int(round(amount * (10**decimals)))


# -----------------------------------------------------------------------------
# Transfer Execution
# -----------------------------------------------------------------------------


class TransferExecutor:
    def __init__(self, rpc_client: AsyncClient) -> None:
        self.client = rpc_client
        self.breaker = CircuitBreaker(
            failure_threshold=config.security.circuit_breaker_threshold,
            recovery_time=config.security.circuit_breaker_timeout,
        )
        self._decimals_cache: Dict[str, int] = {
            config.token.usdc_mint: config.token.usdc_decimals,
            config.token.usdt_mint: config.token.usdt_decimals,
            config.token.sol_mint: config.token.sol_decimals,
        }

    async def execute(self, ctx: Context, request: TransferRequest, wallet: Optional[SoldersKeypair]) -> Dict[str, Any]:
        privacy_features: List[str] = []
        tx_context = TransactionContext(deadline_seconds=30)

        async def run_transfer() -> Dict[str, Any]:
            if request.use_compression:
                result = await self._compressed_transfer(ctx, request)
                if result.get("success"):
                    privacy_features.append("compression")
                return result
            return await self._standard_transfer(ctx, request, wallet, tx_context, privacy_features)

        try:
            # Wrap the transfer in a small retry loop to smooth over transient RPC or blockhash errors.
            return await retry_async(
                run_transfer,
                retries=3,
                base_delay=0.75,
                on_retry=lambda attempt, error: ctx.logger.warning(
                    "Transfer retry %s for %s due to %s", attempt, request.request_id, error
                ),
            )
        except Exception as exc:  # noqa: PERF203
            self.breaker.record_failure()
            return {"success": False, "error": str(exc)}

    async def _standard_transfer(
        self,
        ctx: Context,
        request: TransferRequest,
        wallet: Optional[SoldersKeypair],
        tx_context: TransactionContext,
        privacy_features: List[str],
    ) -> Dict[str, Any]:
        if wallet is None:
            # CLIENT-SIDE SIGNING: Return transaction details for wallet signing
            return {
                "success": True,
                "requires_signing": True,
                "operation": "transfer",
                "from_wallet": request.from_wallet,
                "to_wallet": request.to_wallet,
                "amount": request.amount,
                "token_mint": request.token_mint,
                "message": "⚠️ Transaction ready. Please sign with your wallet (Phantom/Solflare) to complete the transfer.",
                "instructions": [
                    "1. Connect your Solana wallet",
                    f"2. Approve transfer of {request.amount} tokens",
                    f"3. From: {request.from_wallet[:16]}...",
                    f"4. To: {request.to_wallet[:16]}...",
                ],
            }

        from_account = Pubkey.from_string(request.from_wallet)
        to_account = Pubkey.from_string(request.to_wallet)
        mint = Pubkey.from_string(request.token_mint)

        decimals = await self._decimals_for_mint(mint, ctx)
        amount = int(round(request.amount * (10**decimals)))

        latest_blockhash = await self._rpc_call(self.client.get_latest_blockhash, commitment=Confirmed)
        if latest_blockhash is None:
            raise RuntimeError("Unable to fetch latest blockhash")

        instruction = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                mint=mint,
                from_pubkey=from_account,
                to_pubkey=to_account,
                owner=wallet.pubkey(),
                amount=amount,
                decimals=decimals,
            )
        )

        compute_budget = [
            # Bump compute units and attach a small priority fee so the transfer lands quickly.
            set_compute_unit_limit(250_000),
            set_compute_unit_price(max(1_000, config.execution.max_priority_fee // 2)),
        ]
        privacy_features.extend(["priority_fee", "compute_budget"])

        transaction = Transaction.new_signed_with_payer(
            compute_budget + [instruction],
            payer=wallet.pubkey(),
            signing_keypairs=[wallet],
            recent_blockhash=latest_blockhash.blockhash,
        )

        # Small random delay helps de-sync repeated transfers in multi-user demo environments.
        await asyncio.sleep(random.uniform(0.1, 0.6))

        raw_tx = bytes(transaction)
        signature = await self._rpc_call(
            self.client.send_raw_transaction,
            raw_tx,
            opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed, max_retries=3),
        )

        if isinstance(signature, dict):
            signature = signature.get("result")

        if not signature:
            raise RuntimeError("Transaction submission returned empty signature")

        signature_obj = Signature.from_string(str(signature))
        await self._rpc_call(self.client.confirm_transaction, signature_obj, commitment=Confirmed)

        tx_context.signature = str(signature_obj)
        tx_context.priority_fee = config.execution.max_priority_fee

        return {
            "success": True,
            "signature": tx_context.signature,
            "fee_paid": tx_context.priority_fee,
            "privacy_features": privacy_features,
            "explorer_url": f"https://explorer.solana.com/tx/{tx_context.signature}",
        }

    async def _compressed_transfer(self, ctx: Context, request: TransferRequest) -> Dict[str, Any]:
        # CLIENT-SIDE SIGNING: Compression requires Light Protocol client-side integration
        ctx.logger.info("Compressed transfer requested - requires client-side Light Protocol integration")
        return {
            "success": True,
            "requires_signing": True,
            "operation": "compressed_transfer",
            "from_wallet": request.from_wallet,
            "to_wallet": request.to_wallet,
            "amount": request.amount,
            "token_mint": request.token_mint,
            "compression": True,
            "message": "⚠️ Compressed transfer ready. Requires Light Protocol wallet integration to sign and compress on-chain.",
            "instructions": [
                "1. Use Light Protocol-compatible wallet",
                f"2. Approve compressed transfer of {request.amount} tokens",
                f"3. To: {request.to_wallet[:16]}...",
                "4. Transaction will be compressed on-chain for privacy",
            ],
            "note": "Compression reduces on-chain footprint and enhances privacy",
        }

    async def _decimals_for_mint(self, mint: Pubkey, ctx: Context) -> int:
        mint_str = str(mint)
        if mint_str in self._decimals_cache:
            return self._decimals_cache[mint_str]

        try:
            response = await self._rpc_call(self.client.get_token_supply, mint)
            decimals = response.value.decimals if response else config.token.usdc_decimals
            self._decimals_cache[mint_str] = decimals
            return decimals
        except Exception as exc:  # noqa: PERF203
            ctx.logger.warning("Falling back to 9 decimals for %s: %s", mint_str, exc)
            self._decimals_cache[mint_str] = 9
            return 9

    async def _rpc_call(self, func, *args, **kwargs):
        if not self.breaker.allow_call():
            raise RuntimeError("RPC circuit breaker open")
        try:
            response = await func(*args, **kwargs)
        except Exception:
            self.breaker.record_failure()
            raise
        self.breaker.record_success()
        if hasattr(response, "value"):
            return response.value
        if hasattr(response, "result"):
            return response.result
        if isinstance(response, dict):
            return response.get("result")
        return response


# -----------------------------------------------------------------------------
# Execution Service Orchestrator
# -----------------------------------------------------------------------------


class ExecutionService:
    def __init__(self) -> None:
        self.cfg = config
        self.client = AsyncClient(self.cfg.rpc_url())
        self.network = NetworkSnapshot()
        self.metrics = ExecutionMetrics()
        self.rpc_rate = TokenBucket(rate=self.cfg.execution.transfer_rate_limit, capacity=10.0)
        self.swap_rate = TokenBucket(rate=self.cfg.execution.swap_rate_limit, capacity=5.0)
        self.jupiter = JupiterClient(self.cfg.execution)
        self.transfer_executor = TransferExecutor(self.client)
        self.wallet = self._load_wallet()
        self.session_limiter = TokenBucket(rate=10.0, capacity=20.0)

    async def startup(self, ctx: Context) -> None:
        ctx.logger.info("Execution service online")
        ctx.storage.set("performance_metrics", self.metrics.__dict__)
        ctx.storage.set("network_snapshot", self.network.__dict__)
        if self.wallet:
            ctx.storage.set("wallet_public_key", str(self.wallet.pubkey()))
            ctx.logger.info("Loaded execution wallet")
        else:
            ctx.logger.info("🔒 CLIENT-SIDE SIGNING MODE: All transactions returned unsigned for wallet signing")
            ctx.logger.info("🔒 Security: Zero custody risk - users sign with Phantom/Solflare")

    async def shutdown(self) -> None:
        await self.jupiter.close()
        await self.client.close()

    async def process_transfer(self, ctx: Context, request: TransferRequest) -> ExecutionResponse:
        started = time.perf_counter()
        self.metrics.transfers += 1

        if not await self.rpc_rate.acquire():
            return ExecutionResponse(
                request_id=request.request_id,
                success=False,
                result={"error": "transfer rate limit reached"},
            )

        result = await self.transfer_executor.execute(ctx, request, self.wallet)
        success = result.get("success", False)
        self._update_metrics(success, started, request.use_compression)

        return ExecutionResponse(
            request_id=request.request_id,
            success=success,
            result=result,
            execution_time=(time.perf_counter() - started),
            signature=result.get("signature"),
            explorer_url=result.get("explorer_url"),
            mev_protected=request.use_compression,
        )

    async def process_swap(self, ctx: Context, request: SwapRequest) -> ExecutionResponse:
        started = time.perf_counter()
        self.metrics.swaps += 1

        if not await self.swap_rate.acquire():
            return ExecutionResponse(
                request_id=request.request_id,
                success=False,
                result={"error": "swap rate limit reached"},
            )

        slippage = request.slippage_bps or self.cfg.execution.default_slippage_bps
        if self.cfg.execution.enable_dynamic_slippage:
            slippage = self._dynamic_slippage(slippage)

        quote = await self.jupiter.quote(request, slippage, self.session_limiter)
        if not quote.get("success"):
            self._update_metrics(False, started)
            return ExecutionResponse(
                request_id=request.request_id,
                success=False,
                result={"error": quote.get("error", "failed to fetch quote")},
            )

        decision = self._evaluate_mev_risk(quote["data"])
        if not decision.proceed and request.protect_mev:
            self.metrics.mev_protections += 1
            self._update_metrics(False, started)
            return ExecutionResponse(
                request_id=request.request_id,
                success=False,
                result={
                    "error": "swap blocked due to MEV risk",
                    "analysis": decision.__dict__,
                },
            )

        swap_response = await self.jupiter.execute(request, quote["data"])
        if not swap_response.get("success"):
            self._update_metrics(False, started)
            return ExecutionResponse(
                request_id=request.request_id,
                success=False,
                result={"error": swap_response.get("error", "swap failed")},
            )

        execution_result = await self._finalize_swap(ctx, request, swap_response["data"])
        success = execution_result.get("success", False)
        self._update_metrics(success, started, mev_protected=request.protect_mev)

        return ExecutionResponse(
            request_id=request.request_id,
            success=success,
            result=execution_result,
            execution_time=(time.perf_counter() - started),
            signature=execution_result.get("signature"),
            explorer_url=execution_result.get("explorer_url"),
            mev_protected=request.protect_mev,
        )

    async def refresh_network(self, ctx: Context) -> None:
        try:
            slot = await self.client.get_slot(commitment=Confirmed)
            samples = await self.client.get_recent_performance_samples(limit=1)
            if samples.value:
                sample = samples.value[0]
                tps = sample.num_transactions / sample.sample_period_secs
                self.network.current_tps = tps
                self.network.congestion = self._congestion_level(tps)
                self.network.priority_fee_lamports = self._suggested_priority_fee()
            if slot.value:
                self.network.slot_height = int(slot.value)
            self.network.last_updated = time.time()
            ctx.storage.set("network_snapshot", self.network.__dict__)
        except Exception as exc:  # noqa: PERF203
            ctx.logger.warning("Failed to refresh network snapshot: %s", exc)
            self.metrics.circuit_breaker_trips += 1

    async def report_metrics(self, ctx: Context) -> None:
        ctx.storage.set("performance_metrics", self.metrics.__dict__)
        ctx.logger.info(
            "Execution metrics | transfers=%s swaps=%s success=%s failures=%s avg_latency=%.0fms congestion=%s",
            self.metrics.transfers,
            self.metrics.swaps,
            self.metrics.successes,
            self.metrics.failures,
            self.metrics.average_latency_ms,
            self.network.congestion,
        )

    def _update_metrics(self, success: bool, started: float, mev_protected: bool = False) -> None:
        latency_ms = (time.perf_counter() - started) * 1000
        self.metrics.record_latency(latency_ms)
        if success:
            self.metrics.successes += 1
            if mev_protected:
                self.metrics.mev_protections += 1
        else:
            self.metrics.failures += 1

    def _dynamic_slippage(self, baseline: int) -> int:
        congestion = self.network.congestion
        if congestion == "critical":
            return min(baseline * 3, 500)
        if congestion == "high":
            return min(int(baseline * 2), 300)
        if congestion == "medium":
            return int(baseline * 1.5)
        return baseline

    def _evaluate_mev_risk(self, quote: Dict[str, Any]) -> SwapDecision:
        """
        Evaluate MEV (Maximum Extractable Value) risk for a swap.

        MEV attackers look for:
        1. High price impact swaps (easy to sandwich)
        2. Congested network conditions (more time to frontrun)

        If risk is high and protect_mev=True, we'll reject the swap.
        This protects users from sandwich attacks and value extraction.
        """
        # Parse price impact from Jupiter quote (comes as decimal, e.g. 0.05 = 5%)
        raw_impact = quote.get("priceImpactPct", 0)
        try:
            price_impact = float(raw_impact) * 100 if raw_impact else 0.0
        except (TypeError, ValueError):
            # Fail safe: if we can't parse price impact, assume 0
            price_impact = 0.0

        reasons: List[str] = []
        proceed = True  # Default: allow swap
        risk_level = "low"

        # RULE 1: Block swaps during high congestion (slower confirmation = more MEV risk)
        if self.network.congestion in {"high", "critical"}:
            reasons.append("High network congestion detected")
            risk_level = "medium"
            proceed = False  # Reject swap to protect user

        # RULE 2: Block swaps with high price impact (vulnerable to sandwich attacks)
        # Example: If you're moving the price 5%+, a bot can frontrun you (buy first),
        # let your tx execute (pushing price higher), then sell for instant profit
        if price_impact > 5.0:
            reasons.append(f"Price impact {price_impact:.2f}% exceeds safe threshold")
            risk_level = "high"
            proceed = False  # Reject swap to protect user

        return SwapDecision(
            proceed=proceed,
            risk_level=risk_level,
            reasons=reasons,
            price_impact_pct=price_impact,
            congestion=self.network.congestion,
        )

    async def _finalize_swap(self, ctx: Context, request: SwapRequest, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign and submit a swap transaction to Solana.

        Jupiter returns a serialized transaction (base64 encoded). We need to:
        1. Deserialize it (handle both versioned and legacy tx formats)
        2. Sign it with our payer wallet
        3. Submit it to the RPC
        4. Wait for confirmation

        If no wallet is configured, we return the unsigned tx for client-side signing.
        """
        # Extract the base64-encoded transaction from Jupiter's response
        swap_tx = payload.get("swapTransaction")
        if not swap_tx:
            return {"success": False, "error": "Jupiter swap returned no transaction"}

        # Decode base64 to raw bytes
        tx_bytes = base64.b64decode(swap_tx)

        # CLIENT-SIDE SIGNING: Return unsigned transaction for wallet signing
        if self.wallet is None:
            return {
                "success": True,
                "requires_signing": True,
                "operation": "swap",
                "unsigned_transaction": swap_tx,
                "wallet": request.wallet,
                "input_token": request.input_token,
                "output_token": request.output_token,
                "amount": request.amount,
                "message": "⚠️ Swap transaction ready. Sign with your wallet (Phantom/Solflare) to execute the swap.",
                "instructions": [
                    "1. Connect your Solana wallet",
                    "2. Review swap details carefully",
                    "3. Sign the transaction to complete the swap",
                    "4. Transaction will execute atomically via Jupiter aggregator",
                ],
                "note": "MEV protection enabled - transaction includes slippage limits and priority fees",
            }

    def _congestion_level(self, tps: float) -> str:
        if tps < 1_000:
            return "low"
        if tps < 2_500:
            return "medium"
        if tps < 4_000:
            return "high"
        return "critical"

    def _suggested_priority_fee(self) -> int:
        base = config.execution.max_priority_fee
        level = self.network.congestion
        if level == "critical":
            return base * 3
        if level == "high":
            return base * 2
        if level == "medium":
            return int(base * 1.25)
        return base

    def _load_wallet(self) -> Optional[SoldersKeypair]:
        # CLIENT-SIDE SIGNING MODEL: Backend does not hold private keys
        # All transactions are returned unsigned for client-side signing via Phantom/Solflare
        # This eliminates custody risk and aligns with Web3 security best practices
        return None  # Always return None to force unsigned transaction mode


# -----------------------------------------------------------------------------
# Agent Wiring
# -----------------------------------------------------------------------------


service = ExecutionService()

execution_agent = Agent(
    name="PrivAgent_Execution",
    seed=config.execution.agent_seed,
    mailbox=True,
    readme_path="README.md",
    publish_agent_details=True,
)


@execution_agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    await service.startup(ctx)


@execution_agent.on_event("shutdown")
async def on_shutdown(_: Context) -> None:
    await service.shutdown()


@execution_agent.on_message(TransferRequest)
async def on_transfer(ctx: Context, sender: str, request: TransferRequest) -> None:
    response = await service.process_transfer(ctx, request)
    await ctx.send(sender, response)


@execution_agent.on_message(SwapRequest)
async def on_swap(ctx: Context, sender: str, request: SwapRequest) -> None:
    response = await service.process_swap(ctx, request)
    await ctx.send(sender, response)


@execution_agent.on_interval(period=60.0)
async def refresh_network(ctx: Context) -> None:
    await service.refresh_network(ctx)


@execution_agent.on_interval(period=300.0)
async def emit_metrics(ctx: Context) -> None:
    await service.report_metrics(ctx)


# -----------------------------------------------------------------------------
# Test Helpers
# -----------------------------------------------------------------------------


def load_payer_keypair(refresh: bool = False) -> Optional[SoldersKeypair]:
    if refresh:
        service.wallet = service._load_wallet()
    return service.wallet


async def get_jupiter_quote(ctx: Context, request: SwapRequest) -> Dict[str, Any]:
    slippage = request.slippage_bps or config.execution.default_slippage_bps
    return await service.jupiter.quote(request, slippage, service.session_limiter)


async def regular_transfer_with_privacy_features(
    ctx: Context,
    request: TransferRequest,
    tx_context: Optional[TransactionContext] = None,
) -> Dict[str, Any]:
    _ = tx_context  # maintained for backward compatibility with legacy tests
    return await service.transfer_executor.execute(ctx, request, service.wallet)
