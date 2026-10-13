'use client';

import { useApp } from '@/context/AppContext';
import { ScreenKey } from '@/types';
import { ROLES } from '@/data/mockData';

export default function ViewOnlyNote({ screenKey }: { screenKey: ScreenKey }) {
  const { role, perm } = useApp();
  const p = perm(screenKey);

  if (p !== 'V') return null;

  return (
    <div className="note" style={{ marginBottom: '14px' }}>
      You are signed in as <b>{ROLES[role]?.n || role}</b>. This screen is <b>view only</b> for your role — actions are shown but disabled.
    </div>
  );
}
