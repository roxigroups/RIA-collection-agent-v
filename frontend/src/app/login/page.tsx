'use client';

import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';
import { useApp } from '@/context/AppContext';

// Only the User ID is remembered on the device — never the password.
const REMEMBER_KEY = 'ria.rememberedUserId';

const noSubscribe = () => () => {};
const readRemembered = () => {
  try {
    return localStorage.getItem(REMEMBER_KEY) ?? '';
  } catch {
    return ''; // storage blocked — start with an empty form
  }
};

const svg = {
  width: 14,
  height: 14,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
};

const UserIcon = () => (
  <svg {...svg}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
  </svg>
);

const LockIcon = () => (
  <svg {...svg}>
    <rect x="4.5" y="10.5" width="15" height="10.5" rx="2" />
    <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
    <path d="M12 14.5v2.5" />
  </svg>
);

const EyeIcon = () => (
  <svg {...svg} width={15} height={15}>
    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeOffIcon = () => (
  <svg {...svg} width={15} height={15}>
    <path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-2.9 3.9M6.6 6.6C3.7 8.5 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    <path d="M3 3l18 18" />
  </svg>
);

const InfoIcon = () => (
  <svg {...svg} width={12} height={12} strokeWidth={2}>
    <circle cx="12" cy="12" r="9.5" />
    <path d="M12 11v5.5" />
    <circle cx="12" cy="7.6" r=".6" fill="currentColor" />
  </svg>
);

const ArrowIcon = () => (
  <svg {...svg} width={15} height={15} strokeWidth={2.2}>
    <path d="M4 12h15" />
    <path d="M13 6l6 6-6 6" />
  </svg>
);

const ShieldIcon = () => (
  <svg {...svg} width={22} height={22} strokeWidth={1.6}>
    <path d="M12 2.5l8 3v6c0 5-3.4 8.8-8 10-4.6-1.2-8-5-8-10v-6l8-3z" />
    <path d="M8.5 12l2.5 2.5 4.5-5" />
  </svg>
);

const BulbIcon = () => (
  <svg {...svg} width={22} height={22} strokeWidth={1.6}>
    <path d="M9 17.5h6M10 21h4" />
    <path d="M12 6a5.5 5.5 0 0 0-3.3 9.9c.5.4.8.9.8 1.6h5c0-.7.3-1.2.8-1.6A5.5 5.5 0 0 0 12 6z" />
    <path d="M12 1.5v1.5M4.2 4.7l1.1 1.1M19.8 4.7l-1.1 1.1M1.5 11.5H3M21 11.5h1.5" />
  </svg>
);

export default function LoginPage() {
  const router = useRouter();
  const { login, showToast, isLoggedIn } = useApp();
  const savedUser = useSyncExternalStore(noSubscribe, readRemembered, () => '');
  const [typedUser, setUser] = useState<string | null>(null);
  const [rememberChoice, setRemember] = useState<boolean | null>(null);
  const user = typedUser ?? savedUser;
  const remember = rememberChoice ?? savedUser !== '';
  const [pass, setPass] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isLoggedIn) router.replace('/dashboard');
  }, [isLoggedIn, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !pass) {
      setError('Enter your User ID and password.');
      return;
    }
    setBusy(true);
    const problem = await login(user.trim(), pass);
    setBusy(false);
    if (problem) {
      setError(problem);
      return;
    }
    try {
      if (remember) localStorage.setItem(REMEMBER_KEY, user.trim());
      else localStorage.removeItem(REMEMBER_KEY);
    } catch {
      // storage blocked — signing in still works
    }
    router.push('/dashboard');
  };

  return (
    <div id="login" className="login">
      <div
        className="login-hero"
        role="img"
        aria-label="RIA — AI-Powered Distribution Intelligence Platform. Intelligent Collections. Smarter Decisions."
      />

      <div className="login-form">
        <div className="login-card">
          <h1>Welcome to RIA AI Agent</h1>
          <p className="sub">Sign in to your workspace</p>

          {error && (
            <div className="msg msg-err" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} noValidate>
            <div className="login-field">
              <label htmlFor="lgUser">
                User ID
                <span className="lbl-info" title="Use the User ID provided by your administrator.">
                  <InfoIcon />
                </span>
              </label>
              <div className="login-input">
                <span className="ic">
                  <UserIcon />
                </span>
                <input
                  id="lgUser"
                  type="text"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  placeholder="Enter your User ID"
                  value={user}
                  onChange={(e) => {
                    setUser(e.target.value);
                    setError('');
                  }}
                  aria-describedby="lgUserHint"
                  required
                />
              </div>
              <div id="lgUserHint" className="login-hint">
                Use the User ID provided by your administrator.
              </div>
            </div>

            <div className="login-field pw">
              <label htmlFor="lgPass">Password</label>
              <div className="login-input">
                <span className="ic">
                  <LockIcon />
                </span>
                <input
                  id="lgPass"
                  type={showPass ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={pass}
                  onChange={(e) => {
                    setPass(e.target.value);
                    setError('');
                  }}
                  required
                />
                <button
                  type="button"
                  className="eye"
                  onClick={() => setShowPass((v) => !v)}
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                  aria-pressed={showPass}
                >
                  {showPass ? <EyeIcon /> : <EyeOffIcon />}
                </button>
              </div>
            </div>

            <div className="login-forgot">
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  showToast('Ask your owner or tenant admin to reset your password.');
                }}
              >
                Forgot password?
              </a>
            </div>

            <label className="remember">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
              Remember me on this device
            </label>

            <button type="submit" className="login-submit" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign In'}
              {!busy && <ArrowIcon />}
            </button>
          </form>

          <div className="login-secure">
            <ShieldIcon />
            <div>
              <b>Secured Access</b>
              <span>Your data is encrypted and protected with industry-standard security.</span>
            </div>
          </div>

          <div className="login-tips">
            <span className="bulb">
              <BulbIcon />
            </span>
            <div>
              <h3>Login Tips</h3>
              <ul>
                <li>Use the User ID provided by your administrator.</li>
                <li>Password is case sensitive.</li>
                <li>If you face login issues, click &ldquo;Forgot password&rdquo; or contact your admin.</li>
                <li>Do not share your login credentials with anyone.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
