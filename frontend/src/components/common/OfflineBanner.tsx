'use client';

import { useApp } from '@/context/AppContext';

export default function OfflineBanner() {
  const { viewState } = useApp();
  if (viewState !== 'offline') return null;

  return (
    <div className="offline-bar" style={{ margin: '-20px -24px 18px' }}>
      <span>⚠️</span>
      <span>You are offline. Queued actions are not accepted until the connection returns.</span>
    </div>
  );
}
