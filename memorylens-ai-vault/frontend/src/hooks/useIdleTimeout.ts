import { useCallback, useEffect, useRef, useState } from "react";

// Single place to change the idle-logout timing.
export const IDLE_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes of no activity
export const IDLE_WARNING_MS = 60 * 1000; // show a warning this long before logout

const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousemove",
  "keydown",
  "touchstart",
  "scroll",
  "click",
];

/**
 * Tracks user activity app-wide and reports when a warning should be shown
 * (IDLE_WARNING_MS before the cutoff) and when the idle cutoff itself is
 * hit. Mount once at the app root (e.g. inside AuthProvider's consumer),
 * not per-page, so navigating around the app doesn't reset or duplicate
 * the timers.
 */
export function useIdleTimeout(enabled: boolean, onTimeout: () => void) {
  const [warning, setWarning] = useState(false);
  const warnTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    if (warnTimer.current) clearTimeout(warnTimer.current);
    if (logoutTimer.current) clearTimeout(logoutTimer.current);
    warnTimer.current = null;
    logoutTimer.current = null;
  }, []);

  const reset = useCallback(() => {
    clearTimers();
    setWarning(false);
    if (!enabled) return;
    warnTimer.current = setTimeout(() => setWarning(true), IDLE_TIMEOUT_MS - IDLE_WARNING_MS);
    logoutTimer.current = setTimeout(() => {
      setWarning(false);
      onTimeout();
    }, IDLE_TIMEOUT_MS);
  }, [enabled, clearTimers, onTimeout]);

  useEffect(() => {
    if (!enabled) {
      clearTimers();
      setWarning(false);
      return;
    }
    reset();
    const handleActivity = () => reset();
    ACTIVITY_EVENTS.forEach((evt) => window.addEventListener(evt, handleActivity, { passive: true }));
    return () => {
      ACTIVITY_EVENTS.forEach((evt) => window.removeEventListener(evt, handleActivity));
      clearTimers();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  // "Stay logged in" button in the warning modal.
  const stayActive = useCallback(() => reset(), [reset]);

  return { warning, stayActive };
}
