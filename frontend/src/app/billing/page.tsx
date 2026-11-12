'use client';

import React, { useEffect, useState } from 'react';
import Script from 'next/script';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import { useApp } from '@/context/AppContext';
import { api, ApiError } from '@/lib/api';
import { WalletDetailsResponse, WalletLedgerItem, BillingTransactionItem } from '@/types';

declare global {
  interface Window {
    Razorpay: any;
  }
}

const QUICK_PACKS = [
  { amount: 500, label: 'Starter Pack', minutes: 166, tag: '' },
  { amount: 1000, label: 'Standard Pack', minutes: 333, tag: 'Most Popular' },
  { amount: 2500, label: 'Growth Pack', minutes: 833, tag: 'Best Value' },
  { amount: 5000, label: 'Enterprise Pack', minutes: 1666, tag: 'Max Value' },
];

export default function BillingPage() {
  const { meInfo, showToast, refresh } = useApp();
  const [wallet, setWallet] = useState<WalletDetailsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedAmount, setSelectedAmount] = useState<number>(1000);
  const [isCustom, setIsCustom] = useState(false);
  const [customInput, setCustomInput] = useState<string>('1500');
  const [isPaying, setIsPaying] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'call_burn' | 'topup'>('all');

  const fetchWallet = async () => {
    try {
      setLoading(true);
      const res = await api<WalletDetailsResponse>('/billing/wallet');
      setWallet(res);
    } catch (err: any) {
      console.error('Failed to load wallet details:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWallet();
  }, []);

  const activeAmount = isCustom ? Math.max(100, parseInt(customInput || '0', 10) || 0) : selectedAmount;

  const handleTopup = async () => {
    setErrorMsg('');
    if (activeAmount < 100) {
      setErrorMsg('Minimum top-up amount is ₹100.');
      return;
    }

    setIsPaying(true);
    try {
      // 1. Create top-up order on backend
      const orderRes = await api<{
        order_id: string;
        amount: number;
        currency: string;
        key_id: string;
      }>('/billing/topup/order', {
        body: { amount_inr: activeAmount },
      });

      const keyId =
        orderRes.key_id ||
        process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID ||
        'rzp_test_TzFI10AZU8WRbV';

      if (!window.Razorpay) {
        throw new Error('Razorpay Checkout SDK is still loading. Please try again in a few seconds.');
      }

      // 2. Open Razorpay Checkout modal
      const options = {
        key: keyId,
        amount: orderRes.amount,
        currency: orderRes.currency || 'INR',
        name: 'RIA Collection Agent',
        description: `Calling Credits Recharge — ₹${activeAmount.toLocaleString('en-IN')}`,
        image: '/logo-mark.png',
        order_id: orderRes.order_id,
        prefill: {
          name: meInfo?.n || '',
          email: meInfo?.e || '',
        },
        theme: {
          color: '#1E52C9',
        },
        modal: {
          ondismiss: () => {
            setIsPaying(false);
          },
        },
        handler: async (response: {
          razorpay_payment_id: string;
          razorpay_order_id: string;
          razorpay_signature: string;
        }) => {
          showToast('Payment successful! Crediting your wallet...');
          try {
            const verifyRes = await api<{
              success: boolean;
              message: string;
              data: { balance_inr: number };
            }>('/billing/topup/verify', {
              body: {
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                amount: orderRes.amount,
              },
            });

            if (verifyRes.success) {
              showToast(`₹${activeAmount.toLocaleString('en-IN')} added to your calling wallet!`);
              await fetchWallet();
              await refresh();
            } else {
              throw new Error('Top-up verification failed.');
            }
          } catch (err: any) {
            const msg = err instanceof ApiError ? err.message : err?.message || 'Failed to verify top-up';
            setErrorMsg(msg);
            showToast(msg);
          } finally {
            setIsPaying(false);
          }
        },
      };

      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', (resp: any) => {
        setIsPaying(false);
        const failReason = resp.error?.description || 'Payment was cancelled or could not be processed';
        setErrorMsg(failReason);
        showToast(failReason);
      });
      rzp.open();
    } catch (err: any) {
      setIsPaying(false);
      const msg = err instanceof ApiError ? err.message : err?.message || 'Failed to initiate recharge';
      setErrorMsg(msg);
      showToast(msg);
    }
  };

  const balanceInr = wallet?.balance_inr ?? meInfo?.wallet_balance_inr ?? 0;
  const talkTimeMins = Math.floor(balanceInr / 3);

  const filteredLedger = (wallet?.ledger || []).filter((item) => {
    if (filterType === 'all') return true;
    if (filterType === 'call_burn') return item.type === 'call_burn';
    if (filterType === 'topup') return item.type === 'topup' || item.type === 'welcome_bonus';
    return true;
  });

  return (
    <AppShell screenKey="billing">
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />

      <PageHead
        screenKey="billing"
        rightAction={
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={fetchWallet}
            disabled={loading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <span>🔄</span>
            <span>{loading ? 'Refreshing…' : 'Refresh Balance'}</span>
          </button>
        }
      />

      <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {errorMsg && (
          <div
            style={{
              padding: '12px 18px',
              borderRadius: '8px',
              background: '#FEE2E2',
              border: '1px solid #FCA5A5',
              color: '#991B1B',
              fontSize: '13.5px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Top Section: Hero Wallet Card & Plan Status */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Card 1: Available Balance Hero */}
          <div
            style={{
              background: 'linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)',
              border: '1px solid #E2E8F0',
              borderRadius: '12px',
              padding: '24px',
              boxShadow: '0 4px 12px rgba(15, 35, 80, 0.04)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: '#64748B',
                  }}
                >
                  Calling Credits Balance
                </span>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '6px' }}>
                  <span
                    style={{
                      fontSize: '36px',
                      fontWeight: 800,
                      color: balanceInr < 50 ? '#DC2626' : '#0F2350',
                      letterSpacing: '-0.03em',
                      fontFamily: 'var(--mono, monospace)',
                    }}
                  >
                    ₹{balanceInr.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  <span
                    style={{
                      fontSize: '12.5px',
                      fontWeight: 600,
                      color: '#059669',
                      background: '#ECFDF5',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      border: '1px solid #A7F3D0',
                    }}
                  >
                    ● Live Wallet
                  </span>
                </div>
              </div>
              <div
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '10px',
                  background: '#EFF6FF',
                  border: '1px solid #DBEAFE',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '22px',
                }}
              >
                🪙
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                background: '#F1F5F9',
                borderRadius: '8px',
                fontSize: '13px',
                color: '#334155',
              }}
            >
              <span>📞</span>
              <span>
                Estimated talk time:{' '}
                <strong style={{ color: '#0F2350' }}>~{talkTimeMins} minutes</strong> of AI calling
              </span>
            </div>

            {/* Pricing transparency callout */}
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '8px',
                background: '#EFF6FF',
                border: '1px solid #BFDBFE',
                fontSize: '12.5px',
                color: '#1E40AF',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>⚡</span>
                <span>Transparent Call Burn Rate: ₹3.00 / 1 minute (5 paise / sec)</span>
              </div>
              <ul style={{ margin: '6px 0 0', paddingLeft: '18px', fontSize: '12px', color: '#1D4ED8' }}>
                <li>Time is calculated <strong>strictly after the call is answered</strong>.</li>
                <li>Ringing time, busy lines, and unanswered dials are <strong>100% free (₹0.00)</strong>.</li>
              </ul>
            </div>
          </div>

          {/* Card 2: Workspace & Plan Status */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '12px',
              padding: '24px',
              boxShadow: '0 4px 12px rgba(15, 35, 80, 0.04)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: '#64748B',
                    }}
                  >
                    Platform Subscription
                  </span>
                  <h3
                    style={{
                      fontSize: '20px',
                      fontWeight: 700,
                      color: '#0F2350',
                      margin: '4px 0 0',
                    }}
                  >
                    {(wallet?.plan || meInfo?.plan || 'Starter').toUpperCase()} Platform
                  </h3>
                </div>
                <span
                  style={{
                    padding: '4px 10px',
                    borderRadius: '20px',
                    background: '#ECFDF5',
                    color: '#065F46',
                    fontSize: '12px',
                    fontWeight: 700,
                    border: '1px solid #A7F3D0',
                  }}
                >
                  Active Lifetime
                </span>
              </div>

              <div style={{ margin: '18px 0', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#475569' }}>
                  <span style={{ color: '#059669', fontWeight: 700 }}>✓</span>
                  <span>Autonomous AI Telephony dialer enabled</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#475569' }}>
                  <span style={{ color: '#059669', fontWeight: 700 }}>✓</span>
                  <span>Autonomous 5-min reschedule & callback queue</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#475569' }}>
                  <span style={{ color: '#059669', fontWeight: 700 }}>✓</span>
                  <span>Telugu, Hindi & English conversational AI models</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#475569' }}>
                  <span style={{ color: '#059669', fontWeight: 700 }}>✓</span>
                  <span>Audio recordings & evidence-grade transcripts</span>
                </div>
              </div>
            </div>

            <div
              style={{
                fontSize: '12px',
                color: '#64748B',
                borderTop: '1px solid #F1F5F9',
                paddingTop: '12px',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span>Workspace: <strong>{meInfo?.company || 'Main'}</strong></span>
              <span>Billing ID: <strong>{wallet?.tenant_id || meInfo?.id || '—'}</strong></span>
            </div>
          </div>
        </div>

        {/* Section 2: Quick Top-Up & Custom Recharge */}
        <div
          style={{
            background: '#FFFFFF',
            border: '1px solid #E2E8F0',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: '0 4px 12px rgba(15, 35, 80, 0.04)',
          }}
        >
          <div style={{ marginBottom: '20px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#0F2350', margin: 0 }}>
              Recharge Calling Credits
            </h2>
            <p style={{ fontSize: '13px', color: '#64748B', margin: '4px 0 0' }}>
              Select a quick package or enter a custom amount. Credits are added to your balance immediately after payment.
            </p>
          </div>

          {/* Package Selection Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '14px',
              marginBottom: '20px',
            }}
          >
            {QUICK_PACKS.map((pack) => {
              const isSelected = !isCustom && selectedAmount === pack.amount;
              return (
                <button
                  key={pack.amount}
                  type="button"
                  onClick={() => {
                    setIsCustom(false);
                    setSelectedAmount(pack.amount);
                  }}
                  style={{
                    position: 'relative',
                    textAlign: 'left',
                    padding: '16px 18px',
                    borderRadius: '10px',
                    background: isSelected ? '#EFF6FF' : '#FFFFFF',
                    border: `2px solid ${isSelected ? '#1E52C9' : '#E2E8F0'}`,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? '0 4px 10px rgba(30, 82, 201, 0.12)' : 'none',
                  }}
                >
                  {pack.tag && (
                    <span
                      style={{
                        position: 'absolute',
                        top: '-10px',
                        right: '12px',
                        background: '#1E52C9',
                        color: '#FFFFFF',
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '10px',
                        letterSpacing: '0.04em',
                      }}
                    >
                      {pack.tag}
                    </span>
                  )}
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B' }}>{pack.label}</div>
                  <div
                    style={{
                      fontSize: '22px',
                      fontWeight: 800,
                      color: isSelected ? '#1E52C9' : '#0F2350',
                      marginTop: '4px',
                      fontFamily: 'var(--mono, monospace)',
                    }}
                  >
                    ₹{pack.amount.toLocaleString('en-IN')}
                  </div>
                  <div style={{ fontSize: '12px', color: '#059669', fontWeight: 600, marginTop: '4px' }}>
                    ~{pack.minutes} mins talk time
                  </div>
                </button>
              );
            })}

            {/* Custom Amount Button */}
            <button
              type="button"
              onClick={() => setIsCustom(true)}
              style={{
                textAlign: 'left',
                padding: '16px 18px',
                borderRadius: '10px',
                background: isCustom ? '#EFF6FF' : '#FFFFFF',
                border: `2px solid ${isCustom ? '#1E52C9' : '#E2E8F0'}`,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: isCustom ? '0 4px 10px rgba(30, 82, 201, 0.12)' : 'none',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B' }}>Custom Amount</div>
              <div
                style={{
                  fontSize: '22px',
                  fontWeight: 800,
                  color: isCustom ? '#1E52C9' : '#0F2350',
                  marginTop: '4px',
                }}
              >
                ₹ Custom
              </div>
              <div style={{ fontSize: '12px', color: '#64748B', marginTop: '4px' }}>
                Any amount ≥ ₹100
              </div>
            </button>
          </div>

          {/* Custom Input row if active */}
          {isCustom && (
            <div
              style={{
                marginBottom: '20px',
                padding: '16px',
                background: '#F8FAFC',
                borderRadius: '8px',
                border: '1px solid #E2E8F0',
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                flexWrap: 'wrap',
              }}
            >
              <label htmlFor="customInput" style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>
                Enter custom credit amount (INR):
              </label>
              <div style={{ position: 'relative', width: '220px' }}>
                <span
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    fontWeight: 700,
                    color: '#64748B',
                  }}
                >
                  ₹
                </span>
                <input
                  id="customInput"
                  type="number"
                  min="100"
                  step="50"
                  value={customInput}
                  onChange={(e) => setCustomInput(e.target.value)}
                  placeholder="e.g. 1500"
                  style={{
                    width: '100%',
                    height: '40px',
                    paddingLeft: '28px',
                    paddingRight: '12px',
                    fontSize: '16px',
                    fontWeight: 700,
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontFamily: 'var(--mono, monospace)',
                  }}
                />
              </div>
              <span style={{ fontSize: '12.5px', color: '#64748B' }}>
                (~{Math.floor(activeAmount / 3)} minutes of talk time)
              </span>
            </div>
          )}

          {/* Action Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '16px',
              borderTop: '1px solid #F1F5F9',
              flexWrap: 'wrap',
              gap: '14px',
            }}
          >
            <div>
              <div style={{ fontSize: '13px', color: '#64748B' }}>Total Recharge Payable:</div>
              <div
                style={{
                  fontSize: '24px',
                  fontWeight: 800,
                  color: '#0F2350',
                  fontFamily: 'var(--mono, monospace)',
                }}
              >
                ₹{activeAmount.toLocaleString('en-IN')}.00
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              onClick={handleTopup}
              disabled={isPaying || activeAmount < 100}
              style={{
                height: '46px',
                padding: '0 28px',
                fontSize: '15px',
                fontWeight: 700,
                borderRadius: '8px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 2px 8px rgba(30, 82, 201, 0.25)',
              }}
            >
              {isPaying ? (
                <span>Processing Payment…</span>
              ) : (
                <>
                  <span>💳</span>
                  <span>Recharge ₹{activeAmount.toLocaleString('en-IN')} via Razorpay</span>
                </>
              )}
            </button>
          </div>
          <div style={{ fontSize: '12px', color: '#94A3B8', marginTop: '10px', textAlign: 'right' }}>
            🔒 Secured by Razorpay standard checkout • Supports UPI QR, Netbanking & Cards
          </div>
        </div>

        {/* Section 3: Calling & Billing Activity Statement */}
        <div
          style={{
            background: '#FFFFFF',
            border: '1px solid #E2E8F0',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: '0 4px 12px rgba(15, 35, 80, 0.04)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#0F2350', margin: 0 }}>
                Credit Usage & Transaction Ledger
              </h2>
              <p style={{ fontSize: '13px', color: '#64748B', margin: '4px 0 0' }}>
                Complete evidential record of call burn deductions and credit top-ups.
              </p>
            </div>

            {/* Filter Tabs */}
            <div style={{ display: 'flex', gap: '6px', background: '#F1F5F9', padding: '4px', borderRadius: '8px' }}>
              {(
                [
                  { id: 'all', label: 'All Activity' },
                  { id: 'call_burn', label: 'Call Deductions' },
                  { id: 'topup', label: 'Top-ups & Bonuses' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setFilterType(tab.id)}
                  style={{
                    padding: '5px 12px',
                    fontSize: '12.5px',
                    fontWeight: 600,
                    borderRadius: '6px',
                    border: 'none',
                    background: filterType === tab.id ? '#FFFFFF' : 'transparent',
                    color: filterType === tab.id ? '#0F2350' : '#64748B',
                    boxShadow: filterType === tab.id ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                    cursor: 'pointer',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Ledger Table */}
          {filteredLedger.length === 0 ? (
            <div
              style={{
                padding: '40px 20px',
                textAlign: 'center',
                color: '#64748B',
                fontSize: '13.5px',
                background: '#F8FAFC',
                borderRadius: '8px',
                border: '1px dashed #CBD5E1',
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '8px' }}>📜</div>
              <div style={{ fontWeight: 600, color: '#334155' }}>No activity records found</div>
              <div style={{ fontSize: '12px', color: '#94A3B8', marginTop: '4px' }}>
                Completed calls and recharges will appear here in chronological order.
              </div>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '13px',
                  textAlign: 'left',
                }}
              >
                <thead>
                  <tr style={{ borderBottom: '2px solid #E2E8F0', color: '#64748B' }}>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>Date & Time</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>Activity / Description</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600 }}>Type</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'right' }}>Amount</th>
                    <th style={{ padding: '10px 14px', fontWeight: 600, textAlign: 'right' }}>Balance After</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLedger.map((row: WalletLedgerItem) => {
                    const isDebit = row.amount_paise < 0;
                    const dateFormatted = row.created_at
                      ? new Date(row.created_at).toLocaleString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '—';

                    return (
                      <tr
                        key={row.id}
                        style={{
                          borderBottom: '1px solid #F1F5F9',
                          transition: 'background 0.1s ease',
                        }}
                      >
                        <td style={{ padding: '12px 14px', color: '#64748B', whiteSpace: 'nowrap' }}>
                          {dateFormatted}
                        </td>
                        <td style={{ padding: '12px 14px', color: '#0F2350', fontWeight: 500 }}>
                          {row.description}
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background:
                                row.type === 'call_burn'
                                  ? '#FEE2E2'
                                  : row.type === 'topup'
                                  ? '#ECFDF5'
                                  : '#EFF6FF',
                              color:
                                row.type === 'call_burn'
                                  ? '#991B1B'
                                  : row.type === 'topup'
                                  ? '#065F46'
                                  : '#1E40AF',
                            }}
                          >
                            {row.type === 'call_burn'
                              ? 'Call Spoken'
                              : row.type === 'topup'
                              ? 'Top-up'
                              : 'Bonus Credit'}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: '12px 14px',
                            textAlign: 'right',
                            fontWeight: 700,
                            fontFamily: 'var(--mono, monospace)',
                            color: isDebit ? '#DC2626' : '#059669',
                          }}
                        >
                          {isDebit ? '-' : '+'}₹
                          {Math.abs(row.amount_inr).toFixed(2)}
                        </td>
                        <td
                          style={{
                            padding: '12px 14px',
                            textAlign: 'right',
                            fontWeight: 600,
                            fontFamily: 'var(--mono, monospace)',
                            color: '#0F2350',
                          }}
                        >
                          ₹{row.balance_after_inr.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

