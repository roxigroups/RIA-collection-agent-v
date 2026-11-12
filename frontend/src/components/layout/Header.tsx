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

  const isAdmin = pathname.startsWith('/admin');

  return (
    <header className="top">
      <Link href={isAdmin ? '/admin/dashboard' : '/dashboard'} style={{ textDecoration: 'none', color: 'inherit' }}>
        <div className="brand">
          <Image src="/logo-mark.png" alt="" width={75} height={26} loading="eager" />
          <div className="wm">
            RIA<small>{isAdmin ? 'PLATFORM ADMIN' : 'DISTRIBUTION INTELLIGENCE'}</small>
          </div>
        </div>
      </Link>

      <div className="tenant">
        <span className="dot" style={{ background: isAdmin ? '#22c55e' : undefined }} />
        <span id="tenantName">{isAdmin ? 'Super Admin Command Center' : (config.general.tenant || meInfo?.company || '')}</span>
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
        {Boolean(meInfo?.is_superadmin) && (
          <button
            type="button"
            className={`btn btn-sm ${pathname.startsWith('/admin') ? 'btn-outline' : 'btn-primary'}`}
            style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            onClick={() => {
              if (pathname.startsWith('/admin')) {
                router.push('/dashboard');
              } else {
                router.push('/admin/dashboard');
              }
            }}
          >
            <span>{pathname.startsWith('/admin') ? '📞 Collections Workspace' : '🛡️ Admin Portal'}</span>
          </button>
        )}
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
