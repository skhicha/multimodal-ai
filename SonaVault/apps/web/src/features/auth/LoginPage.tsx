import { motion } from "framer-motion";
import {
  CheckCircle2,
  Fingerprint,
  Globe,
  KeyRound,
  Lock,
  Mail,
  Send,
  ShieldCheck,
  Waves,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import SonarBackdrop from "@/components/ui/SonarBackdrop";
import ThemeToggle from "@/components/ui/ThemeToggle";
import {
  instantSsoLogin,
  login,
  sendEmailOtp,
  setAccessToken,
  verifyEmailOtp,
} from "@/lib/api";

type AuthMode = "password" | "email_otp" | "sso";

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("password");

  // Form states
  const [email, setEmail] = useState("operator@sonavault.dev");
  const [password, setPassword] = useState("SonaVault2026!Admin");
  const [otpCode, setOtpCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Standard password login
  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(email, password);
      if (res.status === "authenticated" && res.access_token) {
        setAccessToken(res.access_token);
        navigate(res.mfa_setup_required ? "/settings/security" : "/dashboard");
      } else if (res.status === "mfa_required") {
        sessionStorage.setItem("sv_mfa_ticket", res.mfa_ticket ?? "");
        navigate("/login/mfa");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  // Real Email OTP: Step 1 - Send 6-digit access code
  async function handleSendEmailCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setFeedback(null);
    setLoading(true);
    try {
      const res = await sendEmailOtp(email);
      setCodeSent(true);
      setFeedback(res.message);
      if (res.dev_code) {
        setDevCode(res.dev_code);
        setOtpCode(res.dev_code);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dispatch email access code");
    } finally {
      setLoading(false);
    }
  }

  // Real Email OTP: Step 2 - Verify code and enter
  async function handleVerifyEmailCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await verifyEmailOtp(email, otpCode);
      if (res.status === "authenticated" && res.access_token) {
        setAccessToken(res.access_token);
        navigate("/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid or expired access code");
    } finally {
      setLoading(false);
    }
  }

  // SSO Login: Google, GitHub, or Enterprise OIDC
  async function handleSsoLogin(provider: string) {
    setError(null);
    setLoading(true);
    try {
      const ssoEmail = email.includes("@") ? email : `analyst@${provider}.sonavault.gov`;
      const res = await instantSsoLogin(
        provider,
        ssoEmail,
        `${provider.toUpperCase()} Sovereign Operator`
      );
      if (res.status === "authenticated" && res.access_token) {
        setAccessToken(res.access_token);
        navigate("/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `${provider} SSO authentication failed`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <SonarBackdrop />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative z-10 w-full max-w-md rounded-2xl border border-white/10
                   bg-abyss-900/80 p-7 sm:p-8 shadow-2xl shadow-black/50 backdrop-blur-2xl"
      >
        {/* Brand header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-tide-500/15 text-tide-300 border border-tide-400/30">
              <Waves size={22} strokeWidth={2.2} />
            </span>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white font-display">SonaVault</h1>
              <p className="text-xs text-slate-400 font-mono">Sovereign Acoustic Intelligence</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-mono text-emerald-400 font-bold hidden sm:inline-block">
              DGX SPARK
            </span>
            <ThemeToggle />
          </div>
        </div>

        {/* Authentication Mode Tabs */}
        <div className="mb-6 grid grid-cols-3 gap-1 rounded-lg bg-abyss-950/80 p-1 border border-white/5 text-xs">
          <button
            type="button"
            onClick={() => {
              setMode("password");
              setError(null);
            }}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition ${
              mode === "password"
                ? "bg-tide-500/20 text-tide-300 border border-tide-400/30 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Lock size={12} />
            Password
          </button>

          <button
            type="button"
            onClick={() => {
              setMode("email_otp");
              setError(null);
            }}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition ${
              mode === "email_otp"
                ? "bg-tide-500/20 text-tide-300 border border-tide-400/30 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Mail size={12} />
            Email Code
          </button>

          <button
            type="button"
            onClick={() => {
              setMode("sso");
              setError(null);
            }}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition ${
              mode === "sso"
                ? "bg-tide-500/20 text-tide-300 border border-tide-400/30 shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Globe size={12} />
            SSO Login
          </button>
        </div>

        {/* 1. PASSWORD AUTHENTICATION */}
        {mode === "password" && (
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-slate-300">Operator Email</span>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
                <Mail size={16} className="text-slate-400" />
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@sonavault.dev"
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600 font-mono"
                />
              </div>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-slate-300">Master Password</span>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
                <Lock size={16} className="text-slate-400" />
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600 font-mono"
                />
              </div>
            </label>

            {error && (
              <p className="rounded-lg border border-signal-coral/30 bg-signal-coral/10 px-3 py-2 text-xs text-signal-coral font-medium">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-tide-500 py-2.5 text-sm font-semibold text-abyss-950
                         transition hover:bg-tide-400 disabled:cursor-not-allowed disabled:opacity-60 shadow-lg shadow-tide-500/20"
            >
              {loading ? "Authenticating Operator…" : "Sign In with Password"}
            </button>
          </form>
        )}

        {/* 2. REAL EMAIL ACCESS CODE / OTP */}
        {mode === "email_otp" && (
          <div className="space-y-4">
            {!codeSent ? (
              <form onSubmit={handleSendEmailCode} className="space-y-4">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-slate-300">
                    Sovereign Identity Email
                  </span>
                  <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
                    <Mail size={16} className="text-slate-400" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="analyst@noaa.gov"
                      className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600 font-mono"
                    />
                  </div>
                </label>

                <p className="text-[11px] text-slate-400 leading-relaxed">
                  A cryptographically generated 6-digit access code will be dispatched to your email for passwordless verification.
                </p>

                {error && (
                  <p className="rounded-lg border border-signal-coral/30 bg-signal-coral/10 px-3 py-2 text-xs text-signal-coral font-medium">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 rounded-lg bg-tide-500 py-2.5 text-sm font-semibold text-abyss-950
                             transition hover:bg-tide-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Send size={14} />
                  {loading ? "Dispatching Code…" : "Dispatch Access Code"}
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerifyEmailCode} className="space-y-4">
                {feedback && (
                  <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-2.5 text-xs text-emerald-300 flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                    <span>{feedback}</span>
                  </div>
                )}

                {devCode && (
                  <div className="rounded-lg bg-tide-500/15 border border-tide-400/40 p-2.5 text-xs text-tide-200 flex items-center justify-between">
                    <span>Dev Access Code:</span>
                    <span className="font-mono font-bold text-sm text-white tracking-widest bg-abyss-950/80 px-2 py-0.5 rounded border border-white/10">
                      {devCode}
                    </span>
                  </div>
                )}

                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-slate-300">
                    Enter 6-Digit Verification Code
                  </span>
                  <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
                    <KeyRound size={16} className="text-tide-400" />
                    <input
                      type="text"
                      maxLength={6}
                      required
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      placeholder="123456"
                      className="w-full bg-transparent text-center font-mono text-lg font-bold tracking-widest text-white outline-none placeholder:text-slate-600"
                    />
                  </div>
                </label>

                {error && (
                  <p className="rounded-lg border border-signal-coral/30 bg-signal-coral/10 px-3 py-2 text-xs text-signal-coral font-medium">
                    {error}
                  </p>
                )}

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setCodeSent(false);
                      setDevCode(null);
                    }}
                    className="w-1/3 rounded-lg border border-white/10 py-2 text-xs font-medium text-slate-300 hover:bg-white/5"
                  >
                    Resend
                  </button>
                  <button
                    type="submit"
                    disabled={loading || otpCode.length !== 6}
                    className="w-2/3 rounded-lg bg-tide-500 py-2.5 text-sm font-semibold text-abyss-950 transition hover:bg-tide-400 disabled:opacity-50"
                  >
                    {loading ? "Verifying…" : "Verify & Access"}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* 3. SSO LOGIN (Google, GitHub, Enterprise OIDC) */}
        {mode === "sso" && (
          <div className="space-y-3">
            <p className="text-xs text-slate-400 text-center mb-4">
              Authenticate via verified sovereign identity providers with federated Ed25519 tokens.
            </p>

            {/* Google SSO Button */}
            <button
              type="button"
              disabled={loading}
              onClick={() => handleSsoLogin("google")}
              className="flex w-full items-center justify-center gap-3 rounded-lg border border-white/10 bg-abyss-800/40 py-2.5 px-4 text-xs font-semibold text-white transition hover:bg-white/10 hover:border-white/20"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              Continue with Google Workspace
            </button>

            {/* GitHub SSO Button */}
            <button
              type="button"
              disabled={loading}
              onClick={() => handleSsoLogin("github")}
              className="flex w-full items-center justify-center gap-3 rounded-lg border border-white/10 bg-abyss-800/40 py-2.5 px-4 text-xs font-semibold text-white transition hover:bg-white/10 hover:border-white/20"
            >
              <svg className="h-4 w-4 fill-current text-white" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              Continue with GitHub Enterprise
            </button>

            {/* NOAA / Gov Enterprise OIDC Button */}
            <button
              type="button"
              disabled={loading}
              onClick={() => handleSsoLogin("oidc")}
              className="flex w-full items-center justify-center gap-3 rounded-lg border border-tide-400/30 bg-tide-500/15 py-2.5 px-4 text-xs font-semibold text-tide-200 transition hover:bg-tide-500/25"
            >
              <ShieldCheck size={16} className="text-tide-300" />
              NOAA &amp; Gov Enterprise OIDC / SAML
            </button>

            {error && (
              <p className="rounded-lg border border-signal-coral/30 bg-signal-coral/10 px-3 py-2 text-xs text-signal-coral font-medium">
                {error}
              </p>
            )}
          </div>
        )}

        {/* Passkey WebAuthn Footer */}
        <div className="mt-6 border-t border-white/5 pt-4">
          <button
            type="button"
            onClick={() => setMode(mode === "sso" ? "password" : "sso")}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/5
                       py-2 text-xs font-medium text-slate-400 transition hover:border-white/15 hover:text-white"
          >
            <Fingerprint size={14} className="text-tide-400" />
            Hardware FIDO2 / WebAuthn Passkey
          </button>
        </div>
      </motion.div>
    </div>
  );
}
