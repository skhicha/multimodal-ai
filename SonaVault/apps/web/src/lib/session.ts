import { apiFetch, getAccessToken, setAccessToken } from "@/lib/api";

/** Silently restores a session from memory/sessionStorage or the HttpOnly refresh cookie
 * on app load (e.g. after a full page reload). */
export async function bootstrapSession(): Promise<boolean> {
  if (getAccessToken()) {
    return true;
  }
  try {
    const res = await apiFetch("/auth/refresh", { method: "POST" });
    if (res.access_token) {
      setAccessToken(res.access_token);
      return true;
    }
  } catch {
    // No valid refresh cookie — user is simply not logged in.
  }
  return false;
}
