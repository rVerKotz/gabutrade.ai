"""
risk_guard.py — Sub-Agent 4: Risk Guardian.

Responsibilities:
  Pure filter function that receives the AI strategy output JSON
  and blocks trades that exceed risk limits.

Risk rules:
  1. Daily loss limit (max daily loss)
  2. Maximum position size (max position size)
  3. Minimum confidence threshold (from config, default 0.55)
  4. Cooldown between trades
  5. Maximum daily trade count
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from config import TradingConfig

logger = logging.getLogger(__name__)


# ── Data Structures ──────────────────────────────────────

def make_risk_verdict(
    approved: bool,
    original_signal: dict[str, Any],
    adjusted_volume: str = "0",
    rejection_reason: str | None = None,
    daily_pnl_remaining: float = 0.0,
    position_utilization: float = 0.0,
) -> dict[str, Any]:
    """Create a standardized RiskVerdict dict."""
    return {
        "approved": approved,
        "original_signal": original_signal,
        "adjusted_volume": adjusted_volume,
        "rejection_reason": rejection_reason,
        "daily_pnl_remaining": daily_pnl_remaining,
        "position_utilization": position_utilization,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Risk Guard Class ─────────────────────────────────────


class RiskGuard:
    """
    Risk guardian that validates every trading decision
    before sending it to MCP for execution.

    All functions are deterministic — no external side effects.
    Internal state only tracks daily P&L and trade count.

    Usage:
        guard = RiskGuard(config)
        verdict = guard.evaluate(signal)
        if verdict["approved"]:
            # execute trade
            guard.record_trade(result)
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config

        # Daily state — resets each day
        self._daily_pnl: float = 0.0
        self._daily_trade_count: int = 0
        self._last_reset_date: date = date.today()

        # Cooldown tracking
        self._last_trade_time: datetime | None = None

        logger.info(
            "Risk Guard initialized — max loss: $%.2f, max position: %.4f, "
            "min confidence: %.2f, max trades/day: %d, cooldown: %ds",
            config.max_daily_loss,
            config.max_position_size,
            config.min_confidence,
            config.max_daily_trades,
            config.trade_cooldown_seconds,
        )

    # ── Daily Reset ───────────────────────────────────────

    def _check_daily_reset(self) -> None:
        """Reset counters if a new day has started."""
        today = date.today()
        if today != self._last_reset_date:
            old_pnl = self._daily_pnl
            old_count = self._daily_trade_count
            self._daily_pnl = 0.0
            self._daily_trade_count = 0
            self._last_reset_date = today
            logger.info(
                "🔄 Daily reset — yesterday P&L: $%.2f, trades: %d",
                old_pnl,
                old_count,
            )

    # ── Core Evaluation ───────────────────────────────────

    def evaluate(self, signal: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate a TradeSignal and return a RiskVerdict.

        Runs all risk rules sequentially.
        Signals with action "HOLD" are always approved without execution.

        Args:
            signal: TradeSignal dict from StrategyLLM

        Returns:
            RiskVerdict dict
        """
        self._check_daily_reset()

        action = signal.get("action", "HOLD").upper()
        volume = signal.get("volume", "0")
        confidence = signal.get("confidence", 0.0)
        pair = signal.get("pair", "UNKNOWN")

        remaining_pnl = self._config.max_daily_loss + self._daily_pnl

        # ── Rule 0: HOLD passthrough ──
        if action == "HOLD":
            logger.info(
                "⏸️  [%s] HOLD — confidence: %.2f | %s",
                pair, confidence, signal.get("reasoning", ""),
            )
            return make_risk_verdict(
                approved=True,
                original_signal=signal,
                adjusted_volume="0",
                daily_pnl_remaining=remaining_pnl,
            )

        # ── Rule 1: Daily loss check ──
        if self._daily_pnl <= -self._config.max_daily_loss:
            reason = (
                f"Daily loss limit reached: ${self._daily_pnl:.2f} "
                f"(max: -${self._config.max_daily_loss:.2f})"
            )
            logger.warning("🛑 [%s] BLOCKED — %s", pair, reason)
            return make_risk_verdict(
                approved=False,
                original_signal=signal,
                rejection_reason=reason,
                daily_pnl_remaining=0,
            )

        # ── Rule 2: Confidence threshold (from config) ──
        if confidence < self._config.min_confidence:
            reason = (
                f"Confidence too low: {confidence:.2f} "
                f"(min: {self._config.min_confidence:.2f})"
            )
            logger.info("⏭️  [%s] SKIPPED — %s", pair, reason)
            return make_risk_verdict(
                approved=False,
                original_signal=signal,
                rejection_reason=reason,
                daily_pnl_remaining=remaining_pnl,
            )

        # ── Rule 3: Position size check ──
        try:
            vol_float = float(volume)
        except ValueError:
            reason = f"Invalid volume: {volume}"
            logger.warning("🛑 [%s] BLOCKED — %s", pair, reason)
            return make_risk_verdict(
                approved=False,
                original_signal=signal,
                rejection_reason=reason,
                daily_pnl_remaining=remaining_pnl,
            )

        adjusted_volume = volume
        if vol_float > self._config.max_position_size:
            adjusted_volume = str(self._config.max_position_size)
            logger.info(
                "📏 [%s] Volume adjusted: %s → %s (max: %s)",
                pair, volume, adjusted_volume, self._config.max_position_size,
            )
        elif vol_float <= 0:
            reason = f"Volume is zero or negative: {volume}"
            logger.warning("🛑 [%s] BLOCKED — %s", pair, reason)
            return make_risk_verdict(
                approved=False,
                original_signal=signal,
                rejection_reason=reason,
                daily_pnl_remaining=remaining_pnl,
            )

        # ── Rule 4: Cooldown check ──
        if self._last_trade_time is not None:
            now = datetime.now(timezone.utc)
            elapsed = (now - self._last_trade_time).total_seconds()
            if elapsed < self._config.trade_cooldown_seconds:
                remaining = self._config.trade_cooldown_seconds - elapsed
                reason = f"Cooldown active: {remaining:.0f}s remaining"
                logger.info("⏳ [%s] COOLDOWN — %s", pair, reason)
                return make_risk_verdict(
                    approved=False,
                    original_signal=signal,
                    rejection_reason=reason,
                    daily_pnl_remaining=remaining_pnl,
                )

        # ── Rule 5: Max daily trades ──
        if self._daily_trade_count >= self._config.max_daily_trades:
            reason = (
                f"Max daily trades reached: {self._daily_trade_count} "
                f"(max: {self._config.max_daily_trades})"
            )
            logger.warning("🛑 [%s] BLOCKED — %s", pair, reason)
            return make_risk_verdict(
                approved=False,
                original_signal=signal,
                rejection_reason=reason,
                daily_pnl_remaining=remaining_pnl,
            )

        # ── All checks passed ──
        position_util = vol_float / self._config.max_position_size
        logger.info(
            "✅ [%s] APPROVED — %s %s vol=%s confidence=%.2f",
            pair, action, signal.get("order_type", "market"),
            adjusted_volume, confidence,
        )

        return make_risk_verdict(
            approved=True,
            original_signal=signal,
            adjusted_volume=adjusted_volume,
            daily_pnl_remaining=remaining_pnl,
            position_utilization=min(position_util, 1.0),
        )

    # ── Trade Recording ───────────────────────────────────

    def record_trade(self, execution_result: dict[str, Any]) -> None:
        """
        Record a trade execution for daily tracking.

        Args:
            execution_result: ExecutionResult dict from mcp_client
        """
        self._daily_trade_count += 1
        self._last_trade_time = datetime.now(timezone.utc)

        logger.info(
            "📝 Trade recorded — today: %d trades, P&L: $%.2f",
            self._daily_trade_count,
            self._daily_pnl,
        )

    def record_pnl(self, pnl_amount: float) -> None:
        """
        Record P&L from a closed trade.

        Args:
            pnl_amount: Profit (positive) or loss (negative)
        """
        self._daily_pnl += pnl_amount
        logger.info(
            "💰 P&L update: %+.2f → daily total: $%.2f",
            pnl_amount,
            self._daily_pnl,
        )

    # ── Status ────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return current risk state for monitoring."""
        remaining = self._config.max_daily_loss + self._daily_pnl
        return {
            "daily_pnl": self._daily_pnl,
            "daily_pnl_remaining": max(remaining, 0),
            "daily_trade_count": self._daily_trade_count,
            "max_daily_trades": self._config.max_daily_trades,
            "max_daily_loss": self._config.max_daily_loss,
            "max_position_size": self._config.max_position_size,
            "min_confidence": self._config.min_confidence,
            "last_trade_time": (
                self._last_trade_time.isoformat()
                if self._last_trade_time
                else None
            ),
            "cooldown_seconds": self._config.trade_cooldown_seconds,
            "last_reset_date": self._last_reset_date.isoformat(),
        }

    def format_status(self) -> str:
        """Format status as a readable string for logging."""
        s = self.get_status()
        return (
            f"P&L: ${s['daily_pnl']:+.2f} "
            f"(${s['daily_pnl_remaining']:.2f} remaining) | "
            f"Trades: {s['daily_trade_count']}/{s['max_daily_trades']}"
        )
