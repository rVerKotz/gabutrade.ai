"""
config.py — Centralized configuration for AI Trading Agent.

Reads settings from environment variables (.env file) with fallback defaults.
All other components import TradingConfig from here.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env dari project root
_PROJECT_ROOT = Path(__file__).parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass
class TradingConfig:
    """Centralized configuration — single source of truth for all modules."""

    # ── Mode ──────────────────────────────────────────────
    mode: str = field(
        default_factory=lambda: os.getenv("TRADING_MODE", "paper")
    )

    # ── Trading Pairs ────────────────────────────────────
    pairs: list[str] = field(
        default_factory=lambda: os.getenv(
            "TRADING_PAIRS", "BTCUSD,ETHUSD,SOLUSD"
        ).split(",")
    )

    # ── Timing ───────────────────────────────────────────
    poll_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL", "30"))
    )
    buffer_size: int = field(
        default_factory=lambda: int(os.getenv("BUFFER_SIZE", "100"))
    )

    # ── Risk Limits ──────────────────────────────────────
    max_daily_loss: float = field(
        default_factory=lambda: float(os.getenv("MAX_DAILY_LOSS", "500"))
    )
    max_position_size: float = field(
        default_factory=lambda: float(os.getenv("MAX_POSITION_SIZE", "0.01"))
    )
    max_daily_trades: int = field(
        default_factory=lambda: int(os.getenv("MAX_DAILY_TRADES", "20"))
    )
    trade_cooldown_seconds: int = field(
        default_factory=lambda: int(os.getenv("TRADE_COOLDOWN", "15"))
    )
    min_confidence: float = field(
        default_factory=lambda: float(os.getenv("MIN_CONFIDENCE", "0.55"))
    )
    take_profit_pct: float = field(
        default_factory=lambda: float(os.getenv("TAKE_PROFIT_PCT", "3.0"))
    )
    stop_loss_pct: float = field(
        default_factory=lambda: float(os.getenv("STOP_LOSS_PCT", "2.0"))
    )

    # ── OHLC Analysis ────────────────────────────────────
    ohlc_intervals: list[int] = field(
        default_factory=lambda: [
            int(x) for x in os.getenv("OHLC_INTERVALS", "15,60").split(",")
        ]
    )

    # ── NVIDIA NIM ───────────────────────────────────────
    nim_base_url: str = field(
        default_factory=lambda: os.getenv(
            "NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
    )
    nim_model: str = field(
        default_factory=lambda: os.getenv(
            "NIM_MODEL", "qwen/qwen3.5-122b-a10b"
        )
    )
    nim_api_key: str = field(
        default_factory=lambda: os.getenv("NVIDIA_API_KEY", "")
    )

    # ── Kraken CLI Path ──────────────────────────────────
    kraken_cli_path: str = field(
        default_factory=lambda: os.getenv(
            "KRAKEN_CLI_PATH",
            str(_PROJECT_ROOT / "bin" / "kraken"),
        )
    )

    # ── Derived ──────────────────────────────────────────
    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"

    def validate(self) -> list[str]:
        """Validate config, return list of error messages (empty = OK)."""
        errors = []
        if not self.nim_api_key:
            errors.append("NVIDIA_API_KEY is not set in .env")
        if self.mode not in ("paper", "live"):
            errors.append(f"Invalid TRADING_MODE: {self.mode}")
        if not self.pairs:
            errors.append("TRADING_PAIRS is empty")
        kraken = Path(self.kraken_cli_path)
        if not kraken.exists():
            errors.append(
                f"Kraken CLI not found at {self.kraken_cli_path}. "
                "Run: curl --proto '=https' --tlsv1.2 -LsSf "
                "https://github.com/krakenfx/kraken-cli/releases/latest/"
                "download/kraken-cli-installer.sh | sh"
            )
        return errors

    def summary(self) -> str:
        """Return human-readable summary for logging."""
        return (
            f"Mode: {self.mode.upper()} | "
            f"Pairs: {', '.join(self.pairs)} | "
            f"Interval: {self.poll_interval_seconds}s | "
            f"Model: {self.nim_model} | "
            f"Max Loss: ${self.max_daily_loss} | "
            f"Max Position: {self.max_position_size} | "
            f"Min Confidence: {self.min_confidence} | "
            f"TP: {self.take_profit_pct}% / SL: {self.stop_loss_pct}%"
        )
