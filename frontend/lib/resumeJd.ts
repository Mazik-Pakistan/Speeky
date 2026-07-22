import { api } from "./api";

export type ParseStatus = "success" | "failed_scanned_or_empty" | "failed_corrupt_or_too_large";

export interface ResumeUploadResult {
  resume_id: string;
  user_id: string;
  filename: string;
  parse_status: ParseStatus;
  redacted_fields: string[];
  extracted_word_count: number;
  fallback_to_generic: boolean;
  warning: string | null;
  uploaded_at: string;
  last_modified_label: string;
}

export interface ResumeSummary {
  resume_id: string;
  filename: string;
  parse_status: ParseStatus;
  uploaded_at: string;
  last_modified_label: string;
}

export interface JDIntakeResult {
  jd_id: string;
  truncated: boolean;
  original_word_count: number;
  cleaned_word_count: number;
  warning: string | null;
}

export interface JDDetail {
  jd_id: string;
  cleaned_text: string;
  truncated: boolean;
}

export interface MismatchCheckResult {
  mismatch_detected: boolean;
  overlap_score: number;
  resume_keywords_found: string[];
  jd_keywords_found: string[];
  note: string;
}

export function uploadResume(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return api<ResumeUploadResult>("/resume-jd-intake/resumes", {
    method: "POST",
    body: formData,
  });
}

export function listResumes() {
  return api<ResumeSummary[]>("/resume-jd-intake/resumes");
}

export function getResumeDetail(resumeId: string) {
  return api<{ resume_id: string; filename: string; parse_status: ParseStatus; extracted_text: string; redacted_fields: string[] }>(
    `/resume-jd-intake/resumes/${resumeId}`
  );
}

export function submitJd(jdText: string) {
  return api<JDIntakeResult>("/resume-jd-intake/jds", {
    method: "POST",
    body: JSON.stringify({ jd_text: jdText }),
  });
}

export function getJdDetail(jdId: string) {
  return api<JDDetail>(`/resume-jd-intake/jds/${jdId}`);
}

export function checkMismatch(resumeId: string, jdId: string) {
  return api<MismatchCheckResult>("/resume-jd-intake/mismatch-check", {
    method: "POST",
    body: JSON.stringify({ resume_id: resumeId, jd_id: jdId }),
  });
}
