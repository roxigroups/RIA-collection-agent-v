'use client';

import Link from 'next/link';
import { useApp } from '@/context/AppContext';
import { EmptyStateView } from '../common/StateViews';
import AudioTranscript from './AudioTranscript';
import ActionButton from '../common/ActionButton';
import { inr } from '@/utils/formatters';

export default function CallDetailView({ callId }: { callId?: string }) {
  const {
    calls,
    retailers,
    scheduledCallbacks,
    selectedCallId,
    setSelectedRetailerId,
    triggerImmediateDial,
    addTicket,
    callRetailer,
    notConnected,
  } = useApp();

  const idToFind = callId || selectedCallId;
  const call = calls.find((c) => c.id === idToFind) || (idToFind ? undefined : calls.find((c) => !c.id.startsWith('Q-')));
  if (!call) {
    return <EmptyStateView screenKey="calldetail" />;
  }
  const retailer = retailers.find((r) => r.id === call.ret || r.name === call.name) || retailers[0];

  const scheduledItem = scheduledCallbacks.find(
    (s) => s.sourceCallId === call.id || s.name === call.name
  );

  const handleCreateTicket = () => {
    addTicket({
      cust: call.name,
      cat: call.disp.includes('Dispute') ? 'Payment dispute' : 'Broken promise',
      st: 'Open',
      src: call.id,
      who: 'Unassigned',
    });
  };

  return (
    <div>
      {scheduledItem && (
        <div
          className="card"
          style={{
            marginBottom: '14px',
            background: 'linear-gradient(90deg, var(--green-soft) 0%, var(--surface) 100%)',
            border: '1px solid #86EFAC',
            padding: '12px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '20px' }}>⏰</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 700, fontSize: '13px', color: '#166534' }}>
                  Autonomous Next Attempt Scheduled
                </span>
                <span className="chip c-green" style={{ fontWeight: 700 }}>
                  {scheduledItem.scheduledTime} ({scheduledItem.relativeDue})
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--t2)', marginTop: '2px' }}>
                Context: {scheduledItem.aiNote}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => triggerImmediateDial(scheduledItem.id)}
            >
              📞 Dial Immediately
            </button>
          </div>
        </div>
      )}

      <div className="grid g4" style={{ marginBottom: '14px' }}>
        <div className="tile navy">
          <div className="n">{call.id}</div>
          <div className="l">Call Reference</div>
          <div className="d">{call.time} · {call.dur} duration</div>
        </div>
        <div className="tile teal">
          <div className="n">{call.disp}</div>
          <div className="l">Captured Disposition</div>
          <div className="d">Language: {call.lang}</div>
        </div>
        <div className="tile">
          <div className="n">{call.score}%</div>
          <div className="l">Cooperation Sentiment</div>
          <div className="d">NLP speech confidence score</div>
        </div>
        <div className="tile gold">
          <div className="n">{call.ptp !== 'None' ? call.ptp : 'No PTP'}</div>
          <div className="l">PTP Commitment</div>
          <div className="d">Autonomy level: {call.auto}</div>
        </div>
      </div>

      <div className="split">
        <AudioTranscript turns={call.turns} />

        <div className="grid" style={{ gap: '14px' }}>
          <div className="card">
            <div className="card-h">
              <h3>Retailer Account Snapshot</h3>
              <div className="r">
                <Link
                  href={`/retailers/${retailer.id}`}
                  onClick={() => setSelectedRetailerId(retailer.id)}
                  className="link"
                  style={{ fontSize: '12px' }}
                >
                  View 360° Profile →
                </Link>
              </div>
            </div>
            <div className="card-b">
              <div style={{ fontWeight: 700, fontSize: '15px', marginBottom: '4px' }}>
                {retailer.name}
              </div>
              <div className="meta" style={{ marginBottom: '12px' }}>
                {retailer.city} · {retailer.phone}
              </div>

              <dl className="kv">
                <dt>Retailer Code</dt>
                <dd className="mono">{retailer.code}</dd>
                <dt>Total Outstanding</dt>
                <dd className="num">{inr(retailer.os)}</dd>
                <dt>Overdue Balance</dt>
                <dd className="num" style={{ color: 'var(--red)' }}>{inr(retailer.od)}</dd>
                <dt>Aging Bucket</dt>
                <dd><span className="chip c-gold">{retailer.bucket}</span></dd>
                <dt>Credit Limit</dt>
                <dd className="num">{inr(retailer.lim)}</dd>
              </dl>
            </div>
          </div>

          <div className="card">
            <div className="card-h">
              <h3>Evidence & Recommended Next Step</h3>
            </div>
            <div className="card-b">
              <div className="rail" style={{ marginBottom: '14px' }}>
                <h4>RIA Autonomous Recommendation:</h4>
                <div style={{ fontSize: '13px', color: 'var(--t2)' }}>
                  {call.summary && <div style={{ marginBottom: '6px' }}>RIA noted: {call.summary}</div>}
                  {call.disp.includes('PTP')
                    ? `Retailer promised to pay${call.ptp && call.ptp !== 'None' ? ` on ${call.ptp}` : ''}. Follow up on the promised date if payment doesn't arrive.`
                    : call.disp.toLowerCase().includes('dispute')
                    ? 'Retailer disputed the invoice. Have the Credit Manager review it before RIA calls again.'
                    : call.disp.includes('not lifted') || call.disp.includes('busy')
                    ? 'Retailer did not answer. RIA retries automatically; after the last attempt, consider a field visit.'
                    : 'Review the transcript and decide the next step.'}
                </div>
              </div>

              <div style={{ display: 'grid', gap: '8px' }}>
                {call.disp.includes('PTP') && (
                  <ActionButton
                    auto={call.auto}
                    label="Send WhatsApp Payment Link"
                    className="btn-green btn-block"
                    screen="calldetail"
                    onClick={() => notConnected('WhatsApp payment links')}
                  />
                )}
                <button
                  className="btn btn-primary btn-block"
                  onClick={handleCreateTicket}
                >
                  Create Customer Care Ticket
                </button>
                <ActionButton
                  auto={call.auto}
                  label="Place Follow-up Call"
                  className="btn-ghost btn-block"
                  screen="calldetail"
                  onClick={() => callRetailer(call.ret)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
