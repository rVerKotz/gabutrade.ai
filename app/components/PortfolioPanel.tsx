'use client';

import { Portfolio } from '@/types/trading';

interface PortfolioProps {
  portfolio: Portfolio;
  price: number;
}

const ETH_PRICE = 3180;

export default function PortfolioPanel({ portfolio, price }: PortfolioProps) {
  const btcUSD = price * portfolio.BTC;
  const ethUSD = ETH_PRICE * portfolio.ETH;
  const total = portfolio.USD + btcUSD + ethUSD;
  const pnl = total - 10000;
  const pnlPct = ((pnl / 10000) * 100).toFixed(2);

  return (
    <div className="side-section">
      <div className="section-title">Portfolio</div>
      <div className="portfolio-grid">
        <div className="pf-item">
          <div>
            <div className="pf-coin">USD</div>
            <div className="pf-amount">Cash</div>
          </div>
          <div className="pf-value">
            ${portfolio.USD.toLocaleString('en-US', { maximumFractionDigits: 2 })}
          </div>
        </div>

        <div className="pf-item">
          <div>
            <div className="pf-coin">BTC</div>
            <div className="pf-amount">{portfolio.BTC.toFixed(4)} BTC</div>
          </div>
          <div>
            <div className="pf-value">
              ${btcUSD.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </div>
            <div className={`pf-pnl ${btcUSD > 33000 ? 'up' : 'down'}`}>
              {btcUSD > 33000 ? '▲' : '▼'} {(Math.abs(btcUSD / 33000 - 1) * 100).toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="pf-item">
          <div>
            <div className="pf-coin">ETH</div>
            <div className="pf-amount">{portfolio.ETH.toFixed(2)} ETH</div>
          </div>
          <div>
            <div className="pf-value">
              ${ethUSD.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </div>
            <div className="pf-pnl up">▲ 2.1%</div>
          </div>
        </div>

        <div
          className="pf-item"
          style={{ borderColor: pnl >= 0 ? '#00d4aa44' : '#ff4d6d44' }}
        >
          <div>
            <div className="pf-coin" style={{ color: 'var(--amber)' }}>
              TOTAL
            </div>
            <div className="pf-amount">All assets</div>
          </div>
          <div>
            <div className="pf-value">
              ${total.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </div>
            <div className={`pf-pnl ${pnl >= 0 ? 'up' : 'down'}`}>
              {pnl >= 0 ? '+' : ''}
              {pnlPct}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

