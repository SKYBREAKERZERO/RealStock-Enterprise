import {
  apiGet,
} from "../api/client";

import {
  getIdentityHeaders,
} from "../api/userIdentity";

import type {
  OutboxEventListResponse,
  OutboxStatusFilter,
  OutboxSummaryResponse,
} from "../types/outbox";


export interface GetOutboxEventsOptions {
  status?: OutboxStatusFilter;
  limit?: number;
  eventType?: string;
  aggregateId?: string;
  signal?: AbortSignal;
}


export function getOutboxEvents(
  options:
    GetOutboxEventsOptions = {},
): Promise<OutboxEventListResponse> {
  const params =
    new URLSearchParams();

  params.set(
    "status",
    options.status ?? "all",
  );

  params.set(
    "limit",
    String(options.limit ?? 50),
  );

  const eventType =
    options.eventType?.trim();

  if (eventType) {
    params.set(
      "event_type",
      eventType,
    );
  }

  const aggregateId =
    options.aggregateId?.trim();

  if (aggregateId) {
    params.set(
      "aggregate_id",
      aggregateId,
    );
  }

  return apiGet<
    OutboxEventListResponse
  >(
    (
      "/api/v1/outbox/events?"
      + params.toString()
    ),
    options.signal,
    getIdentityHeaders(),
  );
}


export function getOutboxSummary(
  signal?: AbortSignal,
): Promise<OutboxSummaryResponse> {
  return apiGet<
    OutboxSummaryResponse
  >(
    "/api/v1/outbox/summary",
    signal,
    getIdentityHeaders(),
  );
}
