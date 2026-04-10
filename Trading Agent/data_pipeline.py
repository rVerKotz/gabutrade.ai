"""
data_pipeline.py — Sub-Agent 2: Data Ingestion & Technical Analysis.

Responsibilities:
  - Fetch ticker data via MCP and maintain a rolling price buffer
  - Fetch OHLC candlestick data (15m, 1h) for richer trend visibility
  - Compute technical indicators (RSI, EMA, Bollinger Bands, VWAP)
  - Provide enriched market summaries for the Strategy LLM
"""

from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime, timezone
from typing import Any

from config import TradingConfig
from mcp_client import KrakenMCPClient

logger = logging.getLogger(__name__)


# ── Data Structures ──────────────────────────────────────

def make_price_snapshot(
    pair: str,
    ask: float,
    bid: float,
    last: float,
    volume_24h: float,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Create a standardized PriceSnapshot dict."""
    return {
        "pair": pair,
        "ask": ask,
        "bid": bid,
        "last": last,
        "volume_24h": volume_24h,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


# ── Pure-Python Technical Indicators ─────────────────────


def compute_ema(prices: list[float], period: int) -> list[float]:
    """
    Compute Exponential Moving Average.

    Args:
        prices: List of closing prices
        period: EMA period (e.g., 9, 21)

    Returns:
        List of EMA values (same length as prices, early values use SMA seed)
    """
    if len(prices) < period:
        return [sum(prices) / len(prices)] * len(prices) if prices else []

    multiplier = 2 / (period + 1)
    ema_values: list[float] = []

    # Seed with SMA of first `period` values
    sma = sum(prices[:period]) / period
    ema_values.extend([sma] * period)

    # Compute EMA for remaining values
    for i in range(period, len(prices)):
        ema = (prices[i] - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    return ema_values


def compute_rsi(prices: list[float], period: int = 14) -> float | None:
    """
    Compute Relative Strength Index (Wilder's smoothing).

    Args:
        prices: List of closing prices (needs at least period + 1 values)
        period: RSI period (default 14)

    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None

    # Compute price changes
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Initial average gain/loss (first `period` deltas)
    gains = [d if d > 0 else 0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0 for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Wilder's smoothing for remaining deltas
    for i in range(period, len(deltas)):
        delta = deltas[i]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def compute_bollinger_bands(
    prices: list[float], period: int = 20, num_std: float = 2.0
) -> dict[str, float] | None:
    """
    Compute Bollinger Bands.

    Returns:
        Dict with upper, middle (SMA), lower bands, and bandwidth, or None
    """
    if len(prices) < period:
        return None

    window = prices[-period:]
    sma = sum(window) / period
    variance = sum((p - sma) ** 2 for p in window) / period
    std_dev = math.sqrt(variance)

    upper = sma + (num_std * std_dev)
    lower = sma - (num_std * std_dev)

    return {
        "upper": round(upper, 2),
        "middle": round(sma, 2),
        "lower": round(lower, 2),
        "bandwidth": round((upper - lower) / sma * 100, 4) if sma > 0 else 0,
        "position": round(
            (prices[-1] - lower) / (upper - lower) * 100, 2
        ) if upper != lower else 50.0,
    }


def compute_vwap(candles: list[dict[str, Any]]) -> float | None:
    """
    Compute Volume-Weighted Average Price from OHLC candles.

    Each candle should have: high, low, close, volume
    """
    if not candles:
        return None

    total_tp_vol = 0.0
    total_vol = 0.0

    for c in candles:
        typical_price = (c["high"] + c["low"] + c["close"]) / 3
        vol = c.get("volume", 0)
        total_tp_vol += typical_price * vol
        total_vol += vol

    return round(total_tp_vol / total_vol, 2) if total_vol > 0 else None


def compute_price_momentum(prices: list[float], lookback: int = 5) -> float:
    """
    Compute simple price momentum as percentage change over lookback period.

    Returns percentage change (e.g., 1.5 means +1.5%).
    """
    if len(prices) < lookback + 1:
        return 0.0
    old = prices[-(lookback + 1)]
    new = prices[-1]
    return round((new - old) / old * 100, 4) if old > 0 else 0.0


# ── Data Pipeline Class ─────────────────────────────────


class DataPipeline:
    """
    Enriched data pipeline that combines ticker snapshots with OHLC
    candlestick analysis and technical indicators.

    Usage:
        pipeline = DataPipeline(mcp_client, config)
        snapshot = await pipeline.fetch_latest("BTCUSD")
        enriched = await pipeline.get_enriched_summary("BTCUSD")
    """

    def __init__(self, mcp_client: KrakenMCPClient, config: TradingConfig) -> None:
        self._mcp = mcp_client
        self._config = config
        # Buffer per pair: dict[pair_name, deque of PriceSnapshot]
        self._buffers: dict[str, deque[dict]] = {}
        # Cache OHLC data per pair per interval
        self._ohlc_cache: dict[str, dict[int, list[dict]]] = {}

    def _get_buffer(self, pair: str) -> deque[dict]:
        """Get or create a price buffer for a pair."""
        if pair not in self._buffers:
            self._buffers[pair] = deque(maxlen=self._config.buffer_size)
        return self._buffers[pair]

    # ── Data Fetching ─────────────────────────────────────

    async def fetch_latest(self, pair: str) -> dict[str, Any]:
        """
        Fetch the latest ticker price for a pair via MCP.

        Appends the result to the rolling buffer and returns the snapshot.
        """
        raw = await self._mcp.get_ticker(pair)

        # Parse ticker response from Kraken CLI
        snapshot = self._parse_ticker(pair, raw)

        # Store in buffer
        buf = self._get_buffer(pair)
        buf.append(snapshot)

        logger.info(
            "📊 %s: $%s (ask: $%s | bid: $%s) — buffer: %d/%d",
            pair,
            f"{snapshot['last']:,.2f}",
            f"{snapshot['ask']:,.2f}",
            f"{snapshot['bid']:,.2f}",
            len(buf),
            self._config.buffer_size,
        )

        return snapshot

    def _parse_ticker(self, pair: str, raw: dict | list) -> dict[str, Any]:
        """
        Parse raw ticker response into a standardized PriceSnapshot.

        Handles the Kraken JSON format:
        {
            "XXBTZUSD": {
                "a": ["84250.50000", "1", "1.000"],  // ask
                "b": ["84248.00000", "1", "1.000"],  // bid
                "c": ["84249.25000", "0.00100000"],  // last trade
                "v": ["1523.45", "2500.00"],          // volume [today, 24h]
            }
        }
        """
        try:
            if isinstance(raw, dict):
                if "a" in raw:
                    data = raw
                elif "raw" in raw:
                    return make_price_snapshot(pair, 0, 0, 0, 0)
                else:
                    first_key = next(iter(raw), None)
                    if first_key and isinstance(raw[first_key], dict):
                        data = raw[first_key]
                    else:
                        data = raw
            else:
                return make_price_snapshot(pair, 0, 0, 0, 0)

            ask = self._extract_price(data.get("a", 0))
            bid = self._extract_price(data.get("b", 0))
            last = self._extract_price(data.get("c", 0))
            volume = self._extract_price(data.get("v", [0, 0]), index=1)

            return make_price_snapshot(pair, ask, bid, last, volume)

        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.warning("Failed to parse ticker for %s: %s", pair, e)
            return make_price_snapshot(pair, 0, 0, 0, 0)

    @staticmethod
    def _extract_price(value: Any, index: int = 0) -> float:
        """Extract a price float from various Kraken response formats."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
        if isinstance(value, list) and len(value) > index:
            return float(value[index])
        return 0.0

    # ── OHLC Data Fetching ────────────────────────────────

    async def fetch_ohlc(
        self, pair: str, interval: int = 60
    ) -> list[dict[str, Any]]:
        """
        Fetch OHLC candlestick data and parse into structured dicts.

        Args:
            pair: Trading pair
            interval: Interval in minutes (15, 60, etc.)

        Returns:
            List of parsed candle dicts with keys:
            {time, open, high, low, close, vwap, volume, count}
        """
        raw = await self._mcp.get_ohlc(pair, interval)
        logger.debug("OHLC %s (%dm): received %s", pair, interval, type(raw).__name__)

        # Extract the candle array from the response
        candle_list: list = []
        if isinstance(raw, list):
            candle_list = raw
        elif isinstance(raw, dict):
            # Kraken returns {pair_name: [[...], ...], "last": ...}
            for key, val in raw.items():
                if key == "last" or key == "raw":
                    continue
                if isinstance(val, list):
                    candle_list = val
                    break

        # Parse each candle array into a dict
        parsed_candles = []
        for candle in candle_list:
            if isinstance(candle, list) and len(candle) >= 7:
                try:
                    parsed_candles.append({
                        "time": int(candle[0]) if candle[0] else 0,
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "vwap": float(candle[5]),
                        "volume": float(candle[6]),
                        "count": int(candle[7]) if len(candle) > 7 else 0,
                    })
                except (ValueError, TypeError):
                    continue

        # Cache the result
        if pair not in self._ohlc_cache:
            self._ohlc_cache[pair] = {}
        self._ohlc_cache[pair][interval] = parsed_candles

        logger.info(
            "🕯️  OHLC %s (%dm): %d candles fetched",
            pair, interval, len(parsed_candles),
        )

        return parsed_candles

    async def fetch_all_ohlc(self, pair: str) -> dict[int, list[dict[str, Any]]]:
        """
        Fetch OHLC data for all configured intervals.

        Returns:
            Dict mapping interval (minutes) to list of candle dicts
        """
        result = {}
        for interval in self._config.ohlc_intervals:
            try:
                candles = await self.fetch_ohlc(pair, interval)
                result[interval] = candles
            except Exception as e:
                logger.warning(
                    "⚠️  Failed to fetch OHLC %s (%dm): %s", pair, interval, e
                )
                result[interval] = []
        return result

    # ── Technical Indicator Computation ───────────────────

    def compute_indicators(
        self, candles: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Compute all technical indicators from a list of OHLC candles.

        Returns a dict of indicator values suitable for LLM prompt injection.
        """
        if not candles:
            return {"error": "no_candle_data"}

        closes = [c["close"] for c in candles]

        # RSI (14-period)
        rsi = compute_rsi(closes, period=14)

        # EMA crossover (9 vs 21)
        ema_9 = compute_ema(closes, 9)
        ema_21 = compute_ema(closes, 21)

        ema_9_current = ema_9[-1] if ema_9 else None
        ema_21_current = ema_21[-1] if ema_21 else None
        ema_9_prev = ema_9[-2] if len(ema_9) > 1 else None
        ema_21_prev = ema_21[-2] if len(ema_21) > 1 else None

        # Detect crossover
        crossover = "NONE"
        if (ema_9_current and ema_21_current and
                ema_9_prev and ema_21_prev):
            if ema_9_prev <= ema_21_prev and ema_9_current > ema_21_current:
                crossover = "BULLISH"  # Golden cross
            elif ema_9_prev >= ema_21_prev and ema_9_current < ema_21_current:
                crossover = "BEARISH"  # Death cross

        # Bollinger Bands (20-period, 2σ)
        bollinger = compute_bollinger_bands(closes, period=20, num_std=2.0)

        # VWAP
        vwap = compute_vwap(candles)

        # Momentum (price change over last 5 candles)
        momentum_5 = compute_price_momentum(closes, lookback=5)
        momentum_10 = compute_price_momentum(closes, lookback=10)

        # Trend summary
        trend = "UNKNOWN"
        if ema_9_current and ema_21_current:
            spread_pct = (ema_9_current - ema_21_current) / ema_21_current * 100
            if spread_pct > 0.1:
                trend = "BULLISH"
            elif spread_pct < -0.1:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"

        return {
            "rsi": rsi,
            "ema_9": round(ema_9_current, 2) if ema_9_current else None,
            "ema_21": round(ema_21_current, 2) if ema_21_current else None,
            "ema_crossover": crossover,
            "bollinger": bollinger,
            "vwap": vwap,
            "momentum_5_candles": momentum_5,
            "momentum_10_candles": momentum_10,
            "trend": trend,
            "last_close": closes[-1] if closes else None,
            "candle_count": len(candles),
        }

    # ── Buffer Access ─────────────────────────────────────

    def get_buffer(self, pair: str) -> list[dict[str, Any]]:
        """Return a copy of the price buffer for a pair."""
        return list(self._get_buffer(pair))

    def get_latest(self, pair: str) -> dict[str, Any] | None:
        """Return the latest snapshot, or None if buffer is empty."""
        buf = self._get_buffer(pair)
        return buf[-1] if buf else None

    # ── Summary & Statistics ──────────────────────────────

    def get_summary(self, pair: str) -> dict[str, Any]:
        """
        Compute summary statistics from the ticker buffer.

        Returns:
            Dict with: current_price, price_change_pct, avg_price_last_10,
            avg_price_last_50, high, low, trend_direction, buffer_count
        """
        buf = self._get_buffer(pair)

        if not buf:
            return {
                "pair": pair,
                "current_price": 0,
                "price_change_pct": 0,
                "avg_price_last_10": 0,
                "avg_price_last_50": 0,
                "high": 0,
                "low": 0,
                "trend_direction": "UNKNOWN",
                "buffer_count": 0,
            }

        prices = [s["last"] for s in buf if s["last"] > 0]

        if not prices:
            return {
                "pair": pair,
                "current_price": 0,
                "price_change_pct": 0,
                "avg_price_last_10": 0,
                "avg_price_last_50": 0,
                "high": 0,
                "low": 0,
                "trend_direction": "UNKNOWN",
                "buffer_count": len(buf),
            }

        current = prices[-1]
        high = max(prices)
        low = min(prices)

        last_10 = prices[-10:] if len(prices) >= 10 else prices
        last_50 = prices[-50:] if len(prices) >= 50 else prices
        avg_10 = sum(last_10) / len(last_10)
        avg_50 = sum(last_50) / len(last_50)

        first = prices[0]
        change_pct = ((current - first) / first * 100) if first > 0 else 0

        if len(prices) < 3:
            trend = "INSUFFICIENT_DATA"
        elif avg_10 > avg_50 * 1.001:
            trend = "UP"
        elif avg_10 < avg_50 * 0.999:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"

        return {
            "pair": pair,
            "current_price": current,
            "price_change_pct": round(change_pct, 4),
            "avg_price_last_10": round(avg_10, 2),
            "avg_price_last_50": round(avg_50, 2),
            "high": high,
            "low": low,
            "trend_direction": trend,
            "buffer_count": len(buf),
        }

    async def get_enriched_summary(self, pair: str) -> dict[str, Any]:
        """
        Generate a comprehensive market analysis combining ticker data,
        OHLC candles, and technical indicators.

        This is the primary data source for the Strategy LLM.

        Returns:
            Enriched summary dict with all available market intelligence
        """
        # Base ticker summary
        summary = self.get_summary(pair)

        # Fetch OHLC data for all configured intervals
        ohlc_data = await self.fetch_all_ohlc(pair)

        # Compute indicators per interval
        indicators_by_interval: dict[str, dict[str, Any]] = {}
        for interval, candles in ohlc_data.items():
            if candles:
                indicators = self.compute_indicators(candles)
                indicators_by_interval[f"{interval}m"] = indicators

        summary["indicators"] = indicators_by_interval

        # Add formatted OHLC candle summaries (last N candles per interval)
        ohlc_summaries: dict[str, list[dict]] = {}
        for interval, candles in ohlc_data.items():
            # Keep last 20 candles for 15m, last 12 for 1h
            max_candles = 20 if interval <= 15 else 12
            recent = candles[-max_candles:] if len(candles) > max_candles else candles
            ohlc_summaries[f"{interval}m"] = [
                {
                    "time": c["time"],
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": round(c["volume"], 4),
                }
                for c in recent
            ]
        summary["ohlc"] = ohlc_summaries

        # Aggregate trend signal across intervals
        trend_signals = []
        for key, ind in indicators_by_interval.items():
            if ind.get("trend"):
                trend_signals.append(ind["trend"])

        if trend_signals:
            bullish = trend_signals.count("BULLISH")
            bearish = trend_signals.count("BEARISH")
            if bullish > bearish:
                summary["multi_tf_trend"] = "BULLISH"
            elif bearish > bullish:
                summary["multi_tf_trend"] = "BEARISH"
            else:
                summary["multi_tf_trend"] = "MIXED"
        else:
            summary["multi_tf_trend"] = "UNKNOWN"

        return summary

    def format_prices_for_llm(self, pair: str, max_entries: int = 20) -> str:
        """
        Format recent prices as text for the LLM prompt.

        Returns:
            A string table of recent prices ready for prompt injection.
        """
        buf = self._get_buffer(pair)
        recent = list(buf)[-max_entries:]

        if not recent:
            return f"No price data available for {pair}."

        lines = [f"Recent {pair} prices (newest last):"]
        lines.append("Timestamp | Last | Bid | Ask | Volume 24h")
        lines.append("-" * 65)

        for snap in recent:
            ts = snap["timestamp"][:19] if snap["timestamp"] else "N/A"
            lines.append(
                f"{ts} | ${snap['last']:>10,.2f} | "
                f"${snap['bid']:>10,.2f} | ${snap['ask']:>10,.2f} | "
                f"{snap['volume_24h']:>10,.2f}"
            )

        return "\n".join(lines)

