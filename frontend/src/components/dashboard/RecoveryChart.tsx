'use client';

import { useApp } from '@/context/AppContext';
import { lakh } from '@/utils/formatters';

export default function RecoveryChart() {
  const { recovery: RECOVERY } = useApp();
  // Scale to the largest week, in steps of ₹3 L so each gridline is a whole lakh
  const peak = Math.max(300000, ...RECOVERY.map((r) => Math.max(r.dem, r.rec)));
  const maxVal = Math.ceil(peak / 300000) * 300000;
  const demTotal = RECOVERY.reduce((a, r) => a + r.dem, 0);
  const recTotal = RECOVERY.reduce((a, r) => a + r.rec, 0);
  const h = 130;
  const w = 520;
  const step = (w - 70) / Math.max(1, RECOVERY.length);

  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${w} 180`} aria-label="Overdue demand vs recovery trend chart">
        <line className="gl" x1="45" y1="20" x2={w - 10} y2="20" />
        <line className="gl" x1="45" y1="63" x2={w - 10} y2="63" />
        <line className="gl" x1="45" y1="106" x2={w - 10} y2="106" />
        <line className="gl" x1="45" y1="150" x2={w - 10} y2="150" />

        <text x="10" y="24">{lakh(maxVal)}</text>
        <text x="10" y="67">{lakh((maxVal * 2) / 3)}</text>
        <text x="10" y="110">{lakh(maxVal / 3)}</text>
        <text x="10" y="153">0</text>

        {RECOVERY.map((r, i) => {
          const x0 = 55 + i * step;
          const hDem = (r.dem / maxVal) * h;
          const hRec = (r.rec / maxVal) * h;
          return (
            <g key={i}>
              <rect x={x0} y={150 - hDem} width="28" height={hDem} rx="4" fill="var(--track)" />
              <rect x={x0 + 6} y={150 - hRec} width="16" height={hRec} rx="3" fill="var(--green)" />
              <text x={x0 + 14} y="170" textAnchor="middle">
                {r.d}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="legend">
        <span>
          <i style={{ background: 'var(--track-2)' }} /> Called about ({lakh(demTotal)})
        </span>
        <span>
          <i style={{ background: 'var(--green)' }} /> Promised to pay ({lakh(recTotal)})
        </span>
      </div>
    </div>
  );
}
