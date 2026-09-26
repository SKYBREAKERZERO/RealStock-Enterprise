export type TradingSide = "BUY" | "SELL";
export type TradingOrderType = "MARKET" | "LIMIT";
export type TradingOrderStatus =
  | "NEW"
  | "PENDING"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "CANCELLED"
  | "REJECTED";

export interface TradingAccount {
  account_id: string;
  initial_cash: string;
  cash_balance: string;
}

export interface TradingPosition {
  symbol: string;
  quantity: number;
  average_cost: string;
  realized_pnl: string;
}

export interface TradingOrder {
  order_id: string;
  account_id: string;
  symbol: string;
  side: TradingSide;
  quantity: number;
  order_type: TradingOrderType;
  status: TradingOrderStatus;
  filled_quantity: number;
  limit_price: string | null;
}

export interface TradingExecution {
  execution_id: string;
  order_id: string;
  symbol: string;
  side: TradingSide;
  quantity: number;
  price: string;
}

export interface TradingTradeExecution {
  order: TradingOrder;
  execution: TradingExecution;
}

export interface SimulatedTradingQuote {
  symbol: string;
  market: string;
  bid_price: string;
  ask_price: string;
  bid_size: number;
  ask_size: number;
  timestamp: string;
}

export interface SetSimulatedTradingQuoteRequest {
  symbol: string;
  bid_price: string;
  ask_price: string;
  bid_size: number;
  ask_size: number;
  ttl_seconds: number;
}
