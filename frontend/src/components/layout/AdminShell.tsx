'use client';

import { ReactNode, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Header from './Header';
import Sidebar from './Sidebar';
import OfflineBanner from '../common/OfflineBanner';
import Toast from '../common/Toast';
import Modal from '../common/Modal';
import { useApp } from '@/context/AppContext';

interface AdminShellProps {
  children: ReactNode;
}

export default function AdminShell({ children }: AdminShellProps) {
  const { isLoggedIn, isSuperAdmin, authChecked } = useApp();
  const router = useRouter();

  useEffect(() => {
    if (authChecked) {
      if (!isLoggedIn) {
        router.replace('/login');
      } else if (!isSuperAdmin) {
        router.replace('/dashboard');
      }
    }
  }, [authChecked, isLoggedIn, isSuperAdmin, router]);

  if (!authChecked || !isLoggedIn || !isSuperAdmin) {
    return (
      <div className="shell">
        <Header />
        <Sidebar />
        <main className="main" id="main">
          <OfflineBanner />
          <div className="pad flex items-center justify-center" style={{ minHeight: '60vh' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
              <div className="spin" style={{ width: 36, height: 36 }} />
              <div style={{ color: 'var(--muted)', fontSize: '14px' }}>Loading Command Center...</div>
            </div>
          </div>
        </main>
        <Modal />
        <Toast />
      </div>
    );
  }

  return (
    <div className="shell">
      <Header />
      <Sidebar />
      <main className="main" id="main">
        <OfflineBanner />
        {children}
      </main>
      <Modal />
      <Toast />
    </div>
  );
}

