'use client';

import { useMemo } from 'react';
import { rand } from '@/types/trading';

interface OrderBookProps {
  price: number;
}

export default function OrderBook({ price }: OrderBookProps) {
  const { asks, bids } = useMemo(() => {
    const spread = price * 0.00018;
    const asks = Array.from({ length: 5 }, (_, i) => ({
      price: (price + spread * (5 - i)).toFixed(1),
      qty: rand(0.1, 3).toFixed(3),
      width: rand(10, 95).toFixed(0),
    }));
    const bids = Array.from({ length: 5 }, (_, i) => ({
      price: (price - spread * (i + 1)).toFixed(1),
      qty: rand(0.1, 3).toFixed(3),
      width: rand(10, 95).toFixed(0),
    }));
    return { asks, bids };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Math.round(price / 10)]);

  return (
    <div className="side-section">
      <div className="section-title">Order Book</div>
      <div className="orderbook">
        <div>
          <div className="ob-header">
            <span>ASKS</span>
            <span>QTY</span>
          </div>
          {asks.map((row, i) => (
            <div key={i} className="ob-row ask">
              <div className="ob-bar" style={{ width: `${row.width}%` }} />
              <span className="ob-price">{row.price}</span>
              <span className="ob-qty">{row.qty}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="ob-header">
            <span>BIDS</span>
            <span>QTY</span>
          </div>
          {bids.map((row, i) => (
            <div key={i} className="ob-row bid">
              <div className="ob-bar" style={{ width: `${row.width}%` }} />
              <span className="ob-price">{row.price}</span>
              <span className="ob-qty">{row.qty}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

