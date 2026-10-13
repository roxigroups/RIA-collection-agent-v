'use client';

import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import EscalationsTable from '@/components/tickets/EscalationsTable';

export default function EscalationsPage() {
  return (
    <AppShell screenKey="tickets">
      <PageHead screenKey="tickets" />

      <EscalationsTable />
    </AppShell>
  );
}
