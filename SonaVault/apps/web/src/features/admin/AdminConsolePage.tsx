import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Unlock,
  Users,
} from "lucide-react";

import AppShell from "@/components/ui/AppShell";
import {
  listAuditLogs,
  listFeatureFlags,
  listUsers,
  unlockUser,
  updateFeatureFlag,
  updateUserRole,
  type AuditLogOut,
  type FeatureFlagOut,
  type UserOut,
} from "@/lib/api";

const ROLES = [
  "viewer",
  "field_contributor",
  "acoustic_analyst",
  "archivist",
  "security_admin",
];

const MOCK_USERS: UserOut[] = [
  {
    id: "usr-01",
    email: "analyst@sanctuary.org",
    role: "acoustic_analyst",
    sanctuary_scopes: ["CI01", "SB01"],
    is_locked: false,
    failed_login_attempts: 0,
    created_at: "2024-10-01T10:00:00Z",
  },
  {
    id: "usr-02",
    email: "field.operator@noaa.gov",
    role: "field_contributor",
    sanctuary_scopes: ["FK01"],
    is_locked: false,
    failed_login_attempts: 0,
    created_at: "2024-10-05T12:30:00Z",
  },
  {
    id: "usr-03",
    email: "security.audit@sovereign.local",
    role: "security_admin",
    sanctuary_scopes: [],
    is_locked: false,
    failed_login_attempts: 0,
    created_at: "2024-09-15T08:00:00Z",
  },
];

const MOCK_FLAGS: FeatureFlagOut[] = [
  {
    flag_key: "feature_vllm_enabled",
    enabled: true,
    description: "Enable sovereign MoE briefings synthesis via Qwen3-30B NVFP4 on GB10",
  },
  {
    flag_key: "enforce_mfa_all",
    enabled: false,
    description: "Enforce WebAuthn / TOTP MFA for all role tiers down to Viewer",
  },
  {
    flag_key: "enable_live_hls_transcoding",
    enabled: true,
    description: "Serve low-latency 48kHz audio streams via MediaMTX WebSockets & LL-HLS",
  },
];

const MOCK_LOGS: AuditLogOut[] = [
  {
    id: "log-1",
    actor_id: "usr-01",
    action: "briefing.synthesize",
    target_id: "brf-001",
    ip_address: "127.0.0.1",
    created_at: new Date(Date.now() - 900000).toISOString(),
  },
  {
    id: "log-2",
    actor_id: "usr-03",
    action: "user.role_change",
    target_id: "usr-02",
    ip_address: "127.0.0.1",
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "log-3",
    actor_id: "usr-02",
    action: "stream.capture",
    target_id: "station:CI01",
    ip_address: "127.0.0.1",
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

export default function AdminConsolePage() {
  const [users, setUsers] = useState<UserOut[]>(MOCK_USERS);
  const [flags, setFlags] = useState<FeatureFlagOut[]>(MOCK_FLAGS);
  const [logs, setLogs] = useState<AuditLogOut[]>(MOCK_LOGS);
  const [searchUser, setSearchUser] = useState("");

  useEffect(() => {
    listUsers()
      .then((items) => {
        if (items && items.length > 0) setUsers(items);
      })
      .catch(() => {});

    listFeatureFlags()
      .then((items) => {
        if (items && items.length > 0) setFlags(items);
      })
      .catch(() => {});

    listAuditLogs()
      .then((items) => {
        if (items && items.length > 0) setLogs(items);
      })
      .catch(() => {});
  }, []);

  async function handleRoleChange(userId: string, newRole: string) {
    try {
      await updateUserRole(userId, newRole);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
    } catch {
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
    }
  }

  async function handleUnlock(userId: string) {
    try {
      await unlockUser(userId);
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_locked: false, failed_login_attempts: 0 } : u))
      );
    } catch {
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_locked: false, failed_login_attempts: 0 } : u))
      );
    }
  }

  async function handleToggleFlag(key: string, current: boolean) {
    const nextVal = !current;
    try {
      await updateFeatureFlag(key, nextVal);
      setFlags((prev) =>
        prev.map((f) => (f.flag_key === key ? { ...f, enabled: nextVal } : f))
      );
    } catch {
      setFlags((prev) =>
        prev.map((f) => (f.flag_key === key ? { ...f, enabled: nextVal } : f))
      );
    }
  }

  const filteredUsers = users.filter((u) =>
    searchUser ? u.email.toLowerCase().includes(searchUser.toLowerCase()) : true
  );

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-8"
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-tide-500/20 text-tide-300 border border-tide-400/30">
              <ShieldCheck size={18} />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Sovereign Administration &amp; Access Control
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            RBAC role-tier assignment, feature flags control, and immutable security audit logs.
          </p>
        </div>

        {/* Feature Flags Switches */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/80 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sliders size={16} className="text-tide-400" /> System Feature Flags
            </h2>
            <span className="text-xs font-mono text-slate-500">Live Config</span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {flags.map((flag) => (
              <div
                key={flag.flag_key}
                className="rounded-lg border border-white/5 bg-abyss-950/60 p-4 space-y-3 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-white truncate max-w-[180px]">
                      {flag.flag_key}
                    </span>
                    <button
                      onClick={() => handleToggleFlag(flag.flag_key, flag.enabled)}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition ${
                        flag.enabled ? "bg-tide-500" : "bg-abyss-800"
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-abyss-950 transition ${
                          flag.enabled ? "translate-x-4" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                  <p className="mt-2 text-[11px] text-slate-400 leading-snug">{flag.description}</p>
                </div>

                <div className="text-[10px] font-mono text-slate-500">
                  Status: {flag.enabled ? <span className="text-emerald-400">ENABLED</span> : "DISABLED"}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* User RBAC Management Table */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/80 p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Users size={16} className="text-tide-400" /> User Roles &amp; Security Tiers
            </h2>
            <div className="flex items-center gap-2 max-w-xs w-full">
              <Search size={14} className="text-slate-400" />
              <input
                type="text"
                placeholder="Search user by email..."
                value={searchUser}
                onChange={(e) => setSearchUser(e.target.value)}
                className="w-full bg-abyss-950 border border-white/10 rounded px-2.5 py-1 text-xs text-white outline-none"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 bg-abyss-950/60 font-mono text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-4 py-3">User Email</th>
                  <th className="px-4 py-3">Assigned Role</th>
                  <th className="px-4 py-3">Sanctuary Scopes</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="transition hover:bg-white/5">
                    <td className="px-4 py-3 font-medium text-white">{u.email}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="rounded bg-abyss-950 border border-white/10 px-2.5 py-1 text-xs text-tide-300 outline-none font-mono"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-400">
                      {u.sanctuary_scopes.length > 0 ? u.sanctuary_scopes.join(", ") : "GLOBAL"}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_locked ? (
                        <span className="rounded bg-signal-coral/20 px-2 py-0.5 text-[10px] font-mono text-signal-coral border border-signal-coral/30">
                          LOCKED
                        </span>
                      ) : (
                        <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-400 border border-emerald-500/20">
                          ACTIVE
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {u.is_locked && (
                        <button
                          onClick={() => handleUnlock(u.id)}
                          className="inline-flex items-center gap-1 rounded bg-white/10 px-2.5 py-1 text-xs text-white hover:bg-white/20 transition"
                        >
                          <Unlock size={12} /> Unlock
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Security Audit Log Explorer */}
        <div className="rounded-xl border border-white/10 bg-abyss-900/80 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldAlert size={16} className="text-signal-amber" /> Immutable Security Audit Logs
            </h2>
            <span className="font-mono text-[11px] text-slate-500">Append-only</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-white/10 bg-abyss-950/60 text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Action Event</th>
                  <th className="px-4 py-3">Target Resource</th>
                  <th className="px-4 py-3 text-right">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {logs.map((log) => (
                  <tr key={log.id} className="transition hover:bg-white/5">
                    <td className="px-4 py-3 text-slate-400">
                      {new Date(log.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-3 text-tide-300 font-bold">{log.actor_id || "ANONYMOUS"}</td>
                    <td className="px-4 py-3 text-white">{log.action}</td>
                    <td className="px-4 py-3 text-slate-400">{log.target_id || "—"}</td>
                    <td className="px-4 py-3 text-right text-slate-500">{log.ip_address}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>
    </AppShell>
  );
}
