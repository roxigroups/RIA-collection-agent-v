'use client';

import { useApp } from '@/context/AppContext';

export default function ResponseBars() {
  const { resp: RESP, respTotal } = useApp();
  // Avoid 0/0 before the first call of the day
  const RESP_TOTAL = respTotal || 1;
  return (
    <div>
      <div className="stack" style={{ height: '14px', marginBottom: '14px' }}>
        {RESP.map((r) => {
          const pct = ((r.n / RESP_TOTAL) * 100).toFixed(1);
          return (
            <span
              key={r.k}
              style={{
                width: `${pct}%`,
                background: r.c,
              }}
              title={`${r.l}: ${r.n} (${pct}%)`}
            />
          );
        })}
      </div>

      <div className="grid g2" style={{ gap: '10px' }}>
        {RESP.map((r) => {
          const pct = ((r.n / RESP_TOTAL) * 100).toFixed(1);
          return (
            <div
              key={r.k}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 10px',
                border: '1px solid var(--line-2)',
                borderRadius: '8px',
                background: 'var(--surface-2)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                <span
                  style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    background: r.c,
                    flex: 'none',
                  }}
                />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>{r.l}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="num" style={{ fontSize: '14px' }}>
                  {r.n}
                </span>
                <span style={{ fontSize: '11.5px', color: 'var(--t3)', width: '38px', textAlign: 'right' }}>
                  {pct}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
