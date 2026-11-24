import { motion } from "framer-motion";
import { KeyRound, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import SonarBackdrop from "@/components/ui/SonarBackdrop";
import { mfaVerify, setAccessToken } from "@/lib/api";

type Tab = "totp" | "recovery_code";

export default function MfaChallengePage() {
  const navigate = useNavigate();
  const ticket = sessionStorage.getItem("sv_mfa_ticket");
  const [tab, setTab] = useState<Tab>("totp");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!ticket) {
    return <Navigate to="/login" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await mfaVerify(ticket!, tab, code);
      setAccessToken(res.access_token);
      sessionStorage.removeItem("sv_mfa_ticket");
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
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
        <div className="mb-6 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-tide-500/15 text-tide-300">
            <ShieldCheck size={22} strokeWidth={2.2} />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">Verify it&apos;s you</h1>
            <p className="text-xs text-slate-400">Second-factor authentication required</p>
          </div>
        </div>

        <div className="mb-5 flex gap-1 rounded-lg bg-abyss-800/60 p-1">
          {(
            [
              ["totp", "Authenticator"],
              ["recovery_code", "Backup code"],
            ] as [Tab, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setTab(value);
                setCode("");
                setError(null);
              }}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
                tab === value ? "bg-tide-500 text-abyss-950" : "text-slate-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-300">
              {tab === "totp" ? "6-digit code" : "Recovery code"}
            </span>
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5 focus-within:border-tide-400/60 focus-within:ring-1 focus-within:ring-tide-400/40">
              <KeyRound size={16} className="text-slate-500" />
              <input
                type="text"
                required
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={tab === "totp" ? "123456" : "XXXX-XXXX-XXXX"}
                className="w-full bg-transparent text-sm tracking-widest text-white outline-none placeholder:text-slate-600"
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
            {loading ? "Verifying…" : "Verify"}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
