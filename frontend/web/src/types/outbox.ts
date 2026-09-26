export type OutboxEventStatus =
  | "pending"
  | "published"
  | "failed";

export type OutboxStatusFilter =
  | "all"
  | OutboxEventStatus;

export interface OutboxEvent {
  event_id: string;
  aggregate_type: string;
  aggregate_id: string;
  event_type: string;
  schema_version: number;
  source: string;
  occurred_at: string;
  created_at: string;
  published_at: string | null;
  attempt_count: number;
  next_attempt_at: string;
  last_error: string | null;
  locked_by: string | null;
  locked_until: string | null;
  status: OutboxEventStatus;
}

export interface OutboxEventListResponse {
  items: OutboxEvent[];
  count: number;
  status_filter: OutboxStatusFilter;
}

export interface OutboxSummaryResponse {
  total_count: number;
  pending_count: number;
  published_count: number;
  failed_count: number;
  unpublished_count: number;
  oldest_unpublished_at: string | null;
}
