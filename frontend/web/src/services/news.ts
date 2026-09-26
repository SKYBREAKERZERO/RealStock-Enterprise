import {
  apiGet,
} from "../api/client";


export interface NewsItem {
  id: string;

  published_at: string;

  title: string;

  summary: string;

  source?: string;

  url?: string;
}


export interface NewsResponse {
  items: NewsItem[];

  count: number;

  cached?: boolean;
}


export function getNews(
  signal?: AbortSignal,
): Promise<NewsResponse> {
  return apiGet<NewsResponse>(
    "/api/v1/news?limit=20",
    signal,
  );
}