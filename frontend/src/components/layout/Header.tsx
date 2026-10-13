'use client';

import { useSyncExternalStore } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useApp } from '@/context/AppContext';
import { ROLES, NAV, AV } from '@/data/mockData';
import { initials } from '@/utils/formatters';
import { isDarkTheme, setDarkTheme, subscribeTheme } from '@/lib/theme';
import GlobalSearch from './GlobalSearch';

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { role, perm, me, meInfo, config, logout } = useApp();

  const activeKey = pathname.startsWith('/calls/')
    ? 'calls'
    : pathname.startsWith('/retailers')
    ? 'collections'
    : pathname.replace('/', '') || 'dashboard';

  const allowedNav = NAV.filter((n) => perm(n.k) !== 'X');

  const handleMobileNav = (key: string) => {
    router.push(`/${key}`);
  };

  const dark = useSyncExternalStore(subscribeTheme, isDarkTheme, () => false);
  const userInitial = initials(me());
  const avatarBg = AV[role] || '#0F2350';

  return (
    <header className="top">
      <Link href="/dashboard" style={{ textDecoration: 'none', color: 'inherit' }}>
        <div className="brand">
          <Image src="/logo-mark.png" alt="" width={75} height={26} loading="eager" />
          <div className="wm">
            RIA<small>DISTRIBUTION INTELLIGENCE</small>
          </div>
        </div>
      </Link>

      <div className="tenant">
        <span className="dot" />
        <span id="tenantName">{config.general.tenant || meInfo?.company || ''}</span>
      </div>

      <div className="mobile-nav">
        <select value={activeKey} onChange={(e) => handleMobileNav(e.target.value)}>
          {allowedNav.map((n) => (
            <option key={n.k} value={n.k}>
              {n.t}
            </option>
          ))}
        </select>
      </div>

      <GlobalSearch />

      <div className="top-right">
        <div className="ctrl">
          <span>Role</span>
          <span style={{ fontWeight: 600 }}>{role} — {ROLES[role]?.n}</span>
        </div>

        <button
          type="button"
          className="btn btn-ghost btn-sm theme-btn"
          onClick={() => setDarkTheme(!dark)}
          aria-pressed={dark}
          title={dark ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          <span aria-hidden="true">{dark ? '☀' : '☾'}</span>
          <span className="theme-label">{dark ? 'Light' : 'Dark'}</span>
        </button>

        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            logout();
            router.replace('/login');
          }}
        >
          Sign out
        </button>

        <div
          className="avatar"
          style={{ background: avatarBg }}
          title={`Signed in as ${me()} (${ROLES[role]?.n})`}
        >
          {userInitial}
        </div>
      </div>
    </header>
  );
}
