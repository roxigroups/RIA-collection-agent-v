'use client';

import { use, Suspense } from 'react';
import Link from 'next/link';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import Retailer360View from '@/components/retailers/Retailer360View';
import { SkeletonView } from '@/components/common/StateViews';

function RetailerDetailInner({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const id = resolvedParams.id;

  return (
    <AppShell screenKey="retailers">
      <PageHead
        screenKey="retailers"
        rightAction={
          <Link href="/collections" className="link" style={{ fontSize: '13px' }}>
            ← Back to Collections
          </Link>
        }
      />

      <Retailer360View retailerId={id} />
    </AppShell>
  );
}

export default function RetailerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<SkeletonView />}>
      <RetailerDetailInner params={params} />
    </Suspense>
  );
}
