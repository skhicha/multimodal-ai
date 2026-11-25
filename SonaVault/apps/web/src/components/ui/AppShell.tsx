import {
  Database,
  FileCode,
  GitBranch,
  LayoutDashboard,
  Lock,
  LogOut,
  Radio,
  Search,
  ShieldCheck,
  Sparkles,
  Waves,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { apiFetch, setAccessToken } from "@/lib/api";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Sanctuaries", icon: LayoutDashboard },
  { to: "/streams", label: "Live Streams", icon: Radio },
  { to: "/vault", label: "Vault Ingest", icon: Database },
  { to: "/workbench", label: "Workbench", icon: Waves },
  { to: "/search", label: "Search Studio", icon: Search },
  { to: "/briefings", label: "AI Briefings", icon: Sparkles },
  { to: "/documents", label: "Telemetry & Docs", icon: FileCode },
  { to: "/jobs", label: "Pipeline & PREMIS", icon: GitBranch },
  { to: "/admin", label: "Admin Console", icon: ShieldCheck },
  { to: "/settings/security", label: "Security & MFA", icon: Lock },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      navigate("/login", { replace: true });
    }
  }

  return (
    <div className="min-h-screen bg-abyss-950 text-slate-100 flex flex-col font-body">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-abyss-900/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5 sm:px-6">
          <div className="flex items-center gap-6">
            <NavLink to="/dashboard" className="flex items-center gap-2 text-sm font-bold tracking-wider text-white">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-tide-500/20 text-tide-300 border border-tide-400/30">
                <Waves size={18} />
              </span>
              <span className="font-display text-base">SonaVault</span>
              <span className="hidden sm:inline-block rounded px-1.5 py-0.5 text-[10px] font-mono tracking-tight bg-tide-500/10 text-tide-400 border border-tide-400/20">
                DGX SPARK GB10
              </span>
            </NavLink>

            <nav className="hidden lg:flex items-center gap-1 overflow-x-auto py-1">
              {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition whitespace-nowrap ${
                      isActive
                        ? "bg-tide-500/15 text-tide-300 border border-tide-400/30"
                        : "text-slate-400 hover:bg-white/5 hover:text-white"
                    }`
                  }
                >
                  <Icon size={13} />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded bg-abyss-800/80 border border-white/5 text-[11px] font-mono text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>MoE 30B NVFP4</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-signal-coral"
              title="Sign out"
            >
              <LogOut size={14} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>

        {/* Mobile / Tablet Horizontal Navigation Scrollbar */}
        <div className="flex lg:hidden overflow-x-auto px-4 py-2 border-t border-white/5 gap-1.5 bg-abyss-950/70">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium whitespace-nowrap transition ${
                  isActive
                    ? "bg-tide-500/20 text-tide-300 border border-tide-400/30"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <Icon size={12} />
              {label}
            </NavLink>
          ))}
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">{children}</main>

      <footer className="border-t border-white/5 bg-abyss-950/80 py-4 text-center text-xs text-slate-500">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6">
          <p>SonaVault Sovereign Acoustic Intelligence — Blackwell sm_121 Native</p>
          <p className="font-mono text-[11px] text-slate-600">PREMIS Sealed • Blake3 • WebAuthn L3</p>
        </div>
      </footer>
    </div>
  );
}
