'use client';

import { useEffect, useRef, useState } from 'react';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';
import { LiveState } from '@/types';

// Faster than the screen-wide refresh: a call starts and ends within a minute or two
const POLL_MS = 3000;

function clock(seconds: number) {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export default function LiveCallsPanel() {
  const { refresh, pauseBatch, canAct } = useApp();
  const [live, setLive] = useState<LiveState | null>(null);
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);
  const lastKey = useRef('');

  useEffect(() => {
    let stopped = false;
    const load = async () => {
      try {
        const next = await api<LiveState>('/live');
        if (stopped) return;
        setLive(next);
        setTick(0);
        setFailed(false);
        // A call started or ended: reload the batches so their outcomes show at once
        const key = `${next.live.map((l) => `${l.callId}:${l.state}`).join(',')}|${next.waiting}`;
        if (lastKey.current && key !== lastKey.current) refresh();
        lastKey.current = key;
      } catch {
        if (!stopped) setFailed(true);
      }
    };
    load();
    const poll = setInterval(load, POLL_MS);
    // Timers on screen count up between polls
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => {
      stopped = true;
      clearInterval(poll);
      clearInterval(timer);
    };
  }, [refresh]);

  const d = live?.dialer || {};
  const status = failed
    ? { cls: 'c-red', text: 'Live view unavailable — cannot reach the RIA server' }
    : !live
    ? { cls: 'c-grey', text: 'Loading…' }
    : d.configured === false
    ? { cls: 'c-red', text: 'Dialer not set up (Vobiz trunk missing)' }
    : d.running === false
    ? { cls: 'c-red', text: `Dialer stopped${d.error ? `: ${d.error}` : ''}` }
    : d.paused
    ? { cls: 'c-gold', text: 'Dialer paused on the server — no calls go out' }
    : d.in_calling_hours === false
    ? { cls: 'c-gold', text: `Outside calling hours (${d.calling_hours}) — calls wait until they open` }
    : { cls: 'c-green', text: `Dialer ready · one call at a time · ${d.calling_hours}` };

  const onCall = live?.live || [];
  const upNext = live?.next || [];

  return (
    <div className="card" style={{ marginBottom: '18px' }} data-testid="live-calls">
      <div className="card-h">
        <h3>Live Calls</h3>
        <span className="sub">Who RIA is on the phone with right now, and who is next</span>
        <div className="r">
          <span className={`chip ${status.cls}`} data-testid="dialer-status">{status.text}</span>
        </div>
      </div>
      <div className="card-b">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
          <div>
            <div className="meta" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', marginBottom: '8px' }}>
              On the phone now ({onCall.length})
            </div>
            {onCall.length === 0 ? (
              <div className="meta" style={{ padding: '14px', background: 'var(--surface-2)', borderRadius: '8px' }} data-testid="no-live-call">
                No call right now.
              </div>
            ) : (
              onCall.map((c) => (
                <div
                  key={c.callId}
                  data-testid="live-call"
                  style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    marginBottom: '8px',
                    border: `1px solid ${c.state === 'on_call' ? '#BFE0CD' : '#F0D9A8'}`,
                    background: c.state === 'on_call' ? 'var(--green-soft)' : 'var(--gold-soft)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                    <div>
                      <b style={{ fontSize: '15px' }}>{c.name}</b>
                      {c.business && c.business !== c.name && <span className="meta"> · {c.business}</span>}
                      <div className="mono" style={{ fontSize: '12px', marginTop: '2px' }}>{c.ph}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span className={`chip ${c.state === 'on_call' ? 'c-green live' : 'c-gold'}`}>
                        {c.state === 'on_call' ? 'On call' : 'Ringing…'}
                      </span>
                      <div className="num" style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px' }}>
                        {clock(c.seconds + tick)}
                      </div>
                    </div>
                  </div>
                  <div className="meta" style={{ fontSize: '12px', marginTop: '6px' }}>
                    {c.invoice} · ₹{c.amount.toLocaleString('en-IN')}
                    {c.batchId && <> · {c.batchName || c.batchId}</>}
                  </div>
                  {c.batchId && canAct('calls') && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ marginTop: '8px' }}
                      onClick={() => pauseBatch(c.batchId as string)}
                    >
                      ⏸ Pause this batch after this call
                    </button>
                  )}
                </div>
              ))
            )}
          </div>

          <div>
            <div className="meta" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', marginBottom: '8px' }}>
              Up next ({live?.waiting ?? 0} waiting)
            </div>
            {upNext.length === 0 ? (
              <div className="meta" style={{ padding: '14px', background: 'var(--surface-2)', borderRadius: '8px' }} data-testid="no-next-call">
                Nobody waiting. Import a call sheet and press 📞 Start calling.
              </div>
            ) : (
              <ol style={{ margin: 0, paddingLeft: '20px' }} data-testid="next-calls">
                {upNext.map((n) => (
                  <li key={n.callId} style={{ marginBottom: '6px' }}>
                    <b>{n.name}</b> <span className="mono" style={{ fontSize: '12px' }}>{n.ph}</span>
                    {n.dialNow && <span className="chip c-blue" style={{ marginLeft: '6px' }}>Call now</span>}
                    <div className="meta" style={{ fontSize: '12px' }}>
                      {n.invoice} · ₹{n.amount.toLocaleString('en-IN')}
                      {n.batchId && <> · {n.batchName || n.batchId}</>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
