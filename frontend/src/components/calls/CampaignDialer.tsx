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
          <div style={{ flex: '1 1 520px', minWidth: 0 }}>
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
                  {all.map((r) => {
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
