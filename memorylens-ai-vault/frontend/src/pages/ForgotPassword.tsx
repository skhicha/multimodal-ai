import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound, Mail } from "lucide-react";
import { api } from "../lib/api";
import "./Auth.css";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onRequestCode = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.forgotPassword(email);
      setInfo("If that email exists, we've sent a password reset code.");
      setStep("reset");
    } catch (err) {
      setError((err as Error).message.replace(/^\d+\s*/, "") || "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  const onReset = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.resetPassword(email, code, newPassword);
      navigate("/login", { replace: true, state: { resetSuccess: true } });
    } catch (err) {
      setError((err as Error).message.replace(/^\d+\s*/, "") || "Could not reset password");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card glass-card">
        <div className="auth-logo">
          {step === "email" ? <Mail size={22} /> : <KeyRound size={22} />}
        </div>
        <h1>{step === "email" ? "Forgot password" : "Reset password"}</h1>
        <p className="auth-subtitle">
          {step === "email"
            ? "Enter your account email and we'll send a reset code."
            : "Enter the code we sent you and choose a new password."}
        </p>

        {info && <div className="auth-success">{info}</div>}
        {error && <div className="auth-error">{error}</div>}

        {step === "email" ? (
          <form onSubmit={onRequestCode}>
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
            <button type="submit" className="btn btn-primary auth-submit" disabled={submitting}>
              {submitting ? "Sending…" : "Send reset code"}
            </button>
          </form>
        ) : (
          <form onSubmit={onReset}>
            <div className="auth-field">
              <label htmlFor="code">Reset code</label>
              <input
                id="code"
                type="text"
                inputMode="numeric"
                maxLength={6}
                required
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
            </div>
            <div className="auth-field">
              <label htmlFor="new_password">New password</label>
              <input
                id="new_password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
                At least 8 characters, with a letter and a number.
              </div>
            </div>
            <button type="submit" className="btn btn-primary auth-submit" disabled={submitting}>
              {submitting ? "Resetting…" : "Reset password"}
            </button>
          </form>
        )}

        <div className="auth-footer">
          {step === "reset" && (
            <button type="button" className="auth-link-btn" onClick={() => setStep("email")}>
              Use a different email
            </button>
          )}
        </div>
        <div className="auth-footer">
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
