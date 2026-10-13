'use client';

import { useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import ResponseTiles from '@/components/collections/ResponseTiles';
import PtpTab from '@/components/collections/PtpTab';
import NoLiftTab from '@/components/collections/NoLiftTab';
import AllRespTab from '@/components/collections/AllRespTab';
import { useApp } from '@/context/AppContext';

export default function CollectionsPage() {
  const { collectionsTab, setCollectionsTab } = useApp();
  const [activeTile, setActiveTile] = useState('ptp');

  const handleSelectTile = (k: string) => {
    setActiveTile(k);
    if (k === 'ptp') setCollectionsTab('today');
    else if (k === 'nolift') setCollectionsTab('nolift');
    else setCollectionsTab('all');
  };

  return (
    <AppShell screenKey="collections">
      <PageHead screenKey="collections" />

      <ResponseTiles activeKey={activeTile} onSelect={handleSelectTile} />

      <div className="card">
        <div className="tabs">
          <button
            className={collectionsTab === 'today' ? 'on' : ''}
            onClick={() => setCollectionsTab('today')}
          >
            Today’s PTP Queue <span className="ct">5</span>
          </button>
          <button
            className={collectionsTab === 'nolift' ? 'on' : ''}
            onClick={() => setCollectionsTab('nolift')}
          >
            Not Lifted & Retries <span className="ct">3</span>
          </button>
          <button
            className={collectionsTab === 'all' ? 'on' : ''}
            onClick={() => setCollectionsTab('all')}
          >
            All Retailer Responses <span className="ct">142</span>
          </button>
        </div>

        <div className="card-b" style={{ padding: 0 }}>
          {collectionsTab === 'today' ? (
            <PtpTab />
          ) : collectionsTab === 'nolift' ? (
            <NoLiftTab />
          ) : (
            <AllRespTab filterKey={activeTile} />
          )}
        </div>
      </div>
    </AppShell>
  );
}
