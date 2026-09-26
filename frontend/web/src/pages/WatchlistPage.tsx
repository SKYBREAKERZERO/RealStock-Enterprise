import {
  FormEvent,
  useState,
} from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  Activity,
  Plus,
  RefreshCw,
  Star,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  ApiError,
} from "../api/client";

import {
  CURRENT_USER_ID,
} from "../api/userIdentity";

import {
  getMarketQuotes,
} from "../services/market";

import {
  addWatchlistItem,
  deleteWatchlistItem,
  getWatchlist,
} from "../services/watchlist";

import "../watchlist.css";


function normalizeSymbol(
  value: string,
): string {
  return value
    .trim()
    .toUpperCase();
}


function isValidSymbol(
  value: string,
): boolean {
  return (
    /^[A-Z0-9.^-]{1,20}$/
      .test(
        value,
      )
  );
}


function formatPrice(
  value: string,
  currency: string,
  isZh: boolean,
): string {
  return new Intl.NumberFormat(
    isZh
      ? "zh-CN"
      : "en-US",
    {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    },
  ).format(
    Number(value),
  );
}


function formatNumber(
  value: string,
): string {
  const number =
    Number(value);

  if (
    !Number.isFinite(
      number,
    )
  ) {
    return value;
  }

  return number.toFixed(2);
}


function formatPercent(
  value: string,
): string {
  const number =
    Number(value);

  return (
    `${number >= 0 ? "+" : ""}`
    + `${number.toFixed(2)}%`
  );
}


function getMutationErrorMessage(
  error: unknown,
  isZh: boolean,
): string {
  if (
    error instanceof ApiError
  ) {
    if (
      error.status
      === 409
    ) {
      if (
        error.message
          .includes(
            "already exists",
          )
      ) {
        return isZh
          ? "该股票已在自选列表中。"
          : "This symbol is already in the watchlist.";
      }

      if (
        error.message
          .includes(
            "limit exceeded",
          )
      ) {
        return isZh
          ? "自选股数量已达到上限。"
          : "The watchlist limit has been reached.";
      }
    }

    if (
      error.status
      === 401
    ) {
      return isZh
        ? "当前用户身份不可用。"
        : "The current user identity is unavailable.";
    }

    if (
      error.status
      === 422
    ) {
      return isZh
        ? "股票代码格式无效。"
        : "Invalid stock symbol format.";
    }

    return error.message;
  }

  return isZh
    ? "请求失败，请稍后重试。"
    : "Request failed. Please try again.";
}


function getSourceLabel(
  source: string | null,
  isZh: boolean,
): string {
  if (
    source === "provider"
  ) {
    return isZh
      ? "实时源"
      : "Provider";
  }

  if (
    source === "cache"
  ) {
    return isZh
      ? "缓存"
      : "Cache";
  }

  if (
    source === "stale_cache"
  ) {
    return isZh
      ? "过期缓存"
      : "Stale cache";
  }

  return isZh
    ? "未知"
    : "Unknown";
}


function getSourceClassName(
  source: string | null,
): string {
  if (
    source === "provider"
  ) {
    return "watchlist-source-badge provider";
  }

  if (
    source === "stale_cache"
  ) {
    return "watchlist-source-badge stale";
  }

  return "watchlist-source-badge cache";
}


export function WatchlistPage() {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language
      .startsWith("zh");

  const queryClient =
    useQueryClient();

  const [
    symbolInput,
    setSymbolInput,
  ] = useState(
    "",
  );

  const [
    symbolError,
    setSymbolError,
  ] = useState<
    string | null
  >(
    null,
  );


  const watchlistQuery =
    useQuery({
      queryKey: [
        "watchlist",
        CURRENT_USER_ID,
      ],

      queryFn: ({
        signal,
      }) =>
        getWatchlist(
          signal,
        ),

      staleTime:
        15_000,

      retry: 1,
    });


  const symbols =
    watchlistQuery
      .data
      ?.items
      .map(
        (
          item,
        ) =>
          item.symbol,
      )
    ?? [];


  const marketQuery =
    useQuery({
      queryKey: [
        "market-quotes",
        symbols,
      ],

      queryFn: ({
        signal,
      }) =>
        getMarketQuotes(
          symbols,
          signal,
        ),

      staleTime:
        30_000,

      refetchInterval:
        60_000,

      retry: 1,

      enabled:
        (
          watchlistQuery
            .isSuccess
          &&
          symbols.length > 0
        ),
    });


  const addMutation =
    useMutation({
      mutationFn:
        (
          symbol: string,
        ) =>
          addWatchlistItem(
            symbol,
          ),

      onSuccess:
        async () => {
          setSymbolInput(
            "",
          );

          setSymbolError(
            null,
          );

          await (
            queryClient
              .invalidateQueries({
                queryKey: [
                  "watchlist",
                  CURRENT_USER_ID,
                ],
              })
          );
        },

      onError:
        (
          error,
        ) => {
          setSymbolError(
            getMutationErrorMessage(
              error,
              isZh,
            ),
          );
        },
    });


  const removeMutation =
    useMutation({
      mutationFn:
        (
          symbol: string,
        ) =>
          deleteWatchlistItem(
            symbol,
          ),

      onSuccess:
        async () => {
          setSymbolError(
            null,
          );

          await (
            queryClient
              .invalidateQueries({
                queryKey: [
                  "watchlist",
                  CURRENT_USER_ID,
                ],
              })
          );
        },

      onError:
        (
          error,
        ) => {
          setSymbolError(
            getMutationErrorMessage(
              error,
              isZh,
            ),
          );
        },
    });


  function addSymbol(
    event:
      FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    setSymbolError(
      null,
    );

    const normalized =
      normalizeSymbol(
        symbolInput,
      );

    if (!normalized) {
      setSymbolError(
        isZh
          ? "请输入股票代码。"
          : "Enter a stock symbol.",
      );

      return;
    }

    if (
      !isValidSymbol(
        normalized,
      )
    ) {
      setSymbolError(
        isZh
          ? "股票代码格式无效。"
          : "Invalid stock symbol format.",
      );

      return;
    }

    if (
      symbols.includes(
        normalized,
      )
    ) {
      setSymbolError(
        isZh
          ? "该股票已在自选列表中。"
          : "This symbol is already in the watchlist.",
      );

      return;
    }

    addMutation.mutate(
      normalized,
    );
  }


  function removeSymbol(
    symbol: string,
  ) {
    setSymbolError(
      null,
    );

    removeMutation.mutate(
      symbol,
    );
  }


  const quoteRows =
    marketQuery
      .data
      ?.items
    ?? [];

  const availableQuotes =
    quoteRows.filter(
      (
        row,
      ) =>
        row.quote !== null
        && row.status !== "error",
    ).length;

  const staleQuotes =
    quoteRows.filter(
      (
        row,
      ) =>
        row.status === "stale",
    ).length;


  return (
    <section
      className="page-section watchlist-page"
    >
      <div
        className="page-card watchlist-card"
      >
        <div
          className="page-card-header watchlist-header"
        >
          <div>
            <h2>
              {isZh
                ? "自选列表"
                : "Watchlist"}
            </h2>

            <p>
              {isZh
                ? (
                  "PostgreSQL 用户自选股 · "
                  + "Twelve Data 行情 · Redis 缓存"
                )
                : (
                  "PostgreSQL watchlist · "
                  + "Twelve Data · Redis cache"
                )}
            </p>
          </div>

          <button
            className="watchlist-refresh-button"
            type="button"
            onClick={() => {
              void marketQuery.refetch();
            }}
            disabled={
              marketQuery.isFetching
              || symbols.length === 0
            }
          >
            <RefreshCw
              size={15}
              className={
                marketQuery.isFetching
                  ? "watchlist-refresh-icon spinning"
                  : "watchlist-refresh-icon"
              }
            />

            {marketQuery.isFetching
              ? (
                isZh
                  ? "刷新中"
                  : "Refreshing"
              )
              : (
                isZh
                  ? "刷新行情"
                  : "Refresh quotes"
              )}
          </button>
        </div>


        <form
          className="stock-picker watchlist-stock-picker"
          onSubmit={
            addSymbol
          }
        >
          <input
            value={
              symbolInput
            }
            onChange={(
              event,
            ) => {
              setSymbolInput(
                event
                  .target
                  .value,
              );

              setSymbolError(
                null,
              );
            }}
            placeholder={
              isZh
                ? "输入股票代码，如 AAPL"
                : "Enter symbol, e.g. AAPL"
            }
            maxLength={20}
            disabled={
              addMutation.isPending
            }
          />

          <button
            type="submit"
            disabled={
              addMutation.isPending
            }
          >
            <Plus
              size={16}
            />

            {addMutation.isPending
              ? (
                isZh
                  ? "添加中"
                  : "Adding"
              )
              : (
                isZh
                  ? "添加"
                  : "Add"
              )}
          </button>
        </form>


        {symbolError ? (
          <p
            className="stock-picker-error"
          >
            {symbolError}
          </p>
        ) : null}


        <div
          className="watchlist-kpi-grid"
        >
          <article
            className="watchlist-kpi"
          >
            <span>
              {isZh
                ? "已保存"
                : "Saved"}
            </span>

            <strong>
              {watchlistQuery
                .data
                ?.count
              ?? 0}
              {" / 8"}
            </strong>

            <small>
              PostgreSQL
            </small>
          </article>

          <article
            className="watchlist-kpi"
          >
            <span>
              {isZh
                ? "可用行情"
                : "Available"}
            </span>

            <strong>
              {availableQuotes}
            </strong>

            <small>
              {isZh
                ? "实时或缓存"
                : "Live or cached"}
            </small>
          </article>

          <article
            className="watchlist-kpi"
          >
            <span>
              {isZh
                ? "过期缓存"
                : "Stale"}
            </span>

            <strong>
              {staleQuotes}
            </strong>

            <small>
              {isZh
                ? "上游异常时回退"
                : "Fallback"}
            </small>
          </article>

          <article
            className="watchlist-kpi"
          >
            <span>
              {isZh
                ? "自动刷新"
                : "Refresh"}
            </span>

            <strong>
              60s
            </strong>

            <small>
              React Query
            </small>
          </article>
        </div>


        {watchlistQuery.isPending ? (
          <div
            className="dashboard-empty-state watchlist-empty-state"
          >
            <Activity
              size={28}
            />

            <strong>
              {isZh
                ? "正在读取自选列表"
                : "Loading watchlist"}
            </strong>

            <span>
              PostgreSQL
            </span>
          </div>
        ) : null}


        {watchlistQuery.isError ? (
          <div
            className="dashboard-empty-state watchlist-empty-state"
          >
            <Star
              size={28}
            />

            <strong>
              {isZh
                ? "自选列表暂时不可用"
                : "Watchlist unavailable"}
            </strong>

            <span>
              {isZh
                ? "请确认 FastAPI 与 PostgreSQL 状态。"
                : "Check FastAPI and PostgreSQL."}
            </span>
          </div>
        ) : null}


        {watchlistQuery.isSuccess
        && symbols.length === 0 ? (
          <div
            className="dashboard-empty-state watchlist-empty-state"
          >
            <Star
              size={30}
            />

            <strong>
              {isZh
                ? "自选列表为空"
                : "Your watchlist is empty"}
            </strong>

            <span>
              {isZh
                ? "在上方输入股票代码，即可保存到 PostgreSQL。"
                : "Add a symbol above to persist it in PostgreSQL."}
            </span>
          </div>
        ) : null}


        {symbols.length > 0
        && marketQuery.isPending ? (
          <div
            className="dashboard-empty-state watchlist-empty-state"
          >
            <Activity
              size={28}
            />

            <strong>
              {isZh
                ? "正在加载市场行情"
                : "Loading market data"}
            </strong>

            <span>
              {isZh
                ? "优先读取 Redis，缺失时访问 Twelve Data。"
                : "Redis first, Twelve Data on cache miss."}
            </span>
          </div>
        ) : null}


        {symbols.length > 0
        && marketQuery.isError ? (
          <div
            className="dashboard-empty-state watchlist-empty-state"
          >
            <Star
              size={28}
            />

            <strong>
              {isZh
                ? "市场行情暂时不可用"
                : "Market data unavailable"}
            </strong>

            <span>
              {isZh
                ? "自选列表仍保存在 PostgreSQL，可稍后刷新行情。"
                : "The watchlist remains persisted in PostgreSQL. Retry quotes later."}
            </span>
          </div>
        ) : null}


        {marketQuery.data ? (
          <div
            className="market-table-wrapper watchlist-table-wrapper"
          >
            <table
              className="market-table watchlist-table"
            >
              <thead>
                <tr>
                  <th>
                    {isZh
                      ? "股票"
                      : "Symbol"}
                  </th>

                  <th>
                    {isZh
                      ? "价格"
                      : "Price"}
                  </th>

                  <th>
                    {isZh
                      ? "涨跌"
                      : "Change"}
                  </th>

                  <th>
                    {isZh
                      ? "涨跌幅"
                      : "Change %"}
                  </th>

                  <th>
                    {isZh
                      ? "52 周区间"
                      : "52W Range"}
                  </th>

                  <th>
                    {isZh
                      ? "交易所"
                      : "Exchange"}
                  </th>

                  <th>
                    {isZh
                      ? "来源"
                      : "Source"}
                  </th>

                  <th />
                </tr>
              </thead>

              <tbody>
                {marketQuery
                  .data
                  .items
                  .map(
                    (
                      row,
                    ) => {
                      if (
                        row.status === "error"
                        || row.quote === null
                      ) {
                        return (
                          <tr
                            key={
                              row.symbol
                            }
                          >
                            <td>
                              <strong>
                                {
                                  row.symbol
                                }
                              </strong>
                            </td>

                            <td
                              colSpan={6}
                              className="market-error"
                            >
                              {isZh
                                ? (
                                  row.error
                                  ?? "暂时无法获取行情"
                                )
                                : (
                                  row.error
                                  ?? "Market data unavailable"
                                )}
                            </td>

                            <td>
                              <button
                                type="button"
                                className="remove-stock-button"
                                disabled={
                                  removeMutation
                                    .isPending
                                }
                                onClick={() =>
                                  removeSymbol(
                                    row.symbol,
                                  )
                                }
                                aria-label={
                                  isZh
                                    ? `删除 ${row.symbol}`
                                    : `Remove ${row.symbol}`
                                }
                              >
                                <X
                                  size={15}
                                />
                              </button>
                            </td>
                          </tr>
                        );
                      }


                      const quote =
                        row.quote;

                      const positive =
                        Number(
                          quote.change,
                        ) >= 0;


                      return (
                        <tr
                          key={
                            row.symbol
                          }
                        >
                          <td>
                            <div
                              className="symbol-cell"
                            >
                              <strong>
                                {
                                  quote.symbol
                                }
                              </strong>

                              <span>
                                {
                                  quote.name
                                }
                              </span>
                            </div>
                          </td>


                          <td
                            className="watchlist-price-cell"
                          >
                            {formatPrice(
                              quote.close,
                              quote.currency,
                              isZh,
                            )}
                          </td>


                          <td>
                            <span
                              className={
                                positive
                                  ? "market-positive"
                                  : "market-negative"
                              }
                            >
                              {positive ? (
                                <TrendingUp
                                  size={14}
                                />
                              ) : (
                                <TrendingDown
                                  size={14}
                                />
                              )}

                              {
                                formatNumber(
                                  quote.change,
                                )
                              }
                            </span>
                          </td>


                          <td>
                            <span
                              className={
                                positive
                                  ? "market-positive"
                                  : "market-negative"
                              }
                            >
                              {formatPercent(
                                quote
                                  .percent_change,
                              )}
                            </span>
                          </td>


                          <td
                            className="watchlist-range-cell"
                          >
                            {quote
                              .fifty_two_week
                              ? (
                                `${formatNumber(
                                  quote
                                    .fifty_two_week
                                    .low,
                                )}`
                                + " – "
                                + `${formatNumber(
                                  quote
                                    .fifty_two_week
                                    .high,
                                )}`
                              )
                              : "—"}
                          </td>


                          <td>
                            {
                              quote.exchange
                            }
                          </td>


                          <td>
                            <span
                              className={
                                getSourceClassName(
                                  row.source,
                                )
                              }
                            >
                              {getSourceLabel(
                                row.source,
                                isZh,
                              )}
                            </span>
                          </td>


                          <td>
                            <button
                              type="button"
                              className="remove-stock-button"
                              disabled={
                                removeMutation
                                  .isPending
                              }
                              onClick={() =>
                                removeSymbol(
                                  row.symbol,
                                )
                              }
                              aria-label={
                                isZh
                                  ? `删除 ${row.symbol}`
                                  : `Remove ${row.symbol}`
                              }
                            >
                              <X
                                size={15}
                              />
                            </button>
                          </td>
                        </tr>
                      );
                    },
                  )}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}
