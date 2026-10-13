'use client';

import { ReactNode } from 'react';
import { ScreenKey } from '@/types';
import { TITLES } from '@/data/mockData';
import { useApp } from '@/context/AppContext';

interface PageHeadProps {
  screenKey: ScreenKey;
  rightAction?: ReactNode;
  isStale?: boolean;
}

export default function PageHead({ screenKey, rightAction, isStale }: PageHeadProps) {
  const { lastSync } = useApp();
  const t = TITLES[screenKey] || ['RIA', 'Page', ''];
  const showStale = isStale ?? (screenKey === 'collections' || screenKey === 'dashboard');

  return (
    <div className="page-head">
      <div>
        <h1>{t[1]}</h1>
        <p>{t[2]}</p>
      </div>
      <div className="head-right">
        {showStale && (
          <span className="stale" title="The dashboard refreshes from the server every 10 seconds">
            ⚡ {lastSync ? `Updated ${lastSync.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Loading…'}
          </span>
        )}
        {rightAction}
      </div>
    </div>
  );
}
