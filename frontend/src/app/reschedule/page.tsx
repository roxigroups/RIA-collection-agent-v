'use client';

import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import RescheduleQueue from '@/components/calls/RescheduleQueue';

export default function ReschedulePage() {
  return (
    <AppShell screenKey="reschedule">
      <PageHead screenKey="reschedule" />
      <RescheduleQueue />
    </AppShell>
  );
}
