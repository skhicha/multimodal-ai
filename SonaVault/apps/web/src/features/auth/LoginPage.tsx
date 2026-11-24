import { motion } from "framer-motion";
import { Fingerprint, Lock, Mail, Waves } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import SonarBackdrop from "@/components/ui/SonarBackdrop";
import { login, setAccessToken } from "@/lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
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
            <h1 className="text-xl font-semibold tracking-tight text-white">SonaVault</h1>
            <p className="text-xs text-slate-400">Acoustic Intelligence Platform</p>
          </div>
        </div>

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
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
              />
            </div>
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
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/10
                       px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-tide-400/40 hover:text-white"
          >
            <Fingerprint size={16} />
            Sign in with Passkey
          </button>
        </form>
      </motion.div>
    </div>
  );
}
