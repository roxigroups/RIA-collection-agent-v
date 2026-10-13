'use client';

import React, { useState } from 'react';
import { useApp } from '@/context/AppContext';
import { UserItem, RoleKey } from '@/types';
import { ROLES, AV } from '@/data/mockData';
import { initials } from '@/utils/formatters';

export function UserModalContent({
  user,
  onClose,
  onSave,
}: {
  user: UserItem;
  onClose: () => void;
  onSave: (updated: Partial<UserItem>) => void;
}) {
  const [name, setName] = useState(user.n);
  const [email, setEmail] = useState(user.e);
  const [phone, setPhone] = useState(user.ph);
  const [role, setRole] = useState<RoleKey>(user.role);
  const [status, setStatus] = useState(user.st);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ n: name, e: email, ph: phone, role, st: status });
    onClose();
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="field">
        <label>Full Name</label>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="field">
        <label>Email Address</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>
      <div className="field">
        <label>Mobile Number</label>
        <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} required />
      </div>
      <div className="field">
        <label>Role Assignment</label>
        <select value={role} onChange={(e) => setRole(e.target.value as RoleKey)}>
          {Object.values(ROLES).map((r) => (
            <option key={r.k} value={r.k}>
              {r.k} — {r.n}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>Account Status</label>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="Active">Active</option>
          <option value="Suspended">Suspended</option>
          <option value="Inactive">Inactive</option>
        </select>
      </div>
      <div className="m-f" style={{ margin: '18px -18px -18px', padding: '14px 18px', display: 'flex', gap: '8px', justifyContent: 'flex-end', background: 'var(--surface-2)' }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary btn-sm">
          Save User
        </button>
      </div>
    </form>
  );
}

export default function UsersCard() {
  const { users, updateUser, canAct, openModal, closeModal } = useApp();
  // Changing users is for the owner and tenant admin (the server checks this too)
  const { role } = useApp();
  const allowed = canAct('dashboard') && (role === 'OW' || role === 'TA');

  const handleEdit = (u: UserItem) => {
    openModal(
      `Edit User — ${u.n}`,
      <UserModalContent
        user={u}
        onClose={closeModal}
        onSave={(updates) => updateUser(u.id, updates)}
      />
    );
  };

  return (
    <div className="card">
      <div className="card-h">
        <h3>Team & Permissions</h3>
        <span className="sub">Role assignments mapped to Phase 1 policy (§ 10.2)</span>
      </div>
      <div className="card-b" style={{ padding: 0 }}>
        {users.map((u) => {
          const bg = AV[u.role] || '#0F2350';
          const init = initials(u.n);

          return (
            <div key={u.id} className="list-row">
              <div className="uav" style={{ background: bg }}>
                {init}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="name">{u.n}</div>
                <div className="meta">
                  {u.e} · {u.ph}
                </div>
              </div>
              <div className="rr">
                <span className="chip c-blue">{u.role} — {ROLES[u.role]?.n.split(' ')[0]}</span>
                <span className="chip c-green">{u.st}</span>
                {allowed && (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleEdit(u)}>
                    Edit
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
