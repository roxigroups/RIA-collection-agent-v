'use client';

import { useApp } from '@/context/AppContext';
import BatchControls, { BatchStateChip, DeleteBatchButton } from './BatchControls';
import CampaignDialer from './CampaignDialer';

interface BatchReportViewProps {
  batchId: string;
  initialSearch?: string;
  onBack: () => void;
}

export default function BatchReportView({ batchId, initialSearch, onBack }: BatchReportViewProps) {
  const { batches, downloadBatchReport } = useApp();
  const batch = batches.find((b) => b.id === batchId);
  if (!batch) {
    return (
      <div className="card" style={{ padding: '24px' }}>
        <p className="meta" style={{ margin: 0 }}>Loading batch {batchId}…</p>
      </div>
    );
  }

  const connectRate =
    batch.totalCalls > 0 ? Math.round((batch.connectedCalls / batch.totalCalls) * 100) : 0;

  return (
    <div className="batch-report-view">
      {/* Top Navigation & Actions */}
      <div
        className="card"
        style={{
          marginBottom: '16px',
          background: 'linear-gradient(180deg, var(--surface) 0%, var(--surface-2) 100%)',
          border: '1px solid #DCE6F5',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
            paddingBottom: '14px',
            borderBottom: '1px solid var(--line)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onBack}
              style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}
            >
              ← Back to All Batches
            </button>
            <div style={{ height: '20px', width: '1px', background: 'var(--line)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="mono" style={{ fontWeight: 700, fontSize: '15px', color: 'var(--navy)' }}>
                {batch.id}
              </span>
              <BatchStateChip batch={batch} />
            </div>
          </div>

          {/* Calling and download actions */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <BatchControls batch={batch} />
            <DeleteBatchButton batch={batch} label="🗑 Delete batch" />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => downloadBatchReport(batch)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}
            >
              <span>📥</span>
              <span>Download Batch Report (CSV)</span>
            </button>
          </div>
        </div>

        {/* Batch Metadata Header */}
        <div style={{ paddingTop: '14px' }}>
          <h2 style={{ margin: '0 0 6px 0', fontSize: '20px', fontWeight: 700, color: 'var(--t1)' }}>
            {batch.name}
          </h2>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '16px',
              fontSize: '13px',
              color: 'var(--t2)',
            }}
          >
            <div>
              <span>Generated: </span>
              <b style={{ color: 'var(--t1)' }}>{batch.createdAt}</b>
            </div>
            <div>
              <span>Imported By: </span>
              <b style={{ color: 'var(--t1)' }}>{batch.importedBy}</b>
            </div>
            <div>
              <span>Source File: </span>
              <span className="mono" style={{ color: 'var(--navy)', fontWeight: 600 }}>
                {batch.fileName}
              </span>
            </div>
            <div>
              <span>Total Accounts in Sheet: </span>
              <b style={{ color: 'var(--t1)' }}>{batch.totalCalls}</b>
            </div>
          </div>
        </div>
      </div>

      {/* The campaign as a phone dialer, with the whole imported sheet */}
      <CampaignDialer batch={batch} initialSearch={initialSearch} />

      {/* KPI Performance Tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div className="card" style={{ padding: '12px 14px' }}>
          <div className="meta" style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700 }}>
            Total Calls In Batch
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', color: 'var(--t1)' }}>
            {batch.totalCalls}
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>{batch.completedCalls} dialed</span>
        </div>

        <div className="card" style={{ padding: '12px 14px', background: 'var(--blue-soft)' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--navy)' }}>
            Connected Rate
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', color: 'var(--navy)' }}>
            {connectRate}%
          </div>
          <span style={{ fontSize: '11px', color: 'var(--navy)' }}>{batch.connectedCalls} connected</span>
        </div>

        <div className="card" style={{ padding: '12px 14px', background: 'var(--green-soft)' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--green-ink)' }}>
            PTPs Committed
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', color: 'var(--green-ink)' }}>
            {batch.ptpCount}
          </div>
          <span style={{ fontSize: '11px', color: 'var(--green-ink)', fontWeight: 600 }}>
            ₹{(batch.ptpAmount / 100000).toFixed(2)} Lakhs
          </span>
        </div>

        <div className="card" style={{ padding: '12px 14px', background: batch.disputeCount > 0 ? 'var(--red-soft)' : '#FFF' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: batch.disputeCount > 0 ? 'var(--red)' : 'var(--t3)' }}>
            Disputes / Tickets
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', color: batch.disputeCount > 0 ? 'var(--red)' : 'var(--t1)' }}>
            {batch.disputeCount}
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>Escalated to team</span>
        </div>

        <div className="card" style={{ padding: '12px 14px', background: batch.noLiftCount > 0 ? 'var(--gold-soft)' : '#FFF' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--gold-ink)' }}>
            Calls Not Lifted
          </div>
          <div className="num" style={{ fontSize: '22px', fontWeight: 700, marginTop: '4px', color: 'var(--gold-ink)' }}>
            {batch.noLiftCount}
          </div>
          <span className="meta" style={{ fontSize: '11px' }}>Auto-retry scheduled</span>
        </div>
      </div>

    </div>
  );
}
