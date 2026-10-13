'use client';

import { useApp } from '@/context/AppContext';
import { ScreenKey } from '@/types';

interface ActionBtnProps {
  auto: string;
  label: string;
  className?: string;
  onClick: () => void;
  screen?: ScreenKey;
}

export default function ActionButton({ auto, label, className = 'btn-ghost btn-sm', onClick, screen }: ActionBtnProps) {
  const { canAct } = useApp();
  const allowed = screen ? canAct(screen) : true;

  const txt = auto === 'L1' ? 'Approve and ' + label.toLowerCase() : auto === 'L0' ? 'Request approval' : label;

  return (
    <button
      className={`btn ${className}`}
      disabled={!allowed}
      onClick={(e) => {
        e.stopPropagation();
        if (allowed) onClick();
      }}
    >
      {txt}
    </button>
  );
}
