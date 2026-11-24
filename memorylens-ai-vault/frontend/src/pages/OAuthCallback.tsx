import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Camera } from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import "./Auth.css";

// Landing point for the Google OAuth redirect: the backend hands us the
// access token as a query param (the refresh token already arrived as an
// httpOnly cookie on that same redirect), we adopt it and bounce into the
// app -- this page itself is never meant to be seen for more than a beat.
export function OAuthCallbackPage() {
  const { completeOAuthLogin } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const token = searchParams.get("token");
    if (!token) {
      navigate("/login?google_error=google_failed", { replace: true });
      return;
    }
    completeOAuthLogin(token)
      .then(() => navigate("/library", { replace: true }))
      .catch(() => setError("Could not complete Google sign-in."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="auth-shell">
      <div className="auth-layout" style={{ gridTemplateColumns: "1fr" }}>
        <div className="auth-card-col">
          <div className="auth-card glass-card" style={{ textAlign: "center" }}>
            <div className="auth-logo" style={{ margin: "0 auto 16px" }}>
              <Camera size={22} />
            </div>
            {error ? (
              <>
                <h1>Sign-in failed</h1>
                <p className="auth-subtitle">{error}</p>
              </>
            ) : (
              <>
                <h1>Signing you in…</h1>
                <p className="auth-subtitle">Finishing up with Google.</p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
