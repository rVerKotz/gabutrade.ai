'use client';

import { useEffect, useState } from 'react';

export default function Header() {
  const [clock, setClock] = useState('--:--:--');

  useEffect(() => {
    const update = () =>
      setClock(new Date().toLocaleTimeString('en-GB') + ' WIB');
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="header">
      <div className="logo">
        <div className="logo-dot" />
        TRADING<span style={{ color: 'var(--green)' }}>BOT</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div className="pair-badge">XBT / USD</div>
        <div style={{ fontSize: '10px', color: 'var(--muted)' }}>Simulated · Kraken</div>
      </div>
      <div style={{ fontSize: '10px', color: 'var(--dim)' }}>{clock}</div>
    </header>
  );
}

