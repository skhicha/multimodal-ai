import { motion } from "framer-motion";
import { CheckCircle2, Lock, Mail, Waves } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import SonarBackdrop from "@/components/ui/SonarBackdrop";
import { register } from "@/lib/api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const strength = passwordStrength(password);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, password);
      setDone(true);
      setTimeout(() => navigate("/login"), 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
                   bg-abyss-900/70 p-8 shadow-2xl shadow-black/40 backdrop-blur-xl"
      >
        <div className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-tide-500/15 text-tide-300">
            <Waves size={22} strokeWidth={2.2} />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">Create account</h1>
            <p className="text-xs text-slate-400">Join SonaVault as a Viewer</p>
          </div>
        </div>

        {done ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center gap-3 py-6 text-center"
          >
            <CheckCircle2 size={40} className="text-tide-400" />
            <p className="text-sm text-slate-300">
              Account created. Redirecting to sign in&hellip;
            </p>
          </motion.div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-300">Email</span>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
                <Mail size={16} className="text-slate-500" />
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@sanctuary.org"
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
              </div>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-300">Password</span>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
                <Lock size={16} className="text-slate-500" />
                <input
                  type="password"
                  required
                  minLength={12}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 12 characters"
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
              </div>
              {password.length > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex h-1.5 flex-1 gap-1 overflow-hidden rounded-full bg-abyss-700">
                    {[0, 1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className={`flex-1 transition-colors ${
                          i < strength.score ? strength.color : "bg-transparent"
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-[11px] text-slate-500">{strength.label}</span>
                </div>
              )}
            </label>

            {error && (
              <p className="rounded-lg border border-signal-coral/30 bg-signal-coral/10 px-3 py-2 text-sm text-signal-coral">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-tide-500 px-4 py-2.5 text-sm font-semibold text-abyss-950
                         transition hover:bg-tide-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Creating account…" : "Create account"}
            </button>

            <p className="text-center text-xs text-slate-500">
              Already have an account?{" "}
              <Link to="/login" className="text-tide-400 hover:text-tide-300">
                Sign in
              </Link>
            </p>
          </form>
        )}
      </motion.div>
    </div>
  );
}

function passwordStrength(password: string): { score: number; label: string; color: string } {
  if (password.length === 0) return { score: 0, label: "", color: "" };
  let score = 0;
  if (password.length >= 12) score++;
  if (password.length >= 16) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password)) score++;

  const labels = ["Too short", "Weak", "Fair", "Good", "Strong"];
  const colors = ["bg-signal-coral", "bg-signal-coral", "bg-signal-amber", "bg-signal-amber", "bg-tide-500"];
  return { score, label: labels[score], color: colors[score] };
}
