import { motion } from "framer-motion";
import { Copy, KeyRound, Laptop, ShieldCheck, ShieldOff } from "lucide-react";
import { useEffect, useState } from "react";

import AppShell from "@/components/ui/AppShell";
import {
  type SessionOut,
  listSessions,
  regenerateRecoveryCodes,
  revokeSession,
  totpConfirm,
  totpEnroll,
} from "@/lib/api";

type EnrollStep = "idle" | "enrolling" | "confirming";

export default function AccountSecurityPage() {
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [enrollStep, setEnrollStep] = useState<EnrollStep>("idle");
  const [secret, setSecret] = useState<string | null>(null);
  const [provisioningUri, setProvisioningUri] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listSessions().then(setSessions).catch(() => setSessions([]));
  }, []);

  async function startEnroll() {
    setError(null);
    setLoading(true);
    try {
      const res = await totpEnroll();
      setSecret(res.secret);
      setProvisioningUri(res.provisioning_uri);
      setEnrollStep("confirming");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start enrollment");
    } finally {
      setLoading(false);
    }
  }

  async function confirmEnroll(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await totpConfirm(code);
      setRecoveryCodes(res.recovery_codes);
      setEnrollStep("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegenerate() {
    setLoading(true);
    try {
      const res = await regenerateRecoveryCodes();
      setRecoveryCodes(res.recovery_codes);
    } finally {
      setLoading(false);
    }
  }

  async function handleRevoke(sid: string) {
    await revokeSession(sid);
    setSessions((prev) => prev.filter((s) => s.id !== sid));
  }

  return (
    <AppShell>
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Account &amp; security</h1>
        <p className="mt-1 text-sm text-slate-400">Multi-factor authentication, recovery codes, and active sessions.</p>

        <section className="mt-8 rounded-xl border border-white/10 bg-abyss-900/60 p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-tide-500/15 text-tide-300">
                <ShieldCheck size={20} />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-white">Authenticator app (TOTP)</h2>
                <p className="text-xs text-slate-500">Time-based one-time codes from an authenticator app</p>
              </div>
            </div>
            {enrollStep === "idle" && !recoveryCodes && (
              <button
                onClick={startEnroll}
                disabled={loading}
                className="rounded-lg bg-tide-500 px-4 py-2 text-sm font-semibold text-abyss-950 transition hover:bg-tide-400 disabled:opacity-60"
              >
                Enable
              </button>
            )}
          </div>

          {enrollStep === "confirming" && secret && (
            <form onSubmit={confirmEnroll} className="mt-5 space-y-3 border-t border-white/10 pt-5">
              <p className="text-xs text-slate-400">
                Scan this secret into your authenticator app, or enter it manually:
              </p>
              <code className="block w-fit rounded-md bg-abyss-800 px-3 py-2 text-sm tracking-widest text-tide-300">
                {secret}
              </code>
              {provisioningUri && (
                <p className="truncate text-[11px] text-slate-600" title={provisioningUri}>
                  {provisioningUri}
                </p>
              )}
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-abyss-800/60 px-3 py-2.5">
                <KeyRound size={16} className="text-slate-500" />
                <input
                  type="text"
                  required
                  autoFocus
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="6-digit code"
                  className="w-full bg-transparent text-sm tracking-widest text-white outline-none placeholder:text-slate-600"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="rounded-lg bg-tide-500 px-4 py-2 text-sm font-semibold text-abyss-950 transition hover:bg-tide-400 disabled:opacity-60"
              >
                Confirm &amp; enable
              </button>
            </form>
          )}

          {error && <p className="mt-3 text-sm text-signal-coral">{error}</p>}

          {recoveryCodes && (
            <div className="mt-5 border-t border-white/10 pt-5">
              <p className="mb-2 text-xs font-medium text-signal-amber">
                Save these recovery codes — each works once and they will not be shown again.
              </p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {recoveryCodes.map((rc) => (
                  <code
                    key={rc}
                    className="rounded-md bg-abyss-800 px-2 py-1.5 text-center text-xs tracking-wide text-slate-200"
                  >
                    {rc}
                  </code>
                ))}
              </div>
              <button
                onClick={() => navigator.clipboard.writeText(recoveryCodes.join("\n"))}
                className="mt-3 flex items-center gap-1.5 text-xs text-slate-400 hover:text-white"
              >
                <Copy size={12} /> Copy all
              </button>
            </div>
          )}
        </section>

        <section className="mt-6 rounded-xl border border-white/10 bg-abyss-900/60 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-tide-500/15 text-tide-300">
                <ShieldOff size={20} />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-white">Recovery codes</h2>
                <p className="text-xs text-slate-500">Regenerate if you&apos;ve used most of your codes</p>
              </div>
            </div>
            <button
              onClick={handleRegenerate}
              disabled={loading}
              className="rounded-lg border border-white/10 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-tide-400/40 hover:text-white disabled:opacity-60"
            >
              Regenerate
            </button>
          </div>
        </section>

        <section className="mt-6 rounded-xl border border-white/10 bg-abyss-900/60 p-6">
          <h2 className="mb-4 text-sm font-semibold text-white">Active sessions</h2>
          <ul className="space-y-2">
            {sessions.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between rounded-lg border border-white/5 bg-abyss-800/40 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <Laptop size={16} className="text-slate-500" />
                  <div>
                    <p className="text-sm text-slate-200">
                      {s.user_agent ?? "Unknown device"}
                      {s.created_current && (
                        <span className="ml-2 rounded-full bg-tide-500/15 px-2 py-0.5 text-[10px] text-tide-300">
                          This device
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500">{s.ip_addr ?? "Unknown IP"} · {s.amr.join(", ")}</p>
                  </div>
                </div>
                {!s.created_current && (
                  <button
                    onClick={() => handleRevoke(s.id)}
                    className="text-xs font-medium text-signal-coral hover:underline"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
            {sessions.length === 0 && <p className="text-sm text-slate-600">No active sessions found.</p>}
          </ul>
        </section>
      </motion.div>
    </AppShell>
  );
}
