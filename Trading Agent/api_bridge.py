import os
import stat
import json
import logging
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import TradingConfig
from data_pipeline import DataPipeline
from mcp_client import KrakenMCPClient
from position_tracker import PositionTracker
from risk_guard import RiskGuard
from strategy_llm import StrategyLLM
from main import run_trading_loop, TradingLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingBridge")

PAPER_BALANCE = 10_000 

class BridgeState:
    def __init__(self):
        self.is_running = False
        self.task: asyncio.Task | None = None
        self.config = TradingConfig()
        self.tracker: PositionTracker | None = None
        if os.getenv("VERCEL"):
            self.log_path = Path("/tmp/trading_log.jsonl")
        else:
            self.log_path = Path(__file__).parent / "logs" / "trading_log.jsonl"


state = BridgeState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Graceful shutdown: cancel the agent task if running
    if state.task and not state.task.done():
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="GabuTrade AI Bridge", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_last_logs(limit: int = 10) -> list[str]:
    """Read the last N trading events from the JSONL log file."""
    if not state.log_path.exists():
        return ["No activity recorded yet."]
    try:
        with open(state.log_path, "r") as f:
            lines = f.readlines()
        logs = []
        for line in lines[-limit:]:
            data = json.loads(line)
            msg = (
                f"[{data.get('timestamp', '')[:19]}] "
                f"{data.get('event', '').upper()}: "
                f"{data.get('data', {})}"
            )
            logs.append(msg)
        return logs or ["Waiting for activity..."]
    except Exception as e:
        return [f"Failed to read log: {e}"]


@app.get("/status")
async def get_status():
    portfolio = state.tracker.get_portfolio_summary() if state.tracker else {}
    return {
        "status": "online" if state.is_running else "idle",
        "thought_process": get_last_logs(),
        "portfolio": portfolio,
        "config": {
            "mode": state.config.mode,
            "pairs": state.config.pairs,
            "initial_capital": PAPER_BALANCE,   # <-- was missing; caused $0 display
        },
    }

@app.post("/agent/stop")
async def stop_agent():
    if not state.is_running:
        return {"message": "Agent is not running"}

    if state.task and not state.task.done():
        state.task.cancel()
        # We don't await here to avoid blocking the HTTP response
        logger.info("Stop signal received: Cancelling agent task...")
        return {"message": "Agent stop signal sent"}
    
    return {"message": "No active task to stop"}


@app.post("/agent/start")
async def start_agent():
    if state.is_running:
        return {"message": "Agent already running"}

    # Cancel any dead previous task before spawning a new one
    if state.task and not state.task.done():
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass

    # asyncio.create_task() keeps everything inside the running event loop,
    # so anyio's cancel scopes (used by MCP stdio_client) are entered and
    # exited in the same task — fixing the "different task" RuntimeError.
    state.task = asyncio.create_task(_agent_loop())
    return {"message": "Agent started"}


async def _agent_loop() -> None:
    """
    Full trading loop. Runs as a plain asyncio Task so that the MCP
    stdio_client's anyio TaskGroup is always entered and exited in the
    same task context.
    """
    state.is_running = True
    mcp: KrakenMCPClient | None = None
    kraken_path = state.config.kraken_cli_path
    if os.path.exists(kraken_path):
        st = os.stat(kraken_path)
        os.chmod(kraken_path, st.st_mode | stat.S_IEXEC)

    try:
        mcp = KrakenMCPClient(state.config)
        pipeline = DataPipeline(mcp, state.config)
        strategy = StrategyLLM(state.config)
        risk = RiskGuard(state.config)
        state.tracker = PositionTracker(state.config)
        tlog = TradingLogger()

        await mcp.connect()
        logger.info("MCP connected — initialising paper account with $%s", PAPER_BALANCE)

        if state.config.is_paper:
            try:
                await mcp.init_paper_trading(balance=PAPER_BALANCE)
            except Exception as e:
                logger.warning("Paper init skipped (may already exist): %s", e)

        await run_trading_loop(
            state.config, mcp, pipeline, strategy, risk, state.tracker, tlog
        )

    except asyncio.CancelledError:
        logger.info("Agent task cancelled — shutting down cleanly")

    except Exception as e:
        logger.error("Agent crashed: %s", e, exc_info=True)

    finally:
        state.is_running = False
        if mcp and mcp.is_connected:
            try:
                await mcp.disconnect()
            except Exception:
                pass
        logger.info("Agent loop exited")