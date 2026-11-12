'use client';

import React, { useState, useEffect } from 'react';
import Script from 'next/script';
import { useRouter } from 'next/navigation';
import { useApp } from '@/context/AppContext';
import { api, ApiError } from '@/lib/api';

declare global {
  interface Window {
    Razorpay: any;
  }
}

interface PlanConfig {
  id: 'starter' | 'pro';
  name: string;
  tagline: string;
  price: string;
  priceAmount: number;
  popular?: boolean;
  buttonText: string;
  featuresHeader: string;
  features: string[];
}

const PLANS: PlanConfig[] = [
  {
    id: 'starter',
    name: 'Starter Platform',
    tagline: 'Ideal for growing distributors automating overdue collections',
    price: '₹4,999',
    priceAmount: 499900,
    buttonText: 'Activate Starter Workspace',
    featuresHeader: 'Everything you need to automate recovery:',
    features: [
      'Dedicated tenant workspace & provisioned caller ID',
      '1 concurrent outbound dialing line',
      'Core Multilingual Voice AI (Hindi, Telugu, English)',
      'Autonomous Promise-to-Pay (PTP) extraction & ledger',
      'Real-time call transcripts & sentiment analysis',
      'Excel / CSV bulk call sheet imports',
      'Automated scheduled callbacks & retry engine',
      'Standard Email & WhatsApp payment link reminders',
      'Up to 2 team member seats',
    ],
  },
  {
    id: 'pro',
    name: 'Pro Platform',
    tagline: 'High-volume recovery with multi-line dialing and full language pack',
    price: '₹7,999',
    priceAmount: 799900,
    popular: true,
    buttonText: 'Activate Pro Workspace',
    featuresHeader: 'Everything in Starter, plus:',
    features: [
      'Multi-line dialer concurrency (up to 4 Bangalore lines simultaneously)',
      'Full 11-Language Pack (Kannada, Tamil, Marathi, Gujarati, Bengali, etc.)',
      'High-fidelity Audio Call Recordings (listen & download MP3s)',
      'Smart Dunning: Dynamic tone control (Friendly to Firm recovery)',
      'Custom business scripts & retailer dispute ticketing',
      'Advanced recovery analytics & daily reconciliation',
      'Up to 10 team member seats with Role-Based Access Control',
      'Priority SLA support & dedicated onboarding guidance',
    ],
  },
];

export default function OnboardingActivatePage() {
  const router = useRouter();
  const { meInfo, isSuperAdmin, showToast } = useApp();
  const [loadingPlan, setLoadingPlan] = useState<'starter' | 'pro' | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // If already active or superadmin, route straight to dashboard
  useEffect(() => {
    if (isSuperAdmin) {
      router.replace('/admin/dashboard');
    } else if (meInfo && meInfo.billing_status === 'active') {
      router.replace('/dashboard');
    }
  }, [meInfo, isSuperAdmin, router]);

  const handleSelectPlan = async (plan: PlanConfig) => {
    setErrorMsg('');
    setLoadingPlan(plan.id);

    try {
      // 1. Create order on backend
      const orderRes = await api<{
        order_id: string;
        amount: number;
        currency: string;
        key_id: string;
        plan_id: string;
      }>('/create-order', {
        body: { plan_id: plan.id, amount: plan.priceAmount },
      });

      const keyId =
        orderRes.key_id ||
        process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID ||
        'rzp_test_TzFI10AZU8WRbV';

      if (!window.Razorpay) {
        throw new Error('Razorpay Checkout SDK is still loading. Please try again in a moment.');
      }

      // 2. Open Razorpay Checkout Modal
      const options = {
        key: keyId,
        amount: orderRes.amount,
        currency: orderRes.currency || 'INR',
        name: 'RIA AI Platform',
        description: `${plan.name} Lifetime Setup + ₹300 Calling Credits`,
        image: '/logo-mark.png',
        order_id: orderRes.order_id,
        prefill: {
          name: meInfo?.n || '',
          email: meInfo?.e || '',
        },
        theme: {
          color: '#2563eb',
        },
        modal: {
          ondismiss: () => {
            setLoadingPlan(null);
            showToast('Checkout was closed. You can resume anytime.');
          },
        },
        handler: async (paymentResponse: {
          razorpay_payment_id: string;
          razorpay_order_id: string;
          razorpay_signature: string;
        }) => {
          showToast('Payment received! Verifying and activating workspace...');
          try {
            // 3. Verify signature on backend
            const verifyRes = await api<{
              success: boolean;
              message: string;
            }>('/verify-payment', {
              body: {
                razorpay_order_id: paymentResponse.razorpay_order_id,
                razorpay_payment_id: paymentResponse.razorpay_payment_id,
                razorpay_signature: paymentResponse.razorpay_signature,
                plan_id: plan.id,
                amount: orderRes.amount,
              },
            });

            if (verifyRes.success) {
              showToast('🎉 Workspace activated! ₹300 welcome credits added.');
              window.location.href = '/dashboard';
            } else {
              throw new Error('Verification did not return success.');
            }
          } catch (err: any) {
            const msg = err instanceof ApiError ? err.message : err?.message || 'Failed to verify payment';
            setErrorMsg(msg);
            showToast(`Error: ${msg}`);
            setLoadingPlan(null);
          }
        },
      };

      const rzpInstance = new window.Razorpay(options);
      rzpInstance.on('payment.failed', (failedRes: any) => {
        const desc = failedRes?.error?.description || 'Payment failed. Please try again.';
        setErrorMsg(desc);
        showToast(desc);
        setLoadingPlan(null);
      });

      rzpInstance.open();
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.message : err?.message || 'Could not initialize payment';
      setErrorMsg(msg);
      showToast(msg);
      setLoadingPlan(null);
    }
  };

  return (
    <div className="activate-page">
      <Script src="https://checkout.razorpay.com/v1/checkout.js" />

      <style jsx global>{`
        .activate-page {
          min-height: 100vh;
          background: #090e1a;
          color: #f1f5f9;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          display: flex;
          flex-direction: column;
          box-sizing: border-box;
        }

        .act-header {
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          background: rgba(13, 19, 34, 0.85);
          backdrop-filter: blur(12px);
          position: sticky;
          top: 0;
          z-index: 20;
          padding: 14px 28px;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .act-logo-box {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .act-logo-icon {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          background: linear-gradient(135deg, #2563eb, #6366f1);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          font-size: 18px;
          color: #fff;
          box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
        }

        .act-title-text {
          font-weight: 800;
          font-size: 15px;
          letter-spacing: -0.01em;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .act-pill-small {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          background: rgba(59, 130, 246, 0.15);
          color: #60a5fa;
          border: 1px solid rgba(59, 130, 246, 0.3);
          padding: 2px 8px;
          border-radius: 999px;
        }

        .act-hero {
          max-width: 1080px;
          margin: 0 auto;
          padding: 48px 24px 64px;
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 100%;
          box-sizing: border-box;
        }

        .act-badge-main {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px;
          border-radius: 999px;
          background: rgba(37, 99, 235, 0.12);
          border: 1px solid rgba(59, 130, 246, 0.25);
          color: #93c5fd;
          font-size: 12px;
          font-weight: 600;
          margin-bottom: 16px;
        }

        .act-badge-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #3b82f6;
          box-shadow: 0 0 8px #3b82f6;
        }

        .act-h1 {
          font-size: clamp(28px, 4vw, 46px);
          font-weight: 800;
          letter-spacing: -0.025em;
          text-align: center;
          margin: 0;
          background: linear-gradient(180deg, #ffffff 30%, #94a3b8 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .act-sub {
          margin: 12px 0 0;
          font-size: 15px;
          color: #94a3b8;
          text-align: center;
          max-width: 640px;
          line-height: 1.55;
        }

        .act-cards-grid {
          margin-top: 40px;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 28px;
          width: 100%;
          max-width: 860px;
        }

        .act-card {
          position: relative;
          background: #111827;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 20px;
          padding: 32px 28px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
          transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .act-card.popular {
          background: linear-gradient(180deg, #131c31 0%, #0d1527 100%);
          border: 2px solid #3b82f6;
          box-shadow: 0 16px 40px -10px rgba(37, 99, 235, 0.25);
        }

        .act-popular-tag {
          position: absolute;
          top: -12px;
          left: 50%;
          transform: translateX(-50%);
          background: linear-gradient(90deg, #2563eb, #4f46e5);
          color: #ffffff;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 4px 14px;
          border-radius: 999px;
          box-shadow: 0 4px 10px rgba(37, 99, 235, 0.4);
        }

        .act-price-row {
          margin: 20px 0 12px;
          display: flex;
          align-items: baseline;
          gap: 8px;
        }

        .act-price-val {
          font-size: 42px;
          font-weight: 900;
          color: #ffffff;
          letter-spacing: -0.02em;
        }

        .act-bonus-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: rgba(16, 185, 129, 0.12);
          border: 1px solid rgba(16, 185, 129, 0.25);
          color: #34d399;
          font-size: 12px;
          font-weight: 600;
          padding: 6px 12px;
          border-radius: 8px;
          margin-bottom: 20px;
        }

        .act-btn {
          width: 100%;
          padding: 14px 16px;
          border-radius: 12px;
          border: 0;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: filter 0.15s ease, transform 0.1s ease;
        }

        .act-btn.primary {
          background: #2563eb;
          color: #ffffff;
          box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
        }

        .act-btn.primary:hover {
          background: #1d4ed8;
        }

        .act-btn.secondary {
          background: #1f2937;
          color: #ffffff;
          border: 1px solid rgba(255, 255, 255, 0.12);
        }

        .act-btn.secondary:hover {
          background: #374151;
        }

        .act-feature-list {
          margin: 24px 0 0;
          padding: 20px 0 0;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          list-style: none;
        }

        .act-feature-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          font-size: 12.5px;
          color: #cbd5e1;
          margin-bottom: 12px;
          line-height: 1.45;
        }

        .act-check {
          color: #3b82f6;
          font-weight: 900;
          flex-shrink: 0;
        }

        .act-footer-trust {
          margin-top: 36px;
          text-align: center;
          font-size: 12px;
          color: #64748b;
          max-width: 480px;
        }
      `}</style>

      {/* Header */}
      <header className="act-header">
        <div className="act-logo-box">
          <div className="act-logo-icon">R</div>
          <div>
            <div className="act-title-text">
              RIA AI AGENT
              <span className="act-pill-small">Platform Activation</span>
            </div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>Distribution Intelligence Platform</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px' }}>
          {meInfo && (
            <span style={{ color: '#94a3b8' }}>
              Signed in as <strong style={{ color: '#f8fafc' }}>{meInfo.e}</strong>
            </span>
          )}
          <button
            onClick={() => {
              window.location.href = '/login';
            }}
            style={{
              background: 'transparent',
              border: 0,
              color: '#3b82f6',
              cursor: 'pointer',
              fontWeight: 600,
              textDecoration: 'underline',
            }}
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="act-hero">
        <div className="act-badge-main">
          <span className="act-badge-dot" />
          One-Time Platform Setup · Lifetime Access
        </div>

        <h1 className="act-h1">Plans that grow with you</h1>
        <p className="act-sub">
          Activate your distribution workspace with autonomous multilingual voice recovery. Both plans include{' '}
          <strong style={{ color: '#60a5fa' }}>₹300 in free voice calling credits</strong> to start dialing immediately.
        </p>

        {errorMsg && (
          <div
            style={{
              marginTop: '20px',
              width: '100%',
              maxWidth: '440px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#fca5a5',
              padding: '12px 16px',
              borderRadius: '10px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>⚠️ {errorMsg}</span>
            <button
              onClick={() => setErrorMsg('')}
              style={{ background: 'transparent', border: 0, color: '#f87171', fontWeight: 700, cursor: 'pointer' }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Pricing Cards */}
        <div className="act-cards-grid">
          {PLANS.map((plan) => {
            const isLoading = loadingPlan === plan.id;
            return (
              <div key={plan.id} className={`act-card ${plan.popular ? 'popular' : ''}`}>
                {plan.popular && <div className="act-popular-tag">Most Popular</div>}

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <h2 style={{ fontSize: '20px', fontWeight: 800, margin: 0, color: '#ffffff' }}>{plan.name}</h2>
                      <p style={{ fontSize: '12px', color: '#94a3b8', margin: '4px 0 0', minHeight: '34px' }}>
                        {plan.tagline}
                      </p>
                    </div>
                    <div
                      style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        background: plan.popular ? 'rgba(37, 99, 235, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '18px',
                      }}
                    >
                      {plan.popular ? '⚡' : '🚀'}
                    </div>
                  </div>

                  <div className="act-price-row">
                    <span className="act-price-val">{plan.price}</span>
                    <span style={{ fontSize: '12px', color: '#94a3b8' }}>one-time · lifetime</span>
                  </div>

                  <div className="act-bonus-pill">
                    <span>🎁</span>
                    <span>Includes ₹300 Free Calling Credits</span>
                  </div>

                  <button
                    onClick={() => handleSelectPlan(plan)}
                    disabled={isLoading || (loadingPlan !== null && !isLoading)}
                    className={`act-btn ${plan.popular ? 'primary' : 'secondary'}`}
                  >
                    {isLoading ? 'Opening Razorpay...' : plan.buttonText}
                  </button>

                  <div style={{ textAlign: 'center', fontSize: '11px', color: '#64748b', marginTop: '8px' }}>
                    Standard Web Checkout · UPI, Cards & Netbanking
                  </div>

                  <ul className="act-feature-list">
                    <div style={{ fontSize: '11px', fontWeight: 700, color: '#e2e8f0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {plan.featuresHeader}
                    </div>
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="act-feature-item">
                        <span className="act-check">✓</span>
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div
                  style={{
                    marginTop: '24px',
                    paddingTop: '14px',
                    borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '11px',
                    color: '#64748b',
                  }}
                >
                  <span>SSL 256-Bit Encrypted</span>
                  <span>Direct Vobiz Provisioning</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="act-footer-trust">
          Payments are securely processed via Razorpay Standard Checkout. After platform setup, you can top-up calling credits in your workspace anytime.
        </div>
      </main>
    </div>
  );
}
