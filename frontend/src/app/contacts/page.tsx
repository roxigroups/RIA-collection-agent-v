'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import ContactsTable from '@/components/contacts/ContactsTable';
import { useApp } from '@/context/AppContext';

// The header search opens /contacts?q=<name>: the table starts filtered to it
function ContactsTableFromUrl() {
  const q = useSearchParams().get('q') || '';
  return <ContactsTable key={q} initialSearch={q} />;
}

export default function ContactsPage() {
  const { campaignContacts } = useApp();

  const credit30 = campaignContacts.filter((c) => c.creditPeriod.includes('30')).length;
  const creditLong = campaignContacts.filter((c) => parseInt(c.creditPeriod) > 30).length;
  const creditShort = campaignContacts.filter((c) => parseInt(c.creditPeriod) < 30).length;

  return (
    <AppShell screenKey="contacts">
      <PageHead screenKey="contacts" />

      <div className="grid g4" style={{ marginBottom: '14px' }}>
        <div className="tile navy">
          <div className="n">{campaignContacts.length}</div>
          <div className="l">Total Campaign Customers</div>
          <div className="d">Global customer directory</div>
        </div>
        <div className="tile teal">
          <div className="n">{credit30}</div>
          <div className="l">Standard 30-Day Accounts</div>
          <div className="d">Default credit terms</div>
        </div>
        <div className="tile gold">
          <div className="n">{creditLong}</div>
          <div className="l">Extended Terms (45–90d)</div>
          <div className="d">High-volume distributors</div>
        </div>
        <div className="tile">
          <div className="n">{creditShort}</div>
          <div className="l">Short Terms (7–21d)</div>
          <div className="d">Strict collection follow-up</div>
        </div>
      </div>

      <Suspense fallback={null}>
        <ContactsTableFromUrl />
      </Suspense>
    </AppShell>
  );
}
