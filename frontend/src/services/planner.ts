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
  transportation?: string;
  price?: number | string;
  tickets?: number;
  rooms?: number;
  cost?: number | string;
  recommended_food?: string;
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

export interface PlanResponse {
  success: boolean;
  plan?: TravelPlan;
  meta?: Record<string, unknown>;
  error?: PlanError;
}

export interface RuntimeHealth {
  ok: boolean;
  deepseek_key_configured: boolean;
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
