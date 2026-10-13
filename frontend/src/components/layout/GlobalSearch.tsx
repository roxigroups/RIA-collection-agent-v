'use client';

import React, { useId, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useApp } from '@/context/AppContext';
import { NAV } from '@/data/mockData';
import { byName, matchesQuery } from '@/utils/search';

interface Hit {
  key: string;
  type: string;
  label: string;
  sub: string;
  open: () => void;
}

const PER_GROUP = 4;

// The header search: pages, contacts, retailers, calls and tickets, as you type
export default function GlobalSearch() {
  const router = useRouter();
  const { perm, retailers, calls, campaignContacts, escalations, setSelectedRetailerId, setSelectedCallId } = useApp();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();

  const q = query.trim();
  const can = (screen: Parameters<typeof perm>[0]) => perm(screen) !== 'X';
  const hits: Hit[] = !q
    ? []
    : [
        ...NAV.filter((n) => can(n.k) && matchesQuery(q, [n.t]))
          .slice(0, PER_GROUP)
          .map((n) => ({ key: `page-${n.k}`, type: 'Page', label: n.t, sub: 'Open page', open: () => router.push(`/${n.k}`) })),
        ...(can('contacts') ? campaignContacts : [])
          .filter((c) => matchesQuery(q, [c.name], [c.phno]))
          .sort(byName)
          .slice(0, PER_GROUP)
          .map((c) => ({
            key: `contact-${c.id}`, type: 'Contact', label: c.name, sub: c.phno,
            open: () => router.push(`/contacts?q=${encodeURIComponent(c.name)}`),
          })),
        ...(can('collections') ? retailers : [])
          .filter((r) => matchesQuery(q, [r.name, r.owner, r.code, r.id], [r.phone]))
          .sort(byName)
          .slice(0, PER_GROUP)
          .map((r) => ({
            key: `retailer-${r.id}`, type: 'Retailer', label: r.name, sub: [r.code, r.phone].filter(Boolean).join(' · '),
            open: () => {
              setSelectedRetailerId(r.id);
              router.push(`/retailers/${r.id}`);
            },
          })),
        ...(can('calls') ? calls : [])
          .filter((c) => matchesQuery(q, [c.name, c.id, c.disp], [c.ph]))
          .slice(0, PER_GROUP)
          .map((c) => ({
            key: `call-${c.id}`, type: 'Call', label: c.name, sub: [c.time, c.disp].filter(Boolean).join(' · '),
            open: () => {
              setSelectedCallId(c.id);
              router.push(`/calls/${c.id}`);
            },
          })),
        ...(can('tickets') ? escalations : [])
          .filter((t) => matchesQuery(q, [t.customer, t.category, t.id]))
          .slice(0, PER_GROUP)
          .map((t) => ({
            key: `ticket-${t.id}`, type: 'Ticket', label: t.customer, sub: `${t.category} · ${t.status}`,
            open: () => router.push('/tickets'),
          })),
      ];
  const current = Math.min(active, Math.max(hits.length - 1, 0));

  const choose = (hit: Hit | undefined) => {
    if (!hit) return;
    hit.open();
    setQuery('');
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setOpen(true);
      if (hits.length) setActive((current + (e.key === 'ArrowDown' ? 1 : hits.length - 1)) % hits.length);
    } else if (e.key === 'Enter') {
      choose(hits[current]);
    } else if (e.key === 'Escape') {
      setOpen(false);
      e.currentTarget.blur();
    }
  };

  return (
    <div className="search">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--t2)" strokeWidth="2.4">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.5-3.5" />
      </svg>
      <input
        type="text"
        placeholder="Search retailers, calls, actions…"
        value={query}
        role="combobox"
        aria-expanded={open && !!q}
        aria-controls={listId}
        aria-activedescendant={open && hits.length ? `${listId}-${current}` : undefined}
        aria-autocomplete="list"
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {open && q && (
        <div className="search-pop" id={listId} role="listbox">
          {hits.length === 0 ? (
            <div className="search-empty">No matches for “{q}”</div>
          ) : (
            hits.map((h, i) => (
              <div
                key={h.key}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === current}
                className={i === current ? 'search-hit on' : 'search-hit'}
                onMouseEnter={() => setActive(i)}
                // mousedown, not click: the input's blur would close the list first
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(h);
                }}
              >
                <span className="search-type">{h.type}</span>
                <span className="search-text">
                  <b>{h.label}</b>
                  {h.sub && <span>{h.sub}</span>}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
