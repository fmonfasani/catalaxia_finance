export interface ApiResponse<T> {
  data: T;
  ok: true;
}

export interface ApiError {
  ok: false;
  error: string;
  code: "UNAUTHORIZED" | "RATE_LIMITED" | "PLAN_REQUIRED" | "NOT_FOUND" | "INTERNAL";
  detail?: string;
}

export type ApiResult<T> = ApiResponse<T> | ApiError;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobStatus {
  job_id: string;
  job_name: "precios" | "financials" | "ratios";
  status: "idle" | "running" | "success" | "error";
  started_at?: string;
  finished_at?: string;
  rows_processed?: number;
  error_message?: string;
  log_tail?: string[];  // últimas líneas del log
}

export interface HealthResponse {
  status: "ok" | "degraded";
  db: "connected" | "error";
  version: string;
  jobs: {
    precios: Pick<JobStatus, "status" | "finished_at">;
    financials: Pick<JobStatus, "status" | "finished_at">;
    ratios: Pick<JobStatus, "status" | "finished_at">;
  };
}
