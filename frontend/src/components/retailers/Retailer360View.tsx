'use client';

import { useApp } from '@/context/AppContext';
import { inr } from '@/utils/formatters';
import ActionButton from '../common/ActionButton';
import PtpTimeline from './PtpTimeline';
import { EmptyStateView } from '../common/StateViews';

export default function Retailer360View({ retailerId }: { retailerId?: string }) {
  const { retailers, selectedRetailerId, addTicket, callRetailer, notConnected } = useApp();

  const idToFind = retailerId || selectedRetailerId;
  const retailer = retailers.find((r) => r.id === idToFind) || (idToFind ? undefined : retailers[0]);
  if (!retailer) {
    return <EmptyStateView screenKey="retailers" />;
  }

  const handleCall = () => {
    callRetailer(retailer.id);
  };

  const handleSendStatement = () => {
    notConnected('WhatsApp statements');
  };

  const handleRaiseDispute = () => {
    addTicket({
      cust: retailer.name,
      cat: 'Payment dispute',
      st: 'Open',
      src: 'Retailer 360',
      who: 'Unassigned',
    });
  };

  return (
    <div>
      <div className="grid g4" style={{ marginBottom: '14px' }}>
        <div className="tile navy">
          <div className="n">{inr(retailer.os)}</div>
          <div className="l">Total Ledger Outstanding</div>
          <div className="d">3 active invoices</div>
        </div>
        <div className="tile red">
          <div className="n">{inr(retailer.od)}</div>
          <div className="l">Overdue Balance</div>
          <div className="d">Aging: {retailer.bucket}</div>
        </div>
        <div className="tile gold">
          <div className="n">{retailer.ptp}</div>
          <div className="l">Current PTP Commitment</div>
          <div className="d">Autonomy level: {retailer.auto}</div>
        </div>
        <div className="tile teal">
          <div className="n">{retailer.score}%</div>
          <div className="l">Payment Reliability Score</div>
          <div className="d">Based on past 12 months data</div>
        </div>
      </div>

      <div className="split">
        <div className="grid" style={{ gap: '14px' }}>
          <div className="card">
            <div className="card-h">
              <h3>Retailer Account Profile & AI Guidance</h3>
              <div className="r">
                <span className="chip c-blue">{retailer.code}</span>
              </div>
            </div>
            <div className="card-b">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: '18px' }}>{retailer.name}</h2>
                  <div className="meta" style={{ marginTop: '2px' }}>
                    Owner: <b>{retailer.owner}</b> · {retailer.city}
                  </div>
                  <div className="meta">Phone: <b>{retailer.phone}</b> · Preferred Language: <b>{retailer.lang}</b></div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className="chip c-green">Credit Limit: {inr(retailer.lim)}</span>
                </div>
              </div>

              <div className="rail" style={{ marginBottom: '16px' }}>
                <h4>AI Telecalling Strategy & Recommendation:</h4>
                <div style={{ fontSize: '13px', color: 'var(--t2)' }}>
                  Account has consistent purchase history. Call in <b>{retailer.lang}</b> between 10 AM – 12 PM. Offer split payment plan on overdue invoices 0891 and 0944 before issuing credit hold.
                </div>
                <ul className="why">
                  <li><b>Bucket:</b> {retailer.bucket}</li>
                  <li><b>Credit Utilization:</b> {((retailer.os / retailer.lim) * 100).toFixed(0)}%</li>
                  <li><b>Avg Payment Delay:</b> 14 days</li>
                  <li><b>WhatsApp Enabled:</b> Yes</li>
                </ul>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <ActionButton
                  auto={retailer.auto}
                  label="Place RIA Call Now"
                  className="btn-primary"
                  screen="retailers"
                  onClick={handleCall}
                />
                <button className="btn btn-ghost" onClick={handleSendStatement}>
                  Send WhatsApp Ledger
                </button>
                <button className="btn btn-ghost" onClick={handleRaiseDispute}>
                  Raise Care Ticket
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-h">
              <h3>Outstanding Invoices & Ledger Breakdown</h3>
            </div>
            <div className="tbl-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Invoice Reference</th>
                    <th>Due Date</th>
                    <th className="right">Amount (INR)</th>
                    <th>Status</th>
                    <th className="right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(retailer.invoices || []).map((inv) => (
                    <tr key={inv.inv}>
                      <td className="mono">{inv.inv}</td>
                      <td>{inv.due}</td>
                      <td className="num right">{inr(inv.amt)}</td>
                      <td>
                        <span
                          className={`chip ${
                            inv.st.includes('Overdue') ? 'c-red' : 'c-green'
                          }`}
                        >
                          {inv.st}
                        </span>
                      </td>
                      <td className="right">
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => notConnected('WhatsApp payment links')}
                        >
                          Pay Link
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="grid" style={{ gap: '14px' }}>
          <PtpTimeline history={retailer.history} />
        </div>
      </div>
    </div>
  );
}
