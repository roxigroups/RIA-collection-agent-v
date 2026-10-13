'use client';

import Link from 'next/link';
import { useApp } from '@/context/AppContext';

export default function NoLiftTab() {
  const { setSelectedRetailerId, nolift: NOLIFT } = useApp();

  return (
    <div className="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Retailer Account</th>
            <th>Attempts Made</th>
            <th>Last Attempt</th>
            <th>Next Scheduled Attempt</th>
          </tr>
        </thead>
        <tbody>
          {NOLIFT.map((n) => (
            <tr key={n.ret}>
              <td>
                <Link
                  href={`/retailers/${n.ret}`}
                  onClick={() => setSelectedRetailerId(n.ret)}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div className="name link">{n.name}</div>
                  <div className="meta">{n.ph} · {n.ret}</div>
                </Link>
              </td>
              <td>
                <span
                  className="num"
                  style={{
                    color: n.att >= 3 ? 'var(--red)' : 'var(--gold)',
                    fontWeight: 700,
                  }}
                >
                  {n.att} of 3
                </span>
              </td>
              <td className="meta">{n.last}</td>
              <td className="meta" style={{ fontWeight: 600, color: 'var(--t1)' }}>
                {n.next}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
