import type { Company, PriceData } from "./ticker";
import type { CompanyRatios, QualityFlag } from "./ratio";

export type Plan = "free" | "pro" | "team" | "catalaxia";

export interface ScreenerFilters {
  // Valuación
  per_min?: number;
  per_max?: number;
  p_book_max?: number;
  ev_ebitda_max?: number;

  // Rentabilidad
  roe_min?: number;
  margen_neto_min?: number;

  // Deuda
  deuda_ebitda_max?: number;

  // Crecimiento
  revenue_cagr_5y_min?: number;

  // Categorías
  sector?: string[];
  country?: string[];
  is_cedear?: boolean;
  has_cnv_data?: boolean;

  // Calidad de datos
  only_clean?: boolean;    // excluir filas con flags (false por defecto)
  exclude_flags?: QualityFlag[];

  // Paginación
  page?: number;
  page_size?: number;      // 25 | 50 | 100 (pro+)
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export interface ScreenerRow extends Pick<Company, "ticker" | "name" | "sector" | "country" | "is_cedear" | "has_cnv_data"> {
  price_usd?: number;
  price_ars?: number;
  market_cap_usd?: number;

  // Ratios (valores directos para la tabla)
  per?: number | null;
  per_flags?: QualityFlag[];
  roe?: number | null;
  roe_flags?: QualityFlag[];
  margen_neto?: number | null;
  deuda_ebitda?: number | null;
  ev_ebitda?: number | null;
  eps_ttm?: number | null;
  revenue_cagr_5y?: number | null;
  dividend_yield?: number | null;
  p_book?: number | null;

  // Estado general de calidad
  has_flags: boolean;
  all_flags: QualityFlag[];
}

export interface ScreenerResponse {
  rows: ScreenerRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  plan_limit?: number;    // null si plan no tiene límite
}

export interface TickerDetailResponse {
  company: Company;
  price: PriceData;
  ratios: CompanyRatios;
  // historial de ratios anuales (hasta 6 años)
  ratios_history: Array<{
    fiscal_year: number;
    per?: number;
    roe?: number;
    margen_neto?: number;
    revenue_usd?: number;
    eps?: number;
  }>;
}
