import { useState } from "react";
import { MailWarning, X } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import "./VerifyEmailBanner.css";

const DISMISS_KEY = "memorylens_verify_banner_dismissed";

export function VerifyEmailBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  if (!user || user.email_verified || dismissed) return null;

  const dismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // ignore - non-essential
    }
  };

  const onResend = async () => {
    setSending(true);
    try {
      await api.resendVerification();
      setSent(true);
    } catch {
      // keep banner visible, user can retry
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="verify-banner">
      <MailWarning size={16} />
      <span>
        {sent
          ? "Verification email sent — check your inbox."
          : "Please verify your email address."}
      </span>
      {!sent && (
        <button className="verify-banner-action" onClick={onResend} disabled={sending}>
          {sending ? "Sending…" : "Resend verification email"}
        </button>
      )}
      <button className="verify-banner-close" onClick={dismiss} aria-label="Dismiss">
        <X size={14} />
      </button>
    </div>
  );
}
