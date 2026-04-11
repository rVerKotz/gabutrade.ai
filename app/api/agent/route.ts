// File: app/api/agent/route.ts
import { NextResponse } from 'next/server';

const PYTHON_BRIDGE_URL = 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${PYTHON_BRIDGE_URL}/status`, {
      cache: 'no-store',
    });

    if (!response.ok) throw new Error('Bridge tidak merespon');

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { 
        status: 'offline', 
        thought_process: ['Koneksi ke Trading Agent terputus. Pastikan Python api_bridge.py berjalan.'],
        portfolio: { total_unrealized_pnl: 0, open_position_count: 0 }
      },
      { status: 503 }
    );
  }
}

export async function POST() {
  try {
    const response = await fetch(`${PYTHON_BRIDGE_URL}/agent/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: 'Gagal memulai Agent' }, { status: 500 });
  }
}