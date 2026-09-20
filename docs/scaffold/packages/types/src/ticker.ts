export type Sector =
  | "Technology"
  | "Healthcare"
  | "Financials"
  | "Energy"
  | "Consumer Discretionary"
  | "Consumer Staples"
  | "Industrials"
  | "Materials"
  | "Real Estate"
  | "Utilities"
  | "Communication Services";

export type Country = "US" | "AR" | "BR" | "MX" | "CL" | "CO" | "PE" | string;

export type Taxonomy = "us-gaap" | "ifrs-full";

export type MarketCapSize = "large" | "mid" | "small" | "micro";

export interface Company {
  ticker: string;
  cik?: string;           // SEC EDGAR CIK (solo empresas US/ADRs)
  cuit?: string;          // CUIT argentino (solo empresas CNV)
  name: string;
  sector: Sector;
  country: Country;
  taxonomy: Taxonomy;
  market_cap_usd?: number;
  size: MarketCapSize;
  is_cedear: boolean;     // cotiza como CEDEAR en Argentina
  has_cnv_data: boolean;  // tiene balances en la CNV argentina
}

export interface PriceData {
  ticker: string;
  price_usd?: number;
  price_ars?: number;     // precio en pesos (BYMA)
  mep_rate?: number;      // tipo de cambio MEP usado
  week_52_high?: number;
  week_52_low?: number;
  updated_at: string;     // ISO 8601
}
