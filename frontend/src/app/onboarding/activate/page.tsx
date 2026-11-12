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
  const [razorpayLoaded, setRazorpayLoaded] = useState(false);
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
              // Redirect to main workspace
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
    <div className="min-h-screen bg-[#0b0f19] text-white flex flex-col justify-between selection:bg-blue-600 selection:text-white">
      <Script
        src="https://checkout.razorpay.com/v1/checkout.js"
        onLoad={() => setRazorpayLoaded(true)}
      />

      {/* Top Navigation Bar */}
      <header className="border-b border-gray-800/80 bg-[#0d1322]/80 backdrop-blur-md sticky top-0 z-20 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-bold text-lg shadow-lg shadow-blue-500/20">
            R
          </div>
          <div>
            <div className="font-bold tracking-tight text-base flex items-center gap-2">
              RIA AI AGENT
              <span className="text-[11px] font-semibold uppercase tracking-wider bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full">
                Platform Activation
              </span>
            </div>
            <div className="text-xs text-gray-400">Distribution Intelligence Platform</div>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {meInfo && (
            <span className="text-gray-400">
              Signed in as <span className="text-gray-200 font-medium">{meInfo.e}</span>
            </span>
          )}
          <button
            onClick={() => {
              window.location.href = '/login';
            }}
            className="text-xs text-gray-400 hover:text-gray-200 transition-colors underline"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Main Hero & Pricing Cards Section */}
      <main className="max-w-6xl mx-auto px-6 py-12 flex-1 flex flex-col items-center justify-center">
        {/* Banner Pill */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/25 text-blue-300 text-xs font-medium mb-4 shadow-inner">
          <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          One-Time Platform Setup · Lifetime Access
        </div>

        {/* Title & Subtitle */}
        <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight text-center bg-gradient-to-b from-white via-gray-100 to-gray-400 bg-clip-text text-transparent">
          Plans that grow with you
        </h1>
        <p className="mt-3 text-sm md:text-base text-gray-400 text-center max-w-2xl">
          Activate your distribution workspace with autonomous multilingual voice collection. Both plans include{' '}
          <span className="text-blue-400 font-semibold">₹300 in free voice calling credits</span> to start dialing immediately.
        </p>

        {errorMsg && (
          <div className="mt-6 w-full max-w-md bg-red-950/40 border border-red-500/40 text-red-300 px-4 py-3 rounded-xl text-xs flex items-center justify-between">
            <span>⚠️ {errorMsg}</span>
            <button onClick={() => setErrorMsg('')} className="text-red-400 hover:text-red-200 font-bold ml-2">
              ×
            </button>
          </div>
        )}

        {/* The 2 Cards Grid */}
        <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-4xl">
          {PLANS.map((plan) => {
            const isLoading = loadingPlan === plan.id;
            return (
              <div
                key={plan.id}
                className={`relative rounded-3xl p-8 flex flex-col justify-between transition-all duration-200 ${
                  plan.popular
                    ? 'bg-gradient-to-b from-[#141d33] to-[#0f172a] border-2 border-blue-500/60 shadow-2xl shadow-blue-500/15'
                    : 'bg-[#111726]/90 border border-gray-800 hover:border-gray-700 shadow-xl'
                }`}
              >
                {/* Popular Pill */}
                {plan.popular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-[11px] font-bold tracking-wider uppercase px-3.5 py-1 rounded-full shadow-md">
                    Most Popular
                  </div>
                )}

                <div>
                  {/* Icon & Plan Name */}
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-bold text-white tracking-tight">{plan.name}</h2>
                      <p className="text-xs text-gray-400 mt-1 min-h-[32px]">{plan.tagline}</p>
                    </div>
                    <div
                      className={`w-11 h-11 rounded-2xl flex items-center justify-center text-lg ${
                        plan.popular ? 'bg-blue-600/20 text-blue-400' : 'bg-gray-800/60 text-gray-300'
                      }`}
                    >
                      {plan.popular ? '⚡' : '🚀'}
                    </div>
                  </div>

                  {/* Price */}
                  <div className="mt-6 flex items-baseline gap-2">
                    <span className="text-4xl md:text-5xl font-black text-white tracking-tight">{plan.price}</span>
                    <span className="text-xs text-gray-400 font-medium">one-time · lifetime</span>
                  </div>

                  {/* Welcome Bonus Callout */}
                  <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                    <span>🎁</span>
                    <span>Includes ₹300 Free Calling Credits</span>
                  </div>

                  {/* Action Button */}
                  <button
                    onClick={() => handleSelectPlan(plan)}
                    disabled={isLoading || (loadingPlan !== null && !isLoading)}
                    className={`mt-6 w-full py-3.5 px-4 rounded-xl font-semibold text-sm transition-all duration-150 flex items-center justify-center gap-2 shadow-lg ${
                      plan.popular
                        ? 'bg-blue-600 hover:bg-blue-500 active:scale-[0.99] text-white shadow-blue-600/30'
                        : 'bg-gray-800 hover:bg-gray-700 active:scale-[0.99] text-white'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {isLoading ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Opening Razorpay...</span>
                      </>
                    ) : (
                      <span>{plan.buttonText}</span>
                    )}
                  </button>

                  <div className="mt-2 text-center text-[11px] text-gray-400">
                    Standard Web Checkout · UPI, Cards & Netbanking
                  </div>

                  {/* Feature Checklist */}
                  <div className="mt-8 pt-6 border-t border-gray-800/80">
                    <div className="text-xs font-semibold text-gray-300 mb-4">{plan.featuresHeader}</div>
                    <ul className="space-y-3">
                      {plan.features.map((feature, idx) => (
                        <li key={idx} className="flex items-start gap-2.5 text-xs text-gray-300 leading-relaxed">
                          <span className="text-blue-400 font-bold mt-0.5">✓</span>
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-gray-800/40 text-[11px] text-gray-400 flex items-center justify-between">
                  <span>SSL 256-Bit Encrypted</span>
                  <span>Direct Vobiz Provisioning</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom Trust Guarantee */}
        <div className="mt-12 text-center text-xs text-gray-400 max-w-md">
          Payments are securely processed via Razorpay Standard Checkout. After setup, you can add more calling credits to your wallet at any time.
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/60 py-4 px-6 text-center text-xs text-gray-400">
        © 2026 RIA AI AGENT — Distribution Intelligence Platform. All rights reserved.
      </footer>
    </div>
  );
}
