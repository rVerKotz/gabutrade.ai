"""
main.py — Sub-Agent 5: Main Loop (Central Orchestrator).

Responsibilities:
  Central async loop connecting all components:
  1. Fetch prices + OHLC via DataPipeline
  2. Check auto TP/SL via PositionTracker
  3. Analyze with enriched data via StrategyLLM (NVIDIA NIM)
  4. Validate via RiskGuard
  5. Execute via KrakenMCPClient
  6. Record positions and P&L

Run:
  source .venv/bin/activate
  python main.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import TradingConfig
from data_pipeline import DataPipeline
from mcp_client import KrakenMCPClient
from position_tracker import PositionTracker
from risk_guard import RiskGuard
from strategy_llm import StrategyLLM

# ── Paths ─────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / "logs"
TRADING_LOG_FILE = LOG_DIR / "trading_log.jsonl"


# ── JSON Log Writer ───────────────────────────────────────


class TradingLogger:
    """
    Structured JSON logger — writes every trading event to a JSONL file.

    Format: one JSON object per line (JSON Lines).
    File: logs/trading_log.jsonl
    """

    def __init__(self, log_file: Path = TRADING_LOG_FILE) -> None:
        self._log_file = log_file
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        # Open file in append mode
        self._file = open(self._log_file, "a", encoding="utf-8")  # noqa: SIM115

    def log(self, event_type: str, data: dict) -> None:
        """Write one event to the JSONL file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **data,
        }
        self._file.write(json.dumps(entry, default=str) + "\n")
        self._file.flush()

    def close(self) -> None:
        """Close file handle."""
        if self._file and not self._file.closed:
            self._file.close()


# ── Console Logging Setup ─────────────────────────────────


def setup_logging() -> None:
    """Configure logging with informative, colored format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(name)-18s │ %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


logger = logging.getLogger("main")


# ── Banner ────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════╗
║                                                  ║
║     🤖  AI TRADING AGENT  ·  KRAKEN MCP          ║
║                                                  ║
║     Model  : NVIDIA NIM / Qwen 3.5               ║
║     Engine : Kraken CLI via MCP (stdio)           ║
║     Mode   : {mode:<10s}                          ║
║     Strategy: Momentum + Technical Analysis       ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"""


# ── Main Loop ─────────────────────────────────────────────


async def run_trading_loop(
    config: TradingConfig,
    mcp: KrakenMCPClient,
    pipeline: DataPipeline,
    strategy: StrategyLLM,
    risk: RiskGuard,
    tracker: PositionTracker,
    tlog: TradingLogger,
) -> None:
    """
    Main trading loop.

    Each iteration:
    1. Fetch latest ticker prices + OHLC candles for each pair
    2. Check auto TP/SL on existing positions
    3. Send enriched data to LLM for analysis
    4. Validate signal through risk guard
    5. Execute order if approved
    6. Record position and P&L changes
    """
    iteration = 0

    while True:
        iteration += 1
        now = datetime.now(timezone.utc)
        logger.info(
            "═══ Iteration #%d ═══ %s ═══ %s ═══",
            iteration,
            now.strftime("%H:%M:%S UTC"),
            risk.format_status(),
        )

        tlog.log("iteration_start", {
            "iteration": iteration,
            "risk_status": risk.get_status(),
            "portfolio": tracker.get_portfolio_summary(),
        })

        for pair in config.pairs:
            try:
                await process_pair(
                    pair, mcp, pipeline, strategy, risk, tracker, tlog,
                )
            except Exception as e:
                logger.error(
                    "💥 Error processing %s: %s: %s",
                    pair, type(e).__name__, e,
                )
                tlog.log("error", {
                    "pair": pair,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                })

        logger.info(
            "💤 Sleeping %ds until next iteration...\n",
            config.poll_interval_seconds,
        )
        await asyncio.sleep(config.poll_interval_seconds)


async def process_pair(
    pair: str,
    mcp: KrakenMCPClient,
    pipeline: DataPipeline,
    strategy: StrategyLLM,
    risk: RiskGuard,
    tracker: PositionTracker,
    tlog: TradingLogger,
) -> None:
    """Process one trading pair: fetch → TP/SL check → analyze → validate → execute."""

    # ── Step 1: Fetch latest ticker price ──
    snapshot = await pipeline.fetch_latest(pair)

    if snapshot["last"] == 0:
        logger.warning("⚠️  [%s] No valid price data, skipping", pair)
        return

    current_price = snapshot["last"]

    # Log price data
    tlog.log("price_update", {
        "pair": pair,
        "price": current_price,
        "ask": snapshot["ask"],
        "bid": snapshot["bid"],
        "volume_24h": snapshot["volume_24h"],
    })

    # ── Step 2: Check auto TP/SL on existing positions ──
    exit_check = tracker.should_exit(pair, current_price)

    if exit_check["should_exit"]:
        logger.info(
            "🎯 [%s] AUTO-EXIT: %s | P&L: $%+,.2f (%.2f%%)",
            pair, exit_check["reason"],
            exit_check["unrealized_pnl"],
            exit_check["unrealized_pnl_pct"],
        )
        tlog.log("auto_exit_triggered", {
            "pair": pair,
            "reason": exit_check["reason"],
            "unrealized_pnl": exit_check["unrealized_pnl"],
            "unrealized_pnl_pct": exit_check["unrealized_pnl_pct"],
        })

        # Execute the auto-exit
        await execute_auto_exit(
            pair, exit_check, mcp, tracker, risk, tlog,
        )
        return  # Skip LLM analysis after auto-exit

    # ── Step 3: Get enriched summary (ticker + OHLC + indicators) ──
    logger.info("🕯️  [%s] Fetching OHLC candles + computing indicators...", pair)
    enriched_summary = await pipeline.get_enriched_summary(pair)
    prices = pipeline.get_buffer(pair)

    # ── Step 4: Build position context for LLM ──
    position_context = tracker.format_for_llm(pair, current_price)

    # Collect current prices for all pairs for portfolio summary
    current_prices = {}
    for p in tracker.open_positions:
        latest = pipeline.get_latest(p)
        if latest:
            current_prices[p] = latest["last"]
    current_prices[pair] = current_price
    portfolio_summary = tracker.get_portfolio_summary(current_prices)

    # ── Step 5: Ask LLM for analysis ──
    logger.info("🧠 [%s] Analyzing with LLM (enriched data)...", pair)
    signal_data = await strategy.analyze(
        pair, enriched_summary, prices,
        position_context=position_context,
        portfolio_summary=portfolio_summary,
    )

    action = signal_data.get("action", "HOLD")
    confidence = signal_data.get("confidence", 0.0)
    reasoning = signal_data.get("reasoning", "")
    thinking = signal_data.get("_thinking", "")

    # Log action
    action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(action, "❓")
    logger.info(
        "%s [%s] Signal: %s | Confidence: %.2f | %s",
        action_emoji, pair, action, confidence, reasoning,
    )

    # Extract indicator summaries for log
    indicator_log = {}
    for tf, ind in enriched_summary.get("indicators", {}).items():
        indicator_log[tf] = {
            "rsi": ind.get("rsi"),
            "ema_crossover": ind.get("ema_crossover"),
            "trend": ind.get("trend"),
            "momentum_5": ind.get("momentum_5_candles"),
        }

    tlog.log("signal", {
        "pair": pair,
        "action": action,
        "confidence": confidence,
        "reasoning": reasoning,
        "thinking": thinking[:500] if thinking else "",
        "order_type": signal_data.get("order_type", "market"),
        "volume": signal_data.get("volume", "0"),
        "price_summary": {
            "current_price": enriched_summary.get("current_price"),
            "multi_tf_trend": enriched_summary.get("multi_tf_trend"),
            "buffer_count": enriched_summary.get("buffer_count"),
        },
        "indicators": indicator_log,
        "position": tracker.get_position_side(pair),
    })

    # ── Step 6: Risk validation ──
    verdict = risk.evaluate(signal_data)

    tlog.log("risk_verdict", {
        "pair": pair,
        "approved": verdict["approved"],
        "rejection_reason": verdict.get("rejection_reason"),
        "adjusted_volume": verdict.get("adjusted_volume", "0"),
        "daily_pnl_remaining": verdict.get("daily_pnl_remaining", 0),
    })

    if not verdict["approved"]:
        if verdict["rejection_reason"]:
            logger.info(
                "🚫 [%s] Rejected: %s",
                pair, verdict["rejection_reason"],
            )
        return

    # ── Step 7: Execute if not HOLD ──
    if action == "HOLD":
        return

    volume = verdict["adjusted_volume"]
    order_type = signal_data.get("order_type", "market")
    price = signal_data.get("price")

    logger.info(
        "⚡ [%s] EXECUTING: %s %s vol=%s type=%s price=%s",
        pair, action, pair, volume, order_type, price or "market",
    )

    try:
        result = await mcp.place_order(
            action=action,
            pair=pair,
            volume=volume,
            order_type=order_type,
            price=price,
        )

        # Record trade in risk guard
        risk.record_trade(result)

        # Record position in tracker
        if action == "BUY":
            tracker.open_position(pair, "LONG", current_price, float(volume))
        elif action == "SELL" and tracker.has_position(pair):
            trade_record = tracker.close_position(pair, current_price)
            risk.record_pnl(trade_record["pnl"])
            tlog.log("position_closed", trade_record)

        logger.info(
            "✅ [%s] Order executed: %s",
            pair,
            _format_execution_result(result),
        )

        tlog.log("execution", {
            "pair": pair,
            "action": action,
            "volume": volume,
            "order_type": order_type,
            "price": price,
            "result": result,
            "success": True,
        })

    except Exception as e:
        logger.error(
            "💥 [%s] Order execution failed: %s: %s",
            pair, type(e).__name__, e,
        )
        tlog.log("execution_error", {
            "pair": pair,
            "action": action,
            "volume": volume,
            "error_type": type(e).__name__,
            "error_message": str(e),
        })


async def execute_auto_exit(
    pair: str,
    exit_check: dict,
    mcp: KrakenMCPClient,
    tracker: PositionTracker,
    risk: RiskGuard,
    tlog: TradingLogger,
) -> None:
    """Execute an automatic TP/SL exit for a position."""
    position = tracker.get_position(pair)
    if not position:
        return

    action = exit_check["action"]
    volume = str(position["volume"])

    logger.info(
        "⚡ [%s] AUTO-EXIT EXECUTING: %s vol=%s (TP/SL)",
        pair, action, volume,
    )

    try:
        result = await mcp.place_order(
            action=action,
            pair=pair,
            volume=volume,
            order_type="market",
        )

        # Record trade
        risk.record_trade(result)

        # Close position and record P&L
        current_price = position["entry_price"]  # Will be updated from snapshot
        if exit_check.get("unrealized_pnl") is not None:
            # Compute the exit price from the unrealized P&L
            if position["side"] == "LONG":
                current_price = position["entry_price"] + (
                    exit_check["unrealized_pnl"] / position["volume"]
                )
            else:
                current_price = position["entry_price"] - (
                    exit_check["unrealized_pnl"] / position["volume"]
                )

        trade_record = tracker.close_position(pair, current_price)
        risk.record_pnl(trade_record["pnl"])

        logger.info(
            "✅ [%s] Auto-exit completed: P&L $%+,.2f",
            pair, trade_record["pnl"],
        )

        tlog.log("auto_exit_execution", {
            "pair": pair,
            "action": action,
            "volume": volume,
            "trade_record": trade_record,
            "reason": exit_check["reason"],
            "success": True,
        })

    except Exception as e:
        logger.error(
            "💥 [%s] Auto-exit failed: %s: %s",
            pair, type(e).__name__, e,
        )
        tlog.log("auto_exit_error", {
            "pair": pair,
            "error_type": type(e).__name__,
            "error_message": str(e),
        })


def _format_execution_result(result: dict) -> str:
    """Format execution result for readable logging."""
    if isinstance(result, dict):
        if "raw" in result:
            return result["raw"][:200]
        return str(result)[:300]
    return str(result)[:300]


# ── Main ──────────────────────────────────────────────────


async def main() -> None:
    """Entry point — initialize all components and run the loop."""
    setup_logging()

    # ── Load config ──
    config = TradingConfig()
    errors = config.validate()

    print(BANNER.format(mode=config.mode.upper()))
    logger.info("Config: %s", config.summary())

    if errors:
        for err in errors:
            logger.error("❌ Config error: %s", err)
        logger.error("Fix the above errors and try again.")
        sys.exit(1)

    # ── Initialize components ──
    mcp = KrakenMCPClient(config)
    pipeline = DataPipeline(mcp, config)
    strategy = StrategyLLM(config)
    risk = RiskGuard(config)
    tracker = PositionTracker(config)
    tlog = TradingLogger()

    logger.info("📁 JSON log: %s", tlog._log_file)

    # ── Log startup event ──
    tlog.log("startup", {
        "mode": config.mode,
        "pairs": config.pairs,
        "model": config.nim_model,
        "poll_interval": config.poll_interval_seconds,
        "max_daily_loss": config.max_daily_loss,
        "max_position_size": config.max_position_size,
        "min_confidence": config.min_confidence,
        "take_profit_pct": config.take_profit_pct,
        "stop_loss_pct": config.stop_loss_pct,
        "ohlc_intervals": config.ohlc_intervals,
    })

    # ── Setup graceful shutdown ──
    shutdown_event = asyncio.Event()

    def handle_shutdown(sig: int, frame: object) -> None:  # noqa: ARG001
        sig_name = signal.Signals(sig).name
        logger.info("🛑 Received %s — shutting down gracefully...", sig_name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # ── Connect MCP ──
    logger.info("🔌 Connecting to Kraken CLI via MCP...")
    try:
        await mcp.connect()
    except Exception as e:
        logger.error("❌ Failed to connect MCP: %s: %s", type(e).__name__, e)
        logger.error(
            "Make sure Kraken CLI is installed at: %s",
            config.kraken_cli_path,
        )
        sys.exit(1)

    # Log available tools
    tools = mcp.list_tools()
    logger.info("🔧 Available MCP tools: %d", len(tools))

    tlog.log("mcp_connected", {
        "tools_count": len(tools),
        "tool_names": list(tools.keys()),
    })

    # ── Init paper trading if needed ──
    if config.is_paper:
        logger.info("📝 Paper trading mode — checking account...")
        try:
            balance = await mcp.get_balance()
            logger.info("💰 Paper balance: %s", balance)
            tlog.log("balance", {"balance": balance})
        except Exception:
            logger.info("📝 Initializing paper trading account...")
            try:
                await mcp.init_paper_trading(balance=10000)
                logger.info("✅ Paper account initialized with $10,000")
                tlog.log("paper_init", {"balance": 10000})
            except Exception as e:
                logger.warning("⚠️  Paper init issue: %s (may already exist)", e)

    # ── Run loop ──
    logger.info("🚀 Starting trading loop — Ctrl+C to stop\n")

    try:
        loop_task = asyncio.create_task(
            run_trading_loop(config, mcp, pipeline, strategy, risk, tracker, tlog)
        )
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [loop_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    finally:
        # ── Cleanup ──
        logger.info("🧹 Cleaning up...")

        # Log final portfolio state
        portfolio = tracker.get_portfolio_summary()
        tlog.log("shutdown", {
            "reason": "graceful",
            "final_portfolio": portfolio,
        })

        tlog.close()
        if mcp.is_connected:
            await mcp.disconnect()
        logger.info("👋 Trading agent stopped. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
