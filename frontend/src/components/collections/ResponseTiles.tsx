'use client';

import { useApp } from '@/context/AppContext';

interface ResponseTilesProps {
  activeKey: string;
  onSelect: (k: string) => void;
}

export default function ResponseTiles({ activeKey, onSelect }: ResponseTilesProps) {
  const { resp: RESP } = useApp();
  const top4 = RESP.slice(0, 4);

  return (
    <div className="resp" style={{ marginBottom: '14px' }}>
      {top4.map((r) => {
        const isSelected = activeKey === r.k;
        return (
          <button
            key={r.k}
            className={`rstat ${isSelected ? 'on' : ''}`}
            onClick={() => onSelect(r.k)}
          >
            <div className="l">
              <i style={{ background: r.c }} />
              {r.l}
            </div>
            <div className="n">{r.n}</div>
            <div className="d">{r.d}</div>
          </button>
        );
      })}
    </div>
  );
}
