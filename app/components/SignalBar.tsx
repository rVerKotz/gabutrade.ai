'use client';

import { useMemo } from 'react';
import { Signals, SignalClass, getSignals } from '@/types/trading';

interface SignalBarProps {
  priceHistory: number[];
  volumeHistory: number[];
  price: number;
}

interface SignalItem {
  label: string;
  value: string;
  cls: SignalClass;
}

export default function SignalBar({ priceHistory, volumeHistory, price }: SignalBarProps) {
  const signals: SignalItem[] = useMemo(() => {
    if (priceHistory.length < 2) return [];
    const s: Signals = getSignals(priceHistory, volumeHistory, price);

    const bbPos = (s.cur - s.bb_lo) / (s.bb_up - s.bb_lo);

    return [
      {
        label: 'RSI',
        value: s.rsi.toFixed(0),
        cls: s.rsi < 35 ? 'bull' : s.rsi > 65 ? 'bear' : 'neut',
      },
      {
        label: 'MACD',
        value: s.macd > 0 ? '▲ POS' : '▼ NEG',
        cls: s.macd > 0 ? 'bull' : 'bear',
      },
      {
        label: 'BOLLINGER',
        value: bbPos < 0.25 ? 'LOW' : bbPos > 0.75 ? 'HIGH' : 'MID',
        cls: bbPos < 0.25 ? 'bull' : bbPos > 0.75 ? 'bear' : 'neut',
      },
      {
        label: 'EMA-20',
        value: s.cur > s.ema ? 'ABOVE' : 'BELOW',
        cls: s.cur > s.ema ? 'bull' : 'bear',
      },
      {
        label: 'VOL TREND',
        value: s.volRatio > 1.2 ? '↑ HIGH' : s.volRatio < 0.8 ? '↓ LOW' : '→ NORM',
        cls: s.volRatio > 1.2 ? 'bull' : 'neut',
      },
    ];
  }, [priceHistory, volumeHistory, price]);

  return (
    <div className="signal-bar">
      {signals.map((sig) => (
        <div key={sig.label} className="signal-item">
          <div className="signal-label">{sig.label}</div>
          <div className={`signal-val ${sig.cls}`}>{sig.value}</div>
        </div>
      ))}
    </div>
  );
}

