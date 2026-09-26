import {
  apiDelete,
  apiGet,
  apiPost,
} from "../api/client";

import {
  getIdentityHeaders,
} from "../api/userIdentity";

import type {
  AddWatchlistItemRequest,
  WatchlistItem,
  WatchlistResponse,
} from "../types/watchlist";


const WATCHLIST_PATH =
  "/api/v1/watchlist";


export function getWatchlist(
  signal?: AbortSignal,
): Promise<WatchlistResponse> {
  return apiGet<
    WatchlistResponse
  >(
    WATCHLIST_PATH,
    signal,
    getIdentityHeaders(),
  );
}


export function addWatchlistItem(
  symbol: string,
  signal?: AbortSignal,
): Promise<WatchlistItem> {
  const request:
    AddWatchlistItemRequest = {
      symbol:
        symbol
          .trim()
          .toUpperCase(),
    };

  return apiPost<
    WatchlistItem,
    AddWatchlistItemRequest
  >(
    WATCHLIST_PATH,
    request,
    signal,
    getIdentityHeaders(),
  );
}


export function deleteWatchlistItem(
  symbol: string,
  signal?: AbortSignal,
): Promise<void> {
  const normalized =
    symbol
      .trim()
      .toUpperCase();

  return apiDelete(
    (
      `${WATCHLIST_PATH}/`
      + encodeURIComponent(
        normalized,
      )
    ),
    signal,
    getIdentityHeaders(),
  );
}