'use client';

import { useApp } from '@/context/AppContext';

export default function CallsChart() {
  const { trend: TREND } = useApp();
  // Round the top of the scale up to a tidy number, at least 10
  const peak = Math.max(10, ...TREND.map((t) => t.placed));
  const maxVal = Math.ceil(peak / 10) * 10;
  const h = 130;
  const w = 520;
  const step = (w - 70) / Math.max(1, TREND.length - 1);
  const total = TREND.reduce((a, t) => ({ placed: a.placed + t.placed, conn: a.conn + t.conn, ptp: a.ptp + t.ptp }), { placed: 0, conn: 0, ptp: 0 });
  const pct = (n: number, of: number) => (of ? ((n / of) * 100).toFixed(1) : '0.0');

  const ptsPlaced = TREND.map((t, i) => `${45 + i * step},${150 - (t.placed / maxVal) * h}`).join(' ');
  const ptsConn = TREND.map((t, i) => `${45 + i * step},${150 - (t.conn / maxVal) * h}`).join(' ');
  const ptsPtp = TREND.map((t, i) => `${45 + i * step},${150 - (t.ptp / maxVal) * h}`).join(' ');

  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${w} 180`} aria-label="Call volume trend chart">
        <line className="gl" x1="40" y1="20" x2={w - 10} y2="20" />
        <line className="gl" x1="40" y1="63" x2={w - 10} y2="63" />
        <line className="gl" x1="40" y1="106" x2={w - 10} y2="106" />
        <line className="gl" x1="40" y1="150" x2={w - 10} y2="150" />

        <text x="10" y="24">{maxVal}</text>
        <text x="10" y="67">{Math.round((maxVal * 2) / 3)}</text>
        <text x="10" y="110">{Math.round(maxVal / 3)}</text>
        <text x="10" y="153">0</text>

        <polyline fill="none" stroke="var(--navy)" strokeWidth="2.5" points={ptsPlaced} />
        <polyline fill="none" stroke="var(--blue)" strokeWidth="2.5" points={ptsConn} />
        <polyline fill="none" stroke="var(--green)" strokeWidth="2.5" points={ptsPtp} />

        {TREND.map((t, i) => {
          const x = 45 + i * step;
          const yPlaced = 150 - (t.placed / maxVal) * h;
          const yConn = 150 - (t.conn / maxVal) * h;
          const yPtp = 150 - (t.ptp / maxVal) * h;
          return (
            <g key={i}>
              <circle cx={x} cy={yPlaced} r="3.5" fill="var(--navy)" />
              <circle cx={x} cy={yConn} r="3.5" fill="var(--blue)" />
              <circle cx={x} cy={yPtp} r="3.5" fill="var(--green)" />
              <text x={x} y="170" textAnchor="middle">
                {t.d}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="legend">
        <span>
          <i style={{ background: 'var(--navy)' }} /> Placed ({total.placed.toLocaleString('en-IN')} total)
        </span>
        <span>
          <i style={{ background: 'var(--blue)' }} /> Connected ({total.conn.toLocaleString('en-IN')} · {pct(total.conn, total.placed)}%)
        </span>
        <span>
          <i style={{ background: 'var(--green)' }} /> PTP commitments ({total.ptp.toLocaleString('en-IN')} · {pct(total.ptp, total.conn)}%)
        </span>
      </div>
    </div>
  );
}
