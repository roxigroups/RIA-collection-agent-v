'use client';

import React, { useEffect, useState, useRef } from 'react';
import Script from 'next/script';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import PageHead from '@/components/common/PageHead';
import { useApp } from '@/context/AppContext';
import { api, ApiError } from '@/lib/api';
import { WalletDetailsResponse, WalletLedgerItem } from '@/types';

declare global {
  interface Window {
    Razorpay: any;
  }
}

const QUICK_PACKS = [
  { amount: 1000, minutes: 333, badge: '' },
  { amount: 2500, minutes: 833, badge: '' },
  { amount: 5000, minutes: 1666, badge: 'MOST POPULAR', badgeType: 'popular' },
  { amount: 10000, minutes: 3333, badge: 'BEST VALUE', badgeType: 'value' },
];

export default function WalletPage() {
  const router = useRouter();
  const { meInfo, role, showToast, refresh } = useApp();
  const [wallet, setWallet] = useState<WalletDetailsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'wallet' | 'history'>('wallet');
  const [selectedAmount, setSelectedAmount] = useState<number>(5000);
  const [isCustom, setIsCustom] = useState(false);
  const [customInput, setCustomInput] = useState<string>('2000');
  const [isPaying, setIsPaying] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [showRedeemModal, setShowRedeemModal] = useState(false);
  const [couponCode, setCouponCode] = useState('');
  const rechargeSectionRef = useRef<HTMLDivElement>(null);

  // Strict Admin Guard: Superadmins and Technical Admins do NOT have payment pages
  useEffect(() => {
    if (meInfo?.is_superadmin || role === 'TA') {
      router.replace('/admin/dashboard');
    }
  }, [meInfo, role, router]);

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
    if (!meInfo?.is_superadmin && role !== 'TA') {
      fetchWallet();
    }
  }, [meInfo, role]);

  if (meInfo?.is_superadmin || role === 'TA') {
    return null;
  }

  const activeAmount = isCustom ? Math.max(100, parseInt(customInput || '0', 10) || 0) : selectedAmount;
  const balanceInr = wallet?.balance_inr ?? meInfo?.wallet_balance_inr ?? 0;

  const handleTopup = async () => {
    setErrorMsg('');
    if (activeAmount < 100) {
      setErrorMsg('Minimum top-up amount is ₹100.');
      return;
    }

    setIsPaying(true);
    try {
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

      const options = {
        key: keyId,
        amount: orderRes.amount,
        currency: orderRes.currency || 'INR',
        name: 'RIA Collection Agent',
        description: `Wallet Recharge — ₹${activeAmount.toLocaleString('en-IN')}`,
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
              showToast(`₹${activeAmount.toLocaleString('en-IN')} added to your wallet!`);
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
        const failReason = resp.error?.description || 'Payment was cancelled';
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

  const handleRedeem = (e: React.FormEvent) => {
    e.preventDefault();
    if (!couponCode.trim()) return;
    showToast('Promo code applied! Testing credits will be updated.');
    setShowRedeemModal(false);
    setCouponCode('');
  };

  return (
    <AppShell screenKey="billing">
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />

      {/* Main Container */}
      <div style={{ maxWidth: '1060px', margin: '0 auto', paddingBottom: '40px' }}>
        {/* Header Block matching reference */}
        <div style={{ marginBottom: '16px' }}>
          <h1
            style={{
              fontSize: '28px',
              fontWeight: 700,
              color: '#0F2350',
              margin: '0 0 4px',
              letterSpacing: '-0.02em',
            }}
          >
            Wallet
          </h1>
          <p style={{ fontSize: '14px', color: '#64748B', margin: 0 }}>
            Prepaid balance, spending and recharge
          </p>
        </div>

        {/* Clean Tabs with Cobalt Blue underline */}
        <div
          style={{
            display: 'flex',
            gap: '28px',
            borderBottom: '1px solid #E2E8F0',
            marginBottom: '24px',
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab('wallet')}
            style={{
              padding: '10px 0 12px',
              fontSize: '14px',
              fontWeight: activeTab === 'wallet' ? 700 : 500,
              color: activeTab === 'wallet' ? '#0F2350' : '#64748B',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'wallet' ? '2.5px solid #1E52C9' : '2.5px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            Wallet
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('history')}
            style={{
              padding: '10px 0 12px',
              fontSize: '14px',
              fontWeight: activeTab === 'history' ? 700 : 500,
              color: activeTab === 'history' ? '#0F2350' : '#64748B',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === 'history' ? '2.5px solid #1E52C9' : '2.5px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            Usage & History
          </button>
        </div>

        {errorMsg && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: '8px',
              background: '#FEE2E2',
              border: '1px solid #FCA5A5',
              color: '#991B1B',
              fontSize: '13.5px',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {/* TAB 1: Main Wallet View (Exact 2-Card Layout from Reference) */}
        {activeTab === 'wallet' && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(300px, 1fr) minmax(360px, 1.25fr)',
              gap: '24px',
              alignItems: 'stretch',
            }}
          >
            {/* Left Card: WALLET BALANCE */}
            <div
              style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '16px',
                padding: '28px 24px',
                boxShadow: '0 1px 3px rgba(15, 35, 80, 0.04)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: '340px',
              }}
            >
              <div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: '#64748B',
                  }}
                >
                  <span style={{ fontSize: '15px' }}>💼</span>
                  <span>WALLET BALANCE</span>
                </div>

                <div
                  style={{
                    fontSize: '44px',
                    fontWeight: 800,
                    color: '#0F2350',
                    letterSpacing: '-0.03em',
                    marginTop: '28px',
                    fontFamily: 'var(--mono, monospace)',
                  }}
                >
                  ₹{balanceInr.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </div>

                <div style={{ fontSize: '13px', color: '#64748B', marginTop: '6px' }}>
                  ≈ {Math.floor(balanceInr / 3)} minutes of spoke AI call time
                </div>
              </div>

              {/* Bottom Buttons: Primary Blue + Secondary Outline */}
              <div style={{ display: 'flex', gap: '12px', marginTop: '32px' }}>
                <button
                  type="button"
                  onClick={() => {
                    rechargeSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
                  }}
                  style={{
                    flex: 1,
                    height: '42px',
                    background: '#1E52C9',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '13.5px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 2px 6px rgba(30, 82, 201, 0.2)',
                  }}
                >
                  <span>+</span>
                  <span>Recharge wallet</span>
                </button>

                <button
                  type="button"
                  onClick={() => setShowRedeemModal(true)}
                  style={{
                    height: '42px',
                    padding: '0 16px',
                    background: '#FFFFFF',
                    color: '#0F2350',
                    border: '1px solid #CBD5E1',
                    borderRadius: '8px',
                    fontSize: '13.5px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  <span>🎁</span>
                  <span>Redeem code</span>
                </button>
              </div>
            </div>

            {/* Right Card: Quick Recharge (2x2 Grid + Full Width Button) */}
            <div
              ref={rechargeSectionRef}
              style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: '16px',
                padding: '28px 24px',
                boxShadow: '0 1px 3px rgba(15, 35, 80, 0.04)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <h3
                  style={{
                    fontSize: '18px',
                    fontWeight: 700,
                    color: '#0F2350',
                    margin: '0 0 4px',
                  }}
                >
                  Quick recharge
                </h3>
                <p style={{ fontSize: '13px', color: '#64748B', margin: '0 0 20px' }}>
                  Pick an amount — see how long it lasts at your burn rate.
                </p>

                {/* 2x2 Pack Grid */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '12px',
                    marginBottom: '16px',
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
                          padding: '16px 16px 14px',
                          borderRadius: '12px',
                          background: isSelected ? '#EFF6FF' : '#FFFFFF',
                          border: isSelected ? '2px solid #1E52C9' : '1px solid #E2E8F0',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                          boxShadow: isSelected ? '0 2px 8px rgba(30, 82, 201, 0.12)' : 'none',
                        }}
                      >
                        {pack.badge && (
                          <span
                            style={{
                              position: 'absolute',
                              top: '10px',
                              right: '10px',
                              background: pack.badgeType === 'value' ? '#1E52C9' : '#0F2350',
                              color: '#FFFFFF',
                              fontSize: '9.5px',
                              fontWeight: 700,
                              padding: '2px 7px',
                              borderRadius: '10px',
                              letterSpacing: '0.04em',
                            }}
                          >
                            {pack.badge}
                          </span>
                        )}

                        <div
                          style={{
                            fontSize: '20px',
                            fontWeight: 800,
                            color: isSelected ? '#1E52C9' : '#0F2350',
                            fontFamily: 'var(--mono, monospace)',
                            marginTop: pack.badge ? '8px' : '0',
                          }}
                        >
                          ₹{pack.amount.toLocaleString('en-IN')}
                        </div>

                        <div
                          style={{
                            fontSize: '12px',
                            color: isSelected ? '#1E52C9' : '#64748B',
                            fontWeight: 500,
                            marginTop: '4px',
                          }}
                        >
                          ≈ {pack.minutes} mins talk time
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Custom Amount Toggle */}
                <div style={{ marginBottom: '20px' }}>
                  {!isCustom ? (
                    <button
                      type="button"
                      onClick={() => setIsCustom(true)}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        color: '#1E52C9',
                        fontSize: '12.5px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        textDecoration: 'underline',
                      }}
                    >
                      + Or enter custom amount
                    </button>
                  ) : (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '10px 14px',
                        background: '#F8FAFC',
                        borderRadius: '8px',
                        border: '1px solid #CBD5E1',
                      }}
                    >
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#0F2350' }}>₹</span>
                      <input
                        type="number"
                        min="100"
                        step="50"
                        value={customInput}
                        onChange={(e) => setCustomInput(e.target.value)}
                        placeholder="Enter amount (min ₹100)"
                        style={{
                          width: '100%',
                          border: 'none',
                          background: 'transparent',
                          fontSize: '14px',
                          fontWeight: 700,
                          color: '#0F2350',
                          outline: 'none',
                          fontFamily: 'var(--mono, monospace)',
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setIsCustom(false)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#64748B',
                          fontSize: '12px',
                          cursor: 'pointer',
                        }}
                      >
                        ✕ Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Big Bottom Action Button in RIA Cobalt Blue */}
              <div>
                <button
                  type="button"
                  onClick={handleTopup}
                  disabled={isPaying || activeAmount < 100}
                  style={{
                    width: '100%',
                    height: '48px',
                    background: '#1E52C9',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '15px',
                    fontWeight: 700,
                    cursor: isPaying ? 'wait' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    boxShadow: '0 2px 8px rgba(30, 82, 201, 0.25)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {isPaying ? (
                    <span>Opening Payment…</span>
                  ) : (
                    <span>Recharge ₹{activeAmount.toLocaleString('en-IN')}</span>
                  )}
                </button>
                <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '8px', textAlign: 'center' }}>
                  Burn rate: ₹3.00/min • Spoken time only • Ringing is free
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: Usage & Deductions History */}
        {activeTab === 'history' && (
          <div
            style={{
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '16px',
              padding: '24px',
              boxShadow: '0 1px 3px rgba(15, 35, 80, 0.04)',
            }}
          >
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#0F2350', margin: 0 }}>
                Recent Usage & Call Deductions
              </h3>
              <p style={{ fontSize: '13px', color: '#64748B', margin: '4px 0 0' }}>
                Deductions occur at ₹3.00/min only after calls are answered.
              </p>
            </div>

            {(wallet?.ledger || []).length === 0 ? (
              <div
                style={{
                  padding: '36px 20px',
                  textAlign: 'center',
                  color: '#64748B',
                  fontSize: '13px',
                  background: '#F8FAFC',
                  borderRadius: '8px',
                  border: '1px dashed #E2E8F0',
                }}
              >
                No call deductions or top-ups recorded yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #E2E8F0', color: '#64748B', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Date</th>
                      <th style={{ padding: '8px 12px' }}>Description</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Amount</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(wallet?.ledger || []).map((row: WalletLedgerItem) => {
                      const isDebit = row.amount_paise < 0;
                      return (
                        <tr key={row.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                          <td style={{ padding: '10px 12px', color: '#64748B', whiteSpace: 'nowrap' }}>
                            {row.created_at ? new Date(row.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
                          </td>
                          <td style={{ padding: '10px 12px', color: '#0F2350', fontWeight: 500 }}>
                            {row.description}
                          </td>
                          <td
                            style={{
                              padding: '10px 12px',
                              textAlign: 'right',
                              fontWeight: 700,
                              fontFamily: 'var(--mono, monospace)',
                              color: isDebit ? '#DC2626' : '#059669',
                            }}
                          >
                            {isDebit ? '-' : '+'}₹{Math.abs(row.amount_inr).toFixed(2)}
                          </td>
                          <td
                            style={{
                              padding: '10px 12px',
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
        )}
      </div>

      {/* Redeem Code Simple Modal */}
      {showRedeemModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 35, 80, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              background: '#FFFFFF',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '380px',
              width: '90%',
              boxShadow: '0 12px 30px rgba(0,0,0,0.15)',
            }}
          >
            <h3 style={{ margin: '0 0 6px', fontSize: '18px', color: '#0F2350' }}>Redeem Promo Code</h3>
            <p style={{ margin: '0 0 16px', fontSize: '13px', color: '#64748B' }}>
              Enter a promotion voucher or credit code to add calling credits to your wallet.
            </p>
            <form onSubmit={handleRedeem}>
              <input
                type="text"
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                placeholder="e.g. WELCOME100"
                style={{
                  width: '100%',
                  height: '40px',
                  padding: '0 12px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '14px',
                  marginBottom: '16px',
                  fontWeight: 600,
                  letterSpacing: '0.04em',
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setShowRedeemModal(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    background: '#FFFFFF',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: 'none',
                    background: '#1E52C9',
                    color: '#FFFFFF',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Apply Code
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
