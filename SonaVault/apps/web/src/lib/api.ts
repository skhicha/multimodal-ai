const API_BASE = "/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    try { sessionStorage.setItem("sv_access_token", token); } catch {}
  } else {
    try { sessionStorage.removeItem("sv_access_token"); } catch {}
  }
}

export function getAccessToken() {
  if (accessToken) return accessToken;
  try {
    const stored = sessionStorage.getItem("sv_access_token");
    if (stored) {
      accessToken = stored;
      return stored;
    }
  } catch {
    return null;
  }
  return null;
}

export async function apiFetch<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : body.detail?.code;
    throw new Error(detail ?? `Request failed: ${res.status}`);
  }

  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

// --- Auth & MFA ---
export interface LoginResponse {
  status: "authenticated" | "mfa_required";
  access_token?: string;
  mfa_ticket?: string;
  methods?: string[];
  mfa_setup_required?: boolean;
}

export function register(email: string, password: string) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export interface EmailSendCodeResponse {
  status: string;
  message: string;
  dev_code?: string | null;
}

export function sendEmailOtp(email: string): Promise<EmailSendCodeResponse> {
  return apiFetch("/auth/email/send-code", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function verifyEmailOtp(email: string, code: string): Promise<LoginResponse> {
  return apiFetch("/auth/email/verify-code", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });
}

export interface SsoInitiateResponse {
  auth_url: string;
  provider: string;
  is_mock: boolean;
}

export function initiateSso(provider: string): Promise<SsoInitiateResponse> {
  return apiFetch(`/auth/sso/initiate?provider=${encodeURIComponent(provider)}`);
}

export function instantSsoLogin(
  provider: string,
  email: string,
  displayName?: string
): Promise<LoginResponse> {
  return apiFetch("/auth/sso/instant", {
    method: "POST",
    body: JSON.stringify({ provider, email, display_name: displayName }),
  });
}

export function mfaVerify(mfaTicket: string, method: string, code: string) {
  return apiFetch("/mfa/verify", {
    method: "POST",
    body: JSON.stringify({ mfa_ticket: mfaTicket, method, code }),
  });
}

export interface TotpEnrollResponse {
  secret: string;
  provisioning_uri: string;
}

export function totpEnroll(): Promise<TotpEnrollResponse> {
  return apiFetch("/mfa/totp/enroll", { method: "POST" });
}

export function totpConfirm(code: string) {
  return apiFetch("/mfa/totp/confirm", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function regenerateRecoveryCodes() {
  return apiFetch("/mfa/recovery-codes/regenerate", { method: "POST" });
}

export interface SessionOut {
  id: string;
  ip_addr: string | null;
  user_agent: string | null;
  amr: string[];
  created_current: boolean;
}

export function listSessions(): Promise<SessionOut[]> {
  return apiFetch("/auth/sessions");
}

export function revokeSession(sid: string) {
  return apiFetch(`/auth/sessions/${sid}`, { method: "DELETE" });
}

export function logoutAll() {
  return apiFetch("/auth/logout-all", { method: "POST" });
}

// --- Ingest & Assets ---
export interface AssetOut {
  sha256: string;
  asset_type: string;
  original_filename: string | null;
  mime_type: string;
  size_bytes: number;
  sanctuary_id: string | null;
  station_code: string | null;
  latitude: number | null;
  longitude: number | null;
  geo_qa_flag: string | null;
}

export function listAssets(): Promise<AssetOut[]> {
  return apiFetch("/ingest/assets");
}

export function getAsset(sha256: string): Promise<AssetOut> {
  return apiFetch(`/ingest/assets/${sha256}`);
}

export function ingestAudioFile(formData: FormData) {
  return apiFetch("/ingest/audio", {
    method: "POST",
    body: formData,
  });
}

// --- Transcripts & Workbench ---
export interface TranscriptSegmentOut {
  id: string;
  start_sec: number;
  end_sec: number;
  text: str_or_null;
  speaker_label: string | null;
  language: string | null;
  translations?: Record<string, string>;
}

type str_or_null = string | null;

export interface TranscriptResponse {
  asset_sha256: string;
  detected_language: string;
  segments: TranscriptSegmentOut[];
}

export function getTranscript(sha256: string): Promise<TranscriptResponse> {
  return apiFetch(`/transcripts/${sha256}`);
}

export function translateTranscript(sha256: string, targetLang: string): Promise<TranscriptResponse> {
  return apiFetch(`/transcripts/${sha256}/translate`, {
    method: "POST",
    body: JSON.stringify({ target_lang: targetLang }),
  });
}

export function updateTranscriptSegment(
  sha256: string,
  segmentId: string,
  text: string
): Promise<TranscriptSegmentOut> {
  return apiFetch(`/transcripts/${sha256}/segments/${segmentId}`, {
    method: "PATCH",
    body: JSON.stringify({ text }),
  });
}

// --- Acoustics & Events ---
export interface AcousticEventOut {
  id: string;
  window_start_sec: number;
  window_end_sec: number;
  label: string;
  confidence: number;
}

export interface EventsResponse {
  asset_sha256: string;
  events: AcousticEventOut[];
}

export function getAcousticEvents(sha256: string): Promise<EventsResponse> {
  return apiFetch(`/acoustics/${sha256}/events`);
}

export function getSplData(sha256: string): Promise<number[]> {
  return apiFetch(`/acoustics/${sha256}/spl`);
}

export function updateAcousticEvent(
  sha256: string,
  eventId: string,
  label: string,
  confidence: number
): Promise<AcousticEventOut> {
  return apiFetch(`/acoustics/${sha256}/events/${eventId}`, {
    method: "PATCH",
    body: JSON.stringify({ label, confidence }),
  });
}

// --- Search Studio & Retrieval Debugger ---
export interface SearchResult {
  asset_sha256: string;
  score: number;
  rerank_score: number | null;
  payload: Record<string, any>;
}

export interface SearchResponse {
  results: SearchResult[];
}

export interface ScoreDebugItem {
  id: string;
  text: string;
  asset_sha256: string;
  dense_score: number;
  sparse_score: number;
  dense_rank: number;
  sparse_rank: number;
  rrf_score: number;
  rrf_rank: number;
  rerank_score: number;
  final_rank: number;
  rank_shift: number;
}

export interface SearchScoreDebugResponse {
  collection: string;
  query: string;
  results: ScoreDebugItem[];
}

export function searchHybrid(
  query: string,
  collection: "transcript_segments" | "document_chunks" = "transcript_segments",
  limit = 20,
  rerank = true
): Promise<SearchResponse> {
  return apiFetch("/search/hybrid", {
    method: "POST",
    body: JSON.stringify({ query, collection, limit, rerank }),
  });
}

export function searchDebug(
  query: string,
  collection: "transcript_segments" | "document_chunks" = "transcript_segments",
  limit = 15
): Promise<SearchScoreDebugResponse> {
  return apiFetch("/search/debug", {
    method: "POST",
    body: JSON.stringify({ query, collection, limit, rerank: true }),
  });
}

export function searchAcousticText(query: string, limit = 20): Promise<SearchResponse> {
  return apiFetch("/search/acoustic-text", {
    method: "POST",
    body: JSON.stringify({ query, limit }),
  });
}

// --- Briefings ---
export interface BriefingListItem {
  id: string;
  prompt: string;
  sanctuary_scope: string | null;
  model_id: string;
  created_at: string;
  excerpt: string;
}

export interface BriefingResponse {
  id: string;
  user_id: string;
  prompt: string;
  sanctuary_scope: string | null;
  markdown_body: string;
  cited_sha256s: string[];
  model_id: string;
  created_at: string;
}

export interface BriefingExportResponse {
  briefing_id: string;
  dossier_markdown: string;
  sha256_digest: string;
  created_at: string;
}

export function listBriefings(): Promise<BriefingListItem[]> {
  return apiFetch("/briefings");
}

export function getBriefing(id: string): Promise<BriefingResponse> {
  return apiFetch(`/briefings/${id}`);
}

export function exportBriefing(id: string): Promise<BriefingExportResponse> {
  return apiFetch(`/briefings/${id}/export`);
}

// --- Hydrophone Live Streams ---
export interface StreamItem {
  station_code: string;
  sanctuary_code: string;
  latitude: number;
  longitude: number;
  depth_meters: number;
  sampling_rate_hz: number;
  status: "online" | "offline" | "degraded";
  stream_url?: string;
}

export function listStreams(): Promise<StreamItem[]> {
  return apiFetch("/streams");
}

export function getStream(stationCode: string): Promise<StreamItem> {
  return apiFetch(`/streams/${stationCode}`);
}

export function captureStream(stationCode: string, durationSeconds = 30) {
  return apiFetch(`/streams/${stationCode}/capture`, {
    method: "POST",
    body: JSON.stringify({ duration_seconds: durationSeconds }),
  });
}

// --- Pipeline Jobs & Provenance ---
export interface PipelineStageRunOut {
  id: string;
  stage_name: string;
  status: string;
  attempt_count: number;
  started_at: string | null;
  finished_at: string | null;
  error_detail: string | null;
}

export interface JobOut {
  job_id: string;
  asset_sha256: string;
  pipeline_version: string;
  status: string;
  current_stage: string | null;
  created_at: string;
  finished_at: string | null;
  stages: PipelineStageRunOut[];
}

export function listJobs(): Promise<JobOut[]> {
  return apiFetch("/jobs");
}

export function getJob(jobId: string): Promise<JobOut> {
  return apiFetch(`/jobs/${jobId}`);
}

export function resumeJob(jobId: string): Promise<JobOut> {
  return apiFetch(`/jobs/${jobId}/resume`, { method: "POST" });
}

// --- Documents ---
export interface DocumentChunkOut {
  index: number;
  text: string;
  page_or_section: number;
}

export interface DocumentChunksResponse {
  sha256: string;
  chunks: DocumentChunkOut[];
}

export function getDocumentChunks(sha256: string): Promise<DocumentChunksResponse> {
  return apiFetch(`/documents/${sha256}/chunks`);
}

// --- Admin Console ---
export interface UserOut {
  id: string;
  email: string;
  role: string;
  sanctuary_scopes: string[];
  is_locked: boolean;
  failed_login_attempts: number;
  created_at: string;
}

export interface FeatureFlagOut {
  flag_key: string;
  enabled: boolean;
  description: string | null;
}

export interface AuditLogOut {
  id: string;
  actor_id: string | null;
  action: string;
  target_id: string | null;
  ip_address: string | null;
  created_at: string;
}

export function listUsers(): Promise<UserOut[]> {
  return apiFetch("/admin/users");
}

export function updateUserRole(userId: string, role: string) {
  return apiFetch(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function unlockUser(userId: string) {
  return apiFetch(`/admin/users/${userId}/unlock`, { method: "POST" });
}

export function listFeatureFlags(): Promise<FeatureFlagOut[]> {
  return apiFetch("/admin/feature-flags");
}

export function updateFeatureFlag(key: string, enabled: boolean) {
  return apiFetch(`/admin/feature-flags/${key}`, {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
}

export function listAuditLogs(): Promise<AuditLogOut[]> {
  return apiFetch("/admin/audit-logs");
}

// --- Telemetry & GB10 Hardware ---
export interface UnifiedMemoryTelemetry {
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  utilization_percent: number;
  total_gib: number;
  used_gib: number;
}

export interface GpuTelemetry {
  device_name: string;
  utilization_percent: number;
  temperature_celsius: number;
  power_watts: number | null;
  unified_memory_mode: boolean;
  architecture: string;
}

export interface MoETelemetry {
  model_id: string;
  running_requests: number;
  waiting_requests: number;
  gpu_cache_usage_percent: number;
  generation_throughput_tok_s: number;
  quantization: string;
}

export interface SidecarStatus {
  name: string;
  url: string;
  healthy: boolean;
  latency_ms: number | null;
  last_checked: string;
}

export interface GB10TelemetryResponse {
  timestamp: string;
  hostname: string;
  platform: string;
  unified_memory: UnifiedMemoryTelemetry;
  gpu: GpuTelemetry;
  moe: MoETelemetry;
  pipeline_jobs_running: number;
  sidecars: SidecarStatus[];
}

export interface WatchdogStatusResponse {
  memory_level: "normal" | "warning" | "backpressure" | "emergency";
  used_percent: number;
  total_gib: number;
  used_gib: number;
  backpressure_active: boolean;
  thresholds: {
    warning_percent: number;
    backpressure_percent: number;
    emergency_percent: number;
  };
}

export function getGB10Telemetry(): Promise<GB10TelemetryResponse> {
  return apiFetch("/telemetry/gb10");
}

export function getWatchdogStatus(): Promise<WatchdogStatusResponse> {
  return apiFetch("/telemetry/watchdog");
}

export function triggerWatchdogRelief(): Promise<{
  status: string;
  memory_level: string;
  before_relief_gib: number;
  after_relief_gib: number;
}> {
  return apiFetch("/telemetry/watchdog/relief", { method: "POST" });
}

