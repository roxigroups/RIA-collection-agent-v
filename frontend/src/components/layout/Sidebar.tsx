'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSyncExternalStore } from 'react';
import { useApp } from '@/context/AppContext';
import { NAV } from '@/data/mockData';

// Hidden or shown, the Workspace menu stays that way on this browser across pages and reloads
const COLLAPSED_KEY = 'ria.sidebarCollapsed';
const listeners = new Set<() => void>();
let collapsedFallback = false; // used when the browser blocks storage

const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};
const readCollapsed = () => {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1';
  } catch {
    return collapsedFallback;
  }
};
const setCollapsed = (value: boolean) => {
  collapsedFallback = value;
  try {
    localStorage.setItem(COLLAPSED_KEY, value ? '1' : '0');
  } catch {
    // storage blocked — the fallback keeps it for this visit
  }
  listeners.forEach((cb) => cb());
};

const ADMIN_NAV = [
  { k: 'admin/dashboard', t: 'Platform Overview', ic: '📊' },
  { k: 'admin/numbers', t: 'Telephony Pool', ic: '📱' },
  { k: 'admin/tenants', t: 'Client Tenants', ic: '🏢' },
  { k: 'admin/team', t: 'Admin Team', ic: '🛡️' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { perm, ptps, scheduledCallbacks, escalations, meInfo, role } = useApp();
  const collapsed = useSyncExternalStore(subscribe, readCollapsed, () => false);
  const isAdminPath = pathname.startsWith('/admin');

  // Live counts: promises due today, callbacks waiting, open tickets
  const badges: Record<string, number> = {
    collections: ptps.filter((p) => p.st === 'due').length,
    reschedule: scheduledCallbacks.filter((c) => c.status === 'Queued').length,
    tickets: escalations.filter((e) => e.status === 'Open').length,
  };

  const activeKey = pathname.startsWith('/calls')
    ? 'calls'
    : pathname.startsWith('/retailers')
    ? 'collections'
    : pathname.replace('/', '') || 'dashboard';

  return (
    <nav className={collapsed ? 'side collapsed' : 'side'}>
      <button
        type="button"
        className="nav-toggle"
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
        aria-controls="side-nav"
        title={collapsed ? 'Show workspace menu' : 'Hide workspace menu'}
      >
        {!collapsed && <span className="nav-label">{isAdminPath ? 'Platform Admin' : 'Workspace'}</span>}
        <span className="chev" aria-hidden="true">{collapsed ? '»' : '«'}</span>
      </button>
      <div className="nav" id="side-nav" hidden={collapsed}>
        {isAdminPath ? (
          <>
            <div style={{ padding: '6px 14px', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', fontWeight: 700 }}>
              Command Center
            </div>
            {ADMIN_NAV.map((item) => {
              const isActive = pathname === `/${item.k}`;
              return (
                <Link
                  key={item.k}
                  href={`/${item.k}`}
                  className={isActive ? 'on' : ''}
                  title={item.t}
                >
                  <span className="ic">{item.ic}</span>
                  <span>{item.t}</span>
                </Link>
              );
            })}
            <div style={{ margin: '14px 10px', borderTop: '1px solid var(--border)' }} />
            <Link href="/dashboard" className="" title="Switch to Collections Workspace">
              <span className="ic">📞</span>
              <span>Collections View</span>
            </Link>
          </>
        ) : (
          <>
            {NAV.map((item) => {
              const p = perm(item.k);
              if (p === 'X') return null;
              const isActive = activeKey === item.k;

              return (
                <Link
                  key={item.k}
                  href={`/${item.k}`}
                  className={isActive ? 'on' : ''}
                  title={item.t}
                >
                  <span className="ic">{item.ic}</span>
                  <span>{item.t}</span>
                  {badges[item.k] > 0 && <span className="badge">{badges[item.k]}</span>}
                </Link>
              );
            })}
            {Boolean(meInfo?.is_superadmin) && (
              <>
                <div style={{ margin: '14px 10px', borderTop: '1px solid var(--border)' }} />
                <Link
                  href="/admin/dashboard"
                  className=""
                  title="Super Admin Command Center"
                  style={{ color: 'var(--blue)', fontWeight: 600 }}
                >
                  <span className="ic">🛡️</span>
                  <span>Admin Center</span>
                </Link>
              </>
            )}
          </>
        )}
      </div>
    </nav>
  );
}
