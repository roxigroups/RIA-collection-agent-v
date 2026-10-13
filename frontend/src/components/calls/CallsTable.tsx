'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useApp } from '@/context/AppContext';

export default function CallsTable() {
  const { calls, setSelectedCallId, setSelectedRetailerId } = useApp();
  const [dispFilter, setDispFilter] = useState('ALL');
  const [langFilter, setLangFilter] = useState('ALL');
  const [query, setQuery] = useState('');

  const filtered = calls.filter((c) => {
    if (dispFilter !== 'ALL' && !c.disp.toLowerCase().includes(dispFilter.toLowerCase())) return false;
    if (langFilter !== 'ALL' && c.lang.toLowerCase() !== langFilter.toLowerCase()) return false;
    if (query) {
      const q = query.toLowerCase();
      if (!c.name.toLowerCase().includes(q) && !c.ph.includes(q) && !c.id.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const getDispChipClass = (disp: string) => {
    const d = disp.toLowerCase();
    if (d.includes('ptp')) return 'c-green';
    if (d.includes('dispute') || d.includes('broken')) return 'c-red';
    if (d.includes('not lifted')) return 'c-gold';
    if (d.includes('already paid')) return 'c-blue';
    if (d.includes('person')) return 'c-teal';
    return 'c-grey';
  };

  return (
    <div className="card">
      <div className="filters">
        <input
          type="text"
          placeholder="Filter calls by name, phone or ID..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ maxWidth: '280px', padding: '6px 10px', fontSize: '13px' }}
        />

        <select value={dispFilter} onChange={(e) => setDispFilter(e.target.value)}>
          <option value="ALL">All Dispositions ({calls.length})</option>
          <option value="PTP">PTP Commitments</option>
          <option value="Dispute">Payment Disputes</option>
          <option value="Not lifted">Calls Not Lifted</option>
          <option value="Broken">Broken PTPs</option>
        </select>

        <select value={langFilter} onChange={(e) => setLangFilter(e.target.value)}>
          <option value="ALL">All Languages</option>
          <option value="Telugu">Telugu</option>
          <option value="Hindi">Hindi</option>
          <option value="English">English</option>
          <option value="Tamil">Tamil</option>
          <option value="Kannada">Kannada</option>
        </select>

        <div className="sp">
          <span>Showing <b>{filtered.length}</b> of <b>{calls.length}</b> calls</span>
        </div>
      </div>

      <div className="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th>Call ID</th>
              <th>Retailer Account</th>
              <th>Phone</th>
              <th>Time</th>
              <th>Lang</th>
              <th>Duration</th>
              <th>Disposition & Outcome</th>
              <th className="right">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr
                key={c.id}
                onClick={() => {
                  setSelectedCallId(c.id);
                  setSelectedRetailerId(c.ret);
                }}
              >
                <td className="mono">
                  <Link
                    href={`/calls/${c.id}`}
                    className="link"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedCallId(c.id);
                      setSelectedRetailerId(c.ret);
                    }}
                  >
                    {c.id}
                  </Link>
                </td>
                <td>
                  <Link
                    href={`/retailers/${c.ret}`}
                    style={{ textDecoration: 'none', color: 'inherit' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedRetailerId(c.ret);
                    }}
                  >
                    <div className="name link">{c.name}</div>
                  </Link>
                </td>
                <td className="mono">{c.ph}</td>
                <td className="meta">{c.time}</td>
                <td>
                  <span className="chip c-blue">{c.lang}</span>
                </td>
                <td className="num">{c.dur}</td>
                <td>
                  <span className={`chip ${getDispChipClass(c.disp)}`}>{c.disp}</span>
                </td>
                <td className="right">
                  <Link href={`/calls/${c.id}`}>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCallId(c.id);
                        setSelectedRetailerId(c.ret);
                      }}
                    >
                      Listen & View
                    </button>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
