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
  const [view, setView] = useState<'dashboard' | 'deposit'>('dashboard');
  const [isProcessing, setIsProcessing] = useState(false);
  const [depositError, setDepositError] = useState<string | null>(null);
  
  // State untuk form deposit manual
  const [amount, setAmount] = useState<number>(100);
  const [userBank, setUserBank] = useState('');
  const [userAccountName, setUserAccountName] = useState('');
  const [invoice, setInvoice] = useState<any>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const btcPrice = engine.prices?.['BTC'] || engine.prices?.['XBT'] || engine.price;
  const startPrice = engine.priceHistory[0] ?? btcPrice;
  const pct = startPrice > 0 ? ((btcPrice - startPrice) / startPrice) * 100 : 0;

  const priceDisplay = useMemo(
    () => '$' + btcPrice.toLocaleString('en-US', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    }),
    [btcPrice]
  );

  const handleManualDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userBank || !userAccountName) {
      setDepositError("Mohon isi semua detail bank pengirim.");
      return;
    }

    setIsProcessing(true);
    setDepositError(null);
    try {
      const result = await engine.handleDeposit(amount, userBank, userAccountName);
      if (result.success) {
        setInvoice(result.instructions);
      }
    } catch (err: unknown) {
      setDepositError((err as Error).message || 'Gagal memproses deposit. Silakan coba lagi.');
    } finally {
      setIsProcessing(false);
    }
  };

  if (!mounted) return null;

  const DepositView = () => (
    <div className="dashboard" style={{ 
      justifyContent: 'center', 
      alignItems: 'center', 
      padding: 'clamp(10px, 3vh, 40px)',
      height: 'calc(100vh - 64px)', 
      overflow: 'hidden',
      display: 'flex'
    }}>
      <div className="box" style={{ 
        width: 'min(90vw, 480px)', 
        padding: 'clamp(1.2rem, 4vh, 2rem)',
        textAlign: 'center',
        border: '1px solid var(--border)',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        maxHeight: '100%',
        gap: 'clamp(0.4rem, 1.5vh, 1rem)',
        overflowY: 'auto'
      }}>
        {isProcessing && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0,0,0,0.95)',
            zIndex: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(8px)'
          }}>
            <div className="ai-dot" style={{ width: 'clamp(30px, 5vh, 40px)', height: 'clamp(30px, 5vh, 40px)', background: 'var(--green)', marginBottom: '2vh' }} />
            <div style={{ color: 'var(--green)', fontSize: 'clamp(10px, 1.4vh, 12px)', letterSpacing: '2px', fontWeight: 'bold' }}>
              GENERATING INVOICE...
            </div>
          </div>
        )}

        {!invoice ? (
          <>
            <div>
              <div style={{ 
                display: 'inline-block', 
                padding: 'clamp(8px, 1.5vh, 12px)', 
                borderRadius: '12px', 
                background: 'rgba(0, 212, 170, 0.1)', 
                marginBottom: '1vh' 
              }}>
                <span style={{ fontSize: 'clamp(20px, 3vh, 28px)' }}>🏦</span>
              </div>
              <h2 style={{ fontSize: 'clamp(1.1rem, 2.5vh, 1.4rem)', fontWeight: 'bold', color: 'var(--green)', letterSpacing: '-0.5px', margin: 0 }}>Manual Deposit</h2>
              <p style={{ fontSize: 'clamp(9px, 1.3vh, 11px)', color: 'var(--dim)', marginTop: '0.4vh' }}>Transfer antar bank dengan verifikasi kode unik</p>
            </div>

            {depositError && (
              <div style={{ 
                background: 'rgba(255, 77, 109, 0.1)', 
                border: '1px solid var(--red)', 
                color: 'var(--red)', 
                padding: '1vh 12px', 
                borderRadius: '4px', 
                fontSize: 'clamp(9px, 1.2vh, 11px)', 
                textAlign: 'left'
              }}>
                <strong>Error:</strong> {depositError}
              </div>
            )}

            <form onSubmit={handleManualDeposit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2vh', textAlign: 'left' }}>
              <div>
                <label style={{ fontSize: '10px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>NOMINAL DEPOSIT (USD)</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                  {[100, 500, 1000, 5000].map((amt) => (
                    <button
                      key={amt}
                      type="button"
                      onClick={() => setAmount(amt)}
                      style={{
                        padding: '8px 0',
                        fontSize: '12px',
                        background: amount === amt ? 'var(--green)' : 'rgba(255,255,255,0.05)',
                        color: amount === amt ? 'black' : 'white',
                        border: '1px solid var(--border)',
                        borderRadius: '4px',
                        fontWeight: 'bold'
                      }}
                    >
                      ${amt}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: '10px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>BANK PENGIRIM (MISAL: BCA, MANDIRI)</label>
                <input 
                  type="text" 
                  value={userBank}
                  onChange={(e) => setUserBank(e.target.value)}
                  placeholder="Nama Bank Anda"
                  style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', padding: '10px', fontSize: '12px', borderRadius: '4px' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '10px', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>NAMA PEMILIK REKENING</label>
                <input 
                  type="text" 
                  value={userAccountName}
                  onChange={(e) => setUserAccountName(e.target.value)}
                  placeholder="Sesuai buku tabungan"
                  style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', color: 'white', padding: '10px', fontSize: '12px', borderRadius: '4px' }}
                />
              </div>

              <button 
                type="submit"
                className="btn"
                disabled={isProcessing}
                style={{ 
                  marginTop: '1vh',
                  padding: 'clamp(10px, 1.8vh, 14px)', 
                  fontSize: 'clamp(11px, 1.6vh, 13px)', 
                  background: 'var(--green)',
                  color: 'black',
                  fontWeight: 'bold',
                  opacity: isProcessing ? 0.5 : 1
                }}
              >
                PROSES INVOICE
              </button>
            </form>
          </>
        ) : (
          <div className="text-left" style={{ animation: 'fadeIn 0.3s ease' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--green)', marginBottom: '4px', textAlign: 'center' }}>INVOICE DEPOSIT</h2>
            <p style={{ fontSize: '10px', color: 'var(--dim)', textAlign: 'center', marginBottom: '16px' }}>REF: {invoice.reference_id}</p>
            
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '16px' }}>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '9px', color: 'var(--muted)' }}>BANK TUJUAN</div>
                <div style={{ fontSize: '13px', fontWeight: 'bold' }}>BANK CENTRAL ASIA (BCA)</div>
              </div>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '9px', color: 'var(--muted)' }}>NOMOR REKENING</div>
                <div style={{ fontSize: '16px', fontWeight: 'bold', fontFamily: 'monospace', color: 'white' }}>800-1234-5678</div>
              </div>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '9px', color: 'var(--muted)' }}>ATAS NAMA</div>
                <div style={{ fontSize: '13px', fontWeight: 'bold' }}>GABUTRADE AI TECHNOLOGY</div>
              </div>
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                <div style={{ fontSize: '9px', color: 'var(--amber)', fontWeight: 'bold' }}>JUMLAH TRANSFER (TERMASUK KODE UNIK)</div>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>
                  ${invoice.amount_to_pay.toLocaleString(undefined, { minimumFractionDigits: 3 })}
                </div>
                <p style={{ fontSize: '9px', color: 'var(--amber)', marginTop: '4px', fontStyle: 'italic' }}>
                  PENTING: Transfer harus tepat sampai 3 digit terakhir!
                </p>
              </div>
            </div>

            <button 
              onClick={() => { setInvoice(null); setView('dashboard'); }}
              className="btn"
              style={{ width: '100%', padding: '12px', fontSize: '12px', fontWeight: 'bold', background: 'var(--green)', color: 'black' }}
            >
              KONFIRMASI SUDAH TRANSFER
            </button>
            <button 
              onClick={() => setInvoice(null)}
              style={{ width: '100%', background: 'none', border: 'none', color: 'var(--dim)', fontSize: '10px', textDecoration: 'underline', marginTop: '12px', cursor: 'pointer' }}
            >
              Ubah detail pengirim
            </button>
          </div>
        )}

        <button 
          disabled={isProcessing}
          onClick={() => { setInvoice(null); setView('dashboard'); }}
          style={{ 
            marginTop: '1vh', 
            width: '100%', 
            background: 'none', 
            border: 'none',
            color: 'var(--dim)',
            fontSize: 'clamp(9px, 1.4vh, 11px)',
            textDecoration: 'underline',
            cursor: 'pointer'
          }}
        >
          Cancel and return to dashboard
        </button>
      </div>
    </div>
  );

  return (
    <>
      <Header currentView={view} setView={setView} />
      
      {view === 'dashboard' ? (
        <div className="dashboard">
          <div className="main-panel">
            <div className="price-hero">
              <div className="price-main">{priceDisplay}</div>
              <div className={`price-change ${pct >= 0 ? 'up' : 'down'}`}>
                {pct >= 0 ? '▲' : '▼'} {Math.abs(pct).toFixed(2)}%
              </div>
            </div>

            <div className="stats-row">
              <div className="stat">
                <div className="stat-label">MODE EKSEKUSI</div>
                <div className="stat-value" style={{ color: 'var(--amber)' }}>
                  {engine.isPaper ? 'SIMULASI (PAPER)' : 'LIVE TRADING'}
                </div>
              </div>
              <div className="stat">
                <div className="stat-label">STATUS AGEN AI</div>
                <div className="stat-value" style={{ color: engine.aiActive ? 'var(--green)' : 'var(--red)' }}>
                  {engine.aiActive ? 'AKTIF & MENGAMATI' : 'BERHENTI'}
                </div>
              </div>
              <div className="stat">
                <div className="stat-label">MODAL AWAL</div>
                <div className="stat-value">
                  ${engine.initialCapital.toLocaleString()}
                </div>
              </div>
            </div>

            <PriceChart priceHistory={engine.priceHistory} tradeLog={engine.tradeLog} />
            <SignalBar priceHistory={engine.priceHistory} volumeHistory={engine.volumeHistory} price={btcPrice} />

            <div className="box">
              <div className="box-header">Aktivitas Terakhir (Live dari Kraken)</div>
              <div className="box-body scrollable">
                {engine.tradeLog.length === 0 ? (
                  <div style={{ color: 'var(--dim)', textAlign: 'center', padding: '12px' }}>
                    Belum ada riwayat transaksi dari agen...
                  </div>
                ) : (
                  engine.tradeLog.slice(0, 20).map((trade: Trade, index: number) => (
                    <div key={index} className="trade-row">
                      <span style={{ color: trade.side === 'BUY' ? 'var(--green)' : 'var(--red)' }}>
                        {trade.side === 'BUY' ? '▲' : '▼'} {trade.side}
                      </span>
                      <span>${trade.price.toLocaleString()}</span>
                      <span style={{ color: 'var(--dim)' }}>{trade.qty} {trade.pair?.split('/')[0] || 'XBT'}</span>
                      <span style={{ color: 'var(--dim)', fontSize: '9px' }}>{trade.time}</span>
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
              prices={engine.prices} 
              initialCapital={engine.initialCapital}
            />
            <AIPanel
              aiLog={engine.aiLog}
              aiActive={engine.aiActive}
              onToggleAI={engine.toggleAI}
              onManualOrder={engine.manualOrder}
            />
          </div>
        </div>
      ) : (
        <DepositView />
      )}
    </>
  );
}