import {
  useMemo,
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import {
  useQuery,
} from "@tanstack/react-query";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RadioTower,
  RefreshCcw,
  Search,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  CURRENT_USER_ID,
} from "../api/userIdentity";

import {
  getOutboxEvents,
  getOutboxSummary,
} from "../services/outbox";

import type {
  OutboxEvent,
  OutboxEventStatus,
  OutboxStatusFilter,
} from "../types/outbox";

import "../outbox.css";


function formatDateTime(
  value: string | null,
  isZh: boolean,
): string {
  if (!value) {
    return "—";
  }

  const date =
    new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value;
  }

  return new Intl.DateTimeFormat(
    isZh
      ? "zh-CN"
      : "en-US",
    {
      dateStyle: "medium",
      timeStyle: "medium",
    },
  ).format(date);
}


function getStatusLabel(
  status: OutboxEventStatus,
  isZh: boolean,
): string {
  if (status === "published") {
    return isZh
      ? "已发布"
      : "Published";
  }

  if (status === "failed") {
    return isZh
      ? "失败"
      : "Failed";
  }

  return isZh
    ? "待发布"
    : "Pending";
}


function StatusBadge({
  status,
  isZh,
}: {
  status: OutboxEventStatus;
  isZh: boolean;
}) {
  const icon =
    status === "published"
      ? (
        <CheckCircle2
          size={13}
        />
      )
      : status === "failed"
        ? (
          <AlertTriangle
            size={13}
          />
        )
        : (
          <Clock3
            size={13}
          />
        );

  return (
    <span
      className={
        `outbox-status ${status}`
      }
    >
      {icon}
      {getStatusLabel(
        status,
        isZh,
      )}
    </span>
  );
}


function EventRow({
  event,
  isZh,
}: {
  event: OutboxEvent;
  isZh: boolean;
}) {
  return (
    <tr>
      <td>
        <StatusBadge
          status={event.status}
          isZh={isZh}
        />
      </td>

      <td>
        <div
          className="outbox-event-type"
        >
          <strong
            title={event.event_type}
          >
            {event.event_type}
          </strong>

          <span>
            v{event.schema_version}
            {" · "}
            {event.source}
          </span>
        </div>
      </td>

      <td>
        <div
          className="outbox-aggregate"
        >
          <strong
            title={event.aggregate_id}
          >
            {event.aggregate_id}
          </strong>

          <span>
            {event.aggregate_type}
          </span>
        </div>
      </td>

      <td
        className="outbox-attempts"
      >
        {event.attempt_count}
      </td>

      <td>
        <div
          className="outbox-time"
        >
          <strong>
            {formatDateTime(
              event.created_at,
              isZh,
            )}
          </strong>

          <span>
            {isZh
              ? "创建时间"
              : "Created"}
          </span>
        </div>
      </td>

      <td>
        <div
          className="outbox-time"
        >
          <strong>
            {formatDateTime(
              event.published_at,
              isZh,
            )}
          </strong>

          <span>
            {isZh
              ? "发布时间"
              : "Published"}
          </span>
        </div>
      </td>

      <td>
        {event.last_error
          ? (
            <span
              className="outbox-error-text"
              title={event.last_error}
            >
              {event.last_error}
            </span>
          )
          : "—"}
      </td>
    </tr>
  );
}


export function OutboxEventsPage() {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language
      .startsWith("zh");

  const [
    status,
    setStatus,
  ] = useState<
    OutboxStatusFilter
  >("all");

  const [
    eventTypeInput,
    setEventTypeInput,
  ] = useState("");

  const [
    aggregateIdInput,
    setAggregateIdInput,
  ] = useState("");

  const [
    eventTypeFilter,
    setEventTypeFilter,
  ] = useState("");

  const [
    aggregateIdFilter,
    setAggregateIdFilter,
  ] = useState("");

  const summaryQuery =
    useQuery({
      queryKey: [
        "outbox-summary",
        CURRENT_USER_ID,
      ],
      queryFn: ({
        signal,
      }) =>
        getOutboxSummary(
          signal,
        ),
      staleTime: 10_000,
      refetchInterval: 15_000,
      retry: 1,
    });

  const eventsQuery =
    useQuery({
      queryKey: [
        "outbox-events",
        CURRENT_USER_ID,
        status,
        eventTypeFilter,
        aggregateIdFilter,
      ],
      queryFn: ({
        signal,
      }) =>
        getOutboxEvents({
          status,
          limit: 50,
          eventType:
            eventTypeFilter,
          aggregateId:
            aggregateIdFilter,
          signal,
        }),
      staleTime: 10_000,
      refetchInterval: 15_000,
      retry: 1,
    });

  const events =
    eventsQuery.data?.items
    ?? [];

  const summary =
    summaryQuery.data;

  const oldestAgeLabel =
    useMemo(
      () => {
        if (
          !summary
          || !summary
            .oldest_unpublished_at
        ) {
          return isZh
            ? "当前无未发布事件"
            : "No unpublished events";
        }

        return (
          (
            isZh
              ? "最早未发布："
              : "Oldest unpublished: "
          )
          + formatDateTime(
            summary
              .oldest_unpublished_at,
            isZh,
          )
        );
      },
      [
        isZh,
        summary,
      ],
    );

  function submitFilters(
    event:
      FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setEventTypeFilter(
      eventTypeInput.trim(),
    );

    setAggregateIdFilter(
      aggregateIdInput.trim(),
    );
  }

  function refreshAll() {
    void summaryQuery.refetch();
    void eventsQuery.refetch();
  }

  const refreshing =
    summaryQuery.isFetching
    || eventsQuery.isFetching;

  return (
    <section
      className={
        "page-section "
        + "outbox-page"
      }
    >
      <div
        className={
          "page-card "
          + "outbox-header-card"
        }
      >
        <div
          className="outbox-header-copy"
        >
          <h2>
            {isZh
              ? "Outbox 事件"
              : "Outbox Events"}
          </h2>

          <p>
            {isZh
              ? (
                "PostgreSQL Transactional Outbox "
                + "只读运营视图"
              )
              : (
                "Read-only operational view of "
                + "the PostgreSQL transactional outbox"
              )}
          </p>
        </div>

        <button
          type="button"
          className="outbox-refresh-button"
          onClick={refreshAll}
          disabled={refreshing}
        >
          <RefreshCcw
            size={16}
          />

          {refreshing
            ? (
              isZh
                ? "刷新中"
                : "Refreshing"
            )
            : (
              isZh
                ? "刷新"
                : "Refresh"
            )}
        </button>
      </div>

      <div
        className="outbox-summary-grid"
      >
        <article
          className={
            "dashboard-kpi-card "
            + "outbox-summary-card"
          }
        >
          <div
            className="kpi-card-header"
          >
            <span>
              {isZh
                ? "待发布"
                : "Pending"}
            </span>

            <Clock3
              size={17}
            />
          </div>

          <strong>
            {summaryQuery.isPending
              ? "…"
              : (
                summary
                  ?.pending_count
                ?? 0
              )}
          </strong>

          <small>
            {oldestAgeLabel}
          </small>
        </article>

        <article
          className={
            "dashboard-kpi-card "
            + "outbox-summary-card"
          }
        >
          <div
            className="kpi-card-header"
          >
            <span>
              {isZh
                ? "已发布"
                : "Published"}
            </span>

            <CheckCircle2
              size={17}
            />
          </div>

          <strong>
            {summaryQuery.isPending
              ? "…"
              : (
                summary
                  ?.published_count
                ?? 0
              )}
          </strong>

          <small>
            {isZh
              ? "已成功发送至事件总线"
              : "Successfully published"}
          </small>
        </article>

        <article
          className={
            "dashboard-kpi-card "
            + "outbox-summary-card"
          }
        >
          <div
            className="kpi-card-header"
          >
            <span>
              {isZh
                ? "失败"
                : "Failed"}
            </span>

            <AlertTriangle
              size={17}
            />
          </div>

          <strong>
            {summaryQuery.isPending
              ? "…"
              : (
                summary
                  ?.failed_count
                ?? 0
              )}
          </strong>

          <small>
            {isZh
              ? "等待重试的发布失败事件"
              : "Publish failures awaiting retry"}
          </small>
        </article>

        <article
          className={
            "dashboard-kpi-card "
            + "outbox-summary-card"
          }
        >
          <div
            className="kpi-card-header"
          >
            <span>
              {isZh
                ? "事件总数"
                : "Total Events"}
            </span>

            <RadioTower
              size={17}
            />
          </div>

          <strong>
            {summaryQuery.isPending
              ? "…"
              : (
                summary
                  ?.total_count
                ?? 0
              )}
          </strong>

          <small>
            {isZh
              ? (
                `未发布 ${
                  summary
                    ?.unpublished_count
                  ?? 0
                }`
              )
              : (
                `Unpublished ${
                  summary
                    ?.unpublished_count
                  ?? 0
                }`
              )}
          </small>
        </article>
      </div>

      <div
        className="page-card"
      >
        <form
          className="outbox-filter-panel"
          onSubmit={submitFilters}
        >
          <div
            className="outbox-filter-field"
          >
            <label
              htmlFor="outbox-status"
            >
              {isZh
                ? "状态"
                : "Status"}
            </label>

            <select
              id="outbox-status"
              value={status}
              onChange={(
                event,
              ) => {
                setStatus(
                  event.target.value as OutboxStatusFilter,
                );
              }}
            >
              <option
                value="all"
              >
                {isZh
                  ? "全部"
                  : "All"}
              </option>

              <option
                value="pending"
              >
                {isZh
                  ? "待发布"
                  : "Pending"}
              </option>

              <option
                value="published"
              >
                {isZh
                  ? "已发布"
                  : "Published"}
              </option>

              <option
                value="failed"
              >
                {isZh
                  ? "失败"
                  : "Failed"}
              </option>
            </select>
          </div>

          <div
            className="outbox-filter-field"
          >
            <label
              htmlFor="outbox-event-type"
            >
              Event Type
            </label>

            <input
              id="outbox-event-type"
              value={eventTypeInput}
              onChange={(
                event,
              ) => {
                setEventTypeInput(
                  event.target.value,
                );
              }}
              placeholder={
                "portfolio.position.updated"
              }
            />
          </div>

          <div
            className="outbox-filter-field"
          >
            <label
              htmlFor="outbox-aggregate-id"
            >
              Aggregate ID
            </label>

            <input
              id="outbox-aggregate-id"
              value={aggregateIdInput}
              onChange={(
                event,
              ) => {
                setAggregateIdInput(
                  event.target.value,
                );
              }}
              placeholder={
                isZh
                  ? "按聚合 ID 过滤"
                  : "Filter by aggregate ID"
              }
            />
          </div>

          <button
            type="submit"
            className="outbox-filter-button"
          >
            <Search
              size={16}
            />

            {isZh
              ? "应用筛选"
              : "Apply"}
          </button>
        </form>
      </div>

      <div
        className={
          "page-card "
          + "outbox-table-card"
        }
      >
        <div
          className="outbox-table-toolbar"
        >
          <div>
            <h2>
              {isZh
                ? "最近事件"
                : "Recent Events"}
            </h2>

            <p>
              {isZh
                ? (
                  `当前返回 ${
                    eventsQuery
                      .data?.count
                    ?? 0
                  } 条，最多 50 条`
                )
                : (
                  `Showing ${
                    eventsQuery
                      .data?.count
                    ?? 0
                  } events, max 50`
                )}
            </p>
          </div>

          <RadioTower
            size={20}
          />
        </div>

        {eventsQuery.isError ? (
          <div
            className="outbox-error-state"
          >
            <AlertTriangle
              size={28}
            />

            <strong>
              {isZh
                ? "Outbox 数据读取失败"
                : "Failed to load outbox events"}
            </strong>

            <span>
              {isZh
                ? "请确认 FastAPI 与 PostgreSQL 状态。"
                : "Check FastAPI and PostgreSQL."}
            </span>
          </div>
        ) : eventsQuery.isPending ? (
          <div
            className="outbox-empty"
          >
            <RefreshCcw
              size={26}
            />

            <strong>
              {isZh
                ? "正在读取 Outbox"
                : "Loading outbox events"}
            </strong>
          </div>
        ) : events.length === 0 ? (
          <div
            className="outbox-empty"
          >
            <RadioTower
              size={27}
            />

            <strong>
              {isZh
                ? "当前筛选条件下没有事件"
                : "No events match the current filters"}
            </strong>
          </div>
        ) : (
          <div
            className="market-table-wrapper"
          >
            <table
              className="outbox-table"
            >
              <thead>
                <tr>
                  <th>
                    {isZh
                      ? "状态"
                      : "Status"}
                  </th>

                  <th>
                    Event Type
                  </th>

                  <th>
                    Aggregate
                  </th>

                  <th>
                    {isZh
                      ? "尝试"
                      : "Attempts"}
                  </th>

                  <th>
                    {isZh
                      ? "创建时间"
                      : "Created"}
                  </th>

                  <th>
                    {isZh
                      ? "发布时间"
                      : "Published"}
                  </th>

                  <th>
                    {isZh
                      ? "最后错误"
                      : "Last Error"}
                  </th>
                </tr>
              </thead>

              <tbody>
                {events.map(
                  event => (
                    <EventRow
                      key={event.event_id}
                      event={event}
                      isZh={isZh}
                    />
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
