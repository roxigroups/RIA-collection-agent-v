'use client';

import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import ReportsCard from '@/components/reports/ReportsCard';

export default function ReportsPage() {
  return (
    <AppShell screenKey="reports">
      <PageHead screenKey="reports" />
      <ReportsCard />
    </AppShell>
  );
}
