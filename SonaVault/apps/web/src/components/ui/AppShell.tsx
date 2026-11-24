import { LayoutDashboard, LogOut, ShieldCheck, Waves } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { apiFetch, setAccessToken } from "@/lib/api";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/settings/security", label: "Security", icon: ShieldCheck },
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
    <div className="min-h-screen bg-abyss-950">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-abyss-900/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-2 text-sm font-semibold text-white">
              <Waves size={18} className="text-tide-400" />
              SonaVault
            </span>
            <nav className="flex gap-1">
              {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition ${
                      isActive
                        ? "bg-tide-500/15 text-tide-300"
                        : "text-slate-400 hover:bg-white/5 hover:text-white"
                    }`
                  }
                >
                  <Icon size={14} />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-slate-400 transition hover:bg-white/5 hover:text-signal-coral"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
