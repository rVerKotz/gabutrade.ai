"""
position_tracker.py — Position Manager & Auto TP/SL Engine.

Responsibilities:
  Track open positions per trading pair, compute unrealized P&L,
  and determine when automatic take-profit or stop-loss exits should trigger.

Design:
  - In-memory state (resets on restart — acceptable for hackathon)
  - One position per pair (no stacking)
  - Supports LONG positions only (paper trading limitation)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import TradingConfig

logger = logging.getLogger(__name__)


# ── Position Data ─────────────────────────────────────────


def make_position(
    pair: str,
    side: str,
    entry_price: float,
    volume: float,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Create a standardized position dict."""
    return {
        "pair": pair,
        "side": side.upper(),  # "LONG" or "SHORT"
        "entry_price": entry_price,
        "volume": volume,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


# ── Position Tracker Class ────────────────────────────────


class PositionTracker:
    """
    In-memory position manager that tracks open trades per pair.

    Features:
      - Open / close positions
      - Compute unrealized P&L for each position
      - Auto take-profit and stop-loss threshold checks
      - Portfolio summary for LLM context injection

    Usage:
        tracker = PositionTracker(config)
        tracker.open_position("BTCUSD", "LONG", 84000.0, 0.05)
        pnl = tracker.get_unrealized_pnl("BTCUSD", 85000.0)
        exit_info = tracker.should_exit("BTCUSD", 85000.0)
        if exit_info["should_exit"]:
            realized = tracker.close_position("BTCUSD", 85000.0)
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config
        self._positions: dict[str, dict[str, Any]] = {}
        self._realized_pnl: float = 0.0
        self._trade_history: list[dict[str, Any]] = []

        logger.info(
            "Position Tracker initialized — TP: %.1f%%, SL: %.1f%%",
            config.take_profit_pct,
            config.stop_loss_pct,
        )

    # ── Position Management ───────────────────────────────

    def open_position(
        self, pair: str, side: str, entry_price: float, volume: float
    ) -> dict[str, Any]:
        """
        Open a new position for a pair.

        If a position already exists for this pair, it is replaced
        (one position per pair policy).

        Args:
            pair: Trading pair (e.g. "BTCUSD")
            side: "LONG" or "SHORT"
            entry_price: Price at which the position was entered
            volume: Size of the position in base currency

        Returns:
            The created position dict
        """
        if pair in self._positions:
            logger.warning(
                "⚠️  Replacing existing %s position for %s",
                self._positions[pair]["side"],
                pair,
            )

        position = make_position(pair, side, entry_price, volume)
        self._positions[pair] = position

        logger.info(
            "📈 Opened %s %s: %.6f @ $%.2f",
            side.upper(), pair, volume, entry_price,
        )
        return position

    def close_position(self, pair: str, exit_price: float) -> dict[str, Any]:
        """
        Close an open position and compute realized P&L.

        Args:
            pair: Trading pair to close
            exit_price: Price at which the position is being closed

        Returns:
            Dict with realized P&L details

        Raises:
            KeyError: If no position exists for this pair
        """
        if pair not in self._positions:
            raise KeyError(f"No open position for {pair}")

        pos = self._positions.pop(pair)
        pnl = self._compute_pnl(pos, exit_price)
        pnl_pct = (pnl / (pos["entry_price"] * pos["volume"])) * 100

        self._realized_pnl += pnl

        trade_record = {
            "pair": pair,
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "volume": pos["volume"],
            "pnl": pnl,
            "pnl_pct": round(pnl_pct, 4),
            "entry_time": pos["timestamp"],
            "exit_time": datetime.now(timezone.utc).isoformat(),
        }
        self._trade_history.append(trade_record)

        emoji = "💰" if pnl >= 0 else "💸"
        logger.info(
            "%s Closed %s %s: %.6f @ $%.2f → $%.2f | P&L: $%+.2f (%.2f%%)",
            emoji, pos["side"], pair, pos["volume"],
            pos["entry_price"], exit_price, pnl, pnl_pct,
        )

        return trade_record

    # ── P&L Computation ───────────────────────────────────

    @staticmethod
    def _compute_pnl(position: dict[str, Any], current_price: float) -> float:
        """Compute P&L for a position at a given price."""
        entry = position["entry_price"]
        volume = position["volume"]
        side = position["side"]

        if side == "LONG":
            return (current_price - entry) * volume
        else:  # SHORT
            return (entry - current_price) * volume

    def get_unrealized_pnl(self, pair: str, current_price: float) -> float:
        """
        Get unrealized P&L for a specific pair.

        Returns 0.0 if no position exists.
        """
        if pair not in self._positions:
            return 0.0
        return self._compute_pnl(self._positions[pair], current_price)

    def get_unrealized_pnl_pct(self, pair: str, current_price: float) -> float:
        """Get unrealized P&L as a percentage of entry value."""
        if pair not in self._positions:
            return 0.0
        pos = self._positions[pair]
        pnl = self._compute_pnl(pos, current_price)
        entry_value = pos["entry_price"] * pos["volume"]
        return (pnl / entry_value * 100) if entry_value > 0 else 0.0

    # ── Auto Exit Logic ───────────────────────────────────

    def should_exit(
        self, pair: str, current_price: float
    ) -> dict[str, Any]:
        """
        Check if an open position should be auto-closed.

        Evaluates take-profit and stop-loss thresholds from config.

        Returns:
            {
                "should_exit": bool,
                "reason": str,
                "action": "SELL" | "BUY" | None,
                "unrealized_pnl": float,
                "unrealized_pnl_pct": float,
            }
        """
        if pair not in self._positions:
            return {
                "should_exit": False,
                "reason": "no_position",
                "action": None,
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
            }

        pos = self._positions[pair]
        pnl = self._compute_pnl(pos, current_price)
        entry_value = pos["entry_price"] * pos["volume"]
        pnl_pct = (pnl / entry_value * 100) if entry_value > 0 else 0.0

        # Determine exit action (opposite of position side)
        exit_action = "SELL" if pos["side"] == "LONG" else "BUY"

        # Take-profit check
        if pnl_pct >= self._config.take_profit_pct:
            return {
                "should_exit": True,
                "reason": f"Take-profit triggered: {pnl_pct:+.2f}% >= {self._config.take_profit_pct}%",
                "action": exit_action,
                "unrealized_pnl": pnl,
                "unrealized_pnl_pct": pnl_pct,
            }

        # Stop-loss check
        if pnl_pct <= -self._config.stop_loss_pct:
            return {
                "should_exit": True,
                "reason": f"Stop-loss triggered: {pnl_pct:+.2f}% <= -{self._config.stop_loss_pct}%",
                "action": exit_action,
                "unrealized_pnl": pnl,
                "unrealized_pnl_pct": pnl_pct,
            }

        return {
            "should_exit": False,
            "reason": f"Within limits: {pnl_pct:+.2f}% (TP: {self._config.take_profit_pct}%, SL: {self._config.stop_loss_pct}%)",
            "action": None,
            "unrealized_pnl": pnl,
            "unrealized_pnl_pct": pnl_pct,
        }

    # ── Query Methods ─────────────────────────────────────

    def get_position(self, pair: str) -> dict[str, Any] | None:
        """Get current position for a pair, or None if flat."""
        return self._positions.get(pair)

    def has_position(self, pair: str) -> bool:
        """Check if there's an open position for a pair."""
        return pair in self._positions

    def get_position_side(self, pair: str) -> str:
        """Get position side: 'LONG', 'SHORT', or 'FLAT'."""
        pos = self._positions.get(pair)
        return pos["side"] if pos else "FLAT"

    @property
    def realized_pnl(self) -> float:
        """Total realized P&L across all closed trades."""
        return self._realized_pnl

    @property
    def trade_count(self) -> int:
        """Total number of completed round-trip trades."""
        return len(self._trade_history)

    @property
    def open_positions(self) -> dict[str, dict[str, Any]]:
        """All currently open positions."""
        return dict(self._positions)

    # ── Portfolio Summary (for LLM context) ───────────────

    def get_portfolio_summary(
        self, current_prices: dict[str, float] | None = None
    ) -> dict[str, Any]:
        """
        Generate a portfolio summary suitable for LLM context injection.

        Args:
            current_prices: Dict of {pair: current_price} for unrealized P&L calc

        Returns:
            Summary dict with positions, P&L, trade history stats
        """
        current_prices = current_prices or {}

        positions_summary = []
        total_unrealized = 0.0

        for pair, pos in self._positions.items():
            price = current_prices.get(pair, pos["entry_price"])
            pnl = self._compute_pnl(pos, price)
            pnl_pct = self.get_unrealized_pnl_pct(pair, price)
            total_unrealized += pnl

            positions_summary.append({
                "pair": pair,
                "side": pos["side"],
                "entry_price": pos["entry_price"],
                "current_price": price,
                "volume": pos["volume"],
                "unrealized_pnl": round(pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 4),
            })

        # Recent trade history (last 10)
        recent_trades = self._trade_history[-10:]
        win_count = sum(1 for t in self._trade_history if t["pnl"] > 0)
        loss_count = sum(1 for t in self._trade_history if t["pnl"] < 0)

        return {
            "open_positions": positions_summary,
            "open_position_count": len(self._positions),
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_realized_pnl": round(self._realized_pnl, 2),
            "total_trades": len(self._trade_history),
            "wins": win_count,
            "losses": loss_count,
            "win_rate": (
                round(win_count / len(self._trade_history) * 100, 1)
                if self._trade_history else 0.0
            ),
            "recent_trades": recent_trades,
        }

    def format_for_llm(
        self, pair: str, current_price: float
    ) -> str:
        """
        Format position info for a specific pair as text for LLM prompt.

        Returns a human-readable summary string.
        """
        pos = self._positions.get(pair)

        if not pos:
            return f"Position: FLAT (no open position for {pair})"

        pnl = self._compute_pnl(pos, current_price)
        pnl_pct = self.get_unrealized_pnl_pct(pair, current_price)

        return (
            f"Position: {pos['side']} {pos['volume']:.6f} @ ${pos['entry_price']:,.2f}\n"
            f"Current Price: ${current_price:,.2f}\n"
            f"Unrealized P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            f"TP Target: {self._config.take_profit_pct}% | SL Limit: {self._config.stop_loss_pct}%"
        )
