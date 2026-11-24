import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MailCheck } from "lucide-react";
import "./VerifyEmailBanner.css";

// Confirms, once, right after registration, that a verification email was
// actually dispatched -- without this the only feedback a new user got was
// the persistent "please verify" banner, with no acknowledgement that
// anything had been sent at all.
export function JustRegisteredToast() {
  const location = useLocation();
  const navigate = useNavigate();
  const [email] = useState<string | null>(() => {
    const state = location.state as { justRegisteredEmail?: string } | null;
    return state?.justRegisteredEmail ?? null;
  });

  useEffect(() => {
    if ((location.state as { justRegisteredEmail?: string } | null)?.justRegisteredEmail) {
      navigate(location.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!email) return null;

  return (
    <div className="verify-banner verify-banner-success">
      <MailCheck size={16} />
      <span>
        Account created — a verification email was sent to <strong>{email}</strong>.
      </span>
    </div>
  );
}
