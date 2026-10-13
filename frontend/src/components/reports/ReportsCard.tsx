'use client';

import { REPORTS } from '@/data/mockData';
import { downloadCSV } from '@/utils/formatters';
import { useApp } from '@/context/AppContext';

export default function ReportsCard() {
  const { showToast, calls, ptps: PTPS, nolift: NOLIFT, escalations: ESCALATIONS, auditLog } = useApp();

  const handleDownload = (k: string, template: string) => {
    // Today's date in the file name, not the template's
    const fn = template.replace(/\d{4}_\d{2}_\d{2}/, new Date().toISOString().slice(0, 10).replace(/-/g, '_'));
    if (k === 'daily_summary') {
      const rows = [
        ['Call ID', 'Retailer ID', 'Name', 'Phone', 'Time', 'Language', 'Duration', 'Disposition', 'PTP Date', 'Autonomy Level', 'Sentiment Score'],
        ...calls.map((c) => [c.id, c.ret, c.name, c.ph, c.time, c.lang, c.dur, c.disp, c.ptp, c.auto, c.score]),
      ];
      downloadCSV(fn, rows);
    } else if (k === 'ptp_pipeline') {
      const rows = [
        ['PTP ID', 'Retailer ID', 'Name', 'Phone', 'Due Date', 'Amount (INR)', 'Status', 'Autonomy Level'],
        ...PTPS.map((p) => [p.id, p.ret, p.name, p.ph, p.due, p.amt, p.st, p.auto]),
      ];
      downloadCSV(fn, rows);
    } else if (k === 'disputes') {
      const rows = [
        ['Escalation REF', 'Customer', 'Category', 'Severity', 'Owner', 'Age', 'Source Call'],
        ...ESCALATIONS.map((e) => [e.id, e.customer, e.category, e.severity, e.owner, e.age, e.sourceCallId]),
      ];
      downloadCSV(fn, rows);
    } else if (k === 'no_lift') {
      const rows = [
        ['Retailer ID', 'Name', 'Phone', 'Attempts', 'Last Call', 'Next Scheduled Attempt', 'Autonomy Level'],
        ...NOLIFT.map((n) => [n.ret, n.name, n.ph, n.att, n.last, n.next, n.auto]),
      ];
      downloadCSV(fn, rows);
    } else {
      const rows = [
        ['Timestamp', 'Actor', 'Role', 'Action', 'Target', 'Details'],
        ...auditLog,
      ];
      downloadCSV(fn, rows);
    }
    showToast(`Downloaded ${fn}`);
  };

  return (
    <div className="card">
      <div className="card-h">
        <h3>Reports</h3>
        <span className="sub">Pre-formatted audit-ready CSV exports</span>
      </div>
      <div className="card-b" style={{ padding: 0 }}>
        {REPORTS.map((r) => (
          <div key={r.k} className="list-row">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="name">{r.n}</div>
              <div className="meta">{r.d}</div>
            </div>
            <div className="rr">
              <span className="chip c-grey">{r.fmt}</span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => handleDownload(r.k, r.fn)}
              >
                Download CSV
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
