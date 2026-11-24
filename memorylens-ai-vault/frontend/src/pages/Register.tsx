import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Camera, UserPlus } from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import "./Auth.css";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName);
      navigate("/library", { replace: true, state: { justRegisteredEmail: email } });
    } catch (err) {
      setError((err as Error).message.replace(/^\d+\s*/, "") || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card glass-card">
        <div className="auth-logo">
          <Camera size={22} />
        </div>
        <h1>Create your vault</h1>
        <p className="auth-subtitle">Set up a personal account for MemoryLens AI.</p>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={onSubmit}>
          <div className="auth-field">
            <label htmlFor="display_name">Display name</label>
            <input
              id="display_name"
              type="text"
              autoComplete="name"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>
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
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
              At least 8 characters, with a letter and a number.
            </div>
          </div>
          <button type="submit" className="btn btn-primary auth-submit" disabled={submitting}>
            <UserPlus size={16} />
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
