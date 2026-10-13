'use client';

import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import Retailer360View from '@/components/retailers/Retailer360View';
import { useApp } from '@/context/AppContext';

export default function RetailersPage() {
  const { selectedRetailerId, setSelectedRetailerId, retailers } = useApp();

  return (
    <AppShell screenKey="retailers">
      <PageHead
        screenKey="retailers"
        rightAction={
          <select
            value={selectedRetailerId}
            onChange={(e) => setSelectedRetailerId(e.target.value)}
            style={{ padding: '6px 10px', fontSize: '13px', borderRadius: '7px' }}
          >
            {retailers.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.code})
              </option>
            ))}
          </select>
        }
      />

      <Retailer360View retailerId={selectedRetailerId} />
    </AppShell>
  );
}
