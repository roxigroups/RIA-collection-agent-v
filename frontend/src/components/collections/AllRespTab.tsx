'use client';

import Link from 'next/link';
import { useApp } from '@/context/AppContext';

export default function AllRespTab({ filterKey }: { filterKey?: string }) {
  const { setSelectedRetailerId, allResp: ALL_RESP } = useApp();

  const filtered = filterKey && filterKey !== 'all'
    ? ALL_RESP.filter((r) => {
        const text = (r.disp + ' ' + r.st).toLowerCase();
        if (filterKey === 'ptp') return text.includes('ptp');
        if (filterKey === 'dispute') return text.includes('dispute');
        if (filterKey === 'already_paid') return text.includes('already paid');
        if (filterKey === 'nolift') return text.includes('not lifted');
        return true;
      })
    : ALL_RESP;

  return (
    <div className="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Retailer Account</th>
            <th>Today’s Captured Response & Disposition</th>
            <th>Category</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((r, i) => (
            <tr key={i}>
              <td>
                <Link
                  href={`/retailers/${r.ret}`}
                  onClick={() => setSelectedRetailerId(r.ret)}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div className="name link">{r.name}</div>
                  <div className="meta">{r.ph} · {r.ret}</div>
                </Link>
              </td>
              <td>
                <div style={{ fontSize: '13.5px' }}>{r.disp}</div>
              </td>
              <td>
                <span className={`chip ${r.sc}`}>{r.st}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
