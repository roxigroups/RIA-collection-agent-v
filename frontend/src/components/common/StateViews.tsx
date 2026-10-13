'use client';

import { ScreenKey } from '@/types';
import { EMPTIES } from '@/data/mockData';
import { useApp } from '@/context/AppContext';

export function SkeletonView() {
  return (
    <>
      <div className="grid g4" style={{ marginBottom: '14px' }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card" style={{ height: '88px' }}>
            <div className="card-b">
              <div className="skel" style={{ height: '22px', width: '60%' }} />
              <div className="skel" style={{ height: '12px', width: '40%', marginTop: '10px' }} />
            </div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-b">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skel" style={{ height: '16px', marginBottom: '12px' }} />
          ))}
        </div>
      </div>
    </>
  );
}

export function ErrorBoxView() {
  const { setViewState } = useApp();
  return (
    <div className="card errbox">
      <div className="ico" style={{ fontSize: '26px', marginBottom: '10px', opacity: 0.5 }}>⚠️</div>
      <h3>Something didn’t load</h3>
      <p>We couldn’t reach the RIA services. Check connection or try again.</p>
      <div className="cid" style={{ fontFamily: 'var(--mono)', fontSize: '12px', color: 'var(--t3)', marginBottom: '14px' }}>
        corr-id: 7f3b-9a1c-4e20-8812
      </div>
      <button className="btn btn-primary btn-sm" onClick={() => setViewState('normal')}>
        Retry
      </button>
    </div>
  );
}

export function NoPermView() {
  const { role } = useApp();
  return (
    <div className="card noperm">
      <div className="ico" style={{ fontSize: '26px', marginBottom: '10px', opacity: 0.5 }}>🔒</div>
      <h3>Access restricted</h3>
      <p>Your role ({role}) does not have permission to view this screen.</p>
    </div>
  );
}

export function EmptyStateView({ screenKey }: { screenKey: ScreenKey }) {
  const e = EMPTIES[screenKey] || ['📁', 'No data', 'Nothing to display here yet.'];
  return (
    <div className="card empty">
      <div className="ico" style={{ fontSize: '26px', marginBottom: '10px', opacity: 0.5 }}>{e[0]}</div>
      <h3>{e[1]}</h3>
      <p>{e[2]}</p>
    </div>
  );
}
