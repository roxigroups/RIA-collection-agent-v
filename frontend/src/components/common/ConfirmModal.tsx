'use client';

import React, { useState } from 'react';

// "Are you sure?" body for openModal(): a message and a red confirm button
export default function ConfirmModal({
  message,
  confirmLabel,
  onConfirm,
  onClose,
}: {
  message: React.ReactNode;
  confirmLabel: string;
  onConfirm: () => Promise<unknown> | void;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <div>
      <div style={{ fontSize: '14px', lineHeight: 1.55, color: 'var(--t1)' }}>{message}</div>
      <div
        className="m-f"
        style={{ margin: '18px -18px -18px', padding: '14px 18px', display: 'flex', gap: '8px', justifyContent: 'flex-end', background: 'var(--surface-2)' }}
      >
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-sm"
          data-testid="confirm-delete"
          style={{ background: 'var(--red)', color: '#fff', border: 'none' }}
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await onConfirm();
            setBusy(false);
            onClose();
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}
