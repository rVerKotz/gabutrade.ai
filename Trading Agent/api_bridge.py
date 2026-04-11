
import json
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Impor komponen asli dari folder Trading Agent
from config import TradingConfig
from data_pipeline import DataPipeline
from mcp_client import KrakenMCPClient
from position_tracker import PositionTracker
from risk_guard import RiskGuard
from strategy_llm import StrategyLLM
from main import run_trading_loop, TradingLogger

# Konfigurasi Logging untuk Bridge
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingBridge")

app = FastAPI(title="GabuTrade AI Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# State Global
class BridgeState:
    def __init__(self):
        self.is_running = False
        self.stop_event = asyncio.Event()
        self.config = TradingConfig()
        self.tracker = None
        self.log_path = Path(__file__).parent / "logs" / "trading_log.jsonl"

state = BridgeState()

def get_last_logs(limit=10):
    """Membaca log aktivitas trading terakhir dari file JSONL."""
    if not state.log_path.exists():
        return ["Belum ada aktivitas tercatat."]
    
    logs = []
    try:
        with open(state.log_path, "r") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                data = json.loads(line)
                # Format log sederhana untuk UI
                msg = f"[{data.get('timestamp', '')[:19]}] {data.get('event', '').upper()}: {data.get('data', {})}"
                logs.append(msg)
    except Exception as e:
        return [f"Gagal membaca log: {str(e)}"]
    return logs if logs else ["Menunggu aktivitas..."]

@app.get("/status")
async def get_status():
    """Mengambil status dan ringkasan portofolio dari tracker."""
    portfolio = state.tracker.get_portfolio_summary() if state.tracker else {}
    return {
        "status": "online" if state.is_running else "idle",
        "thought_process": get_last_logs(),
        "portfolio": portfolio,
        "config": {
            "mode": state.config.mode,
            "pairs": state.config.pairs
        }
    }

@app.post("/agent/start")
async def start_agent(background_tasks: BackgroundTasks):
    if state.is_running:
        return {"message": "Agent sudah berjalan"}
    
    state.is_running = True
    background_tasks.add_task(execution_thread)
    return {"message": "Agent berhasil dijalankan di latar belakang"}

async def execution_thread():
    """Menginisialisasi dan menjalankan loop trading seperti di main.py."""
    try:
        # 1. Inisialisasi Komponen (Mirip main.py)
        mcp = KrakenMCPClient(state.config)
        pipeline = DataPipeline(state.config, mcp)
        strategy = StrategyLLM(state.config)
        risk = RiskGuard(state.config)
        state.tracker = PositionTracker(state.config)
        tlog = TradingLogger()

        await mcp.connect()
        
        # Paper init jika diperlukan
        if state.config.is_paper:
            try:
                await mcp.init_paper_trading(balance=10000)
            except: pass

        # 2. Jalankan Loop Utama
        await run_trading_loop(
            state.config, mcp, pipeline, strategy, risk, state.tracker, tlog
        )
    except Exception as e:
        logger.error(f"Kritis: {e}")
    finally:
        state.is_running = False