'use client';

import { Portfolio } from '@/types/trading';

interface PortfolioProps {
  portfolio: Portfolio;
  prices: Record<string, number>;
  initialCapital: number;
}

export default function PortfolioPanel({ portfolio, prices, initialCapital }: PortfolioProps) {
  // Mengambil harga terkini dari data API (via props prices)
  const btcPrice = prices['BTC'] || prices['XBT'] || 0;
  const ethPrice = prices['ETH'] || 3000;

  const btcUSD = btcPrice * portfolio.BTC;
  const ethUSD = ethPrice * portfolio.ETH;
  
  // Total Saldo/Balance saat ini
  const total = portfolio.USD + btcUSD + ethUSD;
  
  // Kalkulasi Profit & Loss berdasarkan modal awal
  const pnl = total - initialCapital;
  const pnlPct = initialCapital > 0 ? ((pnl / initialCapital) * 100).toFixed(2) : "0.00";

  return (
    <div className="side-section">
      <div className="section-title">Portofolio</div>
      <div className="portfolio-grid">
        <div className="pf-item">
          <div>
            <div className="pf-coin">USD</div>
            <div className="pf-amount">Saldo Tunai</div>
          </div>
          <div>
            <div className="pf-value">
              ${portfolio.USD.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="pf-pnl" style={{ color: 'var(--dim)' }}>
              Tersedia
            </div>
          </div>
        </div>

        <div className="pf-item">
          <div>
            <div className="pf-coin">BTC</div>
            <div className="pf-amount">{portfolio.BTC.toFixed(4)} BTC</div>
          </div>
          <div>
            <div className="pf-value">
              ${btcUSD.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className={`pf-pnl ${portfolio.BTC > 0 ? 'up' : ''}`}>
              {portfolio.BTC > 0 ? '▲ Posisi Aktif' : 'Kosong'}
            </div>
          </div>
        </div>

        <div className="pf-item">
          <div>
            <div className="pf-coin">ETH</div>
            <div className="pf-amount">{portfolio.ETH.toFixed(4)} ETH</div>
          </div>
          <div>
            <div className="pf-value">
              ${ethUSD.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className={`pf-pnl ${portfolio.ETH > 0 ? 'up' : ''}`}>
              {portfolio.ETH > 0 ? '▲ Posisi Aktif' : 'Kosong'}
            </div>
          </div>
        </div>

        <div
          className="pf-item"
          style={{ 
            borderColor: pnl >= 0 ? '#00d4aa44' : '#ff4d6d44',
            background: pnl >= 0 ? 'rgba(0, 212, 170, 0.05)' : 'rgba(255, 77, 109, 0.05)',
            marginTop: '8px'
          }}
        >
          <div>
            <div className="pf-coin" style={{ color: 'var(--amber)', fontWeight: 700 }}>
              TOTAL SALDO
            </div>
            <div className="pf-amount" style={{ marginTop: '4px' }}>Modal Awal: ${initialCapital.toLocaleString()}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            {/* The Huge number is now the TOTAL BALANCE the AI has */}
            <div className="pf-value" style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)', fontSize: '16px' }}>
              ${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            {/* PnL is shown underneath as a sub-metric */}
            <div className="pf-pnl" style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)', marginTop: '4px' }}>
              P&L: {pnl >= 0 ? '+' : ''}${pnl.toLocaleString('en-US', { maximumFractionDigits: 2 })} ({pnl >= 0 ? '▲' : '▼'}{Math.abs(Number(pnlPct))}%)
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}