import { apiFetch, setAccessToken } from "@/lib/api";

/** Silently restores a session from the HttpOnly refresh cookie on app load
 * (e.g. after a full page reload), since the access token itself only ever
 * lives in memory and is wiped by any hard navigation or refresh. */
export async function bootstrapSession(): Promise<boolean> {
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
