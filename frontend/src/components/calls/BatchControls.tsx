'use client';

import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import { CallBatch } from '@/types';
import ConfirmModal from '../common/ConfirmModal';

const STATES: Record<CallBatch['dialState'], { cls: string; text: string }> = {
  ready: { cls: 'c-gold', text: 'Ready to call' },
  running: { cls: 'c-blue live', text: 'Calling…' },
  paused: { cls: 'c-grey', text: 'Paused' },
  done: { cls: 'c-green', text: 'All calls made' },
};

// Where the batch's run is, as a chip
export function BatchStateChip({ batch }: { batch: CallBatch }) {
  const s = STATES[batch.dialState] || STATES.done;
  return (
    <span className={`chip ${s.cls}`} data-testid="batch-state">
      {s.text}
      {batch.dialState !== 'done' && ` · ${batch.queuedCalls} waiting${batch.liveCalls ? ` · ${batch.liveCalls} on call` : ''}`}
    </span>
  );
}

// 📞 Start calling / ⏸ Pause for one batch (calls go one after another, in sheet order)
export default function BatchControls({ batch }: { batch: CallBatch }) {
  const { startBatch, pauseBatch, canAct } = useApp();
  const [busy, setBusy] = useState(false);
  if (!canAct('calls') || batch.dialState === 'done') return null;

  const run = async (fn: (id: string) => Promise<boolean>) => {
    setBusy(true);
    await fn(batch.id);
    setBusy(false);
  };

  return batch.dialState === 'running' ? (
    <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => run(pauseBatch)} data-testid="pause-batch">
      ⏸ Pause calling
    </button>
  ) : (
    <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(startBatch)} data-testid="start-batch">
      📞 {batch.dialState === 'paused' ? 'Resume calling' : 'Start calling'} ({batch.queuedCalls})
    </button>
  );
}

// 🗑 Delete a batch: its waiting calls and automatic retries are cancelled; calls
// already made stay in the call history
export function DeleteBatchButton({ batch, label = '🗑 Delete' }: { batch: CallBatch; label?: string }) {
  const { deleteBatch, canAct, openModal, closeModal } = useApp();
  if (!canAct('calls')) return null;
  const onLine = batch.liveCalls > 0;
  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm"
      data-testid="delete-batch"
      style={{ color: onLine ? undefined : 'var(--red)' }}
      disabled={onLine}
      title={onLine ? 'A call from this batch is on the line: pause it and delete after the call' : 'Delete this batch'}
      onClick={(e) => {
        e.stopPropagation();
        openModal(
          `Delete ${batch.id}?`,
          <ConfirmModal
            message={
              <>
                <b>{batch.name}</b> will be removed from Call Campaign.
                {batch.queuedCalls > 0 && (
                  <>
                    {' '}Its <b>{batch.queuedCalls} waiting call{batch.queuedCalls === 1 ? '' : 's'}</b> and any automatic retries are cancelled.
                  </>
                )}{' '}
                Calls already made, promises and tickets stay in the call history; callbacks customers asked for stay in
                Reschedule.
              </>
            }
            confirmLabel="Delete batch"
            onConfirm={() => deleteBatch(batch.id)}
            onClose={closeModal}
          />
        );
      }}
    >
      {label}
    </button>
  );
}
