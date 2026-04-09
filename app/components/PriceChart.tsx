'use client';

import { useEffect, useRef } from 'react';
import { Trade, calcEMA, clamp } from '@/types/trading';

interface PriceChartProps {
  priceHistory: number[];
  tradeLog: Trade[];
}

export default function PriceChart({ priceHistory, tradeLog }: PriceChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const W = canvas.offsetWidth || 600;
    const H = 200;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const data = priceHistory.slice(-60);
    if (data.length < 2) return;

    const min = Math.min(...data) - 300;
    const max = Math.max(...data) + 300;

    const px = (i: number) => (i / (data.length - 1)) * W;
    const py = (v: number) => H - ((v - min) / (max - min)) * H;

    ctx.clearRect(0, 0, W, H);

    // EMA line
    const emaLine = data.map((_, i) => calcEMA(data.slice(0, i + 1), 20));
    ctx.beginPath();
    ctx.strokeStyle = '#f0a50060';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    emaLine.forEach((v, i) => (i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v))));
    ctx.stroke();
    ctx.setLineDash([]);

    // Bollinger Bands
    ctx.strokeStyle = '#58a6ff28';
    ctx.lineWidth = 1;
    (['bb_up', 'bb_lo'] as const).forEach((key) => {
      ctx.beginPath();
      data.forEach((_, i) => {
        const e = calcEMA(data.slice(0, i + 1), 20);
        const v = key === 'bb_up' ? e + 220 : e - 220;
        i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v));
      });
      ctx.stroke();
    });

    // Price fill
    const up = data[data.length - 1] >= data[0];
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, up ? '#00d4aa30' : '#ff4d6d30');
    grad.addColorStop(1, '#00000000');
    ctx.beginPath();
    data.forEach((v, i) => (i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v))));
    ctx.lineTo(px(data.length - 1), H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Price line
    ctx.beginPath();
    ctx.strokeStyle = up ? '#00d4aa' : '#ff4d6d';
    ctx.lineWidth = 1.5;
    data.forEach((v, i) => (i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v))));
    ctx.stroke();

    // AI order markers
    tradeLog.slice(-10).forEach((t: Trade, idx: number) => {
      const x = px(clamp(data.length - 10 + idx, 0, data.length - 1));
      const y = py(clamp(t.price, min, max));
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = t.side === 'BUY' ? '#00d4aacc' : '#ff4d6dcc';
      ctx.fill();
    });
  }, [priceHistory, tradeLog]);

  return (
    <div className="chart-wrap">
      <div className="chart-toolbar">
        <div className="chart-title">PRICE CHART · 1H</div>
        <div className="chart-subtitle">EMA20 · BB · AI Orders</div>
      </div>
      <canvas ref={canvasRef} height={200} style={{ display: 'block', width: '100%' }} />
    </div>
  );
}

