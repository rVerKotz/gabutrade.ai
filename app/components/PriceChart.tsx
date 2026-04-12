'use client';

import { useEffect, useRef } from 'react';
import { Trade, clamp } from '@/types/trading';

interface PriceChartProps {
  priceHistory: number[];
  tradeLog: Trade[];
}

export default function PriceChart({ priceHistory, tradeLog }: PriceChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let mouseX: number | null = null;
    let mouseY: number | null = null;

    const render = () => {
      const W = canvas.offsetWidth || 600;
      const H = 200;
      canvas.width = W;
      canvas.height = H;

      ctx.clearRect(0, 0, W, H);

      // Filter out zeros and keep last 60 ticks
      const data = priceHistory.filter((v) => v > 0).slice(-60);

      // Safety net: waiting screen
      if (data.length < 2) {
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
          const y = (H / 4) * i;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(W, y);
          ctx.stroke();
        }
        ctx.fillStyle = 'var(--dim)';
        ctx.font = '12px monospace';
        ctx.fillText('WAITING FOR PRICE STREAM...', 10, 20);
        return;
      }

      const minP = Math.min(...data) * 0.999;
      const maxP = Math.max(...data) * 1.001;
      const range = maxP - minP || 1;

      const px = (i: number) => (i / Math.max(1, data.length - 1)) * W;
      const py = (v: number) => H - ((v - minP) / range) * H;

      const up = data[data.length - 1] >= data[0];

      // Draw Gradient
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, up ? '#00d4aa30' : '#ff4d6d30');
      grad.addColorStop(1, '#00000000');
      
      ctx.beginPath();
      data.forEach((v, i) => i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v)));
      ctx.lineTo(px(data.length - 1), H);
      ctx.lineTo(0, H);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Draw Line
      ctx.beginPath();
      ctx.strokeStyle = up ? '#00d4aa' : '#ff4d6d';
      ctx.lineWidth = 2;
      data.forEach((v, i) => i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v)));
      ctx.stroke();

      // Draw Order Markers
      tradeLog
        .filter((t) => t.price > 0)
        .slice(-10)
        .forEach((t: Trade, idx: number) => {
          const x = px(clamp(data.length - 10 + idx, 0, data.length - 1));
          const y = py(clamp(t.price, minP, maxP));
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = t.side === 'BUY' ? '#00d4aa' : '#ff4d6d';
          ctx.fill();
          ctx.strokeStyle = '#000';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        });

      // --- NEW: INTERACTIVE HOVER CROSSHAIR ---
      if (mouseX !== null && data.length >= 2) {
        // Find closest data point based on mouse X position
        const hoverIndex = Math.round((mouseX / W) * (data.length - 1));
        const safeIndex = clamp(hoverIndex, 0, data.length - 1);
        const crossX = px(safeIndex);
        const crossY = py(data[safeIndex]);

        // Draw Vertical Crosshair Line
        ctx.beginPath();
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = 'rgba(255,255,255,0.4)';
        ctx.lineWidth = 1;
        ctx.moveTo(crossX, 0);
        ctx.lineTo(crossX, H);
        ctx.stroke();
        ctx.setLineDash([]); // reset dash

        // Draw Hover Dot
        ctx.beginPath();
        ctx.arc(crossX, crossY, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.strokeStyle = up ? '#00d4aa' : '#ff4d6d';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw Tooltip Box
        const priceLabel = '$' + data[safeIndex].toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const tooltipW = 80;
        const tooltipH = 26;
        
        // Ensure tooltip stays within canvas bounds
        let toolX = crossX - tooltipW / 2;
        if (toolX < 5) toolX = 5;
        if (toolX + tooltipW > W - 5) toolX = W - tooltipW - 5;
        
        let toolY = crossY - 35;
        if (toolY < 5) toolY = crossY + 15; // flip below if too high

        ctx.fillStyle = 'rgba(15, 15, 20, 0.9)'; // Dark background
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(toolX, toolY, tooltipW, tooltipH, 4);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.font = '12px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(priceLabel, toolX + tooltipW / 2, toolY + tooltipH / 2);
      }
    };

    // Event listeners to track mouse without React re-renders
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
      render(); // instantly redraw
    };

    const handleMouseLeave = () => {
      mouseX = null;
      mouseY = null;
      render(); // erase crosshair
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseleave', handleMouseLeave);

    render(); // Initial draw

    // Cleanup
    return () => {
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [priceHistory, tradeLog]);

  return (
    <div className="chart-container" style={{ width: '100%', height: '200px', position: 'relative', cursor: 'crosshair' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
    </div>
  );
}