'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useApp } from '@/context/AppContext';
import { EscalationItem } from '@/types';
import { ROLES } from '@/data/mockData';

export function AssignOwnerModalContent({
  escalation,
  onClose,
  onAssign,
}: {
  escalation: EscalationItem;
  onClose: () => void;
  onAssign: (owner: string) => void;
}) {
  const { users } = useApp();
  const [selectedOwner, setSelectedOwner] = useState(escalation.owner || 'Unassigned');

  // Your team, from Team & Permissions
  const ownerOptions = [
    'Unassigned',
    ...users.filter((u) => u.st === 'Active').map((u) => `${u.n} (${ROLES[u.role]?.n || u.role})`),
  ];
  if (!ownerOptions.includes(selectedOwner)) ownerOptions.push(selectedOwner);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAssign(selectedOwner);
    onClose();
  };

  return (
    <form onSubmit={handleSubmit}>
      <p className="sub" style={{ marginBottom: '14px' }}>
        Assign owner for escalation <b>{escalation.id}</b> ({escalation.customer}).
      </p>

      <div className="field">
        <label>Select Team Member / Role</label>
        <select
          value={selectedOwner}
          onChange={(e) => setSelectedOwner(e.target.value)}
          required
        >
          {ownerOptions.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
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
        <button type="submit" className="btn btn-primary btn-sm">
          Save Assignment
        </button>
      </div>
    </form>
  );
}

export function ResolveModalContent({
  escalation,
  onClose,
  onResolve,
}: {
  escalation: EscalationItem;
  onClose: () => void;
  onResolve: (note: string) => void;
}) {
  const [note, setNote] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onResolve(note);
    onClose();
  };

  return (
    <form onSubmit={handleSubmit}>
      <p className="sub" style={{ marginBottom: '14px' }}>
        Resolve escalation <b>{escalation.id}</b> for <b>{escalation.customer}</b>.
      </p>

      <div className="field">
        <label>Resolution Action / Settlement Note</label>
        <textarea
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="e.g. Credit note CN-102 issued for damaged stock; payment promised for balance."
          required
        />
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
        <button type="submit" className="btn btn-primary btn-sm">
          Confirm Resolution
        </button>
      </div>
    </form>
  );
}

export default function EscalationsTable() {
  const {
    escalations,
    assignEscalation,
    resolveEscalation,
    openModal,
    closeModal,
    setSelectedCallId,
    canAct,
  } = useApp();

  const allowed = canAct('tickets');
  const openEscalations = escalations.filter((e) => e.status !== 'Resolved');

  const handleOpenAssign = (e: EscalationItem) => {
    openModal(
      `Assign Ticket — ${e.id}`,
      <AssignOwnerModalContent
        escalation={e}
        onClose={closeModal}
        onAssign={(owner) => assignEscalation(e.id, owner)}
      />
    );
  };

  const handleOpenResolve = (e: EscalationItem) => {
    openModal(
      `Resolve Ticket — ${e.id}`,
      <ResolveModalContent
        escalation={e}
        onClose={closeModal}
        onResolve={(note) => resolveEscalation(e.id, note)}
      />
    );
  };

  return (
    <div>
      <div className="card" style={{ marginBottom: '18px' }}>
        <div
          className="card-h"
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '10px',
            padding: '14px 18px',
          }}
        >
          <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0 }}>Open tickets</h3>
          <span
            style={{
              fontSize: '13px',
              color: 'var(--t3)',
              fontWeight: 500,
            }}
          >
            oldest and most severe first — items age visibly and surface on the Owner Dashboard
          </span>
        </div>

        <div className="tbl-wrap">
          <table style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ width: '10%', padding: '12px 18px' }}>REF</th>
                <th style={{ width: '28%' }}>CATEGORY</th>
                <th style={{ width: '12%' }}>SEVERITY</th>
                <th style={{ width: '18%' }}>OWNER</th>
                <th style={{ width: '10%' }}>AGE</th>
                <th style={{ width: '10%' }}>SOURCE</th>
                <th style={{ width: '12%', textAlign: 'right', paddingRight: '18px' }}></th>
              </tr>
            </thead>
            <tbody>
              {openEscalations.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '36px', color: 'var(--t3)' }}>
                    No open escalations at this time.
                  </td>
                </tr>
              ) : (
                openEscalations.map((e) => {
                  const isHigh = e.severity === 'High';
                  const isMed = e.severity === 'Medium';

                  return (
                    <tr key={e.id}>
                      <td style={{ padding: '14px 18px' }}>
                        <span className="mono" style={{ fontWeight: 600, color: 'var(--t1)', fontSize: '14px' }}>
                          {e.id}
                        </span>
                      </td>

                      <td>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--t1)' }}>
                          {e.category}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--t3)', marginTop: '2px' }}>
                          {e.customer}
                        </div>
                      </td>

                      <td>
                        <span
                          className={`chip ${isHigh ? 'c-red' : isMed ? 'c-gold' : 'c-blue'}`}
                          style={{ fontSize: '11.5px', padding: '3px 9px' }}
                        >
                          {e.severity}
                        </span>
                      </td>

                      <td style={{ color: 'var(--t1)', fontWeight: 500, fontSize: '13.5px' }}>
                        {e.owner}
                      </td>

                      <td className="mono" style={{ color: 'var(--t1)', fontWeight: 600, fontSize: '13px' }}>
                        {e.age}
                      </td>

                      <td>
                        <Link
                          href={`/calls/${e.sourceCallId}`}
                          onClick={() => setSelectedCallId(e.sourceCallId)}
                          style={{
                            color: 'var(--blue)',
                            fontWeight: 700,
                            textDecoration: 'none',
                            fontFamily: 'var(--mono)',
                            fontSize: '13px',
                          }}
                        >
                          {e.sourceCallId}
                        </Link>
                      </td>

                      <td style={{ textAlign: 'right', paddingRight: '18px' }}>
                        <div style={{ display: 'inline-flex', gap: '8px', alignItems: 'center' }}>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            disabled={!allowed}
                            onClick={() => handleOpenAssign(e)}
                            style={{ padding: '6px 14px', fontSize: '12.5px', fontWeight: 600 }}
                          >
                            Assign
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={!allowed}
                            onClick={() => handleOpenResolve(e)}
                            style={{
                              background: 'var(--brand-bg)',
                              color: '#fff',
                              padding: '6px 14px',
                              fontSize: '12.5px',
                              fontWeight: 600,
                            }}
                          >
                            Resolve
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div
        className="note"
        style={{
          fontSize: '12.5px',
          color: 'var(--t2)',
          lineHeight: '1.5',
          background: 'var(--surface-2)',
          border: '1px solid var(--line-2)',
          borderRadius: '8px',
          padding: '12px 16px',
        }}
      >
        A ticket is raised when a promise falls outside the credit period, a dispute or already-paid claim is made, model confidence is low, retries are exhausted, promises are repeatedly broken, or the retailer asks for a person.
      </div>
    </div>
  );
}
