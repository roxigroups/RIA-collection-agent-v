'use client';

import { useState, useRef } from 'react';
import { RecentRow, useApp } from '@/context/AppContext';
import { CSV_ALIASES } from '@/data/mockData';
import { parseCSV, downloadCSV } from '@/utils/formatters';

// One valid call-sheet row, as previewed and sent to the API
interface ParsedRow {
  code: string;
  businessName: string;
  name: string;
  phone: string;
  invoiceNumber: string;
  invoiceDate: string;
  invoiceAmount: number;
  amount: number;
  dueDate: string;
  lang: string;
}

interface ParsedImport {
  filename: string;
  total: number;
  valid: ParsedRow[];
  rejects: { row: string[]; reason: string }[];
  totalOd: number;
}

export function ImportPreviewModalContent({
  imp,
  onClose,
  onSchedule,
}: {
  imp: ParsedImport;
  onClose: () => void;
  onSchedule: (start: boolean) => void;
}) {
  const handleDownloadRejects = () => {
    const rows = [
      ['Row Number', 'Raw Data', 'Reason For Rejection'],
      ...imp.rejects.map((r, i) => [i + 1, JSON.stringify(r.row), r.reason]),
    ];
    downloadCSV(`rejects_${imp.filename}`, rows);
  };

  return (
    <div>
      <div className="grid g3" style={{ marginBottom: '14px' }}>
        <div
          style={{
            background: 'var(--green-soft)',
            padding: '10px 12px',
            borderRadius: '8px',
            border: '1px solid #BFE0CD',
          }}
        >
          <span
            style={{
              fontSize: '11px',
              color: 'var(--green-ink)',
              fontWeight: 700,
              textTransform: 'uppercase',
            }}
          >
            Ready to Dial
          </span>
          <div className="num" style={{ fontSize: '20px', color: 'var(--green-ink)' }}>
            {imp.valid.length} accounts
          </div>
        </div>
        <div
          style={{
            background: imp.rejects.length > 0 ? 'var(--red-soft)' : '#F4F6FA',
            padding: '10px 12px',
            borderRadius: '8px',
            border: '1px solid var(--line)',
          }}
        >
          <span
            style={{
              fontSize: '11px',
              color: 'var(--t2)',
              fontWeight: 700,
              textTransform: 'uppercase',
            }}
          >
            Rejected / Invalid
          </span>
          <div
            className="num"
            style={{
              fontSize: '20px',
              color: imp.rejects.length > 0 ? 'var(--red)' : 'var(--t1)',
            }}
          >
            {imp.rejects.length} rows
          </div>
        </div>
        <div
          style={{
            background: 'var(--blue-soft)',
            padding: '10px 12px',
            borderRadius: '8px',
            border: '1px solid #C9DCFA',
          }}
        >
          <span
            style={{
              fontSize: '11px',
              color: 'var(--navy)',
              fontWeight: 700,
              textTransform: 'uppercase',
            }}
          >
            Overdue In Batch
          </span>
          <div className="num" style={{ fontSize: '20px', color: 'var(--navy)' }}>
            ₹{(imp.totalOd / 100000).toFixed(2)} L
          </div>
        </div>
      </div>

      <div style={{ marginBottom: '12px' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--t2)' }}>
          First 5 Accounts in Dialing Queue:
        </span>
      </div>

      <div
        className="tbl-wrap"
        style={{
          maxHeight: '240px',
          border: '1px solid var(--line)',
          borderRadius: '8px',
          marginBottom: '16px',
        }}
      >
        <table>
          <thead>
            <tr>
              <th>Business Name</th>
              <th>Phone</th>
              <th>Due Date</th>
              <th>Invoice Number</th>
              <th className="right">Invoice Amount</th>
            </tr>
          </thead>
          <tbody>
            {imp.valid.slice(0, 5).map((v, i) => (
              <tr key={i}>
                <td>
                  <b>{v.businessName || v.name}</b>
                </td>
                <td className="mono">{v.phone}</td>
                <td className="mono" style={{ fontSize: '12px' }}>
                  {v.dueDate || v.invoiceDate || '—'}
                </td>
                <td className="mono">{v.invoiceNumber || '—'}</td>
                <td className="num right" style={{ color: 'var(--navy)' }}>
                  {Number(v.invoiceAmount || v.amount || 0) > 0
                    ? `₹${Number(v.invoiceAmount || v.amount || 0).toLocaleString('en-IN')}`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="m-f"
        style={{
          margin: '18px -18px -18px',
          padding: '14px 18px',
          display: 'flex',
          gap: '8px',
          justifyContent: 'flex-end',
          background: 'var(--surface-2)',
        }}
      >
        {imp.rejects.length > 0 && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleDownloadRejects}>
            Download Rejected ({imp.rejects.length})
          </button>
        )}
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => onSchedule(false)}
          data-testid="import-only"
        >
          Import batch ({imp.valid.length} calls)
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => onSchedule(true)}
          data-testid="import-and-call"
        >
          📞 Import & start calling
        </button>
      </div>
    </div>
  );
}

// Customers RIA already spoke to about the same invoice in the last 20 hours: call again or leave out
function RecentChoice({
  rows,
  canSkip,
  onChoose,
  onClose,
}: {
  rows: RecentRow[];
  canSkip: boolean;
  onChoose: (choice: 'call' | 'skip') => Promise<void>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const choose = async (choice: 'call' | 'skip') => {
    setBusy(true);
    await onChoose(choice);
    setBusy(false);
  };
  return (
    <div data-testid="recent-choice">
      <div
        style={{
          fontSize: '14px',
          lineHeight: 1.55,
          color: 'var(--t1)',
          marginBottom: '10px',
        }}
      >
        RIA already spoke to {rows.length === 1 ? 'this customer' : `these ${rows.length} customers`} about the same
        invoice in the last 20 hours. Call {rows.length === 1 ? 'them' : 'them all'} again in this new campaign?
      </div>
      <div className="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th>Row</th>
              <th>Customer</th>
              <th>Invoice</th>
              <th>Last call</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.row}>
                <td>{r.row}</td>
                <td>
                  <b>{r.name}</b>
                  <div className="mono" style={{ fontSize: '12px' }}>
                    {r.phone}
                  </div>
                </td>
                <td className="mono" style={{ fontSize: '12px' }}>
                  {r.invoice}
                </td>
                <td style={{ fontSize: '12px' }}>
                  {r.lastCall}
                  {r.outcome && <div className="meta">{r.outcome}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div
        className="m-f"
        style={{
          margin: '18px -18px -18px',
          padding: '14px 18px',
          display: 'flex',
          gap: '8px',
          justifyContent: 'flex-end',
          background: 'var(--surface-2)',
          flexWrap: 'wrap',
        }}
      >
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        {canSkip && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => choose('skip')}
            disabled={busy}
            data-testid="recent-skip"
          >
            Leave them out
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => choose('call')}
          disabled={busy}
          data-testid="recent-call"
        >
          📞 Call them again
        </button>
      </div>
    </div>
  );
}

export default function ImportCard() {
  const { showToast, importCallSheet, setSelectedBatchId, openModal, closeModal } = useApp();
  const [isOver, setIsOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processText = (filename: string, text: string) => {
    const rawRows = parseCSV(text);
    if (rawRows.length < 2) {
      showToast('CSV must contain a header row and at least 1 data row.');
      return;
    }

    if (rawRows.length - 1 > 100) {
      showToast(`The uploaded CSV contains ${rawRows.length - 1} contacts. Maximum allowed is 100 contacts per file.`);
      return;
    }

    const headers = rawRows[0].map((h) =>
      h
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9_]/g, '_'),
    );
    const mapCol = (canonical: string) => {
      const aliases = (CSV_ALIASES[canonical] || [canonical]).map((a) => a.replace(/[^a-z0-9_]/g, '_'));
      // An exact header wins: a partial match let "invoice date" pass for the invoice number
      const exact = headers.findIndex((h) => aliases.includes(h));
      return exact !== -1 ? exact : headers.findIndex((h) => aliases.some((a) => h.includes(a)));
    };

    const cBusiness = mapCol('business_name');
    const cPhone = mapCol('phno');
    const cDueDate = mapCol('due_date') !== -1 ? mapCol('due_date') : mapCol('invoice_date');
    const cInvNum = mapCol('invoice_number');
    const cInvAmt = mapCol('invoice_amount');
    const cLang = mapCol('lang');

    const valid: ParsedRow[] = [];
    const rejects: { row: string[]; reason: string }[] = [];
    let totalOd = 0;

    for (let i = 1; i < rawRows.length; i++) {
      const r = rawRows[i];
      const phoneRaw = cPhone !== -1 ? r[cPhone] : '';
      const cleanPhone = phoneRaw.replace(/[^0-9]/g, '');

      // Only valid Indian phone number is strictly required to place a call
      if (cleanPhone.length < 10) {
        rejects.push({ row: r, reason: `Invalid phone number: ${phoneRaw || 'empty'}` });
        continue;
      }

      const rawBusiness = cBusiness !== -1 && r[cBusiness] ? r[cBusiness].trim() : '';
      const businessName = rawBusiness || 'Customer';

      const dueDateVal = cDueDate !== -1 && r[cDueDate] ? r[cDueDate].trim() : '';
      const invoiceNumVal = cInvNum !== -1 && r[cInvNum] ? r[cInvNum].trim() : '';
      const amountVal = cInvAmt !== -1 && r[cInvAmt] ? parseFloat(r[cInvAmt].replace(/[^0-9.-]/g, '')) || 0 : 0;
      if (amountVal > 0) {
        totalOd += amountVal;
      }

      valid.push({
        code: invoiceNumVal || '—',
        businessName: businessName,
        name: businessName,
        phone: cleanPhone.length === 10 ? `+91 ${cleanPhone.slice(0, 5)} ${cleanPhone.slice(5)}` : `+${cleanPhone}`,
        invoiceNumber: invoiceNumVal,
        invoiceDate: dueDateVal,
        dueDate: dueDateVal,
        invoiceAmount: amountVal,
        amount: amountVal,
        lang: cLang !== -1 && r[cLang] ? r[cLang].trim() : 'Telugu',
      });
    }

    const parsedData: ParsedImport = {
      filename,
      total: rawRows.length - 1,
      valid,
      rejects,
      totalOd,
    };

    const send = async (start: boolean, recent?: 'call' | 'skip') => {
      const res = await importCallSheet(
        filename,
        valid.map((v) => ({
          businessName: v.businessName,
          name: v.name,
          phone: v.phone,
          invoiceNumber: v.invoiceNumber,
          dueDate: v.dueDate || v.invoiceDate,
          invoiceDate: v.dueDate || v.invoiceDate,
          invoiceAmount: v.invoiceAmount,
          lang: v.lang,
        })),
        start,
        recent,
      );
      if (!res) return;
      if (res.recent?.length) {
        // Nothing imported yet: these customers were spoken to in the last 20 hours
        openModal(
          'Already called today',
          <RecentChoice
            rows={res.recent}
            canSkip={res.recent.length < valid.length}
            onChoose={(choice) => send(start, choice)}
            onClose={closeModal}
          />,
        );
        return;
      }
      closeModal();
      if (res.batch) setSelectedBatchId(res.batch);
      const skipped = res.skipped.length
        ? ` ${res.skipped.length} skipped: ${res.skipped
            .slice(0, 2)
            .map((x) => `row ${x.row} ${x.reason}`)
            .join('; ')}${res.skipped.length > 2 ? '…' : ''}`
        : '';
      showToast(
        res.queued
          ? start
            ? `📞 Calling ${res.queued} customer${res.queued === 1 ? '' : 's'} in ${res.batch}, one after another.${skipped}`
            : `Imported ${res.queued} calls in ${res.batch}. Press 📞 Start calling when you're ready.${skipped}`
          : `Nothing imported.${skipped}`,
      );
    };

    openModal(
      `Call Sheet Validation — ${filename}`,
      <ImportPreviewModalContent imp={parsedData} onClose={closeModal} onSchedule={(start) => send(start)} />,
      undefined,
      true,
    );
  };

  const handleFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      processText(file.name, text);
    };
    reader.readAsText(file);
  };

  const downloadTemplate = () => {
    const rows = [
      ['business name', 'phno', 'due date', 'invoice number', 'invoice amount'],
      ['Example Kirana Store (replace me)', 'replace with a real mobile', '2026-10-15', 'INV-2026-001', '18000'],
      ['Example Super Bazar (replace me)', 'replace with a real mobile', '2026-10-20', 'INV-2026-002', '38000'],
    ];
    downloadCSV('ria_call_sheet_template.csv', rows);
    showToast('Downloaded ria_call_sheet_template.csv');
  };

  return (
    <div className="card" style={{ marginBottom: '18px' }}>
      <div className="card-h">
        <h3>Import Daily Call List (CSV)</h3>
        <span className="sub">Drop your ERP export sheet or distributor ledger (Max 100 contacts)</span>
        <div className="r">
          <button className="btn btn-ghost btn-sm" onClick={downloadTemplate}>
            Download template
          </button>
        </div>
      </div>
      <div className="card-b">
        <div className="imp-grid">
          <div
            className={`drop ${isOver ? 'over' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsOver(true);
            }}
            onDragLeave={() => setIsOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsOver(false);
              if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0]);
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="big">📄</div>
            <div style={{ fontWeight: 600, marginTop: '6px' }}>Drag & drop your call sheet CSV here (Max 100 contacts)</div>
            <div className="meta" style={{ marginTop: '4px' }}>
              or click to browse from computer (UTF-8 encoded, up to 100 contacts)
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files?.[0]) handleFile(e.target.files[0]);
              }}
            />
          </div>

          <div className="cols">
            <div
              style={{
                fontWeight: 700,
                fontSize: '12px',
                letterSpacing: '.08em',
                textTransform: 'uppercase',
                color: 'var(--t3)',
              }}
            >
              Template Structure (Max 100 contacts):
            </div>
            <div>
              <span className="mono">business name</span>{' '}
              <span className="meta">Retailer store or commercial trade name [Optional]</span>
            </div>
            <div>
              <span className="mono">phno</span> <span className="meta">10-digit Indian mobile / contact number [Required]</span>
            </div>
            <div>
              <span className="mono">due date</span>{' '}
              <span className="meta">Payment due date (YYYY-MM-DD) [Optional]</span>
            </div>
            <div>
              <span className="mono">invoice number</span>{' '}
              <span className="meta">ERP invoice or bill reference (e.g. INV-2026-001) [Optional]</span>
            </div>
            <div>
              <span className="mono">invoice amount</span>{' '}
              <span className="meta">Total overdue or pending balance (INR) [Optional]</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
