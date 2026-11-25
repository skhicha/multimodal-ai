import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try {
      const stored = localStorage.getItem("sv_theme");
      if (stored === "light" || stored === "dark") return stored;
    } catch {}
    return "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
      root.classList.remove("light");
      root.style.colorScheme = "dark";
    } else {
      root.classList.remove("dark");
      root.classList.add("light");
      root.style.colorScheme = "light";
    }
    try {
      localStorage.setItem("sv_theme", theme);
    } catch {}
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return { theme, toggleTheme, setTheme };
}

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition cursor-pointer ${
        theme === "dark"
          ? "border-white/10 bg-abyss-800/80 text-slate-300 hover:bg-white/10 hover:text-white"
          : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100 hover:text-slate-900 shadow-sm"
      } ${className}`}
      title={theme === "dark" ? "Switch to Ocean Light Mode" : "Switch to Deep Abyss Dark Mode"}
      aria-label="Toggle theme mode"
    >
      {theme === "dark" ? (
        <>
          <Sun size={13} className="text-amber-400" />
          <span className="hidden sm:inline text-[11px] font-mono">Light</span>
        </>
      ) : (
        <>
          <Moon size={13} className="text-teal-600" />
          <span className="hidden sm:inline text-[11px] font-mono">Dark</span>
        </>
      )}
    </button>
  );
}
