'use client';

import React, { useEffect, useState, useCallback } from 'react';
import AdminShell from '@/components/layout/AdminShell';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';

const DEFAULT_TEAM = [
  'karnativikas1612@gmail.com',
  'gyanvardhan186@gmail.com',
  'superadmin@roxygroup.in',
];

export default function AdminTeamPage() {
  const { meInfo } = useApp();
  const [loading, setLoading] = useState(true);
  const [admins, setAdmins] = useState<string[]>(DEFAULT_TEAM);

  const fetchTeam = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api<{ admins: string[] }>('/admin/team');
      if (res && Array.isArray(res.admins) && res.admins.length > 0) {
        setAdmins(res.admins);
      }
    } catch {
      // Retain the 3 authorized admin emails
      setAdmins(DEFAULT_TEAM);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTeam();
  }, [fetchTeam]);

  return (
    <AdminShell>
      {/* Page Header */}
      <div className="page-head">
        <div style={{ flex: 1, minWidth: '280px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '20px' }}>🛡️</span>
            <h1>Super Admin Team</h1>
            <span className="badge" style={{ background: 'rgba(34, 197, 94, 0.15)', color: '#22c55e', border: '1px solid #22c55e', fontSize: '11px' }}>
              Access Control
            </span>
          </div>
          <p>Personnel authorized with full platform governance, telephony control, and tenant management rights</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={fetchTeam}
            disabled={loading}
          >
            <span>↻</span> {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Admin Cards Grid */}
      <div className="card" style={{ marginBottom: '18px' }}>
        <div className="card-h">
          <h3>Authorized Super Administrators ({admins.length})</h3>
          <span className="sub">Accounts with platform-wide administrative privileges</span>
        </div>

        <div className="card-b">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px' }}>
            {admins.map((email) => {
              const isCurrentUser = meInfo?.e?.toLowerCase() === email.toLowerCase();
              return (
                <div
                  key={email}
                  style={{
                    padding: '14px 16px',
                    borderRadius: '8px',
                    background: isCurrentUser ? 'var(--blue-soft)' : 'var(--hover)',
                    border: isCurrentUser ? '1px solid var(--blue)' : '1px solid var(--line)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                  }}
                >
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      background: 'var(--navy)',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '15px',
                    }}
                  >
                    {email[0]?.toUpperCase() || 'A'}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontWeight: 600, fontSize: '13.5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {email}
                      </span>
                      {isCurrentUser && (
                        <span className="badge" style={{ background: 'var(--blue)', color: '#fff', fontSize: '9.5px', padding: '1px 5px' }}>
                          YOU
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '11.5px', color: 'var(--t2)', marginTop: '2px' }}>
                      Full Platform Super Admin
                    </div>
                  </div>

                  <span className="badge" style={{ background: 'rgba(34, 197, 94, 0.15)', color: '#22c55e', border: '1px solid #22c55e', fontSize: '10px' }}>
                    ACTIVE
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Permissions Breakdown Info */}
      <div className="card">
        <div className="card-h">
          <h3>Super Admin Permissions & Scope</h3>
          <span className="sub">Guaranteed access rights across backend services and database</span>
        </div>
        <div className="card-b">
          <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--t1)', fontSize: '13px', lineHeight: '1.8' }}>
            <li><strong>Dynamic Telephony Control:</strong> Add, pause, or remove Vobiz numbers in real time with instant LiveKit SIP sync.</li>
            <li><strong>Least Active Calls Balancing:</strong> Real-time visibility into active channels and anti-spam burn meters across all numbers.</li>
            <li><strong>Multi-Tenant Governance:</strong> Onboard and manage all 50+ client companies, set daily calling limits, and inspect campaigns.</li>
            <li><strong>Platform Concurrency Watchdog:</strong> Monitor LiveKit WebRTC audio channels, telephony errors, and system health.</li>
            <li><strong>Dual-Workspace Switching:</strong> Seamlessly toggle between the Admin Center and the Collections Workspace with one click.</li>
          </ul>
        </div>
      </div>
    </AdminShell>
  );
}
