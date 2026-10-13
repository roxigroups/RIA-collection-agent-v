'use client';

import React, { useState, useRef } from 'react';
import { useApp } from '@/context/AppContext';
import { parseCSV } from '@/utils/formatters';
import { byName, matchesQuery } from '@/utils/search';
import { CampaignContact } from '@/types';
import AddContactModalContent from './AddContactModal';
import ConfirmModal from '../common/ConfirmModal';

export default function ContactsTable({ initialSearch = '' }: { initialSearch?: string }) {
  const {
    campaignContacts, addCampaignContact, deleteCampaignContacts,
    queueContactCall, openModal, closeModal, showToast, canAct,
  } = useApp();
  const allowed = canAct('contacts');
  const [search, setSearch] = useState(initialSearch);
  const [creditFilter, setCreditFilter] = useState('ALL');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // Ticked for deleting: separate from the campaign selection above, which queues calls
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filtered = campaignContacts
    .filter((c) => (creditFilter === 'ALL' || c.creditPeriod === creditFilter) && matchesQuery(search, [c.name], [c.phno]))
    .sort(byName);

  const checked = campaignContacts.filter((c) => checkedIds.has(c.id));
  const allShownChecked = filtered.length > 0 && filtered.every((c) => checkedIds.has(c.id));
  const someShownChecked = filtered.some((c) => checkedIds.has(c.id));

  const toggleChecked = (id: string) => {
    const next = new Set(checkedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setCheckedIds(next);
  };

  const toggleAllShown = () => {
    const next = new Set(checkedIds);
    for (const c of filtered) {
      if (allShownChecked) next.delete(c.id);
      else next.add(c.id);
    }
    setCheckedIds(next);
  };

  const handleDeleteChecked = () => {
    const ids = checked.map((c) => c.id);
    const shown = checked.slice(0, 8);
    openModal(
      `Delete ${ids.length} contact${ids.length === 1 ? '' : 's'}?`,
      <ConfirmModal
        message={
          <>
            These contacts will be removed from the campaign customer list:
            <ul style={{ margin: '8px 0', paddingLeft: '18px' }}>
              {shown.map((c) => (
                <li key={c.id}>
                  <b>{c.name}</b> ({c.phno})
                </li>
              ))}
              {ids.length > shown.length && <li>and {ids.length - shown.length} more</li>}
            </ul>
            Their invoices and call history stay in Retailer 360.
          </>
        }
        confirmLabel={`Delete ${ids.length} contact${ids.length === 1 ? '' : 's'}`}
        onConfirm={async () => {
          if (await deleteCampaignContacts(ids)) {
            setCheckedIds(new Set());
            setSelectedIds(new Set([...selectedIds].filter((id) => !ids.includes(id))));
          }
        }}
        onClose={closeModal}
      />
    );
  };

  const handleToggleSelect = async (c: CampaignContact) => {
    const next = new Set(selectedIds);

    if (selectedIds.has(c.id)) {
      next.delete(c.id);
      setSelectedIds(next);
      showToast(`Deselected ${c.name}`);
      return;
    }
    // Ticking a contact queues a real call about their oldest unpaid invoice
    if (await queueContactCall(c.id)) {
      next.add(c.id);
      setSelectedIds(next);
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
      showToast('Deselected all contacts');
    } else {
      const allIds = new Set(filtered.map((c) => c.id));
      setSelectedIds(allIds);
      showToast(`Selected all ${filtered.length} contacts (tick a contact to queue its call)`);
    }
  };

  const handleOpenAddModal = () => {
    openModal(
      'Add Customer to Campaign List',
      <AddContactModalContent
        onClose={closeModal}
        onSave={(newC) => addCampaignContact(newC)}
      />
    );
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const rows = parseCSV(text);
      if (rows.length < 2) {
        showToast('CSV must contain a header and at least 1 contact row.');
        return;
      }
      let importedCount = 0;
      for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const name = row[0]?.trim();
        const ph = row[1]?.trim();
        const terms = row[2]?.trim() || '30 Days';
        if (name && ph) {
          addCampaignContact({
            name,
            phno: ph.startsWith('+') ? ph : `+91 ${ph}`,
            creditPeriod: terms,
          });
          importedCount++;
        }
      }
      showToast(`✓ Imported ${importedCount} contacts from ${file.name}`);
    };
    reader.readAsText(file);
  };

  return (
    <div className="card">
      <div className="card-h">
        <div>
          <h3>Campaign Customer Directory</h3>
          <span className="sub">
            All customer accounts added to automated telecalling campaigns ({campaignContacts.length} total)
          </span>
        </div>
        <div className="r">
          {allowed && checked.length > 0 && (
            <>
              <button
                type="button"
                className="btn btn-red btn-sm"
                data-testid="delete-selected-contacts"
                onClick={handleDeleteChecked}
              >
                🗑 Delete selected ({checked.length})
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setCheckedIds(new Set())}>
                Clear
              </button>
            </>
          )}
          {selectedIds.size > 0 && (
            <span className="chip c-green" style={{ fontSize: '12px' }}>
              {selectedIds.size} Selected for Campaign
            </span>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => fileInputRef.current?.click()}
            title="Import contacts from a CSV file"
          >
            Import .csv
          </button>
          {allowed && (
            <button className="btn btn-primary btn-sm" onClick={handleOpenAddModal}>
              + Add Contact
            </button>
          )}
        </div>
      </div>

      <div className="filters">
        <input
          type="text"
          placeholder="Filter by customer name or phone number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: '300px', padding: '6px 10px', fontSize: '13px' }}
        />

        <select value={creditFilter} onChange={(e) => setCreditFilter(e.target.value)}>
          <option value="ALL">All Credit Periods</option>
          <option value="7 Days">7 Days</option>
          <option value="15 Days">15 Days</option>
          <option value="21 Days">21 Days</option>
          <option value="30 Days">30 Days</option>
          <option value="45 Days">45 Days</option>
          <option value="60 Days">60 Days</option>
          <option value="90 Days">90 Days</option>
          <option value="Immediate / COD">Immediate / COD</option>
        </select>

        <button className="btn btn-ghost btn-sm" onClick={handleSelectAll}>
          {selectedIds.size === filtered.length && filtered.length > 0 ? 'Deselect All' : 'Select All'}
        </button>

        <div className="sp">
          <span>
            Showing <b>{filtered.length}</b> of <b>{campaignContacts.length}</b> contacts
          </span>
        </div>
      </div>

      <div className="tbl-wrap">
        <table>
          <thead>
            <tr>
              {allowed && (
                <th style={{ width: '40px' }}>
                  <input
                    type="checkbox"
                    className="row-check"
                    aria-label="Select all shown contacts for deleting"
                    title="Select all shown contacts for deleting"
                    checked={allShownChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = someShownChecked && !allShownChecked;
                    }}
                    onChange={toggleAllShown}
                    disabled={filtered.length === 0}
                  />
                </th>
              )}
              <th style={{ width: '46%' }}>Name</th>
              <th style={{ width: '32%' }}>Phone Number (phno)</th>
              <th style={{ width: '22%' }}>Credit Period</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={allowed ? 4 : 3} style={{ textAlign: 'center', padding: '32px', color: 'var(--t3)' }}>
                  No customer contacts match your filter.
                </td>
              </tr>
            ) : (
              filtered.map((c) => {
                const isSelected = selectedIds.has(c.id);
                const isChecked = checkedIds.has(c.id);

                return (
                  <tr
                    key={c.id}
                    className={[isSelected && 'sel', isChecked && 'checked'].filter(Boolean).join(' ')}
                    onClick={() => handleToggleSelect(c)}
                  >
                    {allowed && (
                      <td onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="row-check"
                          aria-label={`Select ${c.name} for deleting`}
                          checked={isChecked}
                          onChange={() => toggleChecked(c.id)}
                        />
                      </td>
                    )}
                    <td>
                      <div className="name" style={{ fontSize: '14px' }}>{c.name}</div>
                    </td>
                    <td className="mono" style={{ fontSize: '13.5px', color: 'var(--navy)', fontWeight: 600 }}>
                      {c.phno}
                    </td>
                    <td>
                      <span className="chip c-blue" style={{ fontSize: '12px', padding: '4px 10px' }}>
                        {c.creditPeriod}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
