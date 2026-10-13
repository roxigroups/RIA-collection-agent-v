'use client';

import { useState } from 'react';
import { ScheduledCallbackItem } from '@/types';

interface RescheduleModalProps {
  item: ScheduledCallbackItem;
  onSave: (id: string, newTime: string, note?: string) => void;
  onClose: () => void;
}

export default function RescheduleModal({ item, onSave, onClose }: RescheduleModalProps) {
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [customDate, setCustomDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [customTime, setCustomTime] = useState<string>('16:30');
  const [note, setNote] = useState<string>(item.aiNote || '');

  const handlePreset = (presetText: string) => {
    setSelectedPreset(presetText);
  };

  const handleSave = () => {
    let finalTime = selectedPreset;
    if (!finalTime) {
      finalTime = `${customDate} at ${customTime}`;
    }
    onSave(item.id, finalTime, note);
    onClose();
  };

  return (
    <div style={{ padding: '4px' }}>
      {/* Retailer Info Header */}
      <div
        style={{
          background: 'var(--blue-soft)',
          border: '1px solid #C9DCFA',
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span className="mono" style={{ fontSize: '11px', color: 'var(--navy)', fontWeight: 700 }}>
              {item.id} • {item.ret}
            </span>
            <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--navy)' }}>{item.name}</div>
            <div className="mono" style={{ fontSize: '12px', color: 'var(--t2)', marginTop: '2px' }}>
              {item.ph}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase', fontWeight: 700 }}>
              Outstanding Due
            </span>
            <div className="num" style={{ fontSize: '18px', fontWeight: 700, color: 'var(--red)' }}>
              ₹{Number(item.outstanding || 0).toLocaleString('en-IN')}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Adjustment Presets */}
      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--t1)', marginBottom: '8px' }}>
          ⚡ Quick Presets (One-Click Slot Shift)
        </label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {[
            'Today, in +5 mins (Fast Auto-Retry)',
            'Today, in +15 mins',
            'Today, in +30 mins',
            'Today, 05:00 PM (Closing time)',
            'Tomorrow, 10:00 AM (Morning rush)',
          ].map((preset) => (
            <button
              key={preset}
              type="button"
              className={`btn btn-sm ${selectedPreset === preset ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handlePreset(preset)}
              style={{ fontSize: '12px' }}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* Or Pick Exact Custom Time */}
      <div
        style={{
          background: 'var(--surface-2)',
          border: '1px solid var(--line)',
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '16px',
        }}
      >
        <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--t1)', marginBottom: '8px' }}>
          Or Select Custom Date & Time
        </label>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <input
            type="date"
            value={customDate}
            onChange={(e) => {
              setCustomDate(e.target.value);
              setSelectedPreset('');
            }}
            style={{ padding: '6px 10px', fontSize: '13px', borderRadius: '6px', border: '1px solid var(--line)' }}
          />
          <input
            type="time"
            value={customTime}
            onChange={(e) => {
              setCustomTime(e.target.value);
              setSelectedPreset('');
            }}
            style={{ padding: '6px 10px', fontSize: '13px', borderRadius: '6px', border: '1px solid var(--line)' }}
          />
          <span className="meta" style={{ fontSize: '11px' }}>
            (TRAI calling window 09:00 AM – 07:30 PM)
          </span>
        </div>
      </div>

      {/* AI / Agent Note */}
      <div style={{ marginBottom: '18px' }}>
        <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--t1)', marginBottom: '6px' }}>
          Context & Note for Voice Agent
        </label>
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="e.g. Retailer requested callback when accountant arrives..."
          style={{
            width: '100%',
            padding: '8px 10px',
            fontSize: '13px',
            borderRadius: '6px',
            border: '1px solid var(--line)',
            resize: 'vertical',
          }}
        />
        <div className="meta" style={{ marginTop: '4px', fontSize: '11px' }}>
          RIA uses this note when redialing to greet the customer with full context.
        </div>
      </div>

      {/* Footer Buttons */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '8px',
          paddingTop: '12px',
          borderTop: '1px solid var(--line)',
        }}
      >
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary btn-sm" onClick={handleSave}>
          ✓ Save Schedule & Update Queue
        </button>
      </div>
    </div>
  );
}
