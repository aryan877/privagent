from __future__ import annotations

import subprocess
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings


class BlockchainSettings(BaseSettings):
    helius_rpc_url: str = ""
    solana_rpc_url: Optional[str] = None
    solana_network: str = "mainnet-beta"
    backup_rpc_urls: List[str] = []

    class Config:
        env_prefix = "BLOCKCHAIN_"
        case_sensitive = False


class TokenSettings(BaseSettings):
    usdc_mint: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    usdt_mint: str = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
    sol_mint: str = "So11111111111111111111111111111111111111112"

    usdc_decimals: int = 6
    usdt_decimals: int = 6
    sol_decimals: int = 9

    default_compression_amount: float = 100.0
    default_swap_amount: float = 1.0

    @field_validator("usdc_mint", "usdt_mint", "sol_mint")
    @classmethod
    def _validate_mint(cls, value: str) -> str:
        if not 32 <= len(value) <= 44:
            raise ValueError(f"Invalid mint address length: {value}")
        return value

    class Config:
        env_prefix = "TOKEN_"
        case_sensitive = False


class CLISettings(BaseSettings):
    light_cli_path: str = "light"
    light_cli_version: Optional[str] = None

    allowed_cli_commands: List[str] = ["light", "solana"]
    cli_timeout_seconds: int = 30
    max_cli_executions_per_hour: int = 100
    enable_cli_sandbox: bool = True

    require_cli_verification: bool = True
    fallback_to_api: bool = True

    class Config:
        env_prefix = "CLI_"
        case_sensitive = False


class PrivacySettings(BaseSettings):
    agent_port: int = 8001
    agent_seed: str = "privacy_seed_default"

    privacy_levels: List[str] = ["standard", "max", "stealth"]
    default_privacy_level: str = "standard"

    enable_metta_engine: bool = True
    metta_confidence_threshold: float = 0.7

    compression_weight: float = 0.4
    mixing_weight: float = 0.3
    timing_weight: float = 0.2
    reuse_weight: float = 0.1

    @field_validator("default_privacy_level")
    @classmethod
    def _validate_level(cls, value: str, info: ValidationInfo) -> str:
        levels = info.data.get("privacy_levels", ["standard", "max", "stealth"])
        if value not in levels:
            raise ValueError(f"Unsupported privacy level '{value}'")
        return value

    class Config:
        env_prefix = "PRIVACY_"
        case_sensitive = False


class SecuritySettings(BaseSettings):
    enable_rate_limiting: bool = True
    enable_circuit_breaker: bool = True

    rate_limit_window: int = 3600
    max_requests_per_window: int = 1000

    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60

    use_hardware_wallet: bool = False
    key_management_service: Optional[str] = None

    class Config:
        env_prefix = "SECURITY_"
        case_sensitive = False


class MonitoringSettings(BaseSettings):
    agent_port: int = 8003
    agent_seed: str = "monitoring_seed_default"

    mev_detection_enabled: bool = True
    mev_confidence_threshold: float = 0.6
    known_mev_programs: List[str] = [
        "vpeNALzrCEkkgqk4mRoDgqj6b98Fcs81cDnEFiN5ZeQ",
        "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
        "whirLbMiicVpio4qvU8MvDmbU4EwBQdpMvFPKV3PBV",
        "CAMMCzo5YL8w4VFF8KVHpbKwEyj5EYF4M7BjwGATGFjA",
    ]

    default_privacy_threshold: int = 70
    alert_cooldown_minutes: int = 5

    class Config:
        env_prefix = "MONITORING_"
        case_sensitive = False


class ExecutionSettings(BaseSettings):
    agent_port: int = 8002
    agent_seed: str = "execution_seed_default"

    jupiter_lite_url: str = "https://quote-api.jup.ag"
    jupiter_pro_url: str = "https://api.jup.ag"
    jupiter_ultra_url: str = "https://api.jup.ag/ultra"
    jupiter_api_key: Optional[str] = None
    jupiter_timeout_seconds: int = 10
    jupiter_max_retries: int = 3

    jupiter_lite_rpm: int = 60
    jupiter_pro_i_rpm: int = 600
    jupiter_pro_ii_rpm: int = 3000
    jupiter_pro_iii_rpm: int = 6000
    jupiter_pro_iv_rpm: int = 30000
    jupiter_ultra_base_rpm: int = 300

    max_priority_fee: int = 1_000_000
    default_slippage_bps: int = 50
    max_accounts: int = 64

    transfer_rate_limit: float = 10.0
    swap_rate_limit: float = 5.0

    default_routing_preference: str = "best"
    enable_dynamic_slippage: bool = True
    restrict_intermediate_tokens: bool = False

    class Config:
        env_prefix = "EXECUTION_"
        case_sensitive = False


class LLMSettings(BaseSettings):
    # LLM Provider Configuration
    provider: str = "openai"  # openai, asi1, anthropic
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    # Model Configuration
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout_seconds: int = 30

    # ASI:One specific settings
    asi1_base_url: str = "https://api.asi1.ai/v1"
    asi1_model: str = "asi1-mini"

    # Routing Configuration
    max_retries: int = 3

    class Config:
        env_prefix = "LLM_"
        case_sensitive = False


class Settings:
    def __init__(self):
        self.blockchain = BlockchainSettings()
        self.token = TokenSettings()
        self.cli = CLISettings()
        self.privacy = PrivacySettings()
        self.security = SecuritySettings()
        self.monitoring = MonitoringSettings()
        self.execution = ExecutionSettings()
        self.llm = LLMSettings()

    def validate(self) -> List[str]:
        errors: List[str] = []

        if not self.blockchain.helius_rpc_url:
            errors.append("Missing BLOCKCHAIN_HELIUS_RPC_URL")

        if not self.llm.api_key:
            errors.append(
                "Missing LLM_API_KEY. LLM-based routing is required for agent coordination."
            )

        if self.cli.require_cli_verification:
            try:
                result = subprocess.run(
                    [self.cli.light_cli_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode != 0:
                    errors.append(
                        f"Failed to execute '{self.cli.light_cli_path} --version'. "
                        f"Configure CLI_LIGHT_CLI_PATH or disable CLI_REQUIRE_CLI_VERIFICATION."
                    )
            except FileNotFoundError:
                if not self.cli.fallback_to_api:
                    errors.append(
                        f"Light CLI not found at '{self.cli.light_cli_path}' "
                        "and CLI_FALLBACK_TO_API is disabled."
                    )
            except subprocess.SubprocessError as exc:
                errors.append(f"Light CLI verification failed: {exc}")

        return errors

    def rpc_url(self) -> str:
        if self.blockchain.helius_rpc_url:
            return self.blockchain.helius_rpc_url
        if self.blockchain.solana_rpc_url:
            return self.blockchain.solana_rpc_url
        return "https://api.mainnet-beta.solana.com"


@lru_cache()
def get_config() -> Settings:
    settings = Settings()
    config_errors = settings.validate()
    if config_errors:
        raise RuntimeError(f"Configuration errors: {config_errors}")
    return settings


config = get_config()
