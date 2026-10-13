'use client';

import React, { useState } from 'react';
import { CampaignContact } from '@/types';

export default function AddContactModalContent({
  onClose,
  onSave,
  initial,
  submitLabel = '+ Add Customer to Campaign',
}: {
  onClose: () => void;
  onSave: (c: Omit<CampaignContact, 'id'>) => void;
  // Editing an existing contact: the form starts with their details
  initial?: Omit<CampaignContact, 'id'>;
  submitLabel?: string;
}) {
  const [name, setName] = useState(initial?.name || '');
  const [phno, setPhno] = useState(initial?.phno || '+91 ');
  const [creditPeriod, setCreditPeriod] = useState(initial?.creditPeriod || '30 Days');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !phno.trim()) return;
    onSave({ name: name.trim(), phno: phno.trim(), creditPeriod });
    onClose();
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="field">
        <label>Customer / Retailer Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Sri Balaji Kirana & General Store"
          required
        />
      </div>

      <div className="field">
        <label>Phone Number (Mobile / WhatsApp)</label>
        <input
          type="text"
          value={phno}
          onChange={(e) => setPhno(e.target.value)}
          placeholder="+91 98490 12345"
          required
        />
      </div>

      <div className="field">
        <label>Credit Period</label>
        <select value={creditPeriod} onChange={(e) => setCreditPeriod(e.target.value)}>
          <option value="7 Days">7 Days</option>
          <option value="15 Days">15 Days</option>
          <option value="21 Days">21 Days</option>
          <option value="30 Days">30 Days (Standard)</option>
          <option value="45 Days">45 Days</option>
          <option value="60 Days">60 Days</option>
          <option value="90 Days">90 Days</option>
          <option value="Immediate / COD">Immediate / COD</option>
        </select>
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
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary btn-sm" data-testid="save-contact">
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
