'use client';

import { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import ImportCard from '@/components/calls/ImportCard';
import BatchList from '@/components/calls/BatchList';
import BatchReportView from '@/components/calls/BatchReportView';
import CallsTable from '@/components/calls/CallsTable';
import LiveCallsPanel from '@/components/calls/LiveCallsPanel';
import { useApp } from '@/context/AppContext';

export default function CallsPage() {
  const { batches, calls, selectedBatchId, setSelectedBatchId } = useApp();
  const [activeTab, setActiveTab] = useState<'batches' | 'all-calls'>('batches');
  const [batchSearchQuery, setBatchSearchQuery] = useState<string>('');

  return (
    <AppShell screenKey="calls">
      <PageHead screenKey="calls" />

      {/* Who is on a call now, and who is next */}
      <LiveCallsPanel />

      {/* CSV Import Section */}
      <ImportCard />

      {/* View Switcher Tabs & Batch Details */}
      <div style={{ marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px', borderBottom: '1px solid var(--line)', paddingBottom: '10px' }}>
        <button
          type="button"
          className={`btn ${activeTab === 'batches' && !selectedBatchId ? 'btn-primary' : 'btn-ghost'} btn-sm`}
          onClick={() => {
            setActiveTab('batches');
            setSelectedBatchId(null);
          }}
          style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <span>📦</span>
          <span>Batch Reports & Runs ({batches.length})</span>
        </button>

        <button
          type="button"
          className={`btn ${activeTab === 'all-calls' && !selectedBatchId ? 'btn-primary' : 'btn-ghost'} btn-sm`}
          onClick={() => {
            setActiveTab('all-calls');
            setSelectedBatchId(null);
          }}
          style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <span>☏</span>
          <span>All Calls ({calls.length})</span>
        </button>

        {selectedBatchId && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="chip c-blue" style={{ fontWeight: 600 }}>
              Viewing Batch: {selectedBatchId}
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setSelectedBatchId(null)}
            >
              ✕ Close Batch View
            </button>
          </div>
        )}
      </div>

      {/* Content Rendering */}
      {selectedBatchId ? (
        <BatchReportView
          batchId={selectedBatchId}
          initialSearch={batchSearchQuery}
          onBack={() => {
            setSelectedBatchId(null);
            setBatchSearchQuery('');
          }}
        />
      ) : activeTab === 'batches' ? (
        <BatchList onSelectBatch={(id, initialSearch) => {
          setSelectedBatchId(id);
          setBatchSearchQuery(initialSearch || '');
        }} />
      ) : (
        <CallsTable />
      )}
    </AppShell>
  );
}

