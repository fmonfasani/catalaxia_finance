/**
 * Flags de calidad de datos — nunca se estima, se marca.
 * Documentados en docs/06-decisiones-tecnicas.md
 */
export type QualityFlag =
  | "ni_fy"       // Net Income calculado por año fiscal, no TTM
  | "roe_ns"      // ROE no significativo (equity negativo)
  | "fx"          // empresa reporta en moneda no-USD (IFRS)
  | "mktcap_rev"  // market cap posiblemente invertido (data issue en SEC)
  | "stale"       // datos con más de 90 días sin actualizar
  | "ifrs_partial"; // empresa IFRS con mapeo incompleto

export interface RatioValue {
  value: number | null;
  flags: QualityFlag[];
  source: "us-gaap" | "ifrs-full" | "calculated";
  period_end?: string;  // YYYY-MM-DD del último período
}

export interface CompanyRatios {
  ticker: string;
  fiscal_year_end?: string;

  // Valuación
  per: RatioValue;           // Price / EPS TTM
  p_book: RatioValue;        // Price / Book Value
  ev_ebitda: RatioValue;     // Enterprise Value / EBITDA TTM
  ps: RatioValue;            // Price / Sales TTM

  // Rentabilidad
  margen_neto: RatioValue;   // Net Income / Revenue TTM
  margen_bruto: RatioValue;
  margen_ebitda: RatioValue;
  roe: RatioValue;           // Net Income TTM / Avg Equity
  roa: RatioValue;

  // Crecimiento (CAGR 5 años)
  revenue_cagr_5y: RatioValue;
  eps_cagr_5y: RatioValue;

  // Deuda
  deuda_equity: RatioValue;
  deuda_ebitda: RatioValue;
  deuda_lp_ebitda: RatioValue;

  // Flujo de caja
  fcf_yield: RatioValue;     // FCF / Market Cap
  fcfonce_equity_lp: RatioValue;
  fcfonce_neto_caja: RatioValue;

  // Dividendos
  dividend_yield: RatioValue;
  payout_ratio: RatioValue;

  // EPS
  eps_ttm: RatioValue;
  eps_fy: RatioValue;

  updated_at: string;
}
