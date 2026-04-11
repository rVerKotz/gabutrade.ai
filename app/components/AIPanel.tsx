'use client';

import { AILogEntry, TradeSide } from '@/types/trading';

interface AIPanelProps {
  aiLog: AILogEntry[];
  aiActive: boolean;
  onToggleAI: () => void;
  onManualOrder: (side: TradeSide) => void;
}

export default function AIPanel({ aiLog, aiActive, onToggleAI, onManualOrder }: AIPanelProps) {
  return (
    <div className="side-section" style={{ borderBottom: 'none' }}>
      <div className="ai-header">
        <div
          className="ai-dot"
          style={{ background: aiActive ? 'var(--green)' : 'var(--amber)' }}
        />
        <div
          className="ai-status"
          style={{ color: aiActive ? 'var(--green)' : 'var(--amber)' }}
        >
          {aiActive ? 'AI AGENT ACTIVE' : 'AI AGENT STANDBY'}
        </div>
      </div>

      <div className="ai-log">
        {aiLog.length === 0 ? (
          <div className="log-entry info">Menunggu data dari Python...</div>
        ) : (
          aiLog.slice(0, 30).map((entry, i) => (
            <div key={i} className={`log-entry ${entry.type}`}>
              <span className="log-time">{entry.time}</span>
              <span className="log-msg">{entry.msg}</span>
            </div>
          ))
        )}
      </div>

      <div className="controls">
        <button className="btn buy-btn" onClick={() => onManualOrder('BUY')} type="button">
          ▲ BUY
        </button>
        <button className="btn sell-btn" onClick={() => onManualOrder('SELL')} type="button">
          ▼ SELL
        </button>
        <button
          className={`btn ai-btn ${aiActive ? 'active' : ''}`}
          onClick={onToggleAI}
          type="button"
        >
          {aiActive ? '⏹ STOP AI AGENT' : '⚡ START AI AGENT'}
        </button>
      </div>
    </div>
  );
}