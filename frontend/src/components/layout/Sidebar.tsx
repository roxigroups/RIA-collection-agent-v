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

export default function Sidebar() {
  const pathname = usePathname();
  const { perm, ptps, scheduledCallbacks, escalations } = useApp();
  const collapsed = useSyncExternalStore(subscribe, readCollapsed, () => false);
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
        {!collapsed && <span className="nav-label">Workspace</span>}
        <span className="chev" aria-hidden="true">{collapsed ? '»' : '«'}</span>
      </button>
      <div className="nav" id="side-nav" hidden={collapsed}>
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
      </div>
    </nav>
  );
}
