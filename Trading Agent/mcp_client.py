"""
mcp_client.py — Sub-Agent 1: MCP Connector to Kraken CLI.

Single responsibility:
  Manage MCP (Model Context Protocol) connection to Kraken CLI
  and provide wrapper methods for each trading operation.

Kraken CLI runs as an MCP server via stdio transport.
All tools are exposed with the "kraken_" prefix,
for example: kraken_ticker, kraken_paper_buy, kraken_ohlc.
"""

from __future__ import annotations

import json
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import TradingConfig

logger = logging.getLogger(__name__)


class KrakenMCPClient:
    """
    MCP Client to communicate with Kraken CLI.

    Usage:
        client = KrakenMCPClient(config)
        await client.connect()
        ticker = await client.get_ticker("BTCUSD")
        await client.disconnect()
    """

    def __init__(self, config: TradingConfig) -> None:
        self._config = config
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._tools_cache: dict[str, dict] | None = None

    # ── Lifecycle ─────────────────────────────────────────

    async def connect(self) -> None:
        """Open MCP connection to Kraken CLI subprocess."""
        # Use bash wrapper to filter [mcp audit] lines from stderr for cleaner output
        server_params = StdioServerParameters(
            command="bash",
            args=[
                "-c",
                f"'{self._config.kraken_cli_path}' mcp -s all 2> >(grep -v '\\[mcp audit\\]' >&2)"
            ],
        )

        self._exit_stack = AsyncExitStack()
        transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        # transport is a tuple of (read_stream, write_stream)
        read_stream, write_stream = transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

        # Cache available tools for debugging & validation
        tools_result = await self._session.list_tools()
        self._tools_cache = {
            tool.name: {
                "description": tool.description,
                "schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
            }
            for tool in tools_result.tools
        }
        logger.info(
            "MCP connected — %d tools available", len(self._tools_cache)
        )

    async def disconnect(self) -> None:
        """Close MCP connection and clean up resources."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
            self._tools_cache = None
            logger.info("MCP disconnected")

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    # ── Tool Discovery ────────────────────────────────────

    def list_tools(self) -> dict[str, dict]:
        """Return cached dict of available MCP tools (name → info)."""
        return dict(self._tools_cache or {})

    # ── Internal Helper ───────────────────────────────────

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> str:
        """
        Call MCP tool and return raw text response.

        Extracts TextContent from CallToolResult.content list.
        """
        if not self._session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        logger.debug("Calling tool: %s(%s)", tool_name, arguments or {})
        result = await self._session.call_tool(
            tool_name, arguments=arguments or {}
        )

        if result.isError:
            error_text = " | ".join(
                item.text for item in result.content if hasattr(item, "text")
            )
            logger.error("Tool %s error: %s", tool_name, error_text)
            raise RuntimeError(f"MCP tool error [{tool_name}]: {error_text}")

        # Extract text from content items
        texts = []
        for item in result.content:
            if hasattr(item, "text"):
                texts.append(item.text)

        raw = "\n".join(texts)
        logger.debug("Tool %s response length: %d chars", tool_name, len(raw))
        return raw

    async def _call_tool_json(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict | list:
        """Call tool and parse response as JSON."""
        raw = await self._call_tool(tool_name, arguments)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some tools return tables, not JSON.
            # Return as dict with raw text.
            logger.warning(
                "Tool %s returned non-JSON response, wrapping as raw",
                tool_name,
            )
            return {"raw": raw}

    # ── Tool Name Resolution based on Mode ───────────────

    def _tool(self, base: str) -> str:
        """
        Resolve MCP tool name based on mode (paper vs live).

        Kraken CLI MCP v0.3.0 exposes all tools with the 'kraken_' prefix:
          - kraken_ticker, kraken_ohlc, kraken_orderbook
          - kraken_paper_buy, kraken_paper_sell, kraken_paper_balance
          - kraken_order_buy, kraken_order_sell, kraken_balance
        """
        # Market data tools — same for paper & live
        market_tools = {
            "ticker", "ohlc", "orderbook", "orderbook_grouped", "trades",
            "spreads", "assets", "pairs", "status", "server_time",
        }
        if base in market_tools:
            return f"kraken_{base}"

        # Paper vs Live mapping
        if self._config.is_paper:
            paper_map = {
                "buy": "kraken_paper_buy",
                "sell": "kraken_paper_sell",
                "balance": "kraken_paper_balance",
                "orders": "kraken_paper_orders",
                "cancel": "kraken_paper_cancel",
                "cancel_all": "kraken_paper_cancel_all",
                "history": "kraken_paper_history",
                "account_status": "kraken_paper_status",
                "init": "kraken_paper_init",
                "reset": "kraken_paper_reset",
            }
            return paper_map.get(base, f"kraken_paper_{base}")
        else:
            live_map = {
                "buy": "kraken_order_buy",
                "sell": "kraken_order_sell",
                "balance": "kraken_balance",
                "orders": "kraken_open_orders",
                "cancel": "kraken_order_cancel",
                "cancel_all": "kraken_order_cancel_all",
                "history": "kraken_trades_history",
                "account_status": "kraken_trade_balance",
            }
            return live_map.get(base, f"kraken_{base}")

    # ── Market Data Wrappers ──────────────────────────────

    async def get_ticker(self, pair: str) -> dict:
        """
        Fetch ticker data for a single pair.

        Returns dict with keys: ask, bid, last, volume, etc.
        Kraken MCP expects 'pairs' as array of strings.
        """
        return await self._call_tool_json(
            self._tool("ticker"), {"pairs": [pair]}
        )

    async def get_ohlc(self, pair: str, interval: int = 60) -> dict:
        """
        Fetch OHLC candlestick data.

        Args:
            pair: Trading pair (e.g. "BTCUSD")
            interval: Interval in minutes (1, 5, 15, 30, 60, 240, 1440)

        Note: Kraken MCP expects interval as string.
        """
        return await self._call_tool_json(
            self._tool("ohlc"), {"pair": pair, "interval": str(interval)}
        )

    async def get_orderbook(self, pair: str, count: int = 10) -> dict:
        """Fetch L2 order book."""
        return await self._call_tool_json(
            self._tool("orderbook"), {"pair": pair, "count": str(count)}
        )

    # ── Account Wrappers ──────────────────────────────────

    async def get_balance(self) -> dict:
        """Fetch balance (paper or live depending on mode)."""
        return await self._call_tool_json(self._tool("balance"))

    async def get_open_orders(self) -> dict:
        """Fetch list of open orders."""
        return await self._call_tool_json(self._tool("orders"))

    async def get_trade_history(self) -> dict:
        """Fetch trading history."""
        return await self._call_tool_json(self._tool("history"))

    async def get_account_status(self) -> dict:
        """Fetch account / portfolio status."""
        return await self._call_tool_json(self._tool("account_status"))

    # ── Trading Execution Wrappers ────────────────────────

    async def place_buy(
        self,
        pair: str,
        volume: str,
        order_type: str = "market",
        price: str | None = None,
    ) -> dict:
        """
        Execute a buy order.

        Args:
            pair: Trading pair
            volume: Base currency amount
            order_type: "market" or "limit"
            price: Limit price (required if order_type="limit")
        """
        tool = self._tool("buy")
        args: dict[str, Any] = {
            "pair": pair,
            "volume": volume,
        }
        if order_type != "market":
            args["type"] = order_type
        if price is not None:
            args["price"] = price

        logger.info(
            "📤 PLACING BUY: %s %s %s @ %s",
            pair, volume, order_type, price or "market",
        )
        return await self._call_tool_json(tool, args)

    async def place_sell(
        self,
        pair: str,
        volume: str,
        order_type: str = "market",
        price: str | None = None,
    ) -> dict:
        """
        Execute a sell order.

        Args:
            pair: Trading pair
            volume: Base currency amount
            order_type: "market" or "limit"
            price: Limit price (required if order_type="limit")
        """
        tool = self._tool("sell")
        args: dict[str, Any] = {
            "pair": pair,
            "volume": volume,
        }
        if order_type != "market":
            args["type"] = order_type
        if price is not None:
            args["price"] = price

        logger.info(
            "📤 PLACING SELL: %s %s %s @ %s",
            pair, volume, order_type, price or "market",
        )
        return await self._call_tool_json(tool, args)

    async def place_order(
        self,
        action: str,
        pair: str,
        volume: str,
        order_type: str = "market",
        price: str | None = None,
    ) -> dict:
        """
        Unified order placement — route to buy or sell.

        Args:
            action: "BUY" or "SELL"
            pair: Trading pair
            volume: Amount
            order_type: Order type
            price: Limit price (optional)

        Returns:
            ExecutionResult-compatible dict
        """
        if action.upper() == "BUY":
            return await self.place_buy(pair, volume, order_type, price)
        elif action.upper() == "SELL":
            return await self.place_sell(pair, volume, order_type, price)
        else:
            raise ValueError(f"Invalid action: {action}. Must be BUY or SELL.")

    # ── Paper Trading Init ────────────────────────────────

    async def init_paper_trading(self, balance: float = 10000) -> dict:
        """Initialize paper trading account."""
        return await self._call_tool_json(
            self._tool("init"), {"balance": str(balance)}
        )
