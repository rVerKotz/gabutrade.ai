'use client';

import { Portfolio } from '@/types/trading';

interface PortfolioProps {
  portfolio: Portfolio;
  // Menggunakan objek prices untuk menampung harga dari API (misal: { BTC: 65000, ETH: 3200 })
  prices: Record<string, number>;
  // initialCapital sekarang diterima sebagai prop (bisa bersumber dari Payment Gateway atau saldo akun)
  initialCapital: number;
}

export default function PortfolioPanel({ portfolio, prices, initialCapital }: PortfolioProps) {
  // Mengambil harga terkini dari data API (via props prices)
  const btcPrice = prices['BTC'] || prices['XBT'] || 0;
  const ethPrice = prices['ETH'] || 0;

  const btcUSD = btcPrice * portfolio.BTC;
  const ethUSD = ethPrice * portfolio.ETH;
  const total = portfolio.USD + btcUSD + ethUSD;
  
  // Kalkulasi Profit & Loss berdasarkan modal awal yang dinamis
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
            <div className={`pf-pnl ${portfolio.BTC > 0 ? 'up' : ''}`}>
              {portfolio.BTC > 0 ? '▲ Posisi Aktif' : 'Kosong'}
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
            <div className={`pf-pnl ${portfolio.ETH > 0 ? 'up' : ''}`}>
              {portfolio.ETH > 0 ? '▲ Posisi Aktif' : 'Kosong'}
            </div>
          </div>
        </div>

        <div
          className="pf-item"
          style={{ 
            borderColor: pnl >= 0 ? '#00d4aa44' : '#ff4d6d44',
            background: pnl >= 0 ? 'rgba(0, 212, 170, 0.05)' : 'rgba(255, 77, 109, 0.05)'
          }}
        >
          <div>
            <div className="pf-coin" style={{ color: 'var(--amber)' }}>
              TOTAL P&L
            </div>
            <div className="pf-amount">Modal: ${initialCapital.toLocaleString()}</div>
          </div>
          <div>
            <div className="pf-value" style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {pnl >= 0 ? '+' : ''}${pnl.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </div>
            <div className={`pf-pnl ${pnl >= 0 ? 'up' : 'down'}`}>
              {pnl >= 0 ? '▲' : '▼'} {pnlPct}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}