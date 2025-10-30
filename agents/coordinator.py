from __future__ import annotations

import inspect
import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv

# Load .env file BEFORE importing config to ensure environment variables are available
load_dotenv()

from openai import OpenAI
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents.config import config
# Import authentication module for agent-to-agent verification
from agents.auth import auth_manager, create_message_digest
from models.messages import (
    ExecutionResponse,
    MonitoringRequest,
    MonitoringResponse,
    PrivacyAlert,
    PrivacyRequest,
    PrivacyResponse,
    SwapRequest,
    TransferRequest,
)

# Regex patterns for extracting data from natural language
ADDRESS_PATTERN = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")  # Solana base58 address format
AMOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")  # Decimal numbers (e.g., "5.5 USDC")


@dataclass
class RoutingDecision:
    """
    LLM-generated routing decision for a user query.

    The coordinator uses an LLM to:
    1. Understand user intent (e.g., "compress tokens" → privacy agent)
    2. Extract parameters (wallet address, amounts, token symbols)
    3. Route to the correct specialized agent (privacy/execution/monitoring)
    4. Handle multi-step workflows (e.g., compress then transfer)

    Example:
    User: "Compress 100 USDC for wallet ABC123..."
    → intent="compress", parameters={wallet="ABC123", amount=100, token="USDC"}
    → Route to privacy agent
    """
    intent: str  # "transfer", "swap", "compress", "monitor", "report"
    confidence: float  # LLM's confidence 0.0-1.0
    parameters: Dict[str, Any]  # Extracted params (wallet, amount, tokens, etc.)
    missing: list[str]  # Required params that couldn't be extracted
    reasoning: str  # LLM's explanation for debugging
    raw: str  # Raw LLM response for audit trail


class CoordinatorService:
    """
    Central orchestration service - the "brain" of the agent system.

    Responsibilities:
    1. Natural Language Understanding (NLU) - Parse user queries using LLM
    2. Intent Routing - Determine which agent should handle the request
    3. Parameter Extraction - Pull wallet addresses, amounts, tokens from text
    4. Agent Discovery - Find agents on the network (static or dynamic)
    5. Session Management - Track conversations and pending operations
    6. Response Aggregation - Collect results from multiple agents

    Architecture:
    - Uses OpenAI-compatible LLM for intent classification
    - Communicates with specialized agents via uAgents messaging
    - Maintains session state for multi-turn conversations
    - Supports both static (env vars) and dynamic (almanac) agent discovery

    Security: Agent-to-agent messages cryptographically verified (see agents/auth.py)

    Example Flow:
    User: "I want to privately swap 50 USDC to SOL"
    1. LLM extracts: intent=swap, amount=50, input=USDC, output=SOL, privacy=true
    2. Coordinator routes to execution agent (handles swaps)
    3. Execution agent enables MEV protection (privacy flag)
    4. Result returned to user via coordinator
    """

    def __init__(self) -> None:
        # Agent addresses - can be hardcoded (env vars) or discovered dynamically
        self.privacy_agent = os.getenv("PRIVACY_AGENT_ADDRESS", "")
        self.execution_agent = os.getenv("EXECUTION_AGENT_ADDRESS", "")
        self.monitoring_agent = os.getenv("MONITORING_AGENT_ADDRESS", "")
        self.config = config

        # LLM setup for natural language understanding
        api_key = self.config.llm.api_key
        if not api_key:
            raise ValueError("LLM API key is required for coordinator intent routing.")

        base_url = self.config.llm.base_url
        if self.config.llm.provider == "asi1" and not base_url:
            base_url = self.config.llm.asi1_base_url

        # Maintain a single OpenAI client so HTTP sessions and rate limits are shared across requests
        self.llm_client = OpenAI(api_key=api_key, base_url=base_url)

        # LLM parameters
        self._llm_model = (
            self.config.llm.asi1_model
            if self.config.llm.provider == "asi1"
            else self.config.llm.model
        )
        self._llm_temperature = self.config.llm.temperature  # Lower = more deterministic
        self._llm_max_tokens = self.config.llm.max_tokens  # Response length limit
        self._llm_timeout = self.config.llm.timeout_seconds  # Prevent hanging


    async def startup(self, ctx: Context) -> None:
        ctx.storage.set("sessions", {})
        ctx.storage.set("pending", {})
        ctx.storage.set("alerts", [])

        # Log discovery mode
        if self.privacy_agent and self.execution_agent and self.monitoring_agent:
            ctx.logger.info("coordinator ready - using configured agent addresses")
            ctx.logger.info(f"Privacy Agent: {self.privacy_agent}")
            ctx.logger.info(f"Execution Agent: {self.execution_agent}")
            ctx.logger.info(f"Monitoring Agent: {self.monitoring_agent}")
        else:
            # List missing agents
            missing = []
            if not self.privacy_agent:
                missing.append("PRIVACY_AGENT_ADDRESS")
            if not self.execution_agent:
                missing.append("EXECUTION_AGENT_ADDRESS")
            if not self.monitoring_agent:
                missing.append("MONITORING_AGENT_ADDRESS")

            ctx.logger.error(f"❌ Missing required agent addresses in .env: {', '.join(missing)}")
            ctx.logger.error("❌ Please deploy agents to Agentverse and set their addresses in .env")
            ctx.logger.error("❌ Or run all agents locally for testing (see DEPLOYMENT.md)")

    async def handle_chat_message(self, ctx: Context, sender: str, message: ChatMessage) -> None:
        await self._acknowledge(ctx, sender, message)

        for item in message.content:
            if isinstance(item, StartSessionContent):
                await self._open_session(ctx, message.msg_id, sender)
                await self._send_text(ctx, sender, self._welcome_message())
            elif isinstance(item, TextContent):
                reply = await self._route_text(ctx, sender, item.text)
                await self._send_text(ctx, sender, reply)
            elif isinstance(item, EndSessionContent):
                await self._close_session(ctx, message.msg_id)
                await self._send_text(ctx, sender, "Session closed. Reach out anytime.")

    async def receive_privacy_response(self, ctx: Context, sender: str, msg: PrivacyResponse) -> None:
        # Verify message from privacy agent (agent-to-agent auth)
        if self.privacy_agent and sender != self.privacy_agent:
            ctx.logger.warning(f"Privacy response from unauthorized agent: {sender}")
            return

        pending = self._pending(ctx).get(msg.request_id)
        if not pending:
            ctx.logger.warning("untracked privacy response %s", msg.request_id)
            return

        text = self._format_privacy_response(msg)
        await self._send_text(ctx, pending["sender"], text)
        self._remove_pending(ctx, msg.request_id)

    async def receive_execution_response(self, ctx: Context, sender: str, msg: ExecutionResponse) -> None:
        # Verify message from execution agent
        if self.execution_agent and sender != self.execution_agent:
            ctx.logger.warning(f"Execution response from unauthorized agent: {sender}")
            return

        pending = self._pending(ctx).get(msg.request_id)
        if not pending:
            ctx.logger.warning("untracked execution response %s", msg.request_id)
            return

        text = self._format_execution_response(msg)
        await self._send_text(ctx, pending["sender"], text)
        self._remove_pending(ctx, msg.request_id)

    async def receive_monitoring_response(self, ctx: Context, sender: str, msg: MonitoringResponse) -> None:
        # Verify message from monitoring agent
        if self.monitoring_agent and sender != self.monitoring_agent:
            ctx.logger.warning(f"Monitoring response from unauthorized agent: {sender}")
            return

        pending = self._pending(ctx).get(msg.request_id)
        if not pending:
            ctx.logger.warning("untracked monitoring response %s", msg.request_id)
            return

        text = self._format_monitoring_response(msg.result)
        await self._send_text(ctx, pending["sender"], text)
        self._remove_pending(ctx, msg.request_id)

    async def receive_privacy_alert(self, ctx: Context, sender: str, msg: PrivacyAlert) -> None:
        # Verify alert from monitoring/privacy agents
        if self.monitoring_agent and sender not in [self.monitoring_agent, self.privacy_agent]:
            ctx.logger.warning(f"Privacy alert from unauthorized agent: {sender}")
            return

        alerts = ctx.storage.get("alerts", [])
        alerts.append(msg.dict())
        ctx.storage.set("alerts", alerts)
        ctx.logger.info(
            "privacy alert %s for wallet %s (%s)",
            msg.alert_type,
            msg.wallet_address,
            msg.severity,
        )

    async def _acknowledge(self, ctx: Context, sender: str, message: ChatMessage) -> None:
        acknowledgement = ChatAcknowledgement(
            timestamp=datetime.utcnow(),
            acknowledged_msg_id=message.msg_id,
        )
        await ctx.send(sender, acknowledgement)

    async def _open_session(self, ctx: Context, session_id: str, sender: str) -> None:
        sessions = ctx.storage.get("sessions", {})
        sessions[str(session_id)] = {"sender": sender, "opened": datetime.utcnow().isoformat()}
        ctx.storage.set("sessions", sessions)

    async def _close_session(self, ctx: Context, session_id: str) -> None:
        sessions = ctx.storage.get("sessions", {})
        sessions.pop(str(session_id), None)
        ctx.storage.set("sessions", sessions)

    async def _route_text(self, ctx: Context, sender: str, text: str) -> str:
        trimmed = text.strip()
        if not trimmed:
            return "I did not catch that. Try describing the action you want me to take."

        try:
            # The router returns both the intent label and any structured parameters we need.
            decision = self._call_router(trimmed)
        except ValueError as exc:
            ctx.logger.error("intent routing parse error: %s", exc)
            return (
                "I had trouble understanding your request. "
                "Please rephrase or ask for `help` to see examples."
            )
        except Exception as exc:
            ctx.logger.error("intent routing failed: %s", exc)
            return (
                "I encountered an error while processing your request. "
                "Please try again shortly."
            )

        ctx.logger.info(
            "intent=%s confidence=%.2f sender=%s missing=%s reason=%s",
            decision.intent,
            decision.confidence,
            sender,
            decision.missing,
            decision.reasoning,
        )

        if decision.missing:
            missing = ", ".join(decision.missing)
            return (
                f"I still need the following details before I can continue: {missing}. "
                "Please provide them so I can help."
            )

        async def _sync_response(value: str) -> str:
            return value

        # Each supported intent maps to a coroutine that knows how to talk to the downstream agent.
        handler_map: Dict[str, Callable[[], Awaitable[str]]] = {
            "help": lambda: _sync_response(self._help_message()),
            "greeting": lambda: _sync_response(self._welcome_message()),
            "compression": lambda: self._handle_compression_llm(ctx, sender, decision.parameters),
            "transfer": lambda: self._handle_transfer_llm(ctx, sender, decision.parameters),
            "swap": lambda: self._handle_swap_llm(ctx, sender, decision.parameters),
            "privacy_report": lambda: self._handle_privacy_report_llm(ctx, sender, decision.parameters),
            "monitoring": lambda: self._handle_monitoring_llm(ctx, sender, decision.parameters),
        }

        handler = handler_map.get(decision.intent)
        if not handler:
            return (
                "I'm not sure how to handle that request. "
                "Ask for `help` to see available commands."
            )

        result = handler()
        if inspect.isawaitable(result):
            return await result
        return result

    def _call_router(self, text: str) -> RoutingDecision:
        # We ask the LLM to emit compact JSON so that parsing failures are explicit.
        response = self.llm_client.chat.completions.create(
            model=self._llm_model,
            temperature=self._llm_temperature,
            max_tokens=self._llm_max_tokens,
            timeout=self._llm_timeout,
            messages=[
                {"role": "system", "content": self._get_routing_system_prompt()},
                {"role": "user", "content": text},
            ],
        )

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise ValueError("LLM response missing content") from exc

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON") from exc

        if not isinstance(payload, dict):
            raise ValueError("LLM routing payload must be a JSON object")

        intent = str(payload.get("intent") or "unknown")
        confidence_raw = payload.get("confidence")
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0

        parameters = payload.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}

        missing_raw = payload.get("missing") or []
        if isinstance(missing_raw, list):
            missing = [str(item) for item in missing_raw]
        else:
            missing = []

        reasoning = str(payload.get("reasoning") or "")

        return RoutingDecision(
            intent=intent,
            confidence=confidence,
            parameters=parameters,
            missing=missing,
            reasoning=reasoning,
            raw=content,
        )

    def _get_routing_system_prompt(self) -> str:
        return textwrap.dedent(
            """
            You route user requests for a privacy-focused Solana agent system.
            Return compact JSON only in this exact shape:
            {
              "intent": "<intent>",
              "confidence": <float 0-1>,
              "parameters": {...},
              "missing": ["param", ...],
              "reasoning": "short justification"
            }

            Intents: greeting, help, compression, transfer, swap, privacy_report, monitoring, unknown.
            Required parameters:
              compression -> wallet_address, amount
              transfer -> from_wallet, to_wallet, amount, token (USDC|USDT|SOL)
              swap -> wallet, amount, input_token, output_token (USDC|USDT|SOL)
              privacy_report -> wallet_address
              monitoring -> wallet_address, optional threshold (0-100)

            Extract Solana wallet addresses (base58, 32-44 chars).
            Parse numeric amounts as floats.
            Leave missing parameters in the list.
            Keep reasoning brief and factual.
            Never add markdown or extra keys.
            """
        ).strip()

    async def _handle_compression_llm(self, ctx: Context, sender: str, params: Dict[str, Any]) -> str:
        privacy_agent = await self._get_agent_address(ctx, "privacy")
        if not privacy_agent:
            return "❌ Privacy agent not available. Please ensure privacy agents are running and registered on Agentverse."

        wallet_address = params.get("wallet_address")
        amount = params.get("amount", self.config.token.default_compression_amount)

        if not wallet_address:
            return "Wallet address is required for compression requests."

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return "Amount must be numeric for compression requests."

        request_id = str(uuid4())
        request = PrivacyRequest(
            action="compress",
            wallet_address=wallet_address,
            amount=amount_value,
            request_id=request_id,
        )
        await ctx.send(privacy_agent, request)
        self._store_pending(ctx, request_id, sender, "privacy")

        return (
            f"Compression request submitted for {amount_value} tokens in wallet {wallet_address[:8]}... "
            "I will update you when the privacy agent finishes processing."
        )

    async def _handle_transfer_llm(self, ctx: Context, sender: str, params: Dict[str, Any]) -> str:
        execution_agent = await self._get_agent_address(ctx, "execution")
        if not execution_agent:
            return "❌ Execution agent not available. Please ensure execution agents are running and registered on Agentverse."

        from_wallet = params.get("from_wallet")
        to_wallet = params.get("to_wallet")
        amount = params.get("amount")
        token = params.get("token", "USDC")

        if not from_wallet or not to_wallet or amount is None:
            return "Transfer requests require from_wallet, to_wallet, and amount parameters."

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return "Amount must be numeric for transfer requests."

        token_mint = self._token_symbol_to_mint(str(token))
        if not token_mint:
            return f"Unknown token: {token}. Please use USDC, USDT, or SOL."

        request_id = str(uuid4())
        transfer = TransferRequest(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=amount_value,
            token_mint=token_mint,
            use_compression=bool(params.get("use_compression", False)),
            request_id=request_id,
        )
        await ctx.send(execution_agent, transfer)
        self._store_pending(ctx, request_id, sender, "transfer")

        return (
            f"Transfer of {amount_value} {token} from {from_wallet[:8]}... to {to_wallet[:8]}... submitted. "
            "I will relay the transaction status once it is available."
        )

    async def _handle_swap_llm(self, ctx: Context, sender: str, params: Dict[str, Any]) -> str:
        execution_agent = await self._get_agent_address(ctx, "execution")
        if not execution_agent:
            return "❌ Execution agent not available. Please ensure execution agents are running and registered on Agentverse."

        wallet = params.get("wallet")
        amount = params.get("amount")
        input_token = params.get("input_token")
        output_token = params.get("output_token")

        if not wallet or amount is None or not input_token or not output_token:
            return "Swap requests require wallet, amount, input_token, and output_token parameters."

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            return "Amount must be numeric for swap requests."

        input_mint = self._token_symbol_to_mint(str(input_token))
        output_mint = self._token_symbol_to_mint(str(output_token))

        if not input_mint or not output_mint:
            return "Invalid tokens. Please specify USDC, USDT, or SOL for both input and output."

        request_id = str(uuid4())
        swap_request = SwapRequest(
            wallet=wallet,
            input_token=input_mint,
            output_token=output_mint,
            amount=amount_value,
            request_id=request_id,
        )
        await ctx.send(execution_agent, swap_request)
        self._store_pending(ctx, request_id, sender, "swap")

        return (
            f"Swap request sent: {amount_value} {input_token} → {output_token} for wallet {wallet[:8]}... "
            "The execution agent will handle quoting and execution. I'll report back with the outcome."
        )

    async def _handle_privacy_report_llm(self, ctx: Context, sender: str, params: Dict[str, Any]) -> str:
        privacy_agent = await self._get_agent_address(ctx, "privacy")
        if not privacy_agent:
            return "❌ Privacy agent not available. Please ensure privacy agents are running and registered on Agentverse."

        wallet_address = params.get("wallet_address")
        if not wallet_address:
            return "Wallet address is required for privacy reports."

        request_id = str(uuid4())
        request = PrivacyRequest(
            action="report",
            wallet_address=wallet_address,
            request_id=request_id,
        )
        await ctx.send(privacy_agent, request)
        self._store_pending(ctx, request_id, sender, "privacy")

        return (
            f"Privacy report request submitted for wallet {wallet_address[:8]}... "
            "I will provide the analysis once complete."
        )

    async def _handle_monitoring_llm(self, ctx: Context, sender: str, params: Dict[str, Any]) -> str:
        monitoring_agent = await self._get_agent_address(ctx, "monitoring")
        if not monitoring_agent:
            return "❌ Monitoring agent not available. Please ensure monitoring agents are running and registered on Agentverse."

        wallet_address = params.get("wallet_address")
        threshold = params.get("threshold", self.config.monitoring.default_privacy_threshold)

        if not wallet_address:
            return "Wallet address is required for monitoring requests."

        try:
            threshold_value = int(threshold)
        except (TypeError, ValueError):
            return "Threshold must be an integer between 0 and 100."

        threshold_value = max(0, min(100, threshold_value))

        request_id = str(uuid4())
        request = MonitoringRequest(
            action="monitor",
            wallet_address=wallet_address,
            threshold=threshold_value,
            request_id=request_id,
        )
        await ctx.send(monitoring_agent, request)
        self._store_pending(ctx, request_id, sender, "monitoring")

        return (
            f"Monitoring request submitted for wallet {wallet_address[:8]}... with threshold {threshold_value}. "
            "I will alert you of any suspicious activity."
        )

    def _token_symbol_to_mint(self, symbol: str) -> Optional[str]:
        """Convert token symbol (USDC/USDT/SOL) to mint address."""
        symbol_upper = symbol.upper()
        if symbol_upper == "USDC":
            return self.config.token.usdc_mint
        elif symbol_upper == "USDT":
            return self.config.token.usdt_mint
        elif symbol_upper == "SOL":
            return self.config.token.sol_mint
        return None

    # =========================================================================
    # Command Handlers
    # =========================================================================

    async def _handle_compression(self, ctx: Context, sender: str, text: str) -> str:
        privacy_agent = await self._get_agent_address(ctx, "privacy")
        if not privacy_agent:
            return "❌ Privacy agent not available. Please ensure privacy agents are running and registered on Agentverse."

        wallet = self._extract_addresses(text, limit=1)
        amount = self._extract_amount(text)
        if not wallet:
            return "Provide the wallet address you wish to compress. Example: `compress 500 USDC in wallet ...`."

        request_id = str(uuid4())
        request = PrivacyRequest(
            action="compress",
            wallet_address=wallet[0],
            amount=amount or self.config.token.default_compression_amount,
            request_id=request_id,
        )
        await ctx.send(privacy_agent, request)
        self._store_pending(ctx, request_id, sender, "privacy")

        return (
            "Compression request submitted. "
            "I will update you when the privacy agent finishes processing."
        )

    async def _handle_transfer(self, ctx: Context, sender: str, text: str) -> str:
        execution_agent = await self._get_agent_address(ctx, "execution")
        if not execution_agent:
            return "❌ Execution agent not available. Please ensure execution agents are running and registered on Agentverse."

        addresses = self._extract_addresses(text, limit=2)
        if len(addresses) < 2:
            return (
                "Transfers require both a source and destination address. "
                "Example: `transfer 25 usdc from <source> to <destination>`."
            )

        amount = self._extract_amount(text)
        if amount is None:
            return "Specify the amount you want to transfer. Example: `transfer 25 usdc ...`."

        token_mint = self._token_from_text(text)
        if token_mint is None:
            return (
                "I could not determine which token to use. "
                "Mention `USDC`, `USDT`, or `SOL` in your request."
            )

        request_id = str(uuid4())
        transfer = TransferRequest(
            from_wallet=addresses[0],
            to_wallet=addresses[1],
            amount=amount,
            token_mint=token_mint,
            use_compression="compress" in text.lower(),
            request_id=request_id,
        )
        await ctx.send(execution_agent, transfer)
        self._store_pending(ctx, request_id, sender, "transfer")

        return (
            "Transfer submitted to the execution agent. "
            "I will relay the transaction status once it is available."
        )

    async def _handle_swap(self, ctx: Context, sender: str, text: str) -> str:
        execution_agent = await self._get_agent_address(ctx, "execution")
        if not execution_agent:
            return "❌ Execution agent not available. Please ensure execution agents are running and registered on Agentverse."

        amount = self._extract_amount(text)
        if amount is None:
            return "Please include the amount to swap. Example: `swap 1 sol to usdc`."

        tokens = self._extract_tokens_for_swap(text)
        if tokens is None:
            return "I could not determine the swap pair. Example: `swap 1 sol to usdc`."

        if not tokens.wallet:
            return "Include the wallet that should sign the swap. Example: `swap 1 sol to usdc for <wallet>`."

        request_id = str(uuid4())
        swap_request = SwapRequest(
            wallet=tokens.wallet,
            input_token=tokens.input_token,
            output_token=tokens.output_token,
            amount=amount,
            request_id=request_id,
        )
        await ctx.send(execution_agent, swap_request)
        self._store_pending(ctx, request_id, sender, "swap")

        return (
            "Swap request sent. The execution agent will handle quoting and execution. "
            "I'll report back with the outcome."
        )

    async def _handle_privacy_report(self, ctx: Context, sender: str, text: str) -> str:
        privacy_agent = await self._get_agent_address(ctx, "privacy")
        if not privacy_agent:
            return "❌ Privacy agent not available. Please ensure privacy agents are running and registered on Agentverse."

        wallet = self._extract_addresses(text, limit=1)
        if not wallet:
            return "Provide the wallet address you want me to analyse. Example: `privacy report for <wallet>`."

        request_id = str(uuid4())
        request = PrivacyRequest(
            action="report",
            wallet_address=wallet[0],
            request_id=request_id,
        )
        await ctx.send(privacy_agent, request)
        self._store_pending(ctx, request_id, sender, "privacy")

        return "Privacy evaluation started. I'll share the report once it is complete."

    async def _handle_monitoring(self, ctx: Context, sender: str, text: str) -> str:
        monitoring_agent = await self._get_agent_address(ctx, "monitoring")
        if not monitoring_agent:
            return "❌ Monitoring agent not available. Please ensure monitoring agents are running and registered on Agentverse."

        wallet = self._extract_addresses(text, limit=1)
        if not wallet:
            return "Provide the wallet address to monitor. Example: `monitor wallet <address> for privacy issues`."

        threshold = self._extract_threshold(text)

        request_id = str(uuid4())
        request = MonitoringRequest(
            action="monitor",
            wallet_address=wallet[0],
            threshold=threshold,
            request_id=request_id,
        )
        await ctx.send(monitoring_agent, request)
        self._store_pending(ctx, request_id, sender, "monitoring")

        return (
            f"Monitoring request submitted. I'll alert you if the risk score crosses {threshold}."
        )

    async def _send_text(self, ctx: Context, recipient: str, text: str) -> None:
        message = ChatMessage(
            timestamp=datetime.utcnow(),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        )
        await ctx.send(recipient, message)

    def _help_message(self) -> str:
        return textwrap.dedent(
            """
            Supported requests:
              • `compress 500 usdc in <wallet>` – compress a token account
              • `transfer 25 usdc from <source> to <destination>` – send tokens
              • `swap 1 sol to usdc for <wallet>` – quote and execute a swap
              • `privacy report for <wallet>` – run a privacy review

            Ask for `help` anytime to revisit these examples.
            """
        ).strip()

    def _welcome_message(self) -> str:
        return (
            "Welcome. I coordinate between the privacy, execution, and monitoring agents. "
            "Describe what you need or ask for `help` to see available commands."
        )

    def _store_pending(self, ctx: Context, request_id: str, sender: str, category: str) -> None:
        pending = self._pending(ctx)
        pending[request_id] = {"sender": sender, "category": category}
        ctx.storage.set("pending", pending)

    def _pending(self, ctx: Context) -> Dict[str, Dict[str, str]]:
        return ctx.storage.get("pending", {})

    def _remove_pending(self, ctx: Context, request_id: str) -> None:
        pending = ctx.storage.get("pending", {})
        pending.pop(request_id, None)
        ctx.storage.set("pending", pending)

    def _extract_addresses(self, text: str, *, limit: int) -> list[str]:
        return ADDRESS_PATTERN.findall(text)[:limit]

    def _extract_amount(self, text: str) -> Optional[float]:
        match = AMOUNT_PATTERN.search(text.replace(",", ""))
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _token_from_text(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if "usdc" in lowered:
            return self.config.token.usdc_mint
        if "usdt" in lowered:
            return self.config.token.usdt_mint
        if "sol" in lowered:
            return self.config.token.sol_mint
        return None

    def _extract_threshold(self, text: str) -> int:
        match = re.search(r"(\d{2,3})\s*(?:score|risk|threshold)?", text)
        if match:
            try:
                value = int(match.group(1))
                return max(10, min(100, value))
            except ValueError:
                pass
        return self.config.monitoring.default_privacy_threshold

    @dataclass
    class SwapTokens:
        wallet: str
        input_token: str
        output_token: str

    def _extract_tokens_for_swap(self, text: str) -> Optional["CoordinatorService.SwapTokens"]:
        addresses = self._extract_addresses(text, limit=1)
        wallet = addresses[0] if addresses else ""
        lowered = text.lower()

        if "sol" in lowered and "usdc" in lowered:
            return self.SwapTokens(
                wallet=wallet,
                input_token=self.config.token.sol_mint,
                output_token=self.config.token.usdc_mint,
            )
        if "usdc" in lowered and "sol" in lowered:
            return self.SwapTokens(
                wallet=wallet,
                input_token=self.config.token.usdc_mint,
                output_token=self.config.token.sol_mint,
            )
        if "usdt" in lowered and "usdc" in lowered:
            return self.SwapTokens(
                wallet=wallet,
                input_token=self.config.token.usdt_mint,
                output_token=self.config.token.usdc_mint,
            )
        return None

    def _format_privacy_response(self, msg: PrivacyResponse) -> str:
        if not msg.success:
            return f"Privacy operation failed: {msg.result.get('error', 'unknown error')}."

        result = msg.result
        score = result.get("privacy_score")
        if score is None:
            score = result.get("score")
        breakdown = result.get("breakdown", {})
        lines = [
            "Privacy report complete.",
            f"Score: {score}/100" if score is not None else "Score unavailable.",
        ]
        if breakdown:
            parts = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
            lines.append(f"Breakdown: {parts}")
        recommendations = result.get("recommendations")
        if recommendations:
            lines.append("Recommendations:")
            lines.extend(f"- {item}" for item in recommendations[:5])
        return "\n".join(lines)

    def _format_execution_response(self, msg: ExecutionResponse) -> str:
        if not msg.success:
            return f"Transaction failed: {msg.result.get('error', 'unknown error')}."

        signature = msg.signature or msg.result.get("signature", "pending")
        details = msg.result.get("details", {})
        lines = [
            "Transaction confirmed.",
            f"Signature: {signature}",
        ]
        if msg.explorer_url:
            lines.append(f"Explorer: {msg.explorer_url}")
        if details:
            lines.append("Details:")
            lines.extend(f"- {key}: {value}" for key, value in details.items())
        return "\n".join(lines)

    def _format_monitoring_response(self, payload: Dict) -> str:
        if not payload:
            return "Monitoring response received but no data was provided."

        lines = [
            "Monitoring report ready.",
            f"Risk score: {payload.get('risk_score', 'n/a')}",
        ]
        if payload.get("alert"):
            lines.append("⚠️ Alert threshold reached.")
        metrics = payload.get("metrics") or {}
        if metrics:
            lines.append("Key metrics:")
            for key, value in metrics.items():
                lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        issues = payload.get("issues") or []
        if issues:
            lines.append("Findings:")
            lines.extend(f"- {item}" for item in issues)
        return "\n".join(lines)


    async def _get_agent_address(self, ctx: Context, agent_type: str) -> Optional[str]:
        """Get agent address - NO dynamic discovery to prevent wrong agent connections."""
        address_map = {
            "privacy": self.privacy_agent,
            "execution": self.execution_agent,
            "monitoring": self.monitoring_agent
        }

        address = address_map.get(agent_type)

        if address:
            ctx.logger.info(f"✅ Using {agent_type} agent: {address}")
        else:
            ctx.logger.error(f"❌ {agent_type} agent not configured in .env")
            ctx.logger.error(f"❌ Set {agent_type.upper()}_AGENT_ADDRESS in .env file")

        return address


service = CoordinatorService()

coordinator = Agent(
    name="coordinator",
    port=int(os.getenv("AGENT_PORT_COORDINATOR", 8000)),
    mailbox=True,
    seed=os.getenv("COORDINATOR_SEED", "coordinator_seed_default"),
    readme_path="README.md",
    endpoint=[f"http://127.0.0.1:{os.getenv('AGENT_PORT_COORDINATOR', 8000)}/submit"],
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)


@coordinator.on_event("startup")
async def on_startup(ctx: Context) -> None:
    await service.startup(ctx)


@protocol.on_message(ChatMessage)
async def on_chat_message(ctx: Context, sender: str, message: ChatMessage) -> None:
    await service.handle_chat_message(ctx, sender, message)


@protocol.on_message(ChatAcknowledgement)
async def on_chat_ack(ctx: Context, sender: str, message: ChatAcknowledgement) -> None:
    ctx.logger.debug("message %s acknowledged by %s", message.acknowledged_msg_id, sender)


@coordinator.on_message(PrivacyResponse)
async def on_privacy_response(ctx: Context, sender: str, message: PrivacyResponse) -> None:
    await service.receive_privacy_response(ctx, sender, message)


@coordinator.on_message(ExecutionResponse)
async def on_execution_response(ctx: Context, sender: str, message: ExecutionResponse) -> None:
    await service.receive_execution_response(ctx, sender, message)


@coordinator.on_message(MonitoringResponse)
async def on_monitoring_response(ctx: Context, sender: str, message: MonitoringResponse) -> None:
    await service.receive_monitoring_response(ctx, sender, message)


@coordinator.on_message(PrivacyAlert)
async def on_privacy_alert(ctx: Context, sender: str, message: PrivacyAlert) -> None:
    await service.receive_privacy_alert(ctx, sender, message)


coordinator.include(protocol)
