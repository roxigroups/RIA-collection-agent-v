'use client';

import { use, Suspense } from 'react';
import Link from 'next/link';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import CallDetailView from '@/components/calldetail/CallDetailView';
import { SkeletonView } from '@/components/common/StateViews';

function CallDetailInner({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const id = resolvedParams.id;

  return (
    <AppShell screenKey="calldetail">
      <PageHead
        screenKey="calldetail"
        rightAction={
          <Link href="/calls" className="link" style={{ fontSize: '13px' }}>
            ← Back to All Calls
          </Link>
        }
      />

      <CallDetailView callId={id} />
    </AppShell>
  );
}

export default function CallDetailPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<SkeletonView />}>
      <CallDetailInner params={params} />
    </Suspense>
  );
}
