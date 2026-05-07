import axios from "axios";

const INGESTION = process.env.NEXT_PUBLIC_API_INGESTION_URL ?? "http://localhost:8001";
const MODERATION = process.env.NEXT_PUBLIC_API_MODERATION_URL ?? "http://localhost:8002";
const REPORTING = process.env.NEXT_PUBLIC_API_REPORTING_URL ?? "http://localhost:8004";
const NOTIFICATION = process.env.NEXT_PUBLIC_API_NOTIFICATION_URL ?? "http://localhost:8003";

export const ingestionApi = axios.create({ baseURL: INGESTION });
export const moderationApi = axios.create({ baseURL: MODERATION });
export const reportingApi = axios.create({ baseURL: REPORTING });
export const notificationApi = axios.create({ baseURL: NOTIFICATION });

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Review {
  id: string;
  platform: string;
  external_id: string | null;
  reviewer_name: string | null;
  rating: number | null;
  content: string;
  review_date: string | null;
  ingested_at: string;
  url: string | null;
  is_processed: boolean;
}

export interface Classification {
  id: string;
  review_id: string;
  classified_at: string;
  model_used: string;
  overall_risk_score: number;
  is_insult: boolean;
  insult_confidence: number | null;
  is_spam: boolean;
  spam_confidence: number | null;
  is_fake: boolean;
  fake_confidence: number | null;
  has_false_claims: boolean;
  false_claims_confidence: number | null;
  is_toxic: boolean;
  toxic_confidence: number | null;
  reasoning: string | null;
  flagged_phrases: string[] | null;
}

export interface ModerationDraft {
  id: string;
  review_id: string;
  draft_type: "platform_report" | "owner_response" | "legal_notice";
  content: string;
  platform: string;
  status: string;
  created_at: string;
}

// ── API helpers ───────────────────────────────────────────────────────────────

export const reviewsApi = {
  list: (params?: { platform?: string; is_processed?: boolean }) =>
    ingestionApi.get<{ total: number; items: Review[] }>("/reviews", { params }),

  create: (data: Partial<Review>) =>
    ingestionApi.post<Review>("/reviews", data),

  createBatch: (items: Partial<Review>[]) =>
    ingestionApi.post<Review[]>("/reviews/batch", items),

  delete: (id: string) =>
    ingestionApi.delete(`/reviews/${id}`),
};

export const classifyApi = {
  classify: (reviewId: string) =>
    moderationApi.post<Classification>(`/classify/${reviewId}`),

  get: (reviewId: string) =>
    moderationApi.get<Classification>(`/classify/${reviewId}`),

  createDraft: (reviewId: string, draftType: ModerationDraft["draft_type"]) =>
    moderationApi.post<ModerationDraft>(`/classify/${reviewId}/drafts`, {
      draft_type: draftType,
    }),
};

export const reportsApi = {
  generate: (params: { format: "pdf" | "csv" | "json"; min_risk_score?: number }) =>
    reportingApi.post("/reports/generate", params),

  list: () =>
    reportingApi.get<{ id: string; created_at: string; format: string }[]>("/reports"),

  downloadUrl: (reportId: string) =>
    `${REPORTING}/reports/${reportId}/download`,
};
