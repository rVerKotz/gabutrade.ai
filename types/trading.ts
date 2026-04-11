export type TradeSide = 'BUY' | 'SELL';
export type TradeSource = 'MANUAL' | 'AI-AGENT';
export type LogType = 'buy' | 'sell' | 'analysis' | 'info';
export type SignalClass = 'bull' | 'bear' | 'neut';

export interface TradingState {
  price: number;
  priceHistory: number[];
  volumeHistory: number[];
  prices: Record<string, number>;
  portfolio: Portfolio;
  initialCapital: number;
  tradeLog: Trade[];
  aiLog: AILogEntry[];
  aiActive: boolean;
  isPaper: boolean;
}

export interface AgentPosition {
  pair: string;
  volume: number;
  entry_price: number;
  pnl: number;
}


export interface AgentPortfolio {
  open_positions?: AgentPosition[];
  total_realized_pnl?: number;
  recent_trades?: Trade[];
}

export interface AgentConfig {
  initial_capital?: number;
  mode?: 'paper' | 'live';
}

export interface AgentResponse {
  status: 'online' | 'idle' | 'offline';
  thought_process?: string[];
  prices?: Record<string, number>;
  portfolio?: AgentPortfolio;
  config?: AgentConfig;
}

export interface CheckoutResponse {
  url?: string;
  error?: string;
}

export interface Trade {
  side: TradeSide;
  price: number;
  qty: number;
  source: TradeSource;
  time: string;
}

export interface AILogEntry {
  type: LogType;
  msg: string;
  time: string;
}

export interface Portfolio {
  USD: number;
  BTC: number;
  ETH: number;
}

export interface Signals {
  rsi: number;
  ema: number;
  macd: number;
  bb_up: number;
  bb_lo: number;
  cur: number;
  volRatio: number;
}

export interface OrderBookEntry {
  price: string;
  qty: string;
  width: string;
}

export const rand = (min: number, max: number): number =>
  Math.random() * (max - min) + min;

export const clamp = (v: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, v));

export const now = (): string =>
  new Date().toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

export const calcRSI = (data: number[], period = 14): number => {
  if (data.length < period + 1) return 50;
  let gains = 0,
    losses = 0;
  for (let i = data.length - period; i < data.length; i++) {
    const d = data[i] - data[i - 1];
    if (d > 0) gains += d;
    else losses += -d;
  }
  const rs = gains / (losses || 1);
  return 100 - 100 / (1 + rs);
};

export const calcEMA = (data: number[], period = 20): number => {
  if (data.length < period) return data[data.length - 1];
  const k = 2 / (period + 1);
  let ema = data[data.length - period];
  for (let i = data.length - period + 1; i < data.length; i++) {
    ema = data[i] * k + ema * (1 - k);
  }
  return ema;
};

export const calcMACD = (data: number[]): number => {
  if (data.length < 26) return 0;
  return calcEMA(data, 12) - calcEMA(data, 26);
};

export const getSignals = (priceHistory: number[], volumeHistory: number[], price: number) => {
  const rsi = calcRSI(priceHistory);
  const ema = calcEMA(priceHistory, 20);
  const macd = calcMACD(priceHistory);
  const bb_up = ema + 220;
  const bb_lo = ema - 220;
  const volAvg = volumeHistory.slice(-10).reduce((a, b) => a + b, 0) / 10;
  const volNow = volumeHistory[volumeHistory.length - 1];
  return { rsi, ema, macd, bb_up, bb_lo, cur: price, volRatio: volNow / volAvg };
};

export const seedPriceHistory = (): { prices: number[]; volumes: number[] } => {
  const prices: number[] = [];
  const volumes: number[] = [];
  let p = 65800;
  for (let i = 0; i < 80; i++) {
    p += (Math.random() - 0.48) * 280;
    p = clamp(p, 63000, 71000);
    prices.push(p);
    volumes.push(rand(600, 1400));
  }
  return { prices, volumes };
};

