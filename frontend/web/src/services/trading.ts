import {
  apiGet,
  apiPost,
} from "../api/client";

import {
  getIdentityHeaders,
} from "../api/userIdentity";

import type {
  SetSimulatedTradingQuoteRequest,
  SimulatedTradingQuote,
  TradingAccount,
  TradingExecution,
  TradingOrder,
  TradingPosition,
  TradingSide,
  TradingTradeExecution,
} from "../types/trading";


const BASE = "/api/v1/trading";


export function getTradingAccount(
  signal?: AbortSignal,
): Promise<TradingAccount> {
  return apiGet<TradingAccount>(
    `${BASE}/account`,
    signal,
    getIdentityHeaders(),
  );
}


export function createTradingAccount(
  initialCash: string,
): Promise<TradingAccount> {
  return apiPost<
    TradingAccount,
    { initial_cash: string }
  >(
    `${BASE}/account`,
    {
      initial_cash: initialCash,
    },
    undefined,
    getIdentityHeaders(),
  );
}


export function getTradingPositions(
  signal?: AbortSignal,
): Promise<TradingPosition[]> {
  return apiGet<TradingPosition[]>(
    `${BASE}/positions`,
    signal,
    getIdentityHeaders(),
  );
}


export function getOpenTradingOrders(
  signal?: AbortSignal,
): Promise<TradingOrder[]> {
  return apiGet<TradingOrder[]>(
    `${BASE}/orders/open?limit=100`,
    signal,
    getIdentityHeaders(),
  );
}


export function getTradingExecutions(
  signal?: AbortSignal,
): Promise<TradingExecution[]> {
  return apiGet<TradingExecution[]>(
    `${BASE}/executions?limit=50`,
    signal,
    getIdentityHeaders(),
  );
}


export function placeMarketOrder(
  side: TradingSide,
  symbol: string,
  quantity: number,
): Promise<TradingTradeExecution> {
  return apiPost<
    TradingTradeExecution,
    {
      symbol: string;
      quantity: number;
    }
  >(
    `${BASE}/orders/market/${side.toLowerCase()}`,
    {
      symbol,
      quantity,
    },
    undefined,
    getIdentityHeaders(),
  );
}


export function placeLimitOrder(
  side: TradingSide,
  symbol: string,
  quantity: number,
  limitPrice: string,
): Promise<TradingOrder> {
  return apiPost<
    TradingOrder,
    {
      symbol: string;
      quantity: number;
      limit_price: string;
    }
  >(
    `${BASE}/orders/limit/${side.toLowerCase()}`,
    {
      symbol,
      quantity,
      limit_price: limitPrice,
    },
    undefined,
    getIdentityHeaders(),
  );
}


export function cancelTradingOrder(
  orderId: string,
): Promise<TradingOrder> {
  return apiPost<
    TradingOrder,
    Record<string, never>
  >(
    `${BASE}/orders/${encodeURIComponent(orderId)}/cancel`,
    {},
    undefined,
    getIdentityHeaders(),
  );
}


export function getSimulatedTradingQuote(
  symbol: string,
  signal?: AbortSignal,
): Promise<SimulatedTradingQuote> {
  return apiGet<SimulatedTradingQuote>(
    `${BASE}/simulation/quote/${encodeURIComponent(symbol)}`,
    signal,
    getIdentityHeaders(),
  );
}


export function setSimulatedTradingQuote(
  request: SetSimulatedTradingQuoteRequest,
): Promise<SimulatedTradingQuote> {
  return apiPost<
    SimulatedTradingQuote,
    SetSimulatedTradingQuoteRequest
  >(
    `${BASE}/simulation/quote`,
    request,
    undefined,
    getIdentityHeaders(),
  );
}
