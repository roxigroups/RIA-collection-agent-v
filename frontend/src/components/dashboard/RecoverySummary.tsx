'use client';

import { useApp } from '@/context/AppContext';
import { lakh } from '@/utils/formatters';

export default function RecoverySummary() {
  const { summary } = useApp();
  return (
    <div className="grid g3" style={{ marginBottom: '14px' }}>
      <div className="tile navy">
        <div className="n">{lakh(summary.invoiced)}</div>
        <div className="l">Total Invoice Value</div>
        <div className="d">Across {summary.invoiceAccounts.toLocaleString('en-IN')} retailer accounts in uploaded invoice files</div>
      </div>
      <div className="tile teal">
        <div className="n">{lakh(summary.promisedMtd)}</div>
        <div className="l">Promised to Pay (MTD)</div>
        <div className="d">Confirmed by retailers on RIA calls</div>
      </div>
      <div className="tile gold">
        <div className="n">{lakh(summary.pipeline)}</div>
        <div className="l">Open PTP Pipeline</div>
        <div className="d">Promises due today or upcoming</div>
      </div>
    </div>
  );
}
