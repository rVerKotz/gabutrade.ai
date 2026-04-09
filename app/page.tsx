'use client';

import { useMemo } from 'react';
import { Trade } from '@/types/trading';
import Header from './components/Header';
import PriceChart from './components/PriceChart';
import SignalBar from './components/SignalBar';
import OrderBook from './components/OrderBook';
import PortfolioPanel from './components/PortfolioPanel';
import AIPanel from './components/AIPanel';
import { useTradingEngine } from '@/hooks/useTradingEngine';

export default function TradingDashboard() {
  const {
    price,
    priceHistory,
    volumeHistory,
    tradeLog,
    aiLog,
    portfolio,
    aiActive,
    manualOrder,
    toggleAI,
  } = useTradingEngine();

  const startPrice = priceHistory[0] ?? price;
  const pct = ((price - startPrice) / startPrice) * 100;
  const slice60 = priceHistory.slice(-60);
  const hi = slice60.length ? Math.max(...slice60) : price;
  const lo = slice60.length ? Math.min(...slice60) : price;

  const priceDisplay = useMemo(
    () => '$' + price.toLocaleString('en-US', { maximumFractionDigits: 0 }),
    [price]
  );

  return (
    <>
      <Header />
      <div className="dashboard">
        <div className="main-panel">
          <div className="price-hero">
            <div className="price-main">{priceDisplay}</div>
            <div className={`price-change ${pct >= 0 ? 'up' : 'down'}`}>
              {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
            </div>
          </div>

          <div className="stats-row">
            <div className="stat">
              <div className="stat-label">24H HIGH</div>
              <div className="stat-value" style={{ color: 'var(--green)' }}>
                ${hi.toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">24H LOW</div>
              <div className="stat-value" style={{ color: 'var(--red)' }}>
                ${lo.toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">VOLUME</div>
              <div className="stat-value">$1.24B</div>
            </div>
            <div className="stat">
              <div className="stat-label">SPREAD</div>
              <div className="stat-value" style={{ color: 'var(--amber)' }}>
                ${(price * 0.00018).toFixed(2)}
              </div>
            </div>
          </div>

          <PriceChart priceHistory={priceHistory} tradeLog={tradeLog} />

          <SignalBar priceHistory={priceHistory} volumeHistory={volumeHistory} price={price} />

          <div className="box">
            <div className="box-header">Recent Trades</div>
            <div className="box-body scrollable">
              {tradeLog.length === 0 ? (
                <div style={{ color: 'var(--dim)', textAlign: 'center', padding: '12px' }}>
                  No trades yet
                </div>
              ) : (
                tradeLog.slice(0, 20).map((trade: Trade, index: number) => (
                  <div key={index} className="trade-row">
                    <span style={{ color: trade.side === 'BUY' ? 'var(--green)' : 'var(--red)' }}>
                      {trade.side === 'BUY' ? '▲' : '▼'} {trade.side}
                    </span>
                    <span style={{ color: 'var(--muted)' }}>{trade.source}</span>
                    <span>${trade.price.toFixed(0)}</span>
                    <span style={{ color: 'var(--dim)' }}>{trade.qty.toFixed(4)} BTC</span>
                    <span style={{ color: 'var(--dim)', fontSize: '9.5px' }}>{trade.time}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="sidebar">
          <OrderBook price={price} />
          <PortfolioPanel portfolio={portfolio} price={price} />
          <AIPanel
            aiLog={aiLog}
            aiActive={aiActive}
            onToggleAI={toggleAI}
            onManualOrder={manualOrder}
          />
        </div>
      </div>
    </>
  );
}
