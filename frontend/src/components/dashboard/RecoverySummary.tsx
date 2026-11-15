'use client';

import { useApp } from '@/context/AppContext';
import { lakh } from '@/utils/formatters';

export default function RecoverySummary() {
  const { summary } = useApp();

  const uploadedAmount = summary.uploadedTodayAmount ?? summary.invoiced ?? 0;
  const uploadedCount = summary.uploadedTodayCount ?? summary.invoiceAccounts ?? 0;

  const ptpAmount = summary.ptpTodayAmount ?? summary.promisedMtd ?? 0;
  const ptpCount = summary.ptpTodayCount ?? 0;
  const ptpAccounts = summary.ptpTodayAccounts ?? (ptpCount > 0 ? ptpCount : 0);

  const remainingAmount = summary.remainingTodayAmount ?? summary.pipeline ?? Math.max(0, uploadedAmount - ptpAmount);
  const remainingCount = summary.remainingTodayCount ?? Math.max(0, uploadedCount - ptpCount);

  return (
    <div className="grid g3" style={{ marginBottom: '14px' }}>
      <div className="tile navy">
        <div className="n">{lakh(uploadedAmount)}</div>
        <div className="l">Uploaded Today</div>
        <div className="d">
          {uploadedCount.toLocaleString('en-IN')} {uploadedCount === 1 ? 'Invoice' : 'Invoices'} uploaded today
        </div>
      </div>
      <div className="tile teal">
        <div className="n">{lakh(ptpAmount)}</div>
        <div className="l">PTP Secured Today</div>
        <div className="d">
          {ptpAccounts.toLocaleString('en-IN')} {ptpAccounts === 1 ? 'Retailer' : 'Retailers'} committed
        </div>
      </div>
      <div className="tile gold">
        <div className="n">{lakh(remainingAmount)}</div>
        <div className="l">Remaining Today</div>
        <div className="d">
          {remainingCount.toLocaleString('en-IN')} {remainingCount === 1 ? 'Invoice' : 'Invoices'} pending / in retry
        </div>
      </div>
    </div>
  );
}
