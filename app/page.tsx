'use client';

import { useMemo, useState, useEffect } from 'react';
import { Trade } from '@/types/trading';
import Header from './components/Header';
import PriceChart from './components/PriceChart';
import SignalBar from './components/SignalBar';
import OrderBook from './components/OrderBook';
import PortfolioPanel from './components/PortfolioPanel';
import AIPanel from './components/AIPanel';
import { useTradingEngine } from '@/hooks/useTradingEngine';

export default function TradingDashboard() {
  const engine = useTradingEngine();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  // 1. Get Live Prices
  const btcPrice = engine.price > 0 ? engine.price : (engine.prices?.['BTC'] || 0);
  const ethPrice = engine.prices?.['ETH'] || 3000;

  // 2. Calculate AI's Total Live Portfolio Value (USD + BTC Value + ETH Value)
  const initialCap = engine.initialCapital || 10000;
  const totalPortfolioValue = 
    engine.portfolio.USD + 
    (engine.portfolio.BTC * btcPrice) + 
    (engine.portfolio.ETH * ethPrice);
    
  const totalPnl = totalPortfolioValue - initialCap;
  const pnlPct = initialCap > 0 ? (totalPnl / initialCap) * 100 : 0;

  // We ensure ETH is passed down so the Portfolio panel can calculate its value
  const allPricesForPortfolio = {
    ...engine.prices,
    'BTC': btcPrice,
    'ETH': ethPrice, 
  };

  if (!mounted) return null;

  return (
    <>
      <Header />
      <div className="dashboard">
        <div className="main-panel">
          
          {/* AI PORTFOLIO HERO (Changed to show AI Balance instead of BTC Price) */}
          <div className="price-hero">
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px' }}>
              <h1 style={{ fontSize: '42px', letterSpacing: '-1px' }}>
                ${totalPortfolioValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </h1>
              <span style={{ 
                color: totalPnl >= 0 ? 'var(--green)' : 'var(--red)',
                fontSize: '18px',
                fontWeight: 500
              }}>
                {totalPnl >= 0 ? '+' : ''}{pnlPct.toFixed(2)}% 
                <span style={{ fontSize: '14px', marginLeft: '6px', opacity: 0.8 }}>
                  ({totalPnl >= 0 ? '+' : ''}${Math.abs(totalPnl).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})
                </span>
              </span>
            </div>
            <div style={{ color: 'var(--dim)', fontSize: '13px', marginTop: '4px' }}>
              AI Agent Total Balance • Live Execution {engine.isPaper ? '(PAPER)' : '(LIVE)'}
            </div>
          </div>

          <SignalBar priceHistory={engine.priceHistory} volumeHistory={engine.volumeHistory} price={btcPrice} />
          
          {/* BTC PRICE CHART HEADER */}
          <div style={{ marginTop: '32px', marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--fg)' }}>BTC/USD</h3>
              <div style={{ color: 'var(--dim)', fontSize: '12px' }}>Live Market Chart</div>
            </div>
            <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--green)' }}>
              ${btcPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>

          <PriceChart priceHistory={engine.priceHistory} tradeLog={engine.tradeLog} />

          <div className="activity-panel">
            <h3>Recent Activity</h3>
            <div className="trade-list">
              {engine.tradeLog.length === 0 ? (
                <div style={{ color: 'var(--dim)', textAlign: 'center', padding: '12px' }}>
                  No trade history from agent yet...
                </div>
              ) : (
                engine.tradeLog.slice(0, 20).map((trade: Trade, index: number) => (
                  <div key={index} className="trade-row">
                    <span style={{ color: trade.side === 'BUY' ? 'var(--green)' : 'var(--red)' }}>
                      {trade.side === 'BUY' ? '▲' : '▼'} {trade.side}
                    </span>
                    <span>${(trade.price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    <span style={{ color: 'var(--dim)' }}>
                      {trade.qty} {trade.pair?.split('/')[0] || 'BTC'}
                    </span>
                    <span style={{ color: 'var(--dim)', fontSize: '11px' }}>{trade.time}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="sidebar">
          <OrderBook price={btcPrice} />
          <PortfolioPanel
            portfolio={engine.portfolio}
            prices={allPricesForPortfolio}
            initialCapital={initialCap}
          />
          <AIPanel
            aiLog={engine.aiLog}
            aiActive={engine.aiActive}
            onToggleAI={engine.toggleAI}
            onManualOrder={engine.manualOrder}
          />
        </div>
      </div>
    </>
  );
}