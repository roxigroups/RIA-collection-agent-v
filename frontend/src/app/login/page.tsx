'use client';

import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';
import { useApp } from '@/context/AppContext';
import { api, ApiError } from '@/lib/api';

const REMEMBER_KEY = 'ria.rememberedUserId';

const noSubscribe = () => () => {};
const readRemembered = () => {
  try {
    return localStorage.getItem(REMEMBER_KEY) ?? '';
  } catch {
    return '';
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

const MailIcon = () => (
  <svg {...svg}>
    <rect width="20" height="16" x="2" y="4" rx="2" />
    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
  </svg>
);

const UserIcon = () => (
  <svg {...svg}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
  </svg>
);

const BuildingIcon = () => (
  <svg {...svg}>
    <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z" />
    <path d="M6 12H4a2 2 0 0 0-2 2v8" />
    <path d="M18 12h2a2 2 0 0 1 2 2v8" />
    <path d="M10 6h4" />
    <path d="M10 10h4" />
    <path d="M10 14h4" />
    <path d="M10 18h4" />
  </svg>
);

const PhoneIcon = () => (
  <svg {...svg}>
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
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

type Mode = 'signin' | 'signup' | 'signup_otp' | 'forgot' | 'forgot_otp';

export default function LoginPage() {
  const router = useRouter();
  const { login, showToast, isLoggedIn } = useApp();

  const savedUser = useSyncExternalStore(noSubscribe, readRemembered, () => '');
  const [mode, setMode] = useState<Mode>('signin');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [busy, setBusy] = useState(false);

  // Sign In state
  const [typedUser, setUser] = useState<string | null>(null);
  const [rememberChoice, setRemember] = useState<boolean | null>(null);
  const user = typedUser ?? savedUser;
  const remember = rememberChoice ?? savedUser !== '';
  const [pass, setPass] = useState('');
  const [showPass, setShowPass] = useState(false);

  // Sign Up state
  const [companyName, setCompanyName] = useState('');
  const [fullName, setFullName] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [signupPass, setSignupPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [showSignupPass, setShowSignupPass] = useState(false);
  const [showConfirmPass, setShowConfirmPass] = useState(false);
  const [signupOtp, setSignupOtp] = useState('');

  // Forgot Password state
  const [forgotEmail, setForgotEmail] = useState('');
  const [resetOtp, setResetOtp] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmNewPass, setConfirmNewPass] = useState('');
  const [showNewPass, setShowNewPass] = useState(false);
  const [showConfirmNewPass, setShowConfirmNewPass] = useState(false);

  useEffect(() => {
    if (isLoggedIn) router.replace('/dashboard');
  }, [isLoggedIn, router]);

  const switchMode = (newMode: Mode) => {
    setMode(newMode);
    setError('');
    setInfo('');
  };

  // 1. Handle Sign In
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !pass) {
      setError('Enter your email and password.');
      return;
    }
    setBusy(true);
    setError('');
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
      // storage blocked
    }
    router.push('/dashboard');
  };

  // 2. Handle Sign Up Request
  const handleSignupRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim() || !fullName.trim() || !signupEmail.trim() || !signupPass) {
      setError('Please fill in all required fields.');
      return;
    }
    if (signupPass !== confirmPass) {
      setError('Passwords do not match.');
      return;
    }
    if (signupPass.length < 8 || !/[a-zA-Z]/.test(signupPass) || !/[0-9]/.test(signupPass)) {
      setError('Password must be at least 8 characters long and contain both letters and numbers.');
      return;
    }

    setBusy(true);
    setError('');
    try {
      await api('/auth/register/request', {
        body: {
          companyName: companyName.trim(),
          name: fullName.trim(),
          email: signupEmail.trim(),
          phone: phone.trim(),
          password: signupPass,
        },
      });
      setInfo(`We've sent a 6-digit verification code to ${signupEmail.trim()}`);
      setMode('signup_otp');
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Could not send verification code.';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  // 3. Handle Sign Up OTP Confirmation
  const handleSignupConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!signupOtp.trim() || signupOtp.trim().length !== 6) {
      setError('Enter the 6-digit verification code.');
      return;
    }

    setBusy(true);
    setError('');
    try {
      await api('/auth/register/confirm', {
        body: {
          email: signupEmail.trim(),
          code: signupOtp.trim(),
        },
      });
      showToast('Workspace activated! Signing in...');
      // Sign in automatically with the confirmed credentials
      await login(signupEmail.trim(), signupPass);
      router.push('/dashboard');
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Invalid code.';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  // 4. Handle Forgot Password Request
  const handleForgotRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forgotEmail.trim()) {
      setError('Enter your email address.');
      return;
    }

    setBusy(true);
    setError('');
    try {
      await api('/auth/forgot-password/request', {
        body: { email: forgotEmail.trim() },
      });
      setInfo(`If an account exists, a 6-digit reset code has been sent to ${forgotEmail.trim()}`);
      setMode('forgot_otp');
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Could not process reset request.';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  // 5. Handle Forgot Password Confirmation
  const handleForgotConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetOtp.trim() || resetOtp.trim().length !== 6) {
      setError('Enter the 6-digit reset code.');
      return;
    }
    if (newPass !== confirmNewPass) {
      setError('Passwords do not match.');
      return;
    }
    if (newPass.length < 8 || !/[a-zA-Z]/.test(newPass) || !/[0-9]/.test(newPass)) {
      setError('Password must be at least 8 characters long and contain both letters and numbers.');
      return;
    }

    setBusy(true);
    setError('');
    try {
      await api('/auth/forgot-password/confirm', {
        body: {
          email: forgotEmail.trim(),
          code: resetOtp.trim(),
          newPassword: newPass,
        },
      });
      showToast('Password reset successfully! Please sign in with your new password.');
      setUser(forgotEmail.trim());
      setPass('');
      switchMode('signin');
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Invalid code or password.';
      setError(msg);
    } finally {
      setBusy(false);
    }
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
          {/* ============================================================== */}
          {/* VIEW 1: SIGN IN                                                */}
          {/* ============================================================== */}
          {mode === 'signin' && (
            <>
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
                  <label htmlFor="lgUser">Email</label>
                  <div className="login-input">
                    <span className="ic">
                      <MailIcon />
                    </span>
                    <input
                      id="lgUser"
                      type="email"
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      placeholder="you@company.com"
                      value={user}
                      onChange={(e) => {
                        setUser(e.target.value);
                        setError('');
                      }}
                      required
                    />
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
                      placeholder="••••••••••••"
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
                      setForgotEmail(user || '');
                      switchMode('forgot');
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

              <div className="login-switch">
                New to RIA?{' '}
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    switchMode('signup');
                  }}
                >
                  Create a company account
                </a>
              </div>

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
                    <li>Sign in with the email your account was created with.</li>
                    <li>Password is case sensitive.</li>
                    <li>Forgot it? Click &ldquo;Forgot password?&rdquo; and we&apos;ll email you a code.</li>
                    <li>Do not share your login credentials with anyone.</li>
                  </ul>
                </div>
              </div>
            </>
          )}

          {/* ============================================================== */}
          {/* VIEW 2: CREATE ACCOUNT                                         */}
          {/* ============================================================== */}
          {mode === 'signup' && (
            <>
              <h1>Create your RIA account</h1>
              <p className="sub">Set up your company&apos;s workspace</p>

              {error && (
                <div className="msg msg-err" role="alert">
                  <span>⚠️</span>
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSignupRequest} noValidate>
                <div className="login-field">
                  <label htmlFor="suCompany">Company name</label>
                  <div className="login-input">
                    <span className="ic">
                      <BuildingIcon />
                    </span>
                    <input
                      id="suCompany"
                      type="text"
                      placeholder="Your company's name"
                      value={companyName}
                      onChange={(e) => {
                        setCompanyName(e.target.value);
                        setError('');
                      }}
                      required
                    />
                  </div>
                </div>

                <div className="login-field">
                  <label htmlFor="suName">Your name</label>
                  <div className="login-input">
                    <span className="ic">
                      <UserIcon />
                    </span>
                    <input
                      id="suName"
                      type="text"
                      placeholder="Full name"
                      value={fullName}
                      onChange={(e) => {
                        setFullName(e.target.value);
                        setError('');
                      }}
                      required
                    />
                  </div>
                </div>

                <div className="login-field">
                  <label htmlFor="suEmail">Email</label>
                  <div className="login-input">
                    <span className="ic">
                      <MailIcon />
                    </span>
                    <input
                      id="suEmail"
                      type="email"
                      placeholder="you@company.com"
                      value={signupEmail}
                      onChange={(e) => {
                        setSignupEmail(e.target.value);
                        setError('');
                      }}
                      required
                    />
                  </div>
                  <div className="login-subtext">We&apos;ll send a code here to confirm it&apos;s yours.</div>
                </div>

                <div className="login-field">
                  <label htmlFor="suPhone">Phone (optional)</label>
                  <div className="login-input">
                    <span className="ic">
                      <PhoneIcon />
                    </span>
                    <input
                      id="suPhone"
                      type="tel"
                      placeholder="+91 98765 43210"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                    />
                  </div>
                </div>

                <div className="login-field">
                  <label htmlFor="suPass">Password</label>
                  <div className="login-input">
                    <span className="ic">
                      <LockIcon />
                    </span>
                    <input
                      id="suPass"
                      type={showSignupPass ? 'text' : 'password'}
                      placeholder="Create a password"
                      value={signupPass}
                      onChange={(e) => {
                        setSignupPass(e.target.value);
                        setError('');
                      }}
                      required
                    />
                    <button
                      type="button"
                      className="eye"
                      onClick={() => setShowSignupPass((v) => !v)}
                      aria-label={showSignupPass ? 'Hide password' : 'Show password'}
                    >
                      {showSignupPass ? <EyeIcon /> : <EyeOffIcon />}
                    </button>
                  </div>
                  <div className="login-subtext">At least 8 characters, with a letter and a number.</div>
                </div>

                <div className="login-field">
                  <label htmlFor="suConfirmPass">Confirm password</label>
                  <div className="login-input">
                    <span className="ic">
                      <LockIcon />
                    </span>
                    <input
                      id="suConfirmPass"
                      type={showConfirmPass ? 'text' : 'password'}
                      placeholder="Type it again"
                      value={confirmPass}
                      onChange={(e) => {
                        setConfirmPass(e.target.value);
                        setError('');
                      }}
                      required
                    />
                    <button
                      type="button"
                      className="eye"
                      onClick={() => setShowConfirmPass((v) => !v)}
                      aria-label={showConfirmPass ? 'Hide password' : 'Show password'}
                    >
                      {showConfirmPass ? <EyeIcon /> : <EyeOffIcon />}
                    </button>
                  </div>
                </div>

                <button type="submit" className="login-submit" disabled={busy}>
                  {busy ? 'Sending code…' : 'Create account'}
                  {!busy && <ArrowIcon />}
                </button>
              </form>

              <div className="login-switch">
                Already have an account?{' '}
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    switchMode('signin');
                  }}
                >
                  Sign in
                </a>
              </div>

              <div className="login-secure">
                <ShieldIcon />
                <div>
                  <b>Secured Access</b>
                  <span>Your data is encrypted and protected with industry-standard security.</span>
                </div>
              </div>
            </>
          )}

          {/* ============================================================== */}
          {/* VIEW 2B: SIGN UP OTP CONFIRMATION                              */}
          {/* ============================================================== */}
          {mode === 'signup_otp' && (
            <>
              <h1>Verify your email</h1>
              <p className="sub">We sent a 6-digit code to {signupEmail}</p>

              {info && (
                <div className="msg" style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', color: '#1E40AF' }}>
                  <span>✉️</span>
                  <span>{info}</span>
                </div>
              )}

              {error && (
                <div className="msg msg-err" role="alert">
                  <span>⚠️</span>
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSignupConfirm} noValidate>
                <div className="login-field">
                  <label htmlFor="suOtp">6-digit verification code</label>
                  <div className="login-input">
                    <input
                      id="suOtp"
                      type="text"
                      className="otp-input"
                      maxLength={6}
                      placeholder="••••••"
                      value={signupOtp}
                      onChange={(e) => {
                        setSignupOtp(e.target.value.replace(/\D/g, ''));
                        setError('');
                      }}
                      required
                      autoFocus
                    />
                  </div>
                  <div className="login-subtext">Check your inbox or spam folder. Expires in 15 minutes.</div>
                </div>

                <button type="submit" className="login-submit" disabled={busy}>
                  {busy ? 'Verifying…' : 'Verify & Launch Workspace'}
                  {!busy && <ArrowIcon />}
                </button>
              </form>

              <div className="login-switch">
                Didn&apos;t get the code?{' '}
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    handleSignupRequest(e);
                  }}
                >
                  Resend code
                </a>{' '}
                or{' '}
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    switchMode('signup');
                  }}
                >
                  Edit details
                </a>
              </div>

              <div className="login-secure">
                <ShieldIcon />
                <div>
                  <b>Secured Access</b>
                  <span>Your data is encrypted and protected with industry-standard security.</span>
                </div>
              </div>
            </>
          )}

          {/* ============================================================== */}
          {/* VIEW 3: FORGOT PASSWORD                                        */}
          {/* ============================================================== */}
          {mode === 'forgot' && (
            <>
              <h1>Forgot your password?</h1>
              <p className="sub">We&apos;ll email you a code to reset it</p>

              {error && (
                <div className="msg msg-err" role="alert">
                  <span>⚠️</span>
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleForgotRequest} noValidate>
                <div className="login-field">
                  <label htmlFor="fpEmail">Email</label>
                  <div className="login-input">
                    <span className="ic">
                      <MailIcon />
                    </span>
                    <input
                      id="fpEmail"
                      type="email"
                      placeholder="you@company.com"
                      value={forgotEmail}
                      onChange={(e) => {
                        setForgotEmail(e.target.value);
                        setError('');
                      }}
                      required
                    />
                  </div>
                </div>

                <button type="submit" className="login-submit" disabled={busy}>
                  {busy ? 'Sending code…' : 'Send code'}
                  {!busy && <ArrowIcon />}
                </button>
              </form>

              <div className="login-switch">
                Remember your password?{' '}
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    switchMode('signin');
                  }}
                >
                  Sign in
                </a>
              </div>

              <div className="login-secure">
                <ShieldIcon />
                <div>
                  <b>Secured Access</b>
                  <span>Your data is encrypted and protected with industry-standard security.</span>
                </div>
              </div>
            </>
          )}

          {/* ============================================================== */}
          {/* VIEW 3B: FORGOT PASSWORD RESET OTP                             */}
          {/* ============================================================== */}
          {mode === 'forgot_otp' && (
            <>
              <h1>Reset your password</h1>
              <p className="sub">Enter the code sent to {forgotEmail}</p>

              {info && (
                <div className="msg" style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', color: '#1E40AF' }}>
                  <span>✉️</span>
                  <span>{info}</span>
                </div>
              )}

              {error && (
                <div className="msg msg-err" role="alert">
                  <span>⚠️</span>
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleForgotConfirm} noValidate>
                <div className="login-field">
                  <label htmlFor="fpOtp">6-digit reset code</label>
                  <div className="login-input">
                    <input
                      id="fpOtp"
                      type="text"
                      className="otp-input"
                      maxLength={6}
                      placeholder="••••••"
                      value={resetOtp}
                      onChange={(e) => {
                        setResetOtp(e.target.value.replace(/\D/g, ''));
                        setError('');
                      }}
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <div className="login-field">
                  <label htmlFor="fpNewPass">New password</label>
                  <div className="login-input">
                    <span className="ic">
                      <LockIcon />
                    </span>
                    <input
                      id="fpNewPass"
                      type={showNewPass ? 'text' : 'password'}
                      placeholder="Enter new password"
                      value={newPass}
                      onChange={(e) => {
                        setNewPass(e.target.value);
                        setError('');
                      }}
                      required
                    />
                    <button
                      type="button"
                      className="eye"
                      onClick={() => setShowNewPass((v) => !v)}
                      aria-label={showNewPass ? 'Hide password' : 'Show password'}
                    >
                      {showNewPass ? <EyeIcon /> : <EyeOffIcon />}
                    </button>
                  </div>
                  <div className="login-subtext">At least 8 characters, with a letter and a number.</div>
                </div>

                <div className="login-field">
                  <label htmlFor="fpConfirmNewPass">Confirm new password</label>
                  <div className="login-input">
                    <span className="ic">
                      <LockIcon />
                    </span>
                    <input
                      id="fpConfirmNewPass"
                      type={showConfirmNewPass ? 'text' : 'password'}
                      placeholder="Type it again"
                      value={confirmNewPass}
                      onChange={(e) => {
                        setConfirmNewPass(e.target.value);
                        setError('');
                      }}
                      required
                    />
                    <button
                      type="button"
                      className="eye"
                      onClick={() => setShowConfirmNewPass((v) => !v)}
                      aria-label={showConfirmNewPass ? 'Hide password' : 'Show password'}
                    >
                      {showConfirmNewPass ? <EyeIcon /> : <EyeOffIcon />}
                    </button>
                  </div>
                </div>

                <button type="submit" className="login-submit" disabled={busy}>
                  {busy ? 'Updating…' : 'Reset password'}
                  {!busy && <ArrowIcon />}
                </button>
              </form>

              <div className="login-switch">
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    switchMode('signin');
                  }}
                >
                  Back to sign in
                </a>
              </div>

              <div className="login-secure">
                <ShieldIcon />
                <div>
                  <b>Secured Access</b>
                  <span>Your data is encrypted and protected with industry-standard security.</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
