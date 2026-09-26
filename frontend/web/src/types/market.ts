export interface FiftyTwoWeekRange {
  low: string;
  high: string;

  low_change: string;
  high_change: string;

  low_change_percent:
    string;

  high_change_percent:
    string;

  range: string;
}


export interface MarketPriceResponse {
  symbol: string;
  price: string;
}


export interface MarketQuoteResponse {
  symbol: string;
  name: string;

  exchange: string;
  mic_code: string;
  currency: string;

  open: string;
  high: string;
  low: string;
  close: string;

  previous_close: string;

  change: string;
  percent_change: string;

  volume: number;
  average_volume: number;

  is_market_open: boolean;

  timestamp: string;

  last_quote_at:
    string
    | null;

  fifty_two_week:
    FiftyTwoWeekRange
    | null;
}


export type MarketBatchQuoteStatus =
  | "ok"
  | "stale"
  | "error";


export type MarketBatchQuoteSource =
  | "provider"
  | "cache"
  | "stale_cache";


export interface MarketBatchQuoteItem {
  symbol: string;

  status:
    MarketBatchQuoteStatus;

  source:
    MarketBatchQuoteSource
    | null;

  quote:
    MarketQuoteResponse
    | null;

  error:
    string
    | null;
}


export interface MarketBatchQuoteResponse {
  requested: number;
  succeeded: number;
  stale: number;
  failed: number;

  items:
    MarketBatchQuoteItem[];
}