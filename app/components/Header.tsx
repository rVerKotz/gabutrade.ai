'use client';

import { useEffect, useState } from 'react';

export default function Header() {
  const [clock, setClock] = useState('--:--:--');

  useEffect(() => {
    const update = () => setClock(new Date().toLocaleTimeString('en-GB') + ' UTC');
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="header flex items-center justify-between px-4 sm:px-6 py-2 border-b border-white/10 h-14 sm:h-16">
      <div className="flex items-center gap-4">
        <div className="logo flex items-center gap-2">
          <div className="logo-dot" />
          <span className="font-bold tracking-tighter text-xs sm:text-base whitespace-nowrap">
            TRADING<span style={{ color: 'var(--green)' }}>BOT</span>
          </span>
        </div>

        <div style={{
          background: 'rgba(0,212,170,0.08)',
          border: '1px solid rgba(0,212,170,0.2)',
          borderRadius: '4px',
          padding: '3px 10px',
          fontSize: '9px',
          letterSpacing: '1.5px',
          color: 'var(--green)',
          fontWeight: 700,
        }}>
          PAPER MODE
        </div>
      </div>

      <div className="flex items-center gap-4 lg:gap-8">
        <div className="hidden sm:flex items-center gap-3">
          <div className="pair-badge text-[9px] sm:text-[10px] whitespace-nowrap">XBT / USD</div>
          <div className="text-[9px] sm:text-[10px] text-gray-500 hidden lg:block whitespace-nowrap">
            Live · Kraken API
          </div>
        </div>
        <div className="hidden md:block text-[10px] text-gray-500 border-l border-white/10 pl-4 font-mono whitespace-nowrap">
          {clock}
        </div>
      </div>
    </header>
  );
}