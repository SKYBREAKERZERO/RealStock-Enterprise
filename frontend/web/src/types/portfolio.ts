export interface PortfolioPosition {
  position_id: string;
  symbol: string;
  market: string;

  quantity: string;
  average_cost: string;
  cost_basis: string;

  created_at: string;
  updated_at: string;
}

export interface Portfolio {
  portfolio_id: string;
  user_id: string;

  name: string;
  currency: string;

  positions: PortfolioPosition[];

  total_cost_basis: string;

  created_at: string;
  updated_at: string;
}

export interface PortfolioValuationPosition {
  position_id: string;

  symbol: string;
  market: string;

  quantity: string;
  average_cost: string;
  cost_basis: string;

  market_price: string | null;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_percent: string | null;
  quote_timestamp: string | null;

  quote_available: boolean;
}

export interface PortfolioValuation {
  portfolio_id: string;

  total_cost_basis: string;
  priced_cost_basis: string;

  total_market_value: string;
  total_unrealized_pnl: string;

  priced_positions: number;
  missing_quotes: number;

  valuation_complete: boolean;

  positions: PortfolioValuationPosition[];
}

export interface CreatePortfolioRequest {
  name: string;
  currency: string;
}

export interface AddPortfolioPositionRequest {
  symbol: string;
  market: string;

  quantity: string;
  average_cost: string;
}

export interface UpdatePortfolioPositionRequest {
  quantity?: string;
  average_cost?: string;
}
