'use client';

import React, { useState, useEffect } from 'react';
import Script from 'next/script';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useApp } from '@/context/AppContext';
import { api, ApiError } from '@/lib/api';

declare global {
  interface Window {
    Razorpay: any;
  }
}

interface PlanConfig {
  id: 'starter';
  name: string;
  tagline: string;
  price: string;
  pricePeriod: string;
  priceAmount: number;
  popular?: boolean;
  buttonText: string;
  featuresHeader: string;
  features: string[];
}

const PLANS: PlanConfig[] = [
  {
    id: 'starter',
    name: 'RIA Monthly Platform Subscription',
    tagline: 'Complete autonomous multilingual voice recovery & collection workspace for distributors',
    price: '₹4,999',
    pricePeriod: '/ month · billed monthly',
    priceAmount: 499900,
    popular: true,
    buttonText: 'Activate Monthly Workspace — ₹4,999/mo',
    featuresHeader: 'Everything included in your monthly subscription:',
    features: [
      'Dedicated tenant workspace & provisioned caller ID',
      'Autonomous Multilingual Voice AI (Telugu, Hindi, Kannada, Tamil, Marathi & English)',
      'Promise-to-Pay (PTP) extraction, automatic tracking & ledger',
      '₹300 in free voice calling credits included to start dialing',
      'Real-time call transcripts & sentiment analysis',
      'Excel / CSV bulk call sheet imports & campaign manager',
      'Automated scheduled callbacks & smart retry queue',
      'WhatsApp payment link dispatch with instant UPI integration',
      'Dispute escalation ticketing & retailer ledger records',
      'Multi-user team access with distributor role permissions',
      'Full SLA support & ongoing AI model updates',
    ],
  },
];

export default function OnboardingActivatePage() {
  const router = useRouter();
  const { meInfo, isSuperAdmin, showToast, logout } = useApp();
  const [loadingPlan, setLoadingPlan] = useState<'starter' | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = async () => {
    setSigningOut(true);
    await logout();
    window.location.href = '/login';
  };

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
        '';

      if (!window.Razorpay) {
        throw new Error('Razorpay Checkout SDK is still loading. Please try again in a moment.');
      }

      // 2. Open Razorpay Checkout Modal
      const options = {
        key: keyId,
        amount: orderRes.amount,
        currency: orderRes.currency || 'INR',
        name: 'RIA AI Platform',
        description: `${plan.name} (₹4,999/mo) + ₹300 Calling Credits`,
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
    <div className="activate-light-page">
      <Script src="https://checkout.razorpay.com/v1/checkout.js" />

      <style jsx global>{`
        .activate-light-page {
          min-height: 100vh;
          background: #f4f6fa;
          color: #12203f;
          font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          display: flex;
          flex-direction: column;
          box-sizing: border-box;
        }

        .act-light-header {
          border-bottom: 1px solid #e2e8f2;
          background: #ffffff;
          position: sticky;
          top: 0;
          z-index: 20;
          padding: 14px 28px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          box-shadow: 0 1px 3px rgba(15, 35, 80, 0.04);
        }

        .act-logo-box {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .act-logo-icon {
          width: 36px;
          height: 36px;
          border-radius: 9px;
          background: linear-gradient(135deg, #1e52c9, #0f2350);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          font-size: 18px;
          color: #ffffff;
          box-shadow: 0 2px 8px rgba(30, 82, 201, 0.25);
        }

        .act-title-text {
          font-weight: 800;
          font-size: 15px;
          color: #0f2350;
          letter-spacing: -0.01em;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .act-pill-small {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          background: #e8eefc;
          color: #1e52c9;
          border: 1px solid #c7d7f7;
          padding: 2px 8px;
          border-radius: 999px;
        }

        .act-hero {
          max-width: 1080px;
          margin: 0 auto;
          padding: 44px 24px 60px;
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
          background: #e8eefc;
          border: 1px solid #cbdcf9;
          color: #1e52c9;
          font-size: 12px;
          font-weight: 600;
          margin-bottom: 14px;
        }

        .act-badge-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #1e52c9;
        }

        .act-h1 {
          font-size: clamp(28px, 4vw, 42px);
          font-weight: 800;
          letter-spacing: -0.025em;
          text-align: center;
          margin: 0;
          color: #0f2350;
        }

        .act-sub {
          margin: 12px 0 0;
          font-size: 15px;
          color: #53617c;
          text-align: center;
          max-width: 640px;
          line-height: 1.55;
        }

        .act-cards-grid {
          margin-top: 36px;
          display: flex;
          justify-content: center;
          width: 100%;
          max-width: 580px;
        }

        .act-card {
          width: 100%;
          position: relative;
          background: #ffffff;
          border: 2px solid #1e52c9;
          border-radius: 20px;
          padding: 36px 32px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          box-shadow: 0 4px 16px rgba(30, 82, 201, 0.12), 0 20px 40px rgba(15, 35, 80, 0.08);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .act-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(30, 82, 201, 0.16), 0 24px 48px rgba(15, 35, 80, 0.12);
        }

        .act-card.popular {
          border: 2px solid #1e52c9;
          box-shadow: 0 4px 12px rgba(30, 82, 201, 0.12), 0 16px 36px rgba(30, 82, 201, 0.14);
        }

        .act-popular-tag {
          position: absolute;
          top: -12px;
          left: 50%;
          transform: translateX(-50%);
          background: linear-gradient(90deg, #1e52c9, #0f2350);
          color: #ffffff;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 4px 14px;
          border-radius: 999px;
          box-shadow: 0 3px 8px rgba(30, 82, 201, 0.35);
        }

        .act-price-row {
          margin: 18px 0 10px;
          display: flex;
          align-items: baseline;
          gap: 8px;
        }

        .act-price-val {
          font-size: 42px;
          font-weight: 900;
          color: #0f2350;
          letter-spacing: -0.02em;
        }

        .act-bonus-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: #e6f4ec;
          border: 1px solid #bfe0cd;
          color: #157f4c;
          font-size: 12px;
          font-weight: 600;
          padding: 6px 12px;
          border-radius: 8px;
          margin-bottom: 20px;
        }

        .act-btn {
          width: 100%;
          padding: 13px 16px;
          border-radius: 10px;
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
          background: #1e52c9;
          color: #ffffff;
          box-shadow: 0 4px 12px rgba(30, 82, 201, 0.3);
        }

        .act-btn.primary:hover {
          background: #1844a8;
        }

        .act-btn.secondary {
          background: #0f2350;
          color: #ffffff;
        }

        .act-btn.secondary:hover {
          background: #16305f;
        }

        .act-feature-list {
          margin: 22px 0 0;
          padding: 18px 0 0;
          border-top: 1px solid #eef2f8;
          list-style: none;
        }

        .act-feature-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          font-size: 12.5px;
          color: #334155;
          margin-bottom: 12px;
          line-height: 1.45;
        }

        .act-check {
          color: #1e52c9;
          font-weight: 900;
          flex-shrink: 0;
        }

        .act-footer-trust {
          margin-top: 36px;
          text-align: center;
          font-size: 12px;
          color: #8593ad;
          max-width: 480px;
        }
      `}</style>

      {/* Header */}
      <header className="act-light-header">
        <div className="act-logo-box">
          <Image
            src="/logo-ria-official.png"
            alt="RIA AI Platform"
            width={76}
            height={44}
            style={{ objectFit: 'contain' }}
            priority
          />
          <div>
            <div className="act-title-text">
              RIA AI AGENT
              <span className="act-pill-small">Platform Activation</span>
            </div>
            <div style={{ fontSize: '11px', color: '#53617c' }}>Distribution Intelligence Platform</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px' }}>
          {meInfo && (
            <span style={{ color: '#53617c' }}>
              Signed in as <strong style={{ color: '#0f2350' }}>{meInfo.e}</strong>
            </span>
          )}
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            style={{
              background: 'transparent',
              border: 0,
              color: '#1e52c9',
              cursor: signingOut ? 'wait' : 'pointer',
              fontWeight: 600,
              textDecoration: 'underline',
            }}
          >
            {signingOut ? 'Signing out...' : 'Sign out'}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="act-hero">
        <div className="act-badge-main">
          <span className="act-badge-dot" />
          Monthly Platform Subscription · Full Platform Access
        </div>

        <h1 className="act-h1">Activate Your Voice AI Workspace</h1>
        <p className="act-sub">
          Supercharge debt collections with autonomous multilingual voice recovery. Your monthly subscription includes{' '}
          <strong style={{ color: '#1e52c9' }}>₹300 in free voice calling credits</strong> to start dialing immediately.
        </p>

        {errorMsg && (
          <div
            style={{
              marginTop: '18px',
              width: '100%',
              maxWidth: '440px',
              background: '#fdecef',
              border: '1px solid #f6cfd6',
              color: '#a70d26',
              padding: '12px 16px',
              borderRadius: '8px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>⚠️ {errorMsg}</span>
            <button
              onClick={() => setErrorMsg('')}
              style={{ background: 'transparent', border: 0, color: '#a70d26', fontWeight: 700, cursor: 'pointer' }}
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
              <div key={plan.id} className="act-card popular">
                <div className="act-popular-tag">Official Platform Plan</div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <h2 style={{ fontSize: '22px', fontWeight: 800, margin: 0, color: '#0f2350' }}>{plan.name}</h2>
                      <p style={{ fontSize: '13px', color: '#53617c', margin: '6px 0 0', minHeight: '34px' }}>
                        {plan.tagline}
                      </p>
                    </div>
                    <div
                      style={{
                        width: '44px',
                        height: '44px',
                        borderRadius: '12px',
                        background: '#e8eefc',
                        color: '#1e52c9',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '20px',
                      }}
                    >
                      ⚡
                    </div>
                  </div>

                  <div className="act-price-row">
                    <span className="act-price-val">{plan.price}</span>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: '#53617c' }}>{plan.pricePeriod}</span>
                  </div>

                  <div className="act-bonus-pill">
                    <span>🎁</span>
                    <span>Includes ₹300 Free Calling Credits Every Month</span>
                  </div>

                  <button
                    onClick={() => handleSelectPlan(plan)}
                    disabled={isLoading}
                    className="act-btn primary"
                  >
                    {isLoading ? 'Opening Razorpay...' : plan.buttonText}
                  </button>

                  <div style={{ textAlign: 'center', marginTop: '10px' }}>
                    <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#0f2350' }}>
                      ₹4,999 /month
                    </div>
                    <div style={{ fontSize: '11.5px', color: '#53617c', marginTop: '2px', fontWeight: 500 }}>
                      Inclusive of 18% GST. No additional GST at checkout.
                    </div>
                    <div style={{ fontSize: '10.5px', color: '#8593ad', marginTop: '4px' }}>
                      Standard Web Checkout · UPI, Cards & Netbanking
                    </div>
                  </div>

                  <ul className="act-feature-list">
                    <div
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        color: '#53617c',
                        marginBottom: '12px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
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
                    borderTop: '1px solid #eef2f8',
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '11px',
                    color: '#8593ad',
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
