'use client';

import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import RecoverySummary from '@/components/dashboard/RecoverySummary';
import CallsChart from '@/components/dashboard/CallsChart';
import RecoveryChart from '@/components/dashboard/RecoveryChart';
import ResponseBars from '@/components/dashboard/ResponseBars';
import UsersCard from '@/components/dashboard/UsersCard';

export default function DashboardPage() {
  return (
    <AppShell screenKey="dashboard">
      <PageHead screenKey="dashboard" />

      <RecoverySummary />

      <div className="grid g2" style={{ marginBottom: '14px' }}>
        <div className="card">
          <div className="card-h">
            <h3>Call Volume & Connectivity (7 Days)</h3>
            <span className="sub">Outbound telecalling runs</span>
          </div>
          <div className="card-b">
            <CallsChart />
          </div>
        </div>

        <div className="card">
          <div className="card-h">
            <h3>Overdue Demand vs Recovered (Weekly)</h3>
            <span className="sub">Direct ledger attribution</span>
          </div>
          <div className="card-b">
            <RecoveryChart />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '14px' }}>
        <div className="card-h">
          <h3>Retailer Response Breakdown (Today)</h3>
          <span className="sub">Aggregated outcome distribution across all completed calls</span>
        </div>
        <div className="card-b">
          <ResponseBars />
        </div>
      </div>

      <UsersCard />
    </AppShell>
  );
}
