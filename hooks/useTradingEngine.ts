'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Trade, AILogEntry, Portfolio, TradeSide, rand, clamp, now, getSignals, seedPriceHistory } from '@/types/trading';

export function useTradingEngine() {
  const [price, setPrice] = useState(67240);
  const [priceHistory, setPriceHistory] = useState<number[]>([]);
  const [volumeHistory, setVolumeHistory] = useState<number[]>([]);
  const [tradeLog, setTradeLog] = useState<Trade[]>([]);
  const [aiLog, setAiLog] = useState<AILogEntry[]>([
    { type: 'info', msg: 'System initialized · Demo mode (no real orders)', time: now() },
    { type: 'info', msg: 'Press START AI AGENT to activate the trading bot', time: now() },
  ]);
  const [portfolio, setPortfolio] = useState<Portfolio>({ USD: 10000, BTC: 0.5, ETH: 3.2 });
  const [aiActive, setAiActive] = useState(false);
  const [frame, setFrame] = useState(0);

  const priceRef = useRef(price);
  const priceHistoryRef = useRef<number[]>([]);
  const volumeHistoryRef = useRef<number[]>([]);
  const portfolioRef = useRef(portfolio);
  const aiActiveRef = useRef(aiActive);
  const aiThinkingRef = useRef(false);
  const frameRef = useRef(0);

  priceRef.current = price;
  portfolioRef.current = portfolio;
  aiActiveRef.current = aiActive;

  // Seed history on mount
  useEffect(() => {
    const { prices, volumes } = seedPriceHistory();
    priceHistoryRef.current = prices;
    volumeHistoryRef.current = volumes;
    setPriceHistory([...prices]);
    setVolumeHistory([...volumes]);
    priceRef.current = prices[prices.length - 1];
    setPrice(prices[prices.length - 1]);
  }, []);

  const addAILog = useCallback((type: AILogEntry['type'], msg: string) => {
    const entry: AILogEntry = { type, msg, time: now() };
    setAiLog((prev) => [entry, ...prev].slice(0, 80));
  }, []);

  const executeTrade = useCallback(
    (side: TradeSide, p: number, qty: number, source: Trade['source']) => {
      setPortfolio((prev) => {
        const next = { ...prev };
        if (side === 'BUY' && next.USD >= p * qty) {
          next.USD -= p * qty;
          next.BTC += qty;
        }
        if (side === 'SELL' && next.BTC >= qty) {
          next.USD += p * qty;
          next.BTC -= qty;
        }
        portfolioRef.current = next;
        return next;
      });

      const trade: Trade = { side, price: p, qty, source, time: now() };
      setTradeLog((prev) => [trade, ...prev].slice(0, 50));
    },
    []
  );

  const manualOrder = useCallback(
    (side: TradeSide) => {
      const p = portfolioRef.current;
      const qty =
        side === 'BUY'
          ? clamp((p.USD / priceRef.current) * 0.1, 0, 0.01)
          : clamp(p.BTC * 0.1, 0, 0.01);
      if (qty > 0.0001) {
        executeTrade(side, priceRef.current, qty, 'MANUAL');
        addAILog(
          side === 'BUY' ? 'buy' : 'sell',
          `Manual ${side} ${qty.toFixed(4)} BTC @ $${priceRef.current.toFixed(0)}`
        );
      }
    },
    [executeTrade, addAILog]
  );

  const aiDecide = useCallback(() => {
    if (!aiActiveRef.current || aiThinkingRef.current) return;
    aiThinkingRef.current = true;

    const s = getSignals(priceHistoryRef.current, volumeHistoryRef.current, priceRef.current);
    const thoughts = [
      `Scanning RSI=${s.rsi.toFixed(0)}, price=$${s.cur.toFixed(0)}`,
      `EMA20=${s.ema.toFixed(0)} | MACD ${s.macd > 0 ? 'positive ▲' : 'negative ▼'}`,
      `Bollinger: price is ${
        s.cur < s.bb_lo
          ? 'BELOW lower band'
          : s.cur > s.bb_up
          ? 'ABOVE upper band'
          : 'within bands'
      }`,
      `Volume ratio: ${s.volRatio.toFixed(2)}x 10-bar average`,
    ];

    let idx = 0;
    const thinkTimer = setInterval(() => {
      if (idx < thoughts.length) {
        addAILog('analysis', thoughts[idx++]);
      } else {
        clearInterval(thinkTimer);

        const bull =
          (s.rsi < 38 ? 1 : 0) +
          (s.macd > 0 ? 1 : 0) +
          (s.cur < s.bb_lo + 80 ? 1 : 0) +
          (s.cur < s.ema ? 1 : 0);
        const bear =
          (s.rsi > 65 ? 1 : 0) +
          (s.macd < 0 ? 1 : 0) +
          (s.cur > s.bb_up - 80 ? 1 : 0) +
          (s.cur > s.ema ? 1 : 0);

        let decision: TradeSide | null = null;
        let reason = '';

        if (bull >= 3 && portfolioRef.current.USD > 500) {
          decision = 'BUY';
          reason = `BUY signal confirmed: ${bull}/4 bullish indicators ✓`;
        } else if (bear >= 3 && portfolioRef.current.BTC > 0.01) {
          decision = 'SELL';
          reason = `SELL signal confirmed: ${bear}/4 bearish indicators ✓`;
        } else {
          reason = `HOLD — mixed signals (bull:${bull} bear:${bear}), no action`;
        }

        addAILog(
          decision === 'BUY' ? 'buy' : decision === 'SELL' ? 'sell' : 'info',
          reason
        );

        if (decision) {
          const qty =
            decision === 'BUY'
              ? clamp((portfolioRef.current.USD / priceRef.current) * 0.25, 0, 0.05)
              : clamp(portfolioRef.current.BTC * 0.25, 0, 0.05);
          if (qty > 0.001) {
            setTimeout(() => {
              executeTrade(decision!, priceRef.current, qty, 'AI-AGENT');
              addAILog(
                decision === 'BUY' ? 'buy' : 'sell',
                `✓ Executed ${decision} ${qty.toFixed(4)} BTC @ $${priceRef.current.toFixed(0)}`
              );
            }, 800);
          }
        }

        setTimeout(() => {
          aiThinkingRef.current = false;
        }, 2500);
      }
    }, 450);
  }, [addAILog, executeTrade]);

  const toggleAI = useCallback(() => {
    setAiActive((prev) => {
      const next = !prev;
      aiActiveRef.current = next;
      if (next) {
        addAILog('info', '— AI Agent started · Kraken XBT/USD —');
        addAILog('info', 'Strategy: RSI-14 + MACD + Bollinger(20,2) + EMA-20');
        addAILog('info', 'Risk: 25% position sizing per signal');
      } else {
        addAILog('info', '— AI Agent stopped —');
        aiThinkingRef.current = false;
      }
      return next;
    });
  }, [addAILog]);

  // Price tick
  useEffect(() => {
    const tick = () => {
      const vol = 0.0009;
      const recent = priceHistoryRef.current.slice(-20);
      const drift = recent.length > 0 ? (recent[0] - priceRef.current) * 0.002 : 0;
      let newPrice = priceRef.current + (Math.random() - 0.495) * priceRef.current * vol + drift;
      newPrice = clamp(newPrice, 58000, 78000);

      priceRef.current = newPrice;
      priceHistoryRef.current = [...priceHistoryRef.current, newPrice].slice(-300);
      volumeHistoryRef.current = [...volumeHistoryRef.current, rand(500, 1500)].slice(-300);

      setPrice(newPrice);
      setPriceHistory([...priceHistoryRef.current]);
      setVolumeHistory([...volumeHistoryRef.current]);

      frameRef.current++;
      setFrame(frameRef.current);

      if (frameRef.current % 15 === 0 && aiActiveRef.current) {
        aiDecide();
      }
    };

    const interval = setInterval(tick, 1200);
    return () => clearInterval(interval);
  }, [aiDecide]);

  return {
    price,
    priceHistory,
    volumeHistory,
    tradeLog,
    aiLog,
    portfolio,
    aiActive,
    frame,
    manualOrder,
    toggleAI,
  };
}

