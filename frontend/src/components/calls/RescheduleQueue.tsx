'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useApp } from '@/context/AppContext';
import { ScheduledCallbackItem } from '@/types';
import RescheduleModal from './RescheduleModal';

export default function RescheduleQueue() {
  const {
    scheduledCallbacks,
    rescheduleCall,
    triggerImmediateDial,
    cancelScheduledCall,
    addTicket,
    setSelectedRetailerId,
    openModal,
    closeModal,
    config,
  } = useApp();
  // The company's calling rules (Settings), shown in the dialer banner
  const { cooldown, cap, starthour, endhour } = config.rules;
  const clock = (hhmm: string) => {
    const [h, m] = hhmm.split(':').map(Number);
    return `${String(h % 12 || 12).padStart(2, '0')}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
  };

  const [typeFilter, setTypeFilter] = useState('ALL');
  const [query, setQuery] = useState('');

  const activeItems = scheduledCallbacks.filter((c) => c.status !== 'Cancelled');

  const filtered = activeItems.filter((item) => {
    if (typeFilter === 'customer_requested' && item.type !== 'customer_requested') return false;
    if (typeFilter === 'no_lift_retry' && item.type !== 'no_lift_retry') return false;
    if (typeFilter === 'due_now' && !item.isDueNow) return false;
    if (typeFilter === 'exhausted' && item.status !== 'Exhausted') return false;

    if (query) {
      const q = query.toLowerCase();
      if (
        !item.name.toLowerCase().includes(q) &&
        !item.ph.includes(q) &&
        !item.id.toLowerCase().includes(q) &&
        !item.aiNote.toLowerCase().includes(q)
      ) {
        return false;
      }
    }
    return true;
  });

  const countCustomerReq = activeItems.filter((c) => c.type === 'customer_requested').length;
  const countNoLift = activeItems.filter((c) => c.type === 'no_lift_retry' && c.status !== 'Exhausted').length;
  const countDueNow = activeItems.filter((c) => c.isDueNow || c.status === 'Dialing').length;
  const countExhausted = activeItems.filter((c) => c.status === 'Exhausted').length;

  const handleOpenRescheduleModal = (item: ScheduledCallbackItem) => {
    openModal(
      `Reschedule Outbound Call — ${item.name}`,
      <RescheduleModal
        item={item}
        onSave={(id, newTime, note) => rescheduleCall(id, newTime, note)}
        onClose={closeModal}
      />,
      undefined,
      false
    );
  };

  const handleEscalateToTicket = (item: ScheduledCallbackItem) => {
    addTicket({
      cat: 'Repeated No-Lift / Exhausted Attempts',
      cust: item.name,
      who: 'CE — Field Team',
      src: item.sourceCallId || item.id,
    });
  };

  return (
    <div className="reschedule-queue-container">
      {/* Autonomous System Status Banner */}
      <div
        className="card"
        style={{
          marginBottom: '16px',
          background: 'linear-gradient(135deg, #0A1B39 0%, #152A52 100%)',
          color: '#FFFFFF',
          padding: '16px 20px',
          border: '1px solid #1E3A6E',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#10B981',
                boxShadow: '0 0 10px #10B981',
                animation: 'pulse 2s infinite',
              }}
            />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 700, fontSize: '15px', color: '#FFFFFF' }}>
                  Autonomous Dialer Engine (L2 Level Active)
                </span>
                <span
                  className="chip"
                  style={{
                    background: 'rgba(16, 185, 129, 0.2)',
                    color: '#34D399',
                    border: '1px solid #059669',
                    fontSize: '11px',
                    fontWeight: 700,
                  }}
                >
                  ZERO HUMAN EFFORT
                </span>
              </div>
              <div style={{ fontSize: '12px', color: '#94A3B8', marginTop: '2px' }}>
                RIA automatically auto-reschedules unlifted calls for a <b>fast 5-minute retry</b>. Next automated dial in{' '}
                <b style={{ color: '#FCD34D' }}>{cooldown} mins</b>.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <span
              style={{
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#34D399',
                fontWeight: 600,
              }}
            >
              ⚡ No-Lift Retry: <b>Every {cooldown} Mins</b>
            </span>
            <span
              style={{
                background: 'rgba(255,255,255,0.08)',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#E2E8F0',
              }}
            >
              Window: <b>{clock(starthour)} – {clock(endhour)}</b>
            </span>
            <span
              style={{
                background: 'rgba(255,255,255,0.08)',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#E2E8F0',
              }}
            >
              Max: <b>{cap} Attempts</b>
            </span>
          </div>
        </div>
      </div>

      {/* KPI Summary Tiles */}
      <div className="grid g4" style={{ marginBottom: '16px' }}>
        <div
          className="card"
          style={{
            padding: '12px 16px',
            borderLeft: '4px solid var(--blue)',
            cursor: 'pointer',
            background: typeFilter === 'customer_requested' ? 'var(--blue-soft)' : 'var(--surface)',
          }}
          onClick={() => setTypeFilter(typeFilter === 'customer_requested' ? 'ALL' : 'customer_requested')}
        >
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--navy)' }}>
            👤 Customer Callbacks
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--navy)', marginTop: '4px' }}>
            {countCustomerReq} <span style={{ fontSize: '12px', fontWeight: 400 }}>scheduled</span>
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>Explicit customer requests</span>
        </div>

        <div
          className="card"
          style={{
            padding: '12px 16px',
            borderLeft: '4px solid var(--gold)',
            cursor: 'pointer',
            background: typeFilter === 'no_lift_retry' ? 'var(--gold-soft)' : 'var(--surface)',
          }}
          onClick={() => setTypeFilter(typeFilter === 'no_lift_retry' ? 'ALL' : 'no_lift_retry')}
        >
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--gold-ink)' }}>
            🔁 5-Min Auto-Retries (No Lift)
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--gold-ink)', marginTop: '4px' }}>
            {countNoLift} <span style={{ fontSize: '12px', fontWeight: 400 }}>queued</span>
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>Retrying in 5-min fast cycle</span>
        </div>

        <div
          className="card"
          style={{
            padding: '12px 16px',
            borderLeft: '4px solid var(--green)',
            cursor: 'pointer',
            background: typeFilter === 'due_now' ? 'var(--green-soft)' : 'var(--surface)',
          }}
          onClick={() => setTypeFilter(typeFilter === 'due_now' ? 'ALL' : 'due_now')}
        >
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--green-ink)' }}>
            ⚡ Ready / Due Now
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--green-ink)', marginTop: '4px' }}>
            {countDueNow} <span style={{ fontSize: '12px', fontWeight: 400 }}>immediate</span>
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>Dialing in &lt;30 mins</span>
        </div>

        <div
          className="card"
          style={{
            padding: '12px 16px',
            borderLeft: '4px solid var(--red)',
            cursor: 'pointer',
            background: typeFilter === 'exhausted' ? 'var(--red-soft)' : 'var(--surface)',
          }}
          onClick={() => setTypeFilter(typeFilter === 'exhausted' ? 'ALL' : 'exhausted')}
        >
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--red)' }}>
            ⚠️ Max Attempts Reached
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--red)', marginTop: '4px' }}>
            {countExhausted} <span style={{ fontSize: '12px', fontWeight: 400 }}>failed 3x</span>
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>Escalate to field visit</span>
        </div>
      </div>

      {/* Queue Filter Bar */}
      <div className="card" style={{ marginBottom: '16px' }}>
        <div className="filters">
          <input
            type="text"
            placeholder="Search queued calls by retailer name, phone, or notes..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: '320px', padding: '6px 12px', fontSize: '13px' }}
          />

          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="ALL">All Queued Calls ({activeItems.length})</option>
            <option value="customer_requested">Customer Requested Callbacks ({countCustomerReq})</option>
            <option value="no_lift_retry">No-Lift Retries ({countNoLift})</option>
            <option value="due_now">Ready / Due Now ({countDueNow})</option>
            <option value="exhausted">Exhausted ({cap}/{cap} Attempts) ({countExhausted})</option>
          </select>

          <div className="sp">
            <span>
              Showing <b>{filtered.length}</b> of <b>{activeItems.length}</b> scheduled calls
            </span>
          </div>
        </div>
      </div>

      {/* Queue Table */}
      <div className="card">
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Queue ID</th>
                <th>Retailer Account</th>
                <th>Phone Number</th>
                <th>Trigger & Type</th>
                <th>AI Context & Note</th>
                <th>Scheduled Time</th>
                <th>Autonomy</th>
                <th className="right">Actions (Manual Override)</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const isDialing = item.status === 'Dialing';
                const isCompleted = item.status === 'Completed';
                const isExhausted = item.status === 'Exhausted';

                return (
                  <tr key={item.id} style={{ background: isDialing ? '#F0FDF4' : undefined }}>
                    <td className="mono">
                      <span style={{ fontWeight: 600, color: 'var(--navy)' }}>{item.id}</span>
                    </td>
                    <td>
                      <Link
                        href={`/retailers/${item.ret}`}
                        style={{ textDecoration: 'none', color: 'inherit' }}
                        onClick={() => setSelectedRetailerId(item.ret)}
                      >
                        <div className="name link">{item.name}</div>
                        <div className="meta" style={{ fontSize: '11px' }}>
                          ₹{Number(item.outstanding || 0).toLocaleString('en-IN')} outstanding
                        </div>
                      </Link>
                    </td>
                    <td className="mono">{item.ph}</td>
                    <td>
                      {item.type === 'customer_requested' ? (
                        <span className="chip c-blue" title="Explicit customer request">
                          👤 Customer Callback
                        </span>
                      ) : (
                        <span
                          className={`chip ${isExhausted ? 'c-red' : 'c-gold'}`}
                          title={`Attempt ${item.attempt} of ${item.maxAttempts}`}
                        >
                          {isExhausted
                            ? `⚠️ Max Tries (${item.attempt}/${item.maxAttempts})`
                            : `🔁 Retry #${item.attempt}`}
                        </span>
                      )}
                    </td>
                    <td style={{ maxWidth: '300px', fontSize: '12px' }}>
                      <div
                        style={{
                          color: 'var(--t1)',
                          lineHeight: '1.4',
                          background: 'var(--surface-2)',
                          padding: '6px 8px',
                          borderRadius: '4px',
                          border: '1px solid #EEF2F6',
                        }}
                      >
                        {item.aiNote}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--t1)' }}>
                        {item.scheduledTime}
                      </div>
                      <div style={{ marginTop: '2px' }}>
                        {isDialing ? (
                          <span
                            className="chip c-green"
                            style={{ fontWeight: 700, animation: 'pulse 1.5s infinite' }}
                          >
                            📞 Dialing Now...
                          </span>
                        ) : isCompleted ? (
                          <span className="chip c-green">✓ Completed</span>
                        ) : item.isDueNow ? (
                          <span className="chip c-green" style={{ fontWeight: 700 }}>
                            ⚡ {item.relativeDue}
                          </span>
                        ) : (
                          <span className="meta" style={{ fontSize: '11px' }}>
                            ⏰ {item.relativeDue}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="ai-tag">
                        {isExhausted ? 'Needs Field Agent' : '🤖 Auto-Dialing'}
                      </span>
                    </td>
                    <td className="right">
                      <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                        {!isCompleted && !isExhausted && (
                          <button
                            type="button"
                            className={`btn btn-sm ${item.isDueNow ? 'btn-primary' : 'btn-ghost'}`}
                            title="Trigger immediate dial right now ahead of schedule"
                            onClick={() => triggerImmediateDial(item.id)}
                            disabled={isDialing}
                            style={{ fontSize: '12px' }}
                          >
                            {isDialing ? 'Dialing...' : '📞 Dial Now'}
                          </button>
                        )}

                        {!isCompleted && !isExhausted && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            title="Change or shift scheduled time slot"
                            onClick={() => handleOpenRescheduleModal(item)}
                            style={{ fontSize: '12px' }}
                          >
                            ✏️ Edit Time
                          </button>
                        )}

                        {isExhausted && (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => handleEscalateToTicket(item)}
                            style={{ fontSize: '12px' }}
                          >
                            📋 Create Ticket
                          </button>
                        )}

                        {!isCompleted && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            title="Cancel if payment already received"
                            onClick={() => cancelScheduledCall(item.id, 'Retailer paid')}
                            style={{ color: 'var(--t3)', fontSize: '12px' }}
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div style={{ padding: '36px', textAlign: 'center' }}>
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>🎉</div>
            <h4 style={{ margin: '0 0 4px 0' }}>No Pending Callbacks in this filter</h4>
            <p className="meta" style={{ margin: 0 }}>
              All callbacks and retry slots have been cleared or dialed automatically.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
