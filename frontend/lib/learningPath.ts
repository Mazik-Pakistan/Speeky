import { api } from "./api";

// ── Shared types ─────────────────────────────────────────────────────────────

export interface LPModule {
  module_id: string;
  title: string;
  sequence_order: number;
  prerequisites: string[];
  passing_score: number;
  content: string;
  content_version: number;
}

export interface LearningPath {
  path_id: string;
  title: string;
  description: string;
  learning_level: string;
  is_published: boolean;
  strict_sequential: boolean;
  is_enterprise_assigned: boolean;
  is_deprecated?: boolean;
  deprecated_id?: string | null;
  mapped_to_id?: string | null;
  owner_id: string;
  modules: LPModule[];
}

export interface RecommendationResponse {
  recommended_path_id: string;
  path_title: string;
  reasoning: string;
  confidence_score: number;
  learning_level: string;
  is_fallback: boolean;
  available_paths: LearningPath[];
}

export interface PathSwitchResponse {
  success: boolean;
  active_path_id: string;
  previous_path_id: string | null;
  confirmation_required: boolean;
  warning: string | null;
  message: string;
}

export interface MilestoneEvaluateResponse {
  module_id: string;
  awarded_badges: string[];
  already_awarded_count: number;
  message: string;
}

export interface PathResetResponse {
  success: boolean;
  path_id: string;
  archived_version: number;
  message: string;
}

export interface AdminSavePathResponse {
  success: boolean;
  path_id: string;
  message: string;
}

export interface AdminPublishResponse {
  success: boolean;
  path_id: string;
  is_published: boolean;
  message: string;
}

export interface AdminLockResponse {
  success: boolean;
  locked_by: string | null;
  message: string;
}

export interface PauseResumeResponse {
  success: boolean;
  resumed: boolean;
  question_index: number;
  conversation_context: Array<{ role: string; content: string }>;
  in_progress_data: Record<string, unknown>;
  stale_reset: boolean;
  content_updated: boolean;
  was_interrupted: boolean;
  message: string;
}

export interface ModuleAccessResponse {
  module_id: string;
  accessible: boolean;
  reason: string;
  mode: string;
  current_score: number | null;
  required_score: number;
}

export interface ShareableCardData {
  title: string;
  level: string;
  certificate_url: string;
  badge_icon: string;
}

export interface PathCompletionCheckResponse {
  path_id: string;
  is_complete: boolean;
  completed_modules_count: number;
  total_modules_count: number;
  incomplete_module_ids: string[];
  is_grandfathered: boolean;
  summary: PathSummary | null;
}

export interface PathSummary {
  path_id: string;
  path_title: string;
  user_id: string;
  total_practice_time_seconds: number;
  average_confidence_score: number;
  total_vocabulary_mastered: number;
  completed_at: string;
  certificate_id: string;
  shareable_card_data: ShareableCardData;
}

export interface PathSummaryResponse extends PathSummary {}

// ── API calls ─────────────────────────────────────────────────────────────────

export function getRecommendation(): Promise<RecommendationResponse> {
  return api<RecommendationResponse>("/learning-path/recommendation");
}

export function switchPath(data: {
  target_path_id: string;
  confirm: boolean;
  unsaved_progress?: Record<string, unknown>;
  request_id?: string;
}): Promise<PathSwitchResponse> {
  return api<PathSwitchResponse>("/learning-path/switch", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function evaluateMilestone(data: {
  path_id: string;
  module_id: string;
  score?: number;
  completed_at?: string;
  is_offline?: boolean;
  corrupted_progress?: boolean;
}): Promise<MilestoneEvaluateResponse> {
  return api<MilestoneEvaluateResponse>("/learning-path/milestone/evaluate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function resetPath(data: {
  path_id: string;
  confirm: boolean;
}): Promise<PathResetResponse> {
  return api<PathResetResponse>("/learning-path/reset", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function adminSavePath(data: {
  path_id: string;
  title: string;
  description?: string;
  learning_level?: string;
  is_published?: boolean;
  strict_sequential?: boolean;
  modules: Array<{
    module_id: string;
    title: string;
    sequence_order: number;
    prerequisites?: string[];
    passing_score?: number;
    content?: string;
    content_version?: number;
  }>;
  is_enterprise_assigned?: boolean;
}): Promise<AdminSavePathResponse> {
  return api<AdminSavePathResponse>("/learning-path/admin/paths", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function adminPublishPath(path_id: string): Promise<AdminPublishResponse> {
  return api<AdminPublishResponse>(`/learning-path/admin/paths/${path_id}/publish`, {
    method: "POST",
  });
}

export function adminDeleteModule(module_id: string): Promise<{ success: boolean; module_id: string; message: string }> {
  return api(`/learning-path/admin/modules/${module_id}`, {
    method: "DELETE",
  });
}

export function adminAcquireLock(data: {
  path_id: string;
  admin_id: string;
}): Promise<AdminLockResponse> {
  return api<AdminLockResponse>("/learning-path/admin/lock", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function pauseModule(data: {
  path_id: string;
  module_id: string;
  question_index?: number;
  conversation_context?: Array<{ role: string; content: string }>;
  in_progress_data?: Record<string, unknown>;
  was_interrupted?: boolean;
}): Promise<PauseResumeResponse> {
  return api<PauseResumeResponse>("/learning-path/module/pause", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function resumeModule(data: {
  path_id: string;
  module_id: string;
}): Promise<PauseResumeResponse> {
  return api<PauseResumeResponse>("/learning-path/module/resume", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function checkModuleAccess(
  path_id: string,
  module_id: string
): Promise<ModuleAccessResponse> {
  return api<ModuleAccessResponse>(
    `/learning-path/paths/${path_id}/modules/${module_id}/access`
  );
}

export function manualUnlockOverride(data: {
  target_user_id: string;
  path_id: string;
  unlock_all?: boolean;
  module_ids?: string[];
}): Promise<{ success: boolean; user_id: string; message: string }> {
  return api("/learning-path/admin/override-unlock", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function checkPathCompletion(
  path_id: string
): Promise<PathCompletionCheckResponse> {
  return api<PathCompletionCheckResponse>(
    `/learning-path/paths/${path_id}/completion-check`
  );
}

export function getCertification(path_id: string): Promise<PathSummaryResponse> {
  return api<PathSummaryResponse>(
    `/learning-path/paths/${path_id}/certification`
  );
}

/**
 * Maps a Learning Path module to its corresponding real practice session route URL
 * with query parameters tracking the path_id, module_id, and passing_score requirement.
 */
export function getModuleSessionHref(pathId: string, module: LPModule): string {
  const id = module.module_id.toLowerCase();
  const title = module.title.toLowerCase();
  const passingScore = module.passing_score ?? 60;

  let baseRoute = "/dashboard/coaching/general_workplace";

  if (id.includes("email") || title.includes("email")) {
    baseRoute = "/dashboard/coaching/email_writing";
  } else if (
    id.includes("meeting") ||
    title.includes("meeting") ||
    title.includes("greetings") ||
    title.includes("contribution")
  ) {
    baseRoute = "/dashboard/coaching/meeting_communication";
  } else if (
    id.includes("presentation") ||
    title.includes("presentation") ||
    title.includes("boardroom")
  ) {
    baseRoute = "/dashboard/coaching/presentation_prep";
  } else if (
    id.includes("client") ||
    title.includes("client") ||
    title.includes("phone") ||
    title.includes("update")
  ) {
    baseRoute = "/dashboard/coaching/client_communication";
  } else if (
    id.includes("interview") ||
    title.includes("interview") ||
    title.includes("objection") ||
    title.includes("negotiation")
  ) {
    baseRoute = "/dashboard/interview-coach";
  } else if (id.includes("script") || title.includes("script")) {
    baseRoute = "/dashboard/script";
  }

  return `${baseRoute}?lp_path_id=${encodeURIComponent(
    pathId
  )}&lp_module_id=${encodeURIComponent(
    module.module_id
  )}&lp_passing_score=${passingScore}`;
}

