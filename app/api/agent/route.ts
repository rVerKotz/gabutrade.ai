import { NextResponse } from 'next/server';

const getBaseUrl = () => {
  // Always use Railway. We removed the Vercel override so your 
  // frontend doesn't accidentally talk to the wrong server in production.
  const url = process.env.PYTHON_API_URL || 'https://gabutradeaillm-production.up.railway.app';
  return url.endsWith('/') ? url.slice(0, -1) : url;
};

export async function GET() {
  try {
    const response = await fetch(`${getBaseUrl()}/status`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(4000) 
    });

    if (!response.ok) throw new Error('Bridge did not respond properly');

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { 
        status: 'offline', 
        thought_process: [
          '⚠️ Connection to Python Trading Agent lost or offline.',
          `Attempted to reach: ${getBaseUrl()}`,
          'Check Railway logs.'
        ],
        portfolio: { 
          balance: 10000,
          total_unrealized_pnl: 0, 
          open_position_count: 0,
          open_positions: [] 
        },
        prices: { 'BTC': 0, 'ETH': 0 },
        config: { mode: 'paper' }
      },
      { status: 503 }
    );
  }
}

export async function POST() {
  try {
    const response = await fetch(`${getBaseUrl()}/agent/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json({ error: 'Failed to start Agent' }, { status: 500 });
  }
}

export async function DELETE() {
  try {
    const response = await fetch(`${getBaseUrl()}/agent/stop`, {
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' },
    });
    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json({ error: 'Failed to stop Agent' }, { status: 500 });
  }
}