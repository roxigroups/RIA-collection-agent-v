'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';
import { CallBatch, DialerStatus, SheetRow } from '@/types';

// A call starts and ends within a minute or two: poll faster than the screen-wide refresh
const POLL_MS = 3000;

function clock(seconds: number) {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('');
}

function outcomeChip(outcome: string) {
  const o = outcome.toLowerCase();
  if (o.includes('ptp')) return 'c-green';
  if (o.includes('callback') || o.includes('already paid') || o.includes('request')) return 'c-blue';
  if (o.includes('dispute') || o.includes('refused') || o.includes('do not call')) return 'c-red';
  if (o.includes('not lifted') || o.includes('busy')) return 'c-gold';
  return 'c-grey';
}

// The campaign as a phone dialer: the call on the line, big call / pause buttons,
// and the whole imported sheet with where each row's call is
export default function CampaignDialer({ batch }: { batch: CallBatch }) {
  const { startBatch, pauseBatch, dialCallNow, removeSheetRow, callRetailer, canAct, refresh, setSelectedCallId, retailers } = useApp();
  const [rows, setRows] = useState<SheetRow[] | null>(null);
  const [dialer, setDialer] = useState<DialerStatus>({});
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'PTP' | 'WAITING' | 'UNANSWERED' | 'DISPUTES' | 'PAID'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const lastKey = useRef('');

  useEffect(() => {
    let stopped = false;
    const load = async () => {
      try {
        const res = await api<{ rows: SheetRow[]; dialer: DialerStatus }>(`/batches/${batch.id}/sheet`);
        if (stopped) return;
        setRows(res.rows);
        setDialer(res.dialer);
        setTick(0);
        setFailed(false);
        // A call started or ended: reload the batch totals and buttons
        const key = res.rows.map((r) => `${r.callId}:${r.state}`).join(',');
        if (lastKey.current && key !== lastKey.current) refresh();
        lastKey.current = key;
      } catch {
        if (!stopped) setFailed(true);
      }
    };
    load();
    const poll = setInterval(load, POLL_MS);
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => {
      stopped = true;
      clearInterval(poll);
      clearInterval(timer);
    };
  }, [batch.id, refresh]);

  const all = rows || [];
  const countAll = all.length;
  const countPtp = all.filter((r) => Boolean(r.promised) || (r.outcome && r.outcome.toLowerCase().includes('ptp'))).length;
  const countWaiting = all.filter((r) => r.state === 'queued').length;
  const countUnanswered = all.filter((r) => {
    const o = (r.outcome || '').toLowerCase();
    return o.includes('not lifted') || o.includes('busy') || o.includes('failed') || o.includes('unanswered') || o.includes('no-answer');
  }).length;
  const countDisputes = all.filter((r) => {
    const o = (r.outcome || '').toLowerCase();
    return o.includes('dispute') || o.includes('refused') || o.includes('complaint') || o.includes('wrong-person') || o.includes('wrong number') || o.includes('opt-out');
  }).length;
  const countPaid = all.filter((r) => (r.outcome || '').toLowerCase().includes('already paid')).length;

  const filteredRows = all.filter((r) => {
    if (activeFilter === 'PTP') {
      const isPtp = Boolean(r.promised) || (r.outcome && r.outcome.toLowerCase().includes('ptp'));
      if (!isPtp) return false;
    } else if (activeFilter === 'WAITING') {
      if (r.state !== 'queued') return false;
    } else if (activeFilter === 'UNANSWERED') {
      const o = (r.outcome || '').toLowerCase();
      const isUnans = o.includes('not lifted') || o.includes('busy') || o.includes('failed') || o.includes('unanswered') || o.includes('no-answer');
      if (!isUnans) return false;
    } else if (activeFilter === 'DISPUTES') {
      const o = (r.outcome || '').toLowerCase();
      const isDisp = o.includes('dispute') || o.includes('refused') || o.includes('complaint') || o.includes('wrong-person') || o.includes('wrong number') || o.includes('opt-out');
      if (!isDisp) return false;
    } else if (activeFilter === 'PAID') {
      const o = (r.outcome || '').toLowerCase();
      if (!o.includes('already paid')) return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const nameMatch = r.name && r.name.toLowerCase().includes(q);
      const bizMatch = r.business && r.business.toLowerCase().includes(q);
      const phMatch = r.ph && r.ph.includes(q);
      const invMatch = r.invoice && r.invoice.toLowerCase().includes(q);
      if (!nameMatch && !bizMatch && !phMatch && !invMatch) {
        return false;
      }
    }
    return true;
  });

  const current = all.find((r) => r.state === 'live') || all.find((r) => r.state === 'dialing');
  const waiting = all.filter((r) => r.state === 'queued');
  const upNext = [...waiting].sort((a, b) => Number(b.dialNow) - Number(a.dialNow) || a.row - b.row);
  const called = all.filter((r) => r.state === 'done').length;
  const total = all.filter((r) => r.state !== 'cancelled').length;
  const running = batch.dialState === 'running';
  const allowed = canAct('calls');

  const blocker = failed
    ? 'Cannot reach the RIA server'
    : dialer.paused
    ? 'Dialer paused on the server: no calls go out'
    : dialer.running === false
    ? 'Dialer is not running on the server'
    : dialer.in_calling_hours === false
    ? `Outside calling hours (${dialer.calling_hours})`
    : '';

  const screen = current
    ? {
        who: current,
        line: current.state === 'live' ? `On call · ${clock(current.seconds + tick)}` : `Ringing… ${clock(current.seconds + tick)}`,
        color: current.state === 'live' ? '#34D399' : '#FBBF24',
      }
    : batch.dialState === 'done'
    ? { who: null, line: 'Campaign complete', color: '#93C5FD' }
    : running
    ? { who: upNext[0] || null, line: blocker || 'Dialing next…', color: blocker ? '#FBBF24' : '#93C5FD' }
    : { who: upNext[0] || null, line: batch.dialState === 'paused' ? 'Paused' : 'Ready — press call', color: '#CBD5E1' };

  const press = async (fn: (id: string) => Promise<boolean>) => {
    setBusy(true);
    await fn(batch.id);
    setBusy(false);
  };

  const roundBtn = (bg: string): React.CSSProperties => ({
    width: '64px',
    height: '64px',
    borderRadius: '50%',
    border: 'none',
    background: bg,
    color: '#fff',
    fontSize: '26px',
    cursor: 'pointer',
    boxShadow: '0 6px 16px rgba(0,0,0,.35)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  });

  const retailerId = (r: SheetRow) => retailers.find((x) => x.phone === r.ph)?.id;

  return (
    <div className="card" style={{ marginBottom: '16px' }} data-testid="campaign-dialer">
      <div className="card-h">
        <h3>Campaign Dialer</h3>
        <span className="sub">Calls go one after another, in the order of your sheet</span>
        <div className="r">
          <span className="chip c-blue" data-testid="dialer-progress">
            {called} of {total} called
          </span>
        </div>
      </div>
      <div className="card-b">
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {/* The phone */}
          <div
            style={{
              width: '290px',
              flex: '0 0 290px',
              background: '#0B1220',
              borderRadius: '38px',
              padding: '12px',
              boxShadow: '0 18px 40px rgba(15,23,42,.35)',
              margin: '0 auto',
            }}
          >
            <div
              style={{
                borderRadius: '28px',
                background: 'linear-gradient(180deg, #1E3A8A 0%, #0F172A 100%)',
                color: '#fff',
                padding: '18px 18px 22px',
                minHeight: '460px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
              }}
            >
              <div style={{ width: '70px', height: '5px', borderRadius: '3px', background: '#334155', marginBottom: '14px' }} />
              <div style={{ fontSize: '11px', letterSpacing: '.12em', textTransform: 'uppercase', color: '#93C5FD' }}>
                RIA Dialer
              </div>
              <div style={{ fontSize: '12px', color: '#CBD5E1', marginTop: '2px' }}>{batch.name}</div>

              <div
                style={{
                  width: '92px',
                  height: '92px',
                  borderRadius: '50%',
                  marginTop: '26px',
                  background: '#2563EB',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '32px',
                  fontWeight: 700,
                  boxShadow: current ? `0 0 0 8px ${screen.color}33, 0 0 0 16px ${screen.color}1A` : 'none',
                  transition: 'box-shadow .3s',
                }}
              >
                {screen.who ? initials(screen.who.name) : '☏'}
              </div>
              <div style={{ fontSize: '20px', fontWeight: 700, marginTop: '16px' }} data-testid="dialer-name">
                {screen.who ? screen.who.name : batch.dialState === 'done' ? 'All calls made' : 'Nobody waiting'}
              </div>
              {screen.who && (
                <>
                  <div className="mono" style={{ fontSize: '14px', color: '#CBD5E1', marginTop: '4px' }}>{screen.who.ph}</div>
                  <div style={{ fontSize: '12px', color: '#94A3B8', marginTop: '6px' }}>
                    {screen.who.invoice} · ₹{screen.who.amount.toLocaleString('en-IN')} · due {screen.who.dueDate}
                  </div>
                </>
              )}
              <div style={{ fontSize: '15px', fontWeight: 600, color: screen.color, marginTop: '14px' }} data-testid="dialer-line">
                {screen.line}
              </div>

              {/* Progress through the sheet */}
              <div style={{ width: '100%', marginTop: '18px' }}>
                <div style={{ height: '6px', borderRadius: '3px', background: '#1E293B', overflow: 'hidden' }}>
                  <div style={{ width: `${total ? (called / total) * 100 : 0}%`, height: '100%', background: '#34D399', transition: 'width .4s' }} />
                </div>
                <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '6px' }}>
                  {called} called · {waiting.length} waiting{current ? ' · 1 on the line' : ''}
                </div>
              </div>

              <div style={{ flex: 1 }} />

              {/* Call / pause */}
              {allowed && batch.dialState !== 'done' && (
                <div style={{ display: 'flex', gap: '26px', marginTop: '22px', alignItems: 'center' }}>
                  {running ? (
                    <div>
                      <button
                        type="button"
                        aria-label="Pause calling"
                        data-testid="dialer-pause"
                        disabled={busy}
                        style={roundBtn('#DC2626')}
                        onClick={() => press(pauseBatch)}
                      >
                        ⏸
                      </button>
                      <div style={{ fontSize: '11px', marginTop: '6px', color: '#CBD5E1' }}>Pause</div>
                    </div>
                  ) : (
                    <div>
                      <button
                        type="button"
                        aria-label={batch.dialState === 'paused' ? 'Resume calling' : 'Start calling'}
                        data-testid="dialer-call"
                        disabled={busy || waiting.length === 0}
                        style={roundBtn('#16A34A')}
                        onClick={() => press(startBatch)}
                      >
                        📞
                      </button>
                      <div style={{ fontSize: '11px', marginTop: '6px', color: '#CBD5E1' }}>
                        {batch.dialState === 'paused' ? 'Resume' : 'Call'}
                      </div>
                    </div>
                  )}
                </div>
              )}
              {upNext.length > 0 && (
                <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '14px' }}>
                  Next: <b style={{ color: '#E2E8F0' }}>{(current ? upNext[0] : upNext[1])?.name || '—'}</b>
                </div>
              )}
            </div>
          </div>

          {/* The whole imported sheet */}
          <div style={{ flex: '1 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* Quick Action Pills & Search Input */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                background: 'var(--surface)',
                border: '1px solid var(--line)',
                borderRadius: '8px',
                padding: '12px 14px',
              }}
            >
              {/* Top Quick Action Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                <button
                  type="button"
                  className={`btn btn-sm ${activeFilter === 'ALL' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                  onClick={() => setActiveFilter('ALL')}
                >
                  <span>All Customers</span>
                  <span
                    style={{
                      background: activeFilter === 'ALL' ? 'rgba(255,255,255,0.25)' : 'var(--track)',
                      color: activeFilter === 'ALL' ? '#fff' : 'var(--t2)',
                      padding: '1px 6px',
                      borderRadius: '99px',
                      fontSize: '10.5px',
                    }}
                  >
                    {countAll}
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${activeFilter === 'PTP' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    borderColor: activeFilter === 'PTP' ? undefined : 'var(--green)',
                    color: activeFilter === 'PTP' ? undefined : 'var(--green-ink)',
                  }}
                  onClick={() => setActiveFilter(activeFilter === 'PTP' ? 'ALL' : 'PTP')}
                >
                  <span>🔥 PTP Given</span>
                  <span
                    style={{
                      background: activeFilter === 'PTP' ? 'rgba(255,255,255,0.25)' : 'var(--green-soft)',
                      color: activeFilter === 'PTP' ? '#fff' : 'var(--green-ink)',
                      padding: '1px 6px',
                      borderRadius: '99px',
                      fontSize: '10.5px',
                      fontWeight: 700,
                    }}
                  >
                    {countPtp}
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${activeFilter === 'WAITING' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                  onClick={() => setActiveFilter(activeFilter === 'WAITING' ? 'ALL' : 'WAITING')}
                >
                  <span>⏳ Waiting</span>
                  <span
                    style={{
                      background: activeFilter === 'WAITING' ? 'rgba(255,255,255,0.25)' : 'var(--track)',
                      color: activeFilter === 'WAITING' ? '#fff' : 'var(--t2)',
                      padding: '1px 6px',
                      borderRadius: '99px',
                      fontSize: '10.5px',
                    }}
                  >
                    {countWaiting}
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${activeFilter === 'UNANSWERED' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    borderColor: activeFilter === 'UNANSWERED' ? undefined : 'var(--gold)',
                    color: activeFilter === 'UNANSWERED' ? undefined : 'var(--gold-ink)',
                  }}
                  onClick={() => setActiveFilter(activeFilter === 'UNANSWERED' ? 'ALL' : 'UNANSWERED')}
                >
                  <span>📞 Retries / No Lift</span>
                  <span
                    style={{
                      background: activeFilter === 'UNANSWERED' ? 'rgba(255,255,255,0.25)' : 'var(--gold-soft)',
                      color: activeFilter === 'UNANSWERED' ? '#fff' : 'var(--gold-ink)',
                      padding: '1px 6px',
                      borderRadius: '99px',
                      fontSize: '10.5px',
                      fontWeight: 700,
                    }}
                  >
                    {countUnanswered}
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${activeFilter === 'DISPUTES' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    borderColor: activeFilter === 'DISPUTES' ? undefined : 'var(--red)',
                    color: activeFilter === 'DISPUTES' ? undefined : 'var(--red)',
                  }}
                  onClick={() => setActiveFilter(activeFilter === 'DISPUTES' ? 'ALL' : 'DISPUTES')}
                >
                  <span>⚠️ Disputes & Refusals</span>
                  <span
                    style={{
                      background: activeFilter === 'DISPUTES' ? 'rgba(255,255,255,0.25)' : 'var(--red-soft)',
                      color: activeFilter === 'DISPUTES' ? '#fff' : 'var(--red)',
                      padding: '1px 6px',
                      borderRadius: '99px',
                      fontSize: '10.5px',
                      fontWeight: 700,
                    }}
                  >
                    {countDisputes}
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn btn-sm ${activeFilter === 'PAID' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{
                    borderRadius: '20px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    borderColor: activeFilter === 'PAID' ? undefined : 'var(--blue)',
                    color: activeFilter === 'PAID' ? undefined : 'var(--blue)',
                  }}
                  onClick={() => setActiveFilter(activeFilter === 'PAID' ? 'ALL' : 'PAID')}
                >
                  <span>💳 Already Paid</span>
                  <span
                    style={{
                      background: activeFilter === 'PAID' ? 'rgba(255,255,255,0.25)' : 'var(--blue-soft)',
                      color: activeFilter === 'PAID' ? '#fff' : 'var(--blue)',
                      padding: '1px 6px',
                      borderRadius: '99px',
                      fontSize: '10.5px',
                      fontWeight: 700,
                    }}
                  >
                    {countPaid}
                  </span>
                </button>
              </div>

              {/* Search Bar + Result Count */}
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', flex: '1 1 240px', minWidth: '200px' }}>
                  <span
                    style={{
                      position: 'absolute',
                      left: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      fontSize: '13px',
                      color: 'var(--t2)',
                      pointerEvents: 'none',
                    }}
                  >
                    🔍
                  </span>
                  <input
                    type="text"
                    placeholder="Search by customer name, store, phone, or invoice #..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 10px 6px 32px',
                      fontSize: '12.5px',
                      borderRadius: '6px',
                      border: '1px solid var(--line)',
                      background: 'var(--surface-2)',
                    }}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      style={{
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: 'var(--t2)',
                        cursor: 'pointer',
                        fontSize: '12px',
                        padding: '2px',
                      }}
                      title="Clear search"
                    >
                      ✕
                    </button>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto', fontSize: '12px', color: 'var(--t2)' }}>
                  <span>
                    Showing <b>{filteredRows.length}</b> of <b>{all.length}</b> rows
                  </span>
                  {(activeFilter !== 'ALL' || searchQuery) && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ padding: '2px 8px', fontSize: '11px', color: 'var(--red)' }}
                      onClick={() => {
                        setActiveFilter('ALL');
                        setSearchQuery('');
                      }}
                    >
                      Reset filters
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="tbl-wrap" style={{ maxHeight: '520px', border: '1px solid var(--line)', borderRadius: '8px' }}>
              <table data-testid="sheet-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Customer</th>
                    <th>Invoice</th>
                    <th>Call status</th>
                    <th>Promised</th>
                    <th className="right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows === null && (
                    <tr>
                      <td colSpan={6} className="meta">Loading the sheet…</td>
                    </tr>
                  )}
                  {rows !== null && filteredRows.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--t2)' }}>
                        <div style={{ fontSize: '20px', marginBottom: '6px' }}>🔍</div>
                        <div style={{ fontWeight: 600, color: 'var(--t1)', marginBottom: '4px' }}>No matching customer calls</div>
                        <div style={{ fontSize: '12px' }}>Try adjusting your search terms or filter selection.</div>
                        <div style={{ marginTop: '10px' }}>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                              setActiveFilter('ALL');
                              setSearchQuery('');
                            }}
                          >
                            Reset filters
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                  {filteredRows.map((r) => {
                    const onLine = r.state === 'live' || r.state === 'dialing';
                    return (
                      <tr key={r.row} style={onLine ? { background: '#ECFDF5' } : undefined} data-testid="sheet-row">
                        <td className="num">{r.row}</td>
                        <td>
                          <b>{r.name}</b>
                          {r.business && r.business !== r.name && <span className="meta" style={{ fontSize: '11px' }}> · {r.business}</span>}
                          <div className="mono" style={{ fontSize: '12px', whiteSpace: 'nowrap' }}>{r.ph}</div>
                        </td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          <span className="mono">{r.invoice}</span> · <b className="num">₹{r.amount.toLocaleString('en-IN')}</b>
                          <div className="meta" style={{ fontSize: '11px' }}>due {r.dueDate}</div>
                        </td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          {r.state === 'live' ? (
                            <span className="chip c-green live">On call {clock(r.seconds + tick)}</span>
                          ) : r.state === 'dialing' ? (
                            <span className="chip c-gold">Ringing…</span>
                          ) : r.state === 'queued' ? (
                            <span className={`chip ${r.dialNow ? 'c-blue' : 'c-grey'}`}>{r.dialNow ? 'Next in line' : 'Waiting'}</span>
                          ) : r.state === 'cancelled' ? (
                            <span className="chip c-grey" title={r.notes}>Skipped</span>
                          ) : (
                            <span className={`chip ${outcomeChip(r.outcome)}`} title={r.notes}>
                              {r.outcome || 'Done'}
                              {r.duration ? ` · ${r.duration}` : ''}
                            </span>
                          )}
                        </td>
                        <td className="mono" style={{ fontSize: '12px' }}>
                          {r.promised ? <span className="chip c-green">{r.promised}</span> : <span className="meta">—</span>}
                        </td>
                        <td className="right" style={{ whiteSpace: 'nowrap' }}>
                          {r.state === 'queued' && allowed && (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              data-testid="call-now"
                              disabled={r.dialNow}
                              onClick={() => dialCallNow(r.callId, r.name)}
                            >
                              📞 {r.dialNow ? 'Next' : 'Call now'}
                            </button>
                          )}
                          {r.state === 'queued' && allowed && (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              data-testid="remove-row"
                              title="Take this customer out of the campaign (not called)"
                              style={{ marginLeft: '6px', color: 'var(--red)' }}
                              onClick={() => removeSheetRow(r.callId, r.name)}
                            >
                              ✕
                            </button>
                          )}
                          {r.state === 'done' && allowed && retailerId(r) && (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              data-testid="call-again"
                              style={{ marginRight: '6px' }}
                              onClick={() => callRetailer(retailerId(r) as string)}
                            >
                              📞 Again
                            </button>
                          )}
                          {r.recordId && (
                            <Link href={`/calls/${r.recordId}`} onClick={() => setSelectedCallId(r.recordId)}>
                              <button type="button" className="btn btn-ghost btn-sm">View</button>
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
