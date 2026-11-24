import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Camera, LogIn, ShieldCheck, Images, Search, Users, MapPin, KeyRound } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import "./Auth.css";

const GOOGLE_ERROR_MESSAGES: Record<string, string> = {
  not_configured:
    "Google sign-in isn't configured in this environment yet — add GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET to backend/.env (see backend/.env.example for the 5-step setup).",
  denied: "Google sign-in was cancelled.",
  invalid_state: "That Google sign-in link expired — please try again.",
  google_failed: "Google couldn't be reached — please try again in a moment.",
  no_email: "Your Google account didn't share an email address, so we can't sign you in with it.",
  deactivated: "That account has been deactivated. Contact an administrator.",
};

const RESEND_COOLDOWN_SECONDS = 30;

const FEATURES = [
  { icon: Images, text: "One vault for every photo and video, automatically organized" },
  { icon: Users, text: "Face detection groups the people in your memories" },
  { icon: Search, text: "Full-text search across filenames, tags, and video transcripts" },
  { icon: MapPin, text: "A map and timeline of where and when it all happened" },
];

function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-layout">
        <div className="auth-brand-panel">
          <div className="auth-logo">
            <Camera size={22} />
          </div>
          <h1 className="auth-brand-title">MemoryLens AI</h1>
          <p className="auth-brand-tagline">Your personal media vault — searchable, geotagged, and understood.</p>
          <ul className="auth-feature-list">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text}>
                <Icon size={16} />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="auth-card-col">{children}</div>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { login, completeOtpLogin, resendOtp, completeMfaLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [otpToken, setOtpToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [otpError, setOtpError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const cooldownTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaVerifying, setMfaVerifying] = useState(false);

  const [googleConfigured, setGoogleConfigured] = useState<boolean | null>(null);
  const googleError = searchParams.get("google_error");

  useEffect(() => {
    api
      .googleStatus()
      .then((s) => setGoogleConfigured(s.configured))
      .catch(() => setGoogleConfigured(false));
  }, []);

  useEffect(() => {
    if (googleError) {
      const next = new URLSearchParams(searchParams);
      next.delete("google_error");
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onGoogleClick = () => {
    if (!googleConfigured) return;
    window.location.href = "/api/auth/google/login";
  };

  const locationState = location.state as
    | { from?: string; resetSuccess?: boolean; idleLoggedOut?: boolean; sessionRevoked?: boolean }
    | null;
  const from = locationState?.from ?? "/library";
  // Captured once on mount so the banner survives this single render pass;
  // the router state itself is cleared right after so a later back/forward
  // navigation to this same history entry, or any subsequent unrelated
  // login attempt, doesn't resurrect it.
  const [resetSuccess] = useState(() => locationState?.resetSuccess ?? false);
  const [idleLoggedOut] = useState(() => locationState?.idleLoggedOut ?? false);
  const [sessionRevoked] = useState(() => locationState?.sessionRevoked ?? false);

  useEffect(() => {
    return () => {
      if (cooldownTimer.current) clearInterval(cooldownTimer.current);
    };
  }, []);

  useEffect(() => {
    if (locationState?.resetSuccess) {
      navigate(location.pathname, { replace: true, state: { from: locationState.from } });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startCooldown = () => {
    setResendCooldown(RESEND_COOLDOWN_SECONDS);
    if (cooldownTimer.current) clearInterval(cooldownTimer.current);
    cooldownTimer.current = setInterval(() => {
      setResendCooldown((s) => {
        if (s <= 1) {
          if (cooldownTimer.current) clearInterval(cooldownTimer.current);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const outcome = await login(email, password);
      if (outcome.status === "otp_required") {
        setOtpToken(outcome.otpToken);
        startCooldown();
      } else if (outcome.status === "mfa_required") {
        setMfaToken(outcome.mfaToken);
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setError((err as Error).message.replace(/^\d+\s*/, "") || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  const onVerifyMfa = async (e: FormEvent) => {
    e.preventDefault();
    if (!mfaToken) return;
    setMfaError(null);
    setMfaVerifying(true);
    try {
      await completeMfaLogin(mfaToken, mfaCode);
      navigate(from, { replace: true });
    } catch (err) {
      setMfaError((err as Error).message.replace(/^\d+\s*/, "") || "Invalid code");
    } finally {
      setMfaVerifying(false);
    }
  };

  const onVerifyOtp = async (e: FormEvent) => {
    e.preventDefault();
    if (!otpToken) return;
    setOtpError(null);
    setVerifying(true);
    try {
      await completeOtpLogin(otpToken, code);
      navigate(from, { replace: true });
    } catch (err) {
      setOtpError((err as Error).message.replace(/^\d+\s*/, "") || "Invalid code");
    } finally {
      setVerifying(false);
    }
  };

  const onResend = async () => {
    if (!otpToken || resendCooldown > 0) return;
    setOtpError(null);
    try {
      await resendOtp(otpToken);
      startCooldown();
    } catch (err) {
      setOtpError((err as Error).message.replace(/^\d+\s*/, "") || "Could not resend code");
    }
  };

  const backToPassword = () => {
    setOtpToken(null);
    setCode("");
    setOtpError(null);
    setMfaToken(null);
    setMfaCode("");
    setMfaError(null);
    if (cooldownTimer.current) clearInterval(cooldownTimer.current);
    setResendCooldown(0);
  };

  if (mfaToken) {
    return (
      <AuthLayout>
        <div className="auth-card glass-card">
          <div className="auth-logo">
            <KeyRound size={22} />
          </div>
          <h1>Two-factor code</h1>
          <p className="auth-subtitle">
            Enter the 6-digit code from your authenticator app, or one of your backup codes.
          </p>

          {mfaError && <div className="auth-error">{mfaError}</div>}

          <form onSubmit={onVerifyMfa}>
            <div className="auth-field">
              <label htmlFor="mfa-code">Authenticator code</label>
              <input
                id="mfa-code"
                type="text"
                autoComplete="one-time-code"
                maxLength={10}
                required
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.trim())}
              />
            </div>
            <button type="submit" className="btn btn-primary auth-submit" disabled={mfaVerifying || mfaCode.length < 6}>
              <LogIn size={16} />
              {mfaVerifying ? "Verifying…" : "Verify"}
            </button>
          </form>

          <div className="auth-footer">
            <button type="button" className="auth-link-btn" onClick={backToPassword}>
              Back
            </button>
          </div>
        </div>
      </AuthLayout>
    );
  }

  if (otpToken) {
    return (
      <AuthLayout>
        <div className="auth-card glass-card">
          <div className="auth-logo">
            <ShieldCheck size={22} />
          </div>
          <h1>Enter your code</h1>
          <p className="auth-subtitle">Enter the 6-digit code sent to your email.</p>

          {otpError && <div className="auth-error">{otpError}</div>}

          <form onSubmit={onVerifyOtp}>
            <div className="auth-field">
              <label htmlFor="otp-code">Verification code</label>
              <input
                id="otp-code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                autoComplete="one-time-code"
                required
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
            </div>
            <button type="submit" className="btn btn-primary auth-submit" disabled={verifying || code.length < 6}>
              <LogIn size={16} />
              {verifying ? "Verifying…" : "Verify"}
            </button>
          </form>

          <div className="auth-footer">
            <button type="button" className="auth-link-btn" onClick={onResend} disabled={resendCooldown > 0}>
              {resendCooldown > 0 ? `Resend code (${resendCooldown}s)` : "Resend code"}
            </button>
            {" · "}
            <button type="button" className="auth-link-btn" onClick={backToPassword}>
              Back
            </button>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <div className="auth-card glass-card">
        <div className="auth-logo">
          <Camera size={22} />
        </div>
        <h1>Welcome back</h1>
        <p className="auth-subtitle">Sign in to your MemoryLens AI vault.</p>

        {resetSuccess && <div className="auth-success">Password reset. Sign in with your new password.</div>}
        {idleLoggedOut && (
          <div className="auth-success">You were logged out after a period of inactivity. Please sign in again.</div>
        )}
        {sessionRevoked && (
          <div className="auth-success">
            You were logged out because this session ended on another device.
          </div>
        )}
        {googleError && (
          <div className="auth-error">{GOOGLE_ERROR_MESSAGES[googleError] ?? "Google sign-in failed."}</div>
        )}
        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={onSubmit}>
          <div className="auth-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="auth-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary auth-submit" disabled={submitting}>
            <LogIn size={16} />
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="auth-divider">
          <span>or</span>
        </div>

        <button
          type="button"
          className="btn auth-google-btn"
          onClick={onGoogleClick}
          disabled={googleConfigured === null}
          title={googleConfigured === false ? "Google sign-in isn't configured in this environment yet" : undefined}
        >
          <GoogleIcon />
          Sign in with Google
        </button>
        {googleConfigured === false && (
          <p className="auth-google-hint">
            Not configured in this environment — add GOOGLE_CLIENT_ID/SECRET to backend/.env to enable it.
          </p>
        )}

        <div className="auth-footer">
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <div className="auth-footer">
          Don't have an account? <Link to="/register">Create one</Link>
        </div>
      </div>
    </AuthLayout>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 3l5.7-5.7C34.6 6.5 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.8 1.1 8 3l5.7-5.7C34.6 6.5 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.5 0 10.5-2.1 14.3-5.6l-6.6-5.6C29.6 34.7 27 35.6 24 35.6c-5.3 0-9.7-3.4-11.3-8.1l-6.6 5.1C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.3 5.7l6.6 5.6c-.5.4 7.1-5.1 7.1-15.3 0-1.3-.1-2.7-.4-3.5z"
      />
    </svg>
  );
}
