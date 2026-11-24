// Thin typed fetch wrapper for the MemoryLens AI backend.
// Requests go through Vite's dev proxy (/api -> http://localhost:8000).

export type MediaType = "photo" | "video";
export type MediaStatus = "pending" | "processing" | "ready" | "failed";

export interface MediaItem {
  id: string;
  filename: string;
  media_type: MediaType;
  status: MediaStatus;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  fps: number | null;
  camera_model: string | null;
  gps_lat: number | null;
  gps_lon: number | null;
  taken_at: string | null;
  created_at: string;
  has_faces: boolean;
  face_count: number;
  time_of_day: string | null;
  outdoor_guess: string | null;
  asr_status: string;
  error: string | null;
  tags: string[];
  thumb_url: string | null;
  is_favorite: boolean;
  duplicate_count: number;
}

export interface FaceBox {
  frame_time: number;
  x: number;
  y: number;
  w: number;
  h: number;
  keyframe_url: string | null;
}

export interface TranscriptSegment {
  start_time: number;
  end_time: number;
  text: string;
}

export interface MediaCaption {
  frame_time: number;
  caption: string;
}

export interface MediaDetail extends MediaItem {
  faces: FaceBox[];
  transcript: TranscriptSegment[];
  captions: MediaCaption[];
}

export interface DuplicateItem {
  id: string;
  filename: string;
  thumb_url: string | null;
  created_at: string;
}

export interface SearchResult {
  media_id: string;
  filename: string;
  media_type: MediaType;
  thumb_url: string | null;
  source: "filename" | "tag" | "transcript" | "caption";
  segment_start: number | null;
  snippet: string;
}

export interface CollectionFilter {
  media_type?: MediaType | null;
  tag?: string | null;
  date_from?: string | null;
  date_to?: string | null;
}

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  is_smart: boolean;
  filter: CollectionFilter | null;
  item_count: number;
  created_at: string;
}

export interface Citation {
  media_id: string;
  filename: string;
  media_type: MediaType;
  source: string;
  segment_start: number | null;
  snippet: string;
}

export interface AskResponse {
  answer: string;
  provider: string;
  citations: Citation[];
}

export interface DashboardSummary {
  total_media: number;
  total_photos: number;
  total_videos: number;
  total_faces: number;
  total_with_gps: number;
  uploads_by_day: { date: string; count: number }[];
  type_split: { media_type: string; count: number }[];
  tag_distribution: { tag: string; count: number }[];
  map_hotspots: { media_id: string; filename: string; lat: number; lon: number }[];
  is_admin?: boolean;
  system_total_users?: number | null;
  system_total_media?: number | null;
}

export interface SettingsInfo {
  llm_provider: string;
  anthropic_key_configured: boolean;
  whisper_model: string;
}

// In-memory access token, set by AuthContext on login/register/refresh.
// The refresh token itself lives only in the httpOnly cookie and is never
// touched by JS.
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// Set by AuthContext: calls POST /api/auth/refresh and returns the new
// access token (or null on failure). Used by `request` to retry once on 401.
let refreshHandler: (() => Promise<string | null>) | null = null;

export function setRefreshHandler(handler: (() => Promise<string | null>) | null): void {
  refreshHandler = handler;
}

function authHeaders(init?: RequestInit): HeadersInit {
  const headers = new Headers(init?.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  return headers;
}

async function throwForResponse(res: Response): Promise<never> {
  let detail: string = res.statusText;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      // FastAPI validation errors: [{ loc, msg, type }, ...]
      detail = body.detail
        .map((item: { msg?: string }) => item?.msg)
        .filter(Boolean)
        .join("; ") || detail;
    } else if (body.detail != null) {
      detail = JSON.stringify(body.detail);
    }
  } catch {
    // ignore - no JSON body
  }
  throw new Error(`${res.status} ${detail}`);
}

async function request<T>(path: string, init?: RequestInit, skipRetry = false): Promise<T> {
  const res = await fetch(path, { ...init, headers: authHeaders(init), credentials: "include" });
  if (res.status === 401 && refreshHandler && !skipRetry) {
    const newToken = await refreshHandler();
    if (newToken) {
      const retryHeaders = new Headers(init?.headers);
      retryHeaders.set("Authorization", `Bearer ${newToken}`);
      const retryRes = await fetch(path, { ...init, headers: retryHeaders, credentials: "include" });
      if (!retryRes.ok) return throwForResponse(retryRes);
      return retryRes.json() as Promise<T>;
    }
  }
  if (!res.ok) return throwForResponse(res);
  return res.json() as Promise<T>;
}

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "editor" | "viewer";
  email_verified: boolean;
  otp_enabled: boolean;
  mfa_enabled: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface SessionInfo {
  id: string;
  device_label: string | null;
  created_at: string;
  is_current: boolean;
}

export interface OtpRequiredResponse {
  otp_required: true;
  otp_token: string;
}

export interface MfaRequiredResponse {
  mfa_required: true;
  mfa_token: string;
}

// Login returns full tokens, or (when the account has OTP or MFA enabled)
// a short-lived token the caller must exchange via otpVerify/mfaVerify.
export type LoginResult = AuthResponse | OtpRequiredResponse | MfaRequiredResponse;

export function isOtpRequired(res: LoginResult): res is OtpRequiredResponse {
  return (res as OtpRequiredResponse).otp_required === true;
}

export function isMfaRequired(res: LoginResult): res is MfaRequiredResponse {
  return (res as MfaRequiredResponse).mfa_required === true;
}

export interface MfaSetupResponse {
  secret: string;
  otpauth_uri: string;
  qr_code: string;
}

export interface MfaEnableResponse {
  backup_codes: string[];
}

export interface GoogleStatus {
  configured: boolean;
}

export interface MyPermissionsResponse {
  role: string;
  permissions: string[];
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "editor" | "viewer";
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  media_count: number;
}

export interface AdminStats {
  total_users: number;
  total_media: number;
  total_admins: number;
}

export interface AdminPermission {
  code: string;
  resource: string;
  action: string;
  description: string | null;
}

export interface AdminRole {
  id: number;
  name: string;
  slug: "admin" | "editor" | "viewer";
  description: string | null;
  is_system: boolean;
  user_count: number;
  permissions: string[];
}

export const api = {
  register(email: string, password: string, display_name: string) {
    // skipRetry: this is an unauthenticated endpoint. A 401 here (which
    // register shouldn't normally return, but defensively) must never
    // trigger the generic refresh-and-retry -- that path is only correct
    // for an already-logged-in request whose access token expired.
    return request<AuthResponse>(
      `/api/auth/register`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, display_name }),
      },
      true,
    );
  },

  login(email: string, password: string) {
    // skipRetry: a wrong-password 401 must surface as a login error, not
    // trigger the generic refresh-and-retry -- without this, a stale
    // refresh cookie from a PREVIOUS account's session on this browser
    // silently logs the user back into that old account instead of
    // showing "invalid email or password" for the one they just typed.
    return request<LoginResult>(
      `/api/auth/login`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      },
      true,
    );
  },

  otpVerify(otp_token: string, code: string) {
    return request<AuthResponse>(`/api/auth/otp/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp_token, code }),
    });
  },

  otpResend(otp_token: string) {
    return request<{ ok: boolean }>(`/api/auth/otp/resend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp_token }),
    });
  },

  verifyEmail(code: string) {
    return request<{ ok: boolean }>(`/api/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
  },

  resendVerification() {
    return request<{ ok: boolean }>(`/api/auth/resend-verification`, { method: "POST" });
  },

  forgotPassword(email: string) {
    return request<{ ok: boolean }>(`/api/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
  },

  resetPassword(email: string, code: string, new_password: string) {
    return request<{ ok: boolean }>(`/api/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code, new_password }),
    });
  },

  updateMe(otp_enabled: boolean) {
    return request<AuthUser>(`/api/auth/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp_enabled }),
    });
  },

  mfaSetup() {
    return request<MfaSetupResponse>(`/api/auth/mfa/setup`, { method: "POST" });
  },

  mfaEnable(code: string) {
    return request<MfaEnableResponse>(`/api/auth/mfa/enable`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
  },

  mfaDisable(password: string) {
    return request<{ ok: boolean }>(`/api/auth/mfa/disable`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
  },

  mfaVerify(mfa_token: string, code: string) {
    return request<AuthResponse>(`/api/auth/mfa/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mfa_token, code }),
    });
  },

  googleStatus() {
    return request<GoogleStatus>(`/api/auth/google/status`);
  },

  refresh() {
    return request<AuthResponse>(`/api/auth/refresh`, { method: "POST" }, true);
  },

  logout() {
    return request<{ ok: boolean }>(`/api/auth/logout`, { method: "POST" });
  },

  me() {
    return request<AuthUser>(`/api/auth/me`);
  },

  myPermissions() {
    return request<MyPermissionsResponse>(`/api/auth/my-permissions`);
  },

  mySessions() {
    return request<SessionInfo[]>(`/api/auth/sessions`);
  },

  logoutOtherDevices() {
    return request<{ ok: boolean; revoked_count: number }>(`/api/auth/sessions/logout-others`, {
      method: "POST",
    });
  },

  // Exchanges the caller's real access token (sent normally, as an
  // Authorization header) for a short-lived, single-use ticket to open the
  // /api/auth/events SSE connection with -- see the backend endpoint's
  // docstring for why this indirection exists instead of putting the real
  // token in that URL.
  sseTicket() {
    return request<{ ticket: string }>(`/api/auth/sse-ticket`, { method: "POST" });
  },

  adminListUsers() {
    return request<{ users: AdminUser[] }>(`/api/admin/users`);
  },

  adminStats() {
    return request<AdminStats>(`/api/admin/stats`);
  },

  adminDeactivate(id: string) {
    return request<{ ok: boolean }>(`/api/admin/users/${id}/deactivate`, { method: "POST" });
  },

  adminReactivate(id: string) {
    return request<{ ok: boolean }>(`/api/admin/users/${id}/reactivate`, { method: "POST" });
  },

  adminSetRole(id: string, role: "admin" | "editor" | "viewer") {
    return request<{ ok: boolean }>(`/api/admin/users/${id}/role`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
  },

  adminCreateUser(email: string, password: string, display_name: string, role: "admin" | "editor" | "viewer") {
    return request<AdminUser>(`/api/admin/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name, role }),
    });
  },

  adminDeleteUser(id: string) {
    return request<{ ok: boolean }>(`/api/admin/users/${id}`, { method: "DELETE" });
  },

  adminListRoles() {
    return request<{ roles: AdminRole[] }>(`/api/admin/roles`);
  },

  adminListPermissions() {
    return request<{ permissions: AdminPermission[] }>(`/api/admin/permissions`);
  },

  adminUpdateRolePermissions(roleId: number, permissions: string[]) {
    return request<AdminRole>(`/api/admin/roles/${roleId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ permissions }),
    });
  },

  uploadMedia(file: File, onProgress?: (pct: number) => void): Promise<MediaItem> {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/media/upload");
      xhr.withCredentials = true;
      if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          let detail = xhr.statusText || `HTTP ${xhr.status}`;
          try {
            const body = JSON.parse(xhr.responseText);
            if (typeof body.detail === "string") {
              detail = body.detail;
            } else if (Array.isArray(body.detail)) {
              detail = body.detail.map((item: { msg?: string }) => item?.msg).filter(Boolean).join("; ") || detail;
            } else if (body.detail != null) {
              detail = JSON.stringify(body.detail);
            }
          } catch {
            // ignore - no JSON body
          }
          reject(new Error(`Upload failed: ${detail}`));
        }
      };
      xhr.onerror = () => reject(new Error("Upload failed: network error"));
      xhr.send(form);
    });
  },

  listMedia(params?: { media_type?: MediaType; tag?: string; date_from?: string; date_to?: string }) {
    const qs = new URLSearchParams();
    if (params?.media_type) qs.set("media_type", params.media_type);
    if (params?.tag) qs.set("tag", params.tag);
    if (params?.date_from) qs.set("date_from", params.date_from);
    if (params?.date_to) qs.set("date_to", params.date_to);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<MediaItem[]>(`/api/media${suffix}`);
  },

  getMedia(id: string) {
    return request<MediaDetail>(`/api/media/${id}`);
  },

  deleteMedia(id: string) {
    // Soft-delete: moves the item to Trash. See purgeMedia() for the
    // actual permanent delete.
    return request<{ ok: boolean }>(`/api/media/${id}`, { method: "DELETE" });
  },

  listTrash() {
    return request<MediaItem[]>(`/api/media/trash`);
  },

  restoreMedia(id: string) {
    return request<{ ok: boolean }>(`/api/media/${id}/restore`, { method: "POST" });
  },

  purgeMedia(id: string) {
    return request<{ ok: boolean }>(`/api/media/${id}/purge`, { method: "DELETE" });
  },

  getDuplicates(id: string) {
    return request<DuplicateItem[]>(`/api/media/${id}/duplicates`);
  },

  listCollections() {
    return request<Collection[]>(`/api/collections`);
  },

  createCollection(body: { name: string; description?: string; filter?: CollectionFilter }) {
    return request<Collection>(`/api/collections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  getCollection(id: string) {
    return request<Collection>(`/api/collections/${id}`);
  },

  listCollectionItems(id: string) {
    return request<MediaItem[]>(`/api/collections/${id}/items`);
  },

  updateCollection(id: string, body: { name?: string; description?: string }) {
    return request<Collection>(`/api/collections/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  deleteCollection(id: string) {
    return request<{ ok: boolean }>(`/api/collections/${id}`, { method: "DELETE" });
  },

  addToCollection(collectionId: string, mediaId: string) {
    return request<{ ok: boolean }>(`/api/collections/${collectionId}/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_id: mediaId }),
    });
  },

  removeFromCollection(collectionId: string, mediaId: string) {
    return request<{ ok: boolean }>(`/api/collections/${collectionId}/items/${mediaId}`, { method: "DELETE" });
  },

  toggleFavorite(id: string, is_favorite: boolean) {
    return request<MediaItem>(`/api/media/${id}/favorite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_favorite }),
    });
  },

  search(q: string) {
    return request<SearchResult[]>(`/api/search?q=${encodeURIComponent(q)}`);
  },

  ask(question: string) {
    return request<AskResponse>(`/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  },

  dashboardSummary() {
    return request<DashboardSummary>(`/api/dashboard/summary`);
  },

  settings() {
    return request<SettingsInfo>(`/api/dashboard/settings`);
  },

  reindex() {
    return request<{ reindexed: number }>(`/api/dashboard/reindex`, { method: "POST" });
  },

  mediaFileUrl(id: string) {
    return withAuth(`/api/media/${id}/file`);
  },

  thumbnailUrl(id: string) {
    return withAuth(`/api/media/${id}/thumbnail`);
  },
};

// Plain <img>/<video src> tags can't set an Authorization header, so any
// media byte-serving URL (thumbnail/keyframe/file) needs the access token
// appended as a query param instead -- the backend's get_current_user
// accepts either. Every list/detail response from the API embeds relative
// paths like `/api/media/keyframe/<name>`, so this is also applied to those
// via `withAuthUrl` wherever they're rendered.
export function withAuth(path: string): string {
  if (!accessToken) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}token=${encodeURIComponent(accessToken)}`;
}
