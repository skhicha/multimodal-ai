import { useEffect, useState } from "react";
import { RefreshCw, ShieldCheck, Sparkles, KeyRound } from "lucide-react";
import { api, type SessionInfo, type SettingsInfo } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";

type MfaStep = "idle" | "setup" | "backup-codes";

// sessions.created_at comes from SQLite's datetime('now') -- "YYYY-MM-DD
// HH:MM:SS" in UTC with no timezone suffix, so it must be parsed as UTC
// explicitly (new Date("...") with a space instead of "T" and no "Z"
// would otherwise be parsed as local time by most browsers).
function formatSessionDate(createdAt: string): string {
  const iso = createdAt.includes("T") ? createdAt : `${createdAt.replace(" ", "T")}Z`;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return createdAt;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function SettingsPage() {
  const { user, refreshUser, logoutOtherDevices } = useAuth();
  const [settings, setSettings] = useState<SettingsInfo | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null);
  const [logoutOthersBusy, setLogoutOthersBusy] = useState(false);
  const [logoutOthersMsg, setLogoutOthersMsg] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState<string | null>(null);
  const [otpSaving, setOtpSaving] = useState(false);
  const [otpMsg, setOtpMsg] = useState<string | null>(null);
  const [verifySending, setVerifySending] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [verifying, setVerifying] = useState(false);

  // --- Authenticator-app MFA (TOTP) setup/disable state ---
  const [mfaStep, setMfaStep] = useState<MfaStep>("idle");
  const [mfaQr, setMfaQr] = useState<string | null>(null);
  const [mfaSecret, setMfaSecret] = useState<string | null>(null);
  const [mfaConfirmCode, setMfaConfirmCode] = useState("");
  const [mfaBusy, setMfaBusy] = useState(false);
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [disablePassword, setDisablePassword] = useState("");
  const [showDisableForm, setShowDisableForm] = useState(false);

  useEffect(() => {
    api.settings().then(setSettings);
    api.mySessions().then(setSessions).catch(() => setSessions([]));
  }, []);

  const handleLogoutOthers = async () => {
    setLogoutOthersBusy(true);
    setLogoutOthersMsg(null);
    try {
      const count = await logoutOtherDevices();
      setLogoutOthersMsg(count > 0 ? `Signed out ${count} other device${count === 1 ? "" : "s"}.` : "No other devices were signed in.");
      api.mySessions().then(setSessions).catch(() => {});
    } catch {
      setLogoutOthersMsg("Something went wrong — please try again.");
    } finally {
      setLogoutOthersBusy(false);
    }
  };

  const toggleOtp = async () => {
    if (!user) return;
    setOtpSaving(true);
    setOtpMsg(null);
    try {
      await api.updateMe(!user.otp_enabled);
      await refreshUser();
    } catch (err) {
      setOtpMsg((err as Error).message.replace(/^\d+\s*/, "") || "Could not update setting");
    } finally {
      setOtpSaving(false);
    }
  };

  const sendVerification = async () => {
    setVerifySending(true);
    setVerifyMsg(null);
    try {
      await api.resendVerification();
      setVerifyMsg("Verification email sent — check your inbox.");
    } catch (err) {
      setVerifyMsg((err as Error).message.replace(/^\d+\s*/, "") || "Could not send verification email");
    } finally {
      setVerifySending(false);
    }
  };

  const submitVerifyCode = async () => {
    setVerifying(true);
    setVerifyMsg(null);
    try {
      await api.verifyEmail(verifyCode);
      setVerifyCode("");
      await refreshUser();
      setVerifyMsg("Email verified.");
    } catch (err) {
      setVerifyMsg((err as Error).message.replace(/^\d+\s*/, "") || "Invalid or expired code");
    } finally {
      setVerifying(false);
    }
  };

  const startMfaSetup = async () => {
    setMfaError(null);
    setMfaBusy(true);
    try {
      const res = await api.mfaSetup();
      setMfaQr(res.qr_code);
      setMfaSecret(res.secret);
      setMfaStep("setup");
    } catch (err) {
      setMfaError((err as Error).message.replace(/^\d+\s*/, "") || "Could not start MFA setup");
    } finally {
      setMfaBusy(false);
    }
  };

  const confirmMfaEnable = async () => {
    setMfaError(null);
    setMfaBusy(true);
    try {
      const res = await api.mfaEnable(mfaConfirmCode);
      setBackupCodes(res.backup_codes);
      setMfaStep("backup-codes");
      setMfaConfirmCode("");
      await refreshUser();
    } catch (err) {
      setMfaError((err as Error).message.replace(/^\d+\s*/, "") || "Invalid code — check your authenticator app and try again");
    } finally {
      setMfaBusy(false);
    }
  };

  const finishMfaSetup = () => {
    setMfaStep("idle");
    setMfaQr(null);
    setMfaSecret(null);
    setBackupCodes([]);
  };

  const disableMfa = async () => {
    setMfaError(null);
    setMfaBusy(true);
    try {
      await api.mfaDisable(disablePassword);
      setDisablePassword("");
      setShowDisableForm(false);
      await refreshUser();
    } catch (err) {
      setMfaError((err as Error).message.replace(/^\d+\s*/, "") || "Incorrect password");
    } finally {
      setMfaBusy(false);
    }
  };

  const runReindex = async () => {
    setReindexing(true);
    setReindexMsg(null);
    try {
      const res = await api.reindex();
      setReindexMsg(`Re-indexed ${res.reindexed} item(s) for search.`);
    } catch (err) {
      setReindexMsg(`Re-index failed: ${(err as Error).message}`);
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Make it yours</span>
        <h1>Settings<span className="heading-period">.</span></h1>
        <p>Theme, LLM provider status, and index maintenance.</p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr", maxWidth: 560, gap: 20 }}>
        <div className="glass-card" style={{ padding: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase" }}>
            Appearance
          </h3>
          <div style={{ maxWidth: 220 }}>
            <ThemeToggle />
          </div>
        </div>

        <div className="glass-card" style={{ padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase" }}>
              <Sparkles size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
              Ask AI provider
            </h3>
            {settings?.llm_provider === "mock" && (
              <span className="tag-chip" style={{ flexShrink: 0 }}>
                offline mode
              </span>
            )}
          </div>
          {settings ? (
            <div style={{ fontSize: 14, lineHeight: 1.8 }}>
              <p style={{ margin: 0 }}>
                {settings.llm_provider === "mock"
                  ? "Running fully offline — answers are generated from your own data, no cloud calls."
                  : "Connected to a live AI model for richer answers."}
              </p>
              {settings.llm_provider === "anthropic" && !settings.anthropic_key_configured && (
                <div style={{ color: "var(--danger)", fontSize: 13, marginTop: 4 }}>
                  API key missing — falling back to offline mode until it's set.
                </div>
              )}
              <details style={{ marginTop: 10 }}>
                <summary style={{ cursor: "pointer", fontSize: 12.5, color: "var(--text-muted)" }}>
                  Developer details
                </summary>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 8 }}>
                  <div>
                    Provider: <code>{settings.llm_provider}</code>
                  </div>
                  <div>
                    Whisper ASR model: <code>{settings.whisper_model}</code>
                  </div>
                  <p style={{ marginTop: 8 }}>
                    Switch providers by setting <code>LLM_PROVIDER=anthropic</code> and{" "}
                    <code>ANTHROPIC_API_KEY=...</code> in <code>backend/.env</code>, then restart the backend.
                  </p>
                </div>
              </details>
            </div>
          ) : (
            "Loading…"
          )}
        </div>

        <div className="glass-card" style={{ padding: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase" }}>
            <ShieldCheck size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
            Security
          </h3>
          <div style={{ fontSize: 14, lineHeight: 1.8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div>
                <div>Email verification</div>
                <div style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                  {user?.email_verified ? (
                    <span style={{ color: "var(--success)" }}>Verified</span>
                  ) : (
                    <span style={{ color: "var(--danger)" }}>Not verified</span>
                  )}
                </div>
              </div>
              {!user?.email_verified && (
                <button className="btn" onClick={sendVerification} disabled={verifySending}>
                  {verifySending ? "Sending…" : "Resend verification email"}
                </button>
              )}
            </div>
            {!user?.email_verified && (
              <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                <input
                  type="text"
                  placeholder="Enter verification code"
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value.trim())}
                  style={{ flex: 1, minWidth: 0 }}
                />
                <button className="btn btn-primary" onClick={submitVerifyCode} disabled={verifying || verifyCode.length < 4}>
                  {verifying ? "Verifying…" : "Verify"}
                </button>
              </div>
            )}
            {verifyMsg && <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 10 }}>{verifyMsg}</div>}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div>Require a login code (OTP)</div>
                <div style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                  Adds a one-time emailed code when signing in.
                </div>
              </div>
              <button className="btn" onClick={toggleOtp} disabled={otpSaving}>
                {otpSaving ? "Saving…" : user?.otp_enabled ? "Disable" : "Enable"}
              </button>
            </div>
            {otpMsg && <div style={{ fontSize: 13, color: "var(--danger)", marginTop: 10 }}>{otpMsg}</div>}
          </div>
        </div>

        <div className="glass-card" style={{ padding: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase" }}>
            <ShieldCheck size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
            Sessions
          </h3>
          <div style={{ fontSize: 14, lineHeight: 1.8 }}>
            {sessions === null ? (
              <p style={{ margin: "0 0 10px", color: "var(--text-muted)", fontSize: 13 }}>Loading…</p>
            ) : (
              <ul style={{ listStyle: "none", margin: "0 0 12px", padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                {sessions.map((s) => (
                  <li
                    key={s.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "baseline",
                      fontSize: 13,
                      gap: 10,
                    }}
                  >
                    <span>
                      {s.device_label || "Unknown device"}
                      {s.is_current && <span style={{ color: "var(--accent)", fontWeight: 600 }}> (this device)</span>}
                    </span>
                    <span style={{ color: "var(--text-muted)", fontSize: 12, whiteSpace: "nowrap" }}>
                      signed in {formatSessionDate(s.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <button className="btn" onClick={handleLogoutOthers} disabled={logoutOthersBusy || !sessions || sessions.length <= 1}>
              {logoutOthersBusy ? "Signing out other devices…" : "Log out all other devices"}
            </button>
            {logoutOthersMsg && (
              <div style={{ fontSize: 13, color: "var(--success)", marginTop: 10 }}>{logoutOthersMsg}</div>
            )}
          </div>
        </div>

        <div className="glass-card" style={{ padding: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase" }}>
            <KeyRound size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
            Two-factor authentication (authenticator app)
          </h3>

          {mfaStep === "idle" && (
            <div style={{ fontSize: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div>
                    Status:{" "}
                    {user?.mfa_enabled ? (
                      <span style={{ color: "var(--success)" }}>Enabled</span>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>Disabled</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 4 }}>
                    Scan a QR code with Google Authenticator, Authy, or 1Password — the real, offline-capable kind
                    of MFA, separate from the email OTP above.
                  </div>
                </div>
                {user?.mfa_enabled ? (
                  <button className="btn" onClick={() => setShowDisableForm((v) => !v)}>
                    Disable
                  </button>
                ) : (
                  <button className="btn btn-primary" onClick={startMfaSetup} disabled={mfaBusy}>
                    {mfaBusy ? "Starting…" : "Set up"}
                  </button>
                )}
              </div>

              {showDisableForm && (
                <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
                  <input
                    type="password"
                    placeholder="Confirm your password"
                    value={disablePassword}
                    onChange={(e) => setDisablePassword(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="btn" onClick={disableMfa} disabled={mfaBusy || !disablePassword}>
                    {mfaBusy ? "Disabling…" : "Confirm disable"}
                  </button>
                </div>
              )}
              {mfaError && <div style={{ fontSize: 13, color: "var(--danger)", marginTop: 10 }}>{mfaError}</div>}
            </div>
          )}

          {mfaStep === "setup" && mfaQr && (
            <div style={{ fontSize: 14 }}>
              <p style={{ marginTop: 0, color: "var(--text-muted)", fontSize: 13 }}>
                Scan this QR code with your authenticator app, then enter the 6-digit code it shows to confirm.
              </p>
              <img
                src={mfaQr}
                alt="MFA setup QR code"
                style={{ width: 180, height: 180, borderRadius: 8, background: "#fff", padding: 8 }}
              />
              <p style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                Can't scan it? Enter this key manually: <code style={{ userSelect: "all" }}>{mfaSecret}</code>
              </p>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <input
                  type="text"
                  placeholder="6-digit code"
                  value={mfaConfirmCode}
                  onChange={(e) => setMfaConfirmCode(e.target.value.replace(/\D/g, ""))}
                  maxLength={6}
                  style={{ flex: 1 }}
                />
                <button className="btn btn-primary" onClick={confirmMfaEnable} disabled={mfaBusy || mfaConfirmCode.length < 6}>
                  {mfaBusy ? "Confirming…" : "Confirm"}
                </button>
                <button className="btn" onClick={finishMfaSetup}>
                  Cancel
                </button>
              </div>
              {mfaError && <div style={{ fontSize: 13, color: "var(--danger)", marginTop: 10 }}>{mfaError}</div>}
            </div>
          )}

          {mfaStep === "backup-codes" && (
            <div style={{ fontSize: 14 }}>
              <p style={{ marginTop: 0, color: "var(--success)", fontWeight: 600 }}>
                Two-factor authentication is now enabled.
              </p>
              <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Save these one-time backup codes somewhere safe — each one can be used instead of your
                authenticator app if you lose access to it. They're shown only once.
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 8,
                  fontFamily: "monospace",
                  fontSize: 14,
                  background: "var(--surface)",
                  padding: 14,
                  borderRadius: 8,
                }}
              >
                {backupCodes.map((c) => (
                  <div key={c}>{c}</div>
                ))}
              </div>
              <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={finishMfaSetup}>
                Done — I've saved these
              </button>
            </div>
          )}
        </div>

        <div className="glass-card" style={{ padding: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase" }}>
            Search index
          </h3>
          <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
            Rebuilds the full-text search index from current filenames, tags, and transcripts. Useful after
            bulk changes or if search results look stale.
          </p>
          <button className="btn btn-primary" onClick={runReindex} disabled={reindexing}>
            <RefreshCw size={16} className={reindexing ? "spin" : ""} />
            {reindexing ? "Re-indexing…" : "Re-index now"}
          </button>
          {reindexMsg && <div style={{ marginTop: 10, fontSize: 13, color: "var(--text-muted)" }}>{reindexMsg}</div>}
        </div>
      </div>
    </div>
  );
}
