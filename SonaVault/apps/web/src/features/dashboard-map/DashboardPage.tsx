import { motion } from "framer-motion";
import { Activity, MapPin, Radio, ShieldAlert } from "lucide-react";

import AppShell from "@/components/ui/AppShell";

const KPI_CARDS = [
  { label: "Active hydrophone stations", value: "—", icon: Radio },
  { label: "Live sound events (24h)", value: "—", icon: Activity },
  { label: "Monitored sanctuaries", value: "—", icon: MapPin },
  { label: "Open QA flags", value: "—", icon: ShieldAlert },
];

export default function DashboardPage() {
  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-2xl font-semibold tracking-tight text-white">Sanctuary overview</h1>
        <p className="mt-1 text-sm text-slate-400">
          Leaflet station map, live acoustic alerts, and SPL analytics land here in Sprint 3.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {KPI_CARDS.map(({ label, value, icon: Icon }) => (
            <div
              key={label}
              className="rounded-xl border border-white/10 bg-abyss-900/60 p-5 transition hover:border-tide-400/30"
            >
              <Icon size={18} className="text-tide-400" />
              <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
              <p className="mt-1 text-xs text-slate-500">{label}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 flex h-72 items-center justify-center rounded-xl border border-dashed border-white/10 bg-abyss-900/40 text-sm text-slate-600">
          Sanctuary map &amp; live stream widgets (Sprint 3)
        </div>
      </motion.div>
    </AppShell>
  );
}
