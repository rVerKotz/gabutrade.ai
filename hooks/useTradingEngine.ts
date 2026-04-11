import { useState, useEffect, useCallback } from 'react';
import { TradingState, TradeSide, AgentPosition, AILogEntry, AgentResponse, CheckoutResponse } from '@/types/trading';

export function useTradingEngine() {
  const [state, setState] = useState<TradingState>({
    price: 0,
    priceHistory: [],
    volumeHistory: [],
    prices: {},
    portfolio: { USD: 0, BTC: 0, ETH: 0 },
    initialCapital: 0,
    tradeLog: [],
    aiLog: [],
    aiActive: false,
    isPaper: true
  });

  const syncWithPython = useCallback(async () => {
    try {
      const res = await fetch('/api/agent');
      if (!res.ok) return;
      
      const data: AgentResponse = await res.json();

      if (data.status) {
        setState((prev: TradingState): TradingState => {
          const portfolioData = data.portfolio || {};
          const marketPrices = data.prices || {};
          
          const btcPos = portfolioData.open_positions?.find((pos: AgentPosition) => pos.pair.includes('BTC'))?.volume || 0;
          const ethPos = portfolioData.open_positions?.find((pos: AgentPosition) => pos.pair.includes('ETH'))?.volume || 0;

          const newAiLogs: AILogEntry[] = (data.thought_process || []).map((msg: string) => ({
            time: msg.match(/\[(.*?)\]/)?.[1] || new Date().toLocaleTimeString(),
            msg: msg.replace(/\[.*?\]/, '').trim(),
            type: (msg.includes('BUY') ? 'buy' : msg.includes('SELL') ? 'sell' : 'info')
          }));

          const currentBtcPrice = marketPrices['BTC'] || marketPrices['XBT'] || prev.price;

          return {
            ...prev,
            price: currentBtcPrice,
            prices: marketPrices,
            priceHistory: currentBtcPrice > 0 ? [...prev.priceHistory.slice(-59), currentBtcPrice] : prev.priceHistory,
            volumeHistory: [...prev.volumeHistory.slice(-59), Math.random() * 10], 
            aiActive: data.status === 'online',
            aiLog: newAiLogs.length > 0 ? newAiLogs : prev.aiLog,
            portfolio: {
              USD: (data.config?.initial_capital || 0) + (portfolioData.total_realized_pnl || 0),
              BTC: btcPos,
              ETH: ethPos
            },
            initialCapital: data.config?.initial_capital || 0,
            isPaper: data.config?.mode === 'paper',
            tradeLog: portfolioData.recent_trades || prev.tradeLog
          };
        });
      }
    } catch (err) {
      console.error("Gagal sinkronisasi dengan Python Bridge:", err);
    }
  }, []);

  useEffect(() => {
    setState((prev: TradingState): TradingState => ({
      ...prev,
      aiLog: [{ time: new Date().toLocaleTimeString(), msg: "Sistem: Menunggu sinyal dari Python Bridge...", type: 'info' }]
    }));
    syncWithPython();
    const interval = setInterval(syncWithPython, 3000);
    return () => clearInterval(interval);
  }, [syncWithPython]);

  const toggleAI = async () => {
    if (!state.aiActive) {
      await fetch('/api/agent', { method: 'POST' });
      setState((prev: TradingState): TradingState => ({ ...prev, aiActive: true }));
    }
  };

  /**
   * Mendukung deposit manual dengan input detail bank pengirim
   */
  const handleDeposit = async (amount: number, userBank: string, userAccountName: string) => {
    console.log(`[DEPOSIT] Memproses deposit manual $${amount} dari ${userAccountName} (${userBank})...`);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort("Timeout"), 30000); 

    try {
      const response = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          amount, 
          userBank, 
          userAccountName,
          userId: 'USER-PRO-01' // ID statis untuk contoh, bisa diganti ID Auth
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.error || `Server Error (${response.status})`);
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError' || controller.signal.aborted) {
        throw new Error('Koneksi ke server terputus. Silakan coba lagi.');
      }
      throw error;
    }
  };

  const manualOrder = (side: TradeSide) => {
    console.log(`Perintah manual ${side} dikirim ke Kraken via Bridge`);
  };

  return {
    ...state,
    toggleAI,
    manualOrder,
    handleDeposit
  };
}