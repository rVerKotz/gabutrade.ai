'use client';

import { useEffect, useState } from 'react';

interface HeaderProps {
  currentView: 'dashboard' | 'deposit';
  setView: (view: 'dashboard' | 'deposit') => void;
}

export default function Header({ currentView, setView }: HeaderProps) {
  const [clock, setClock] = useState('--:--:--');

  useEffect(() => {
    const update = () =>
      setClock(new Date().toLocaleTimeString('en-GB') + ' WIB');
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="header flex items-center justify-between px-4 sm:px-6 py-2 border-b border-white/10 h-14 sm:h-16">
      <div className="flex items-center gap-4 sm:gap-10 lg:gap-14">
        {/* Logo Section */}
        <div 
          className="logo flex items-center gap-2 cursor-pointer shrink-0" 
          onClick={() => setView('dashboard')}
        >
          <div className="logo-dot" />
          <span className="font-bold tracking-tighter text-xs sm:text-base whitespace-nowrap">
            TRADING<span style={{ color: 'var(--green)' }}>BOT</span>
          </span>
        </div>
        
        {/* Navigation Section */}
        <nav className="flex items-center gap-4 sm:gap-8">
          <button 
            onClick={() => setView('dashboard')}
            className={`transition-colors text-[9px] sm:text-[11px] font-bold tracking-widest whitespace-nowrap ${
              currentView === 'dashboard' ? 'text-[var(--green)]' : 'text-gray-500 hover:text-white'
            }`}
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
          >
            DASHBOARD
          </button>
          <button 
            onClick={() => setView('deposit')}
            className={`transition-colors text-[9px] sm:text-[11px] font-bold tracking-widest flex items-center gap-1 sm:gap-2 whitespace-nowrap ${
              currentView === 'deposit' ? 'text-[var(--green)]' : 'text-gray-500 hover:text-white'
            }`}
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
          >
          DEPOSIT
          </button>
        </nav>
      </div>

      {/* Info Section - Adaptively Hidden */}
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