export type Theme = "dark" | "light";

const STORAGE_KEY = "memorylens-theme";

export function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage unavailable (private mode, etc.) - fall through to default
  }
  return "dark";
}

type Listener = (theme: Theme) => void;
const listeners = new Set<Listener>();

export function setStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore
  }
  document.documentElement.setAttribute("data-theme", theme);
  listeners.forEach((listener) => listener(theme));
}

export function subscribeToTheme(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function applyInitialTheme(): Theme {
  const theme = getStoredTheme();
  document.documentElement.setAttribute("data-theme", theme);
  return theme;
}
