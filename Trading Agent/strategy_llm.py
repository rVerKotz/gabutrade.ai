"""
strategy_llm.py — Sub-Agent 3: AI Strategy Brain (NVIDIA NIM).

Responsibilities:
  Integrate NVIDIA NIM API (OpenAI-compatible) with Qwen 3.5-122B
  to analyze enriched market data (ticker + OHLC + technical indicators)
  and produce actionable trading decisions (BUY, SELL, HOLD).

Design philosophy:
  - Momentum-driven, not conservative — this is a hackathon
  - Position-aware: knows if we are LONG, SHORT, or FLAT
  - Technically grounded: uses RSI, EMA crossover, Bollinger Bands, VWAP
  - Output is always a structured TradeSignal JSON dict
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from config import TradingConfig

logger = logging.getLogger(__name__)

# ── System Prompt ─────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a decisive, momentum-driven crypto trader competing in a hackathon.
Your goal is to MAXIMIZE P&L over the competition period. HOLD generates zero returns.

You receive enriched market data including OHLC candles, technical indicators
(RSI, EMA crossover, Bollinger Bands, VWAP), and current position status.

## Response Format
You MUST respond with EXACTLY one JSON object. No markdown fences, no extra text outside JSON.
If you use <think> tags for reasoning, put them BEFORE the JSON.

{
  "action": "BUY" | "SELL" | "HOLD",
  "pair": "<PAIR>",
  "volume": "<volume as string>",
  "order_type": "market" | "limit",
  "price": null,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<1-2 sentence explanation>"
}

## Entry Criteria (When to BUY)
1. RSI < 35 AND EMA9 crossing above EMA21 (bullish crossover) → STRONG BUY
2. Price touching lower Bollinger Band with upward momentum → BUY
3. RSI < 45 AND multi-timeframe trend is BULLISH → BUY
4. Price is below VWAP with bullish EMA crossover → BUY
5. Strong upward momentum (>0.5% in 5 candles) with RSI < 60 → BUY

## Exit Criteria (When to SELL)
1. RSI > 65 AND EMA9 crossing below EMA21 (bearish crossover) → SELL
2. Price touching upper Bollinger Band with downward momentum → SELL
3. RSI > 55 AND multi-timeframe trend is BEARISH → SELL
4. If currently LONG: unrealized profit > 2% → take profit SELL
5. If currently LONG: unrealized loss > 1.5% → cut losses SELL

## Position Rules
- If FLAT (no position): look for BUY entries
- If LONG: look for SELL exits (take profit or stop loss)
- NEVER hold through a clear reversal signal
- Confidence > 0.55 is sufficient to act — DO NOT be overly cautious
- Volume should be proportional to confidence: 0.55 conf → smaller size, 0.85+ conf → full size

## Volume Guidelines
- BTC: 0.01 to 0.05 (scale with confidence)
- ETH: 0.1 to 0.5
- SOL: 1.0 to 5.0
- Use market orders for speed

## Critical Mindset
- HOLDING indefinitely is LOSING in a hackathon — opportunity cost is real
- When indicators align, TRADE. When they conflict, WAIT (but not forever)
- React to momentum — don't wait for perfect setups
- If you've been HOLDING for too many iterations with clear signals, FORCE a decision
"""


# ── TradeSignal Defaults ─────────────────────────────────

def _hold_signal(pair: str, reason: str = "Default HOLD") -> dict[str, Any]:
    """Create a default HOLD signal — used on error or invalid response."""
    return {
        "action": "HOLD",
        "pair": pair,
        "volume": "0",
        "order_type": "market",
        "price": None,
        "confidence": 0.0,
        "reasoning": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Strategy LLM Class ───────────────────────────────────


class StrategyLLM:
    """
    Momentum-driven strategy brain powered by NVIDIA NIM (Qwen 3.5).

    Analyzes enriched market data including OHLC candles, technical
    indicators, and position context to produce trading decisions.

    Usage:
        strategy = StrategyLLM(config)
        signal = await strategy.analyze("BTCUSD", enriched_summary, prices,
                                         position_context="FLAT")
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config
        self._client = AsyncOpenAI(
            base_url=config.nim_base_url,
            api_key=config.nim_api_key,
        )
        self._hold_streak: dict[str, int] = {}  # Track consecutive HOLDs per pair
        logger.info(
            "Strategy LLM initialized — model: %s @ %s",
            config.nim_model,
            config.nim_base_url,
        )

    async def analyze(
        self,
        pair: str,
        enriched_summary: dict[str, Any],
        recent_prices: list[dict[str, Any]],
        position_context: str = "",
        portfolio_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze enriched market data and produce a TradeSignal.

        Args:
            pair: Trading pair (e.g., "BTCUSD")
            enriched_summary: Output from DataPipeline.get_enriched_summary()
            recent_prices: Output from DataPipeline.get_buffer()
            position_context: Formatted position info string
            portfolio_summary: Portfolio summary dict from PositionTracker

        Returns:
            TradeSignal dict
        """
        # Build user prompt with enriched data
        user_prompt = self._build_prompt(
            pair, enriched_summary, recent_prices,
            position_context, portfolio_summary,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._config.nim_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,  # Slightly higher for more decisive action
                max_tokens=2048,
                top_p=0.9,
            )

            raw_content = response.choices[0].message.content or ""

            # Parse response — extract thinking & JSON
            signal = self._parse_response(pair, raw_content)

            # Track HOLD streaks
            if signal.get("action") == "HOLD":
                self._hold_streak[pair] = self._hold_streak.get(pair, 0) + 1
            else:
                self._hold_streak[pair] = 0

            return signal

        except Exception as e:
            logger.error("🚨 NIM API error for %s: %s", pair, e)
            return _hold_signal(pair, f"LLM error: {type(e).__name__}: {e}")

    def _build_prompt(
        self,
        pair: str,
        summary: dict[str, Any],
        prices: list[dict[str, Any]],
        position_context: str = "",
        portfolio_summary: dict[str, Any] | None = None,
    ) -> str:
        """Build an enriched user prompt from market data + position context."""

        # ── Recent ticker prices (last 10 entries) ──
        recent = prices[-10:] if len(prices) > 10 else prices
        price_lines = []
        for p in recent:
            ts = p.get("timestamp", "")[:19]
            price_lines.append(
                f"  {ts}  Last: ${p.get('last', 0):,.2f}  "
                f"Bid: ${p.get('bid', 0):,.2f}  "
                f"Ask: ${p.get('ask', 0):,.2f}"
            )
        prices_text = "\n".join(price_lines) if price_lines else "  No data yet"

        # ── Technical indicators per timeframe ──
        indicators_text = ""
        indicators = summary.get("indicators", {})
        for timeframe, ind in indicators.items():
            if "error" in ind:
                indicators_text += f"\n### {timeframe} Indicators: No data available\n"
                continue

            bb = ind.get("bollinger", {}) or {}
            indicators_text += f"""
### {timeframe} Technical Indicators
- **RSI (14)**: {ind.get('rsi', 'N/A')}
- **EMA 9**: ${ind.get('ema_9', 'N/A')} | **EMA 21**: ${ind.get('ema_21', 'N/A')}
- **EMA Crossover**: {ind.get('ema_crossover', 'NONE')}
- **Bollinger Upper**: ${bb.get('upper', 'N/A')} | **Middle**: ${bb.get('middle', 'N/A')} | **Lower**: ${bb.get('lower', 'N/A')}
- **Bollinger Position**: {bb.get('position', 'N/A')}% (0%=lower band, 100%=upper band)
- **VWAP**: ${ind.get('vwap', 'N/A')}
- **Momentum (5 candles)**: {ind.get('momentum_5_candles', 0):+.4f}%
- **Momentum (10 candles)**: {ind.get('momentum_10_candles', 0):+.4f}%
- **Trend**: {ind.get('trend', 'UNKNOWN')}
- **Candles analyzed**: {ind.get('candle_count', 0)}
"""

        # ── OHLC summary (condensed) ──
        ohlc_text = ""
        ohlc_data = summary.get("ohlc", {})
        for timeframe, candles in ohlc_data.items():
            if candles:
                last_5 = candles[-5:]
                ohlc_text += f"\n### Last 5 {timeframe} Candles\n"
                for c in last_5:
                    ohlc_text += (
                        f"  O: ${c['open']:,.2f} H: ${c['high']:,.2f} "
                        f"L: ${c['low']:,.2f} C: ${c['close']:,.2f} "
                        f"Vol: {c['volume']:.4f}\n"
                    )

        # ── Position context ──
        position_text = position_context or "Position: FLAT (no open position)"

        # ── Portfolio context ──
        portfolio_text = ""
        if portfolio_summary:
            portfolio_text = f"""
### Portfolio Status
- **Total Realized P&L**: ${portfolio_summary.get('total_realized_pnl', 0):+,.2f}
- **Total Unrealized P&L**: ${portfolio_summary.get('total_unrealized_pnl', 0):+,.2f}
- **Completed Trades**: {portfolio_summary.get('total_trades', 0)} (Wins: {portfolio_summary.get('wins', 0)}, Losses: {portfolio_summary.get('losses', 0)})
- **Win Rate**: {portfolio_summary.get('win_rate', 0):.1f}%
"""

        # ── HOLD streak warning ──
        hold_streak = self._hold_streak.get(pair, 0)
        urgency_note = ""
        if hold_streak >= 5:
            urgency_note = f"""
### ⚠️ URGENCY WARNING
You have been HOLDING {pair} for {hold_streak} consecutive iterations.
If there is ANY reasonable signal, you SHOULD act now. Perpetual HOLD = zero P&L.
Re-examine the indicators more aggressively and lower your threshold for action.
"""
        elif hold_streak >= 3:
            urgency_note = f"""
### Note
{hold_streak} consecutive HOLDs for {pair}. Consider if you're being too cautious.
"""

        return f"""\
## Market Analysis Request for {pair}

### Current Summary
- **Current Price**: ${summary.get('current_price', 0):,.2f}
- **Price Change (buffer)**: {summary.get('price_change_pct', 0):+.4f}%
- **Ticker Trend**: {summary.get('trend_direction', 'UNKNOWN')}
- **Multi-Timeframe Trend**: {summary.get('multi_tf_trend', 'UNKNOWN')}
- **Avg Price (last 10 ticks)**: ${summary.get('avg_price_last_10', 0):,.2f}
- **Avg Price (last 50 ticks)**: ${summary.get('avg_price_last_50', 0):,.2f}
- **High**: ${summary.get('high', 0):,.2f}
- **Low**: ${summary.get('low', 0):,.2f}
- **Buffer Count**: {summary.get('buffer_count', 0)} snapshots

### Current Position
{position_text}
{portfolio_text}
{urgency_note}
### Recent Tick Prices
{prices_text}
{indicators_text}
{ohlc_text}
### Instructions
Analyze ALL the above data for {pair} and provide your trading decision as JSON.
Cross-reference RSI, EMA crossover, Bollinger position, and momentum across timeframes.
If you are FLAT and indicators suggest entry, BUY. If you are LONG and indicators suggest exit, SELL.
Scale volume with your confidence level.
"""

    def _parse_response(
        self, pair: str, raw_content: str
    ) -> dict[str, Any]:
        """
        Parse LLM response — extract thinking tags and JSON.

        Qwen 3.5 sometimes emits <think>...</think> before the answer.
        We preserve thinking for logs, then parse the JSON.
        """
        thinking = ""
        json_text = raw_content

        # 1. Extract <think> tags if present
        think_match = re.search(
            r"<think>(.*?)</think>", raw_content, re.DOTALL
        )
        if think_match:
            thinking = think_match.group(1).strip()
            json_text = re.sub(
                r"<think>.*?</think>", "", raw_content, flags=re.DOTALL
            ).strip()

        # Log thinking if present
        if thinking:
            think_preview = thinking[:300]
            if len(thinking) > 300:
                think_preview += "..."
            logger.info("🤔 Qwen thinking [%s]: %s", pair, think_preview)

        # 2. Extract JSON from response
        signal = self._extract_json(pair, json_text)

        # 3. Add metadata
        signal["timestamp"] = datetime.now(timezone.utc).isoformat()
        if thinking:
            signal["_thinking"] = thinking

        return signal

    def _extract_json(self, pair: str, text: str) -> dict[str, Any]:
        """
        Extract and parse JSON from response text.

        Handles:
        - Pure JSON
        - JSON in markdown code fences
        - JSON mixed with other text
        """
        text = text.strip()

        # Try direct parse
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return self._validate_signal(pair, parsed)
        except json.JSONDecodeError:
            pass

        # Try extract from markdown code fence
        fence_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL
        )
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1).strip())
                if isinstance(parsed, dict):
                    return self._validate_signal(pair, parsed)
            except json.JSONDecodeError:
                pass

        # Try find JSON object pattern anywhere in text
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    return self._validate_signal(pair, parsed)
            except json.JSONDecodeError:
                pass

        # Try find nested JSON (with nested braces)
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    return self._validate_signal(pair, parsed)
            except json.JSONDecodeError:
                pass

        # All parsing failed — return HOLD
        logger.warning(
            "⚠️  Failed to parse JSON from LLM response for %s: %s",
            pair,
            text[:200],
        )
        return _hold_signal(pair, "Failed to parse LLM response")

    def _validate_signal(
        self, pair: str, parsed: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and normalize a parsed signal."""
        action = str(parsed.get("action", "HOLD")).upper()
        if action not in ("BUY", "SELL", "HOLD"):
            action = "HOLD"

        confidence = parsed.get("confidence", 0.0)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.0

        volume = str(parsed.get("volume", "0"))
        try:
            vol_float = float(volume)
            # Cap volume to max_position_size
            if vol_float > self._config.max_position_size:
                volume = str(self._config.max_position_size)
        except ValueError:
            volume = "0"

        order_type = str(parsed.get("order_type", "market")).lower()
        if order_type not in ("market", "limit"):
            order_type = "market"

        price = parsed.get("price")
        if price is not None:
            try:
                price = str(float(price))
            except (TypeError, ValueError):
                price = None

        return {
            "action": action,
            "pair": parsed.get("pair", pair),
            "volume": volume,
            "order_type": order_type,
            "price": price,
            "confidence": confidence,
            "reasoning": str(parsed.get("reasoning", "No reasoning provided")),
        }
