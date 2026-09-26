import {
  apiDelete,
  apiGet,
  apiPost,
  apiRequest,
} from "../api/client";

import {
  getIdentityHeaders,
} from "../api/userIdentity";

import type {
  AddPortfolioPositionRequest,
  CreatePortfolioRequest,
  Portfolio,
  PortfolioPosition,
  PortfolioValuation,
  UpdatePortfolioPositionRequest,
} from "../types/portfolio";


function portfolioPath(
  portfolioId: string,
): string {
  return (
    "/api/v1/portfolios/"
    + encodeURIComponent(
      portfolioId,
    )
  );
}


function positionPath(
  portfolioId: string,
  positionId: string,
): string {
  return (
    portfolioPath(
      portfolioId,
    )
    + "/positions/"
    + encodeURIComponent(
      positionId,
    )
  );
}


export function getPortfolios(
  signal?: AbortSignal,
): Promise<Portfolio[]> {
  return apiGet<Portfolio[]>(
    "/api/v1/portfolios",
    signal,
    getIdentityHeaders(),
  );
}


export function getPortfolio(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<Portfolio> {
  return apiGet<Portfolio>(
    portfolioPath(
      portfolioId,
    ),
    signal,
    getIdentityHeaders(),
  );
}


export function getPortfolioValuation(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<PortfolioValuation> {
  return apiGet<PortfolioValuation>(
    (
      portfolioPath(
        portfolioId,
      )
      + "/valuation"
    ),
    signal,
    getIdentityHeaders(),
  );
}


export function createPortfolio(
  request: CreatePortfolioRequest,
  signal?: AbortSignal,
): Promise<Portfolio> {
  return apiPost<
    Portfolio,
    CreatePortfolioRequest
  >(
    "/api/v1/portfolios",
    request,
    signal,
    getIdentityHeaders(),
  );
}


export function addPortfolioPosition(
  portfolioId: string,
  request: AddPortfolioPositionRequest,
  signal?: AbortSignal,
): Promise<PortfolioPosition> {
  return apiPost<
    PortfolioPosition,
    AddPortfolioPositionRequest
  >(
    (
      portfolioPath(
        portfolioId,
      )
      + "/positions"
    ),
    request,
    signal,
    getIdentityHeaders(),
  );
}


export function updatePortfolioPosition(
  portfolioId: string,
  positionId: string,
  request: UpdatePortfolioPositionRequest,
  signal?: AbortSignal,
): Promise<PortfolioPosition> {
  return apiRequest<PortfolioPosition>(
    positionPath(
      portfolioId,
      positionId,
    ),
    {
      method: "PATCH",
      body: request,
      signal,
      headers:
        getIdentityHeaders(),
    },
  );
}


export async function deletePortfolioPosition(
  portfolioId: string,
  positionId: string,
  signal?: AbortSignal,
): Promise<void> {
  await apiDelete(
    positionPath(
      portfolioId,
      positionId,
    ),
    signal,
    getIdentityHeaders(),
  );
}
