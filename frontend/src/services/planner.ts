export interface PlanRequest {
  query: string;
  start_city?: string;
  target_city?: string;
  target_cities?: string[];
  departure_date?: string;
  return_date?: string;
  days?: number;
  people_number?: number;
  budget?: number;
  use_realtime?: boolean;
}

export interface ConversationGenerateRequest extends PlanRequest {}

export interface ManualPlanEditRequest {
  plan: TravelPlan;
  base_version_id?: string | null;
  conflict_override?: boolean;
  validation_override?: boolean;
}

export interface PlanActivity {
  day?: number;
  start_time?: string;
  end_time?: string;
  type?: string;
  title?: string;
  description?: string;
  TrainID?: string;
  start?: string;
  end?: string;
  position?: string;
  city?: string;
  transportation?: string;
  price?: number | string;
  price_source?: string;
  seat_type?: string;
  seat_label?: string;
  tickets?: number;
  ticket_left?: string;
  duration?: string;
  train_ticket?: Record<string, unknown>;
  rooms?: number;
  cost?: number | string;
  recommended_food?: string;
  amap_poi?: Record<string, unknown>;
}

export interface BudgetBreakdown {
  label: string;
  amount: number | string;
}

export interface PlanDay {
  day?: number;
  title?: string;
  summary?: string;
  image?: string;
  location?: string;
  accommodation?: string;
  budget?: BudgetBreakdown[];
  activities?: PlanActivity[];
}

export type FlatPlanActivity = PlanActivity & {
  day: number;
};

export interface TravelPlan {
  start_city?: string;
  target_city?: string;
  target_cities?: string[];
  departure_date?: string;
  return_date?: string;
  date_source?: string;
  days?: number;
  people_number?: number;
  budget?: number;
  total_cost?: number;
  itinerary?: Array<PlanDay | FlatPlanActivity>;
  llm_summary?: string;
  [key: string]: unknown;
}

export interface PlanError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface RealtimeEvidence {
  title: string;
  url: string;
  content_summary: string;
  source: string;
  fetched_at: string;
  expires_at: string;
  confidence: number;
  risk_flags: string[];
}

export interface PlanMeta {
  request_id?: string;
  realtime?: {
    enabled?: boolean;
    provider?: string;
    cache_hit?: boolean;
    query?: string;
    fallback_queries?: string[];
    searched_queries?: string[];
    success?: boolean;
    evidence_count?: number;
    evidence?: RealtimeEvidence[];
    usage?: Record<string, unknown>;
    error?: Record<string, unknown> | null;
  };
  history_reuse?: Record<string, unknown>;
  memory_write?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface PlanResponse {
  success: boolean;
  plan?: TravelPlan;
  meta?: PlanMeta;
  error?: PlanError;
}

export interface ConversationSummary {
  id: string;
  title: string;
  status: "active" | "archived" | string;
  current_version_id?: string | null;
  created_at: string;
  updated_at: string;
  current_plan_summary?: string | null;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  sequence: number;
  role: "user" | "assistant" | string;
  content: string;
  plan_version_id?: string | null;
  request_id?: string | null;
  created_at: string;
}

export interface PlanVersionSummary {
  id: string;
  conversation_id: string;
  version_number: number;
  parent_version_id?: string | null;
  source: "ai_generated" | "ai_edit" | "manual_edit" | "rollback" | "recommended" | string;
  summary?: string | null;
  total_cost?: number | null;
  validation_warnings?: string[];
  request_id?: string | null;
  created_at: string;
}

export interface ConversationDetailResponse {
  success: boolean;
  conversation?: ConversationSummary | null;
  messages: ConversationMessage[];
  versions: PlanVersionSummary[];
  current_plan?: TravelPlan | null;
  error?: PlanError;
}

export interface ConversationListResponse {
  success: boolean;
  conversations: ConversationSummary[];
  error?: PlanError;
}

export interface ConversationMessageResponse {
  success: boolean;
  conversation?: ConversationSummary | null;
  message?: ConversationMessage | null;
  assistant_message?: ConversationMessage | null;
  version?: PlanVersionSummary | null;
  current_plan?: TravelPlan | null;
  error?: PlanError;
}

export interface RecommendationItem {
  id: string;
  title: string;
  summary: string;
  plan: TravelPlan;
  source: string;
  conversation_id?: string | null;
  version_id?: string | null;
}

export interface RecommendedPlansResponse {
  success: boolean;
  recommendations: RecommendationItem[];
  error?: PlanError;
}

export interface RuntimeHealth {
  ok: boolean;
  deepseek_key_configured: boolean;
  tavily_key_configured?: boolean;
  tavily_real_time_enabled?: boolean;
  database_ready: boolean;
  missing_database_paths: string[];
}

export interface ExtractedFields {
  start_city?: string | null;
  target_city?: string | null;
  days?: number | null;
  people_number?: number | null;
  budget?: number | null;
  preferences?: string[];
}

export interface FieldExtractionResponse {
  success: boolean;
  fields?: ExtractedFields;
  error?: PlanError;
}

export interface ImageSearchItem {
  title?: string | null;
  url: string;
  thumbnail_url?: string | null;
  width?: number | null;
  height?: number | null;
}

export interface ImageSearchResponse {
  success: boolean;
  images: ImageSearchItem[];
  error?: PlanError;
}

export async function requestPlan(payload: PlanRequest): Promise<PlanResponse> {
  const response = await fetch("/api/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await response.json()) as PlanResponse;

  if (!response.ok) {
    return {
      success: false,
      error: {
        code: `HTTP_${response.status}`,
        message: data.error?.message || "请求失败，请稍后重试。",
        details: data as unknown as Record<string, unknown>,
      },
    };
  }

  return data;
}

async function parseApiResponse<T extends { success: boolean; error?: PlanError }>(
  response: Response,
  fallbackMessage: string,
): Promise<T> {
  const data = (await response.json()) as T;

  if (!response.ok) {
    return {
      ...data,
      success: false,
      error: {
        code: `HTTP_${response.status}`,
        message: data.error?.message || fallbackMessage,
        details: data as unknown as Record<string, unknown>,
      },
    };
  }

  return data;
}

export async function requestConversations(): Promise<ConversationListResponse> {
  const response = await fetch("/api/conversations", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  return parseApiResponse<ConversationListResponse>(response, "读取历史规划失败，请稍后重试。");
}

export async function createConversation(message: string): Promise<ConversationDetailResponse> {
  const response = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return parseApiResponse<ConversationDetailResponse>(response, "创建旅行规划失败，请稍后重试。");
}

export async function requestConversationDetail(conversationId: string): Promise<ConversationDetailResponse> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  return parseApiResponse<ConversationDetailResponse>(response, "读取规划详情失败，请稍后重试。");
}

export async function sendConversationMessage(
  conversationId: string,
  message: string,
  options: { base_version_id?: string | null; conflict_override?: boolean } = {},
): Promise<ConversationMessageResponse> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      base_version_id: options.base_version_id,
      conflict_override: options.conflict_override || false,
    }),
  });
  return parseApiResponse<ConversationMessageResponse>(response, "发送修改要求失败，请稍后重试。");
}

export async function generateConversationPlan(
  conversationId: string,
  payload: ConversationGenerateRequest,
): Promise<ConversationMessageResponse> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseApiResponse<ConversationMessageResponse>(response, "确认清单并生成行程失败，请稍后重试。");
}

export async function restorePlanVersion(conversationId: string, versionId: string): Promise<ConversationMessageResponse> {
  const response = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/versions/${encodeURIComponent(versionId)}/restore`,
    {
      method: "POST",
      headers: { Accept: "application/json" },
    },
  );
  return parseApiResponse<ConversationMessageResponse>(response, "回退版本失败，请稍后重试。");
}

export async function archiveConversation(conversationId: string): Promise<ConversationDetailResponse> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/archive`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return parseApiResponse<ConversationDetailResponse>(response, "归档规划失败，请稍后重试。");
}

export async function restoreConversation(conversationId: string): Promise<ConversationDetailResponse> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/restore`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return parseApiResponse<ConversationDetailResponse>(response, "恢复规划失败，请稍后重试。");
}

export async function requestRecommendedPlans(): Promise<RecommendedPlansResponse> {
  const response = await fetch("/api/recommended-plans", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  return parseApiResponse<RecommendedPlansResponse>(response, "读取推荐行程失败，请稍后重试。");
}

export async function openRecommendedPlan(recommendationId: string): Promise<ConversationDetailResponse> {
  const response = await fetch(`/api/recommended-plans/${encodeURIComponent(recommendationId)}/open`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  return parseApiResponse<ConversationDetailResponse>(response, "打开推荐行程失败，请稍后重试。");
}

export async function saveManualPlanEdit(
  conversationId: string,
  payload: ManualPlanEditRequest,
): Promise<ConversationMessageResponse> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/manual-edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseApiResponse<ConversationMessageResponse>(response, "保存手动编辑失败，请稍后重试。");
}

export async function requestFieldExtraction(query: string): Promise<FieldExtractionResponse> {
  const response = await fetch("/api/extract-fields", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = (await response.json()) as FieldExtractionResponse;

  if (!response.ok) {
    return {
      success: false,
      error: {
        code: `HTTP_${response.status}`,
        message: data.error?.message || "智能填表失败，请稍后重试。",
        details: data as unknown as Record<string, unknown>,
      },
    };
  }

  return data;
}

export async function requestImages(keyword: string): Promise<ImageSearchResponse> {
  const params = new URLSearchParams({ q: keyword });
  const response = await fetch(`/api/images?${params.toString()}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  const data = (await response.json()) as ImageSearchResponse;

  if (!response.ok) {
    return {
      success: false,
      images: [],
      error: {
        code: `HTTP_${response.status}`,
        message: data.error?.message || "图片搜索失败。",
        details: data as unknown as Record<string, unknown>,
      },
    };
  }

  return data;
}

export async function requestRuntimeHealth(): Promise<RuntimeHealth> {
  const response = await fetch("/api/health", {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`运行状态检查失败：HTTP ${response.status}`);
  }
  return (await response.json()) as RuntimeHealth;
}
