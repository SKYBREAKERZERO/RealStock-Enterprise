import {
  apiGet,
} from "../api/client";

import type {
  MarketBatchQuoteResponse,
  MarketPriceResponse,
  MarketQuoteResponse,
} from "../types/market";


export type MarketCandleRange =
  | "day"
  | "week"
  | "month";


export interface MarketCandleItem {
  time: string;

  open: number;

  high: number;

  low: number;

  close: number;
}


export interface MarketCandlesResponse {
  symbol: string;

  range: MarketCandleRange;

  interval: string;

  items: MarketCandleItem[];
}


function normalizeSymbol(
  symbol: string,
): string {
  const normalized =
    symbol
      .trim()
      .toUpperCase();

  if (!normalized) {
    throw new Error(
      "Symbol must not be empty",
    );
  }

  return normalized;
}


export function getMarketPrice(
  symbol: string,
  signal?: AbortSignal,
): Promise<MarketPriceResponse> {
  const normalized =
    normalizeSymbol(
      symbol,
    );

  return apiGet<
    MarketPriceResponse
  >(
    (
      "/api/v1/market/price/"
      + encodeURIComponent(
        normalized,
      )
    ),
    signal,
  );
}


export async function getMarketQuote(
  symbol: string,
  signal?: AbortSignal,
): Promise<MarketQuoteResponse> {
  const normalized =
    normalizeSymbol(
      symbol,
    );

  const response =
    await getMarketQuotes(
      [
        normalized,
      ],
      signal,
    );

  const item =
    response.items.find(
      (
        candidate,
      ) =>
        candidate.symbol
        === normalized,
    );

  if (!item) {
    throw new Error(
      (
        "Market quote response "
        + `missing for ${normalized}`
      ),
    );
  }

  if (!item.quote) {
    throw new Error(
      item.error
      ?? (
        "Market quote unavailable "
        + `for ${normalized}`
      ),
    );
  }

  return item.quote;
}


export function getMarketQuotes(
  symbols: string[],
  signal?: AbortSignal,
): Promise<MarketBatchQuoteResponse> {
  const normalized =
    Array.from(
      new Set(
        symbols.map(
          normalizeSymbol,
        ),
      ),
    );

  if (
    normalized.length
    === 0
  ) {
    throw new Error(
      "At least one symbol is required",
    );
  }

  /*
   * encodeURIComponent() intentionally
   * encodes commas.
   *
   * FastAPI decodes the query parameter
   * before parsing the comma-separated
   * symbol list.
   */
  const value =
    encodeURIComponent(
      normalized.join(
        ",",
      ),
    );

  return apiGet<
    MarketBatchQuoteResponse
  >(
    (
      "/api/v1/market/quotes"
      + `?symbols=${value}`
    ),
    signal,
  );
}


export function getMarketCandles(
  symbol: string,
  range: MarketCandleRange,
  signal?: AbortSignal,
): Promise<MarketCandlesResponse> {
  const normalized =
    normalizeSymbol(
      symbol,
    );

  const symbolValue =
    encodeURIComponent(
      normalized,
    );

  const rangeValue =
    encodeURIComponent(
      range,
    );

  return apiGet<
    MarketCandlesResponse
  >(
    (
      "/api/v1/market/candles"
      + `?symbol=${symbolValue}`
      + `&range=${rangeValue}`
    ),
    signal,
  );
}