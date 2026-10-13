'use client';

import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import BatchControls, { BatchStateChip, DeleteBatchButton } from './BatchControls';

interface BatchListProps {
  onSelectBatch: (batchId: string) => void;
}

export default function BatchList({ onSelectBatch }: BatchListProps) {
  const { batches, downloadBatchReport } = useApp();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filteredBatches = batches.filter((b) => {
    if (statusFilter !== 'ALL' && b.dialState !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      if (
        !b.id.toLowerCase().includes(q) &&
        !b.name.toLowerCase().includes(q) &&
        !b.fileName.toLowerCase().includes(q) &&
        !b.importedBy.toLowerCase().includes(q)
      ) {
        return false;
      }
    }
    return true;
  });

  return (
    <div className="batch-list-container">
      {/* Search & Filter Bar */}
      <div className="card" style={{ marginBottom: '16px' }}>
        <div className="filters">
          <input
            type="text"
            placeholder="Search batches by ID, campaign name, or filename..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: '320px', padding: '6px 12px', fontSize: '13px' }}
          />

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '6px 12px', fontSize: '13px' }}
          >
            <option value="ALL">All Batch Statuses ({batches.length})</option>
            <option value="ready">Ready to call</option>
            <option value="running">Calling now</option>
            <option value="paused">Paused</option>
            <option value="done">All calls made</option>
          </select>

          <div className="sp">
            <span>
              Showing <b>{filteredBatches.length}</b> of <b>{batches.length}</b> campaign runs
            </span>
          </div>
        </div>
      </div>

      {/* Batch Cards Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {filteredBatches.map((batch) => {
          const connectRate =
            batch.totalCalls > 0
              ? Math.round((batch.connectedCalls / batch.totalCalls) * 100)
              : 0;

          return (
            <div
              key={batch.id}
              className="card"
              style={{
                cursor: 'pointer',
                transition: 'all 0.15s ease-in-out',
                border: '1px solid var(--line)',
                padding: '16px 20px',
              }}
              onClick={() => onSelectBatch(batch.id)}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--blue)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(26,86,219,0.08)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--line)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              {/* Batch Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  flexWrap: 'wrap',
                  gap: '10px',
                  marginBottom: '12px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span className="mono" style={{ fontWeight: 700, fontSize: '14px', color: 'var(--navy)' }}>
                      {batch.id}
                    </span>
                    <BatchStateChip batch={batch} />
                  </div>
                  <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--t1)' }}>
                    {batch.name}
                  </h4>
                  <div className="meta" style={{ marginTop: '3px', fontSize: '12px' }}>
                    Imported: {batch.createdAt} • Uploaded by <b>{batch.importedBy}</b> • Source:{' '}
                    <span className="mono">{batch.fileName}</span>
                  </div>
                </div>

                {/* Batch Actions */}
                <div
                  style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <BatchControls batch={batch} />
                  <DeleteBatchButton batch={batch} />
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    title="Download complete batch report CSV with all calls and outcomes"
                    onClick={() => downloadBatchReport(batch)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    <span>📥</span>
                    <span>Download Report (CSV)</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => onSelectBatch(batch.id)}
                  >
                    View Batch Details →
                  </button>
                </div>
              </div>

              {/* Batch KPI Snapshot */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '10px',
                  paddingTop: '12px',
                  borderTop: '1px solid #F0F2F6',
                }}
              >
                <div style={{ background: 'var(--surface-2)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Total Queued
                  </div>
                  <div className="num" style={{ fontSize: '17px', fontWeight: 700, color: 'var(--t1)' }}>
                    {batch.totalCalls} <span style={{ fontSize: '12px', fontWeight: 400 }}>calls</span>
                  </div>
                </div>

                <div style={{ background: 'var(--blue-soft)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--navy)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Connected Rate
                  </div>
                  <div className="num" style={{ fontSize: '17px', fontWeight: 700, color: 'var(--navy)' }}>
                    {connectRate}% <span style={{ fontSize: '12px', fontWeight: 400 }}>({batch.connectedCalls})</span>
                  </div>
                </div>

                <div style={{ background: 'var(--green-soft)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--green-ink)', textTransform: 'uppercase', fontWeight: 600 }}>
                    PTPs Committed
                  </div>
                  <div className="num" style={{ fontSize: '17px', fontWeight: 700, color: 'var(--green-ink)' }}>
                    {batch.ptpCount} <span style={{ fontSize: '11px', fontWeight: 600 }}>₹{(batch.ptpAmount / 100000).toFixed(1)}L</span>
                  </div>
                </div>

                <div style={{ background: batch.disputeCount > 0 ? 'var(--red-soft)' : 'var(--surface-2)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: batch.disputeCount > 0 ? 'var(--red)' : 'var(--t3)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Disputes Raised
                  </div>
                  <div className="num" style={{ fontSize: '17px', fontWeight: 700, color: batch.disputeCount > 0 ? 'var(--red)' : 'var(--t1)' }}>
                    {batch.disputeCount}
                  </div>
                </div>

                <div style={{ background: batch.noLiftCount > 0 ? 'var(--gold-soft)' : 'var(--surface-2)', padding: '8px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--gold-ink)', textTransform: 'uppercase', fontWeight: 600 }}>
                    Not Lifted
                  </div>
                  <div className="num" style={{ fontSize: '17px', fontWeight: 700, color: 'var(--gold-ink)' }}>
                    {batch.noLiftCount}
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        {filteredBatches.length === 0 && (
          <div className="card" style={{ padding: '36px', textAlign: 'center' }}>
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>📋</div>
            <h4 style={{ margin: '0 0 6px 0' }}>No Batch Reports Found</h4>
            <p className="meta" style={{ margin: 0 }}>
              Try adjusting your search filter or import a new daily call sheet above.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
