
// Timeline colour by what happened on the call
function eventClass(disp: string): string {
  const d = disp.toLowerCase();
  if (d.includes('ptp') || d.includes('paid')) return 'pay';
  if (d.includes('dispute') || d.includes('refused') || d.includes('do not call') || d.includes('wrong')) return 'esc';
  return 'ptp';
}

export default function PtpTimeline({
  history,
}: {
  history?: Array<{ d: string; typ: string; dur: string; disp: string }>;
}) {
  const events = history || [];

  return (
    <div className="card">
      <div className="card-h">
        <h3>Touchpoint & PTP Timeline</h3>
        <span className="sub">Chronological audit trail of all interactions</span>
      </div>
      <div className="card-b">
        {events.length === 0 ? (
          <div className="meta">No calls with this retailer yet.</div>
        ) : (
          <div className="timeline">
            {events.map((e, idx) => (
              <div key={idx} className={`tl ${eventClass(e.disp)}`}>
                <div className="when">{e.d}</div>
                <div className="what">
                  {e.typ} call · {e.dur}
                </div>
                <div className="det">{e.disp}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
