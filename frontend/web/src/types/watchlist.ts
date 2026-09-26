export interface WatchlistItem {
  watchlist_item_id: string;

  symbol: string;

  created_at: string;
}


export interface WatchlistResponse {
  items:
    WatchlistItem[];

  count: number;
}


export interface AddWatchlistItemRequest {
  symbol: string;
}