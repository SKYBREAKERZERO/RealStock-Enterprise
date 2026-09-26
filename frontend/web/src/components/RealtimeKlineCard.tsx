import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  useQuery,
} from "@tanstack/react-query";

import {
  Activity,
  RefreshCw,
} from "lucide-react";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  type BusinessDay,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import {
  useTranslation,
} from "react-i18next";

import {
  getMarketCandles,
  type MarketCandleRange,
} from "../services/market";


interface RealtimeKlineCardProps {
  symbol?: string;
}


interface RangeOption {
  key: MarketCandleRange;

  zh: string;

  en: string;
}


const RANGE_OPTIONS: RangeOption[] = [
  {
    key: "day",
    zh: "日",
    en: "Day",
  },
  {
    key: "week",
    zh: "周",
    en: "Week",
  },
  {
    key: "month",
    zh: "月",
    en: "Month",
  },
];


const DAY_REFRESH_INTERVAL =
  60_000;


const WEEK_REFRESH_INTERVAL =
  5 * 60_000;


const MONTH_REFRESH_INTERVAL =
  15 * 60_000;


function parseCandleTime(
  value: string,
): Time {
  /*
   * Daily data:
   *
   *   2026-09-21
   *
   * Use BusinessDay rather than converting it through Date.
   */
  const dailyMatch =
    /^(\d{4})-(\d{2})-(\d{2})$/
      .exec(
        value,
      );

  if (dailyMatch) {
    const year =
      Number(
        dailyMatch[1],
      );

    const month =
      Number(
        dailyMatch[2],
      );

    const day =
      Number(
        dailyMatch[3],
      );

    const businessDay:
      BusinessDay = {
        year,
        month,
        day,
      };

    return businessDay;
  }


  /*
   * Intraday Twelve Data response:
   *
   *   2026-09-21 13:30:00
   *
   * Backend requests timezone=UTC, therefore explicitly append Z.
   */
  let normalized =
    value.trim();

  if (
    !normalized.includes(
      "T",
    )
  ) {
    normalized =
      normalized.replace(
        " ",
        "T",
      );
  }

  if (
    !normalized.endsWith(
      "Z",
    )
    &&
    !/[+-]\d{2}:\d{2}$/.test(
      normalized,
    )
  ) {
    normalized += "Z";
  }

  const milliseconds =
    Date.parse(
      normalized,
    );

  if (
    Number.isNaN(
      milliseconds,
    )
  ) {
    throw new Error(
      `Invalid candle time: ${value}`,
    );
  }

  return (
    Math.floor(
      milliseconds / 1000,
    ) as UTCTimestamp
  );
}


function getRefreshInterval(
  range: MarketCandleRange,
): number {
  switch (range) {
    case "day":
      return (
        DAY_REFRESH_INTERVAL
      );

    case "week":
      return (
        WEEK_REFRESH_INTERVAL
      );

    case "month":
      return (
        MONTH_REFRESH_INTERVAL
      );
  }
}


function formatPrice(
  value: number,
): string {
  return (
    new Intl.NumberFormat(
      "en-US",
      {
        minimumFractionDigits:
          2,

        maximumFractionDigits:
          4,
      },
    )
      .format(
        value,
      )
  );
}


function formatUpdatedAt(
  timestamp: number,
  language: string,
): string {
  if (
    timestamp <= 0
  ) {
    return "-";
  }

  return (
    new Intl.DateTimeFormat(
      language.startsWith(
        "zh",
      )
        ? "zh-CN"
        : "en-US",
      {
        hour:
          "2-digit",

        minute:
          "2-digit",

        second:
          "2-digit",
      },
    )
      .format(
        new Date(
          timestamp,
        ),
      )
  );
}


function getErrorMessage(
  error: unknown,
  isZh: boolean,
): string {
  if (
    error instanceof Error
  ) {
    return (
      error.message
    );
  }

  return (
    isZh
      ? "未知市场数据错误。"
      : "Unknown market data error."
  );
}


export function RealtimeKlineCard({
  symbol = "AAPL",
}: RealtimeKlineCardProps) {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language
      .startsWith(
        "zh",
      );


  const [
    range,
    setRange,
  ] = useState<
    MarketCandleRange
  >(
    "day",
  );


  const containerRef =
    useRef<
      HTMLDivElement | null
    >(
      null,
    );


  const chartRef =
    useRef<
      IChartApi | null
    >(
      null,
    );


  const seriesRef =
    useRef<
      ISeriesApi<
        "Candlestick",
        Time
      >
      | null
    >(
      null,
    );


  const klineQuery =
    useQuery({
      queryKey: [
        "market",
        "candles",
        symbol,
        range,
      ],

      queryFn: ({
        signal,
      }) =>
        getMarketCandles(
          symbol,
          range,
          signal,
        ),

      staleTime:
        range === "day"
          ? 30_000
          : range === "week"
            ? 2 * 60_000
            : 5 * 60_000,

      refetchInterval:
        getRefreshInterval(
          range,
        ),

      refetchOnWindowFocus:
        false,

      retry:
        3,

      retryDelay:
        (
          attemptIndex,
        ) =>
          Math.min(
            1_000
            * 2
            ** attemptIndex,
            8_000,
          ),
    });


  const chartData =
    useMemo<
      CandlestickData<
        Time
      >[]
    >(
      () => {
        const items =
          klineQuery
            .data
            ?.items
          ?? [];

        return (
          items.map(
            (
              item,
            ) => ({
              time:
                parseCandleTime(
                  item.time,
                ),

              open:
                item.open,

              high:
                item.high,

              low:
                item.low,

              close:
                item.close,
            }),
          )
        );
      },
      [
        klineQuery.data,
      ],
    );


  const latestCandle =
    klineQuery
      .data
      ?.items
      .at(
        -1,
      );


  /*
   * Create chart once.
   */
  useEffect(
    () => {
      const container =
        containerRef.current;

      if (!container) {
        return;
      }

      const chart =
        createChart(
          container,
          {
            width:
              container.clientWidth,

            height:
              300,

            layout: {
              background: {
                type:
                  ColorType.Solid,

                color:
                  "#ffffff",
              },

              textColor:
                "#64748b",

              fontFamily:
                (
                  "Inter, system-ui, "
                  + "-apple-system, "
                  + "BlinkMacSystemFont, "
                  + "\"Segoe UI\", sans-serif"
                ),
            },

            grid: {
              vertLines: {
                color:
                  "#eef2f7",
              },

              horzLines: {
                color:
                  "#eef2f7",
              },
            },

            rightPriceScale: {
              borderColor:
                "#e2e8f0",

              scaleMargins: {
                top:
                  0.08,

                bottom:
                  0.08,
              },
            },

            timeScale: {
              borderColor:
                "#e2e8f0",

              timeVisible:
                true,

              secondsVisible:
                false,

              rightOffset:
                2,

              barSpacing:
                8,

              minBarSpacing:
                3,
            },

            crosshair: {
              mode:
                CrosshairMode.Normal,
            },

            localization: {
              locale:
                isZh
                  ? "zh-CN"
                  : "en-US",
            },
          },
        );


      const series =
        chart.addSeries(
          CandlestickSeries,
          {
            upColor:
              "#16a34a",

            downColor:
              "#ef4444",

            borderVisible:
              false,

            wickUpColor:
              "#16a34a",

            wickDownColor:
              "#ef4444",

            priceLineVisible:
              true,

            lastValueVisible:
              true,
          },
        );


      chartRef.current =
        chart;

      seriesRef.current =
        series;


      const resizeObserver =
        new ResizeObserver(
          (
            entries,
          ) => {
            const entry =
              entries[0];

            if (!entry) {
              return;
            }

            const width =
              Math.floor(
                entry
                  .contentRect
                  .width,
              );

            if (
              width <= 0
            ) {
              return;
            }

            chart.applyOptions({
              width,
            });
          },
        );


      resizeObserver.observe(
        container,
      );


      return () => {
        resizeObserver.disconnect();

        seriesRef.current =
          null;

        chartRef.current =
          null;

        chart.remove();
      };
    },
    [
      isZh,
    ],
  );


  /*
   * Only replace chart data when query data changes.
   */
  useEffect(
    () => {
      const chart =
        chartRef.current;

      const series =
        seriesRef.current;

      if (
        !chart
        ||
        !series
      ) {
        return;
      }

      series.setData(
        chartData,
      );

      if (
        chartData.length
        > 0
      ) {
        chart
          .timeScale()
          .fitContent();
      }
    },
    [
      chartData,
    ],
  );


  const intervalLabel =
    klineQuery
      .data
      ?.interval
    ?? "-";


  const updatedAt =
    formatUpdatedAt(
      klineQuery
        .dataUpdatedAt,
      i18n.language,
    );


  const errorMessage =
    klineQuery.isError
      ? getErrorMessage(
          klineQuery.error,
          isZh,
        )
      : null;


  return (
    <section
      className="page-section"
    >
      <div
        className="page-card"
      >
        <div
          className="page-card-header"
        >
          <div>
            <div
              style={{
                display:
                  "flex",

                alignItems:
                  "center",

                gap:
                  "10px",

                flexWrap:
                  "wrap",
              }}
            >
              <h2
                style={{
                  margin:
                    0,
                }}
              >
                {isZh
                  ? "实时 K 线图"
                  : "Realtime Candlestick"}
              </h2>


              <span
                style={{
                  display:
                    "inline-flex",

                  alignItems:
                    "center",

                  border:
                    "1px solid #dbe3ef",

                  borderRadius:
                    "999px",

                  padding:
                    "4px 9px",

                  fontSize:
                    "12px",

                  fontWeight:
                    700,

                  color:
                    "#334155",

                  background:
                    "#f8fafc",
                }}
              >
                {symbol}
              </span>


              <span
                style={{
                  fontSize:
                    "12px",

                  color:
                    "#64748b",
                }}
              >
                {intervalLabel}
              </span>
            </div>


            <p>
              {isZh
                ? (
                  `基于 ${symbol} 的真实市场 OHLC 数据，`
                  + "支持日 / 周 / 月范围切换。"
                )
                : (
                  `Real OHLC market data for ${symbol} `
                  + "with Day / Week / Month ranges."
                )}
            </p>
          </div>


          <div
            style={{
              display:
                "flex",

              alignItems:
                "center",

              gap:
                "8px",

              flexWrap:
                "wrap",
            }}
          >
            {RANGE_OPTIONS.map(
              (
                item,
              ) => (
                <button
                  key={
                    item.key
                  }
                  type="button"
                  className={
                    range
                    === item.key
                      ? (
                        "range-button "
                        + "active"
                      )
                      : "range-button"
                  }
                  onClick={() => {
                    setRange(
                      item.key,
                    );
                  }}
                >
                  {isZh
                    ? item.zh
                    : item.en}
                </button>
              ),
            )}


            <button
              type="button"
              className="range-button"
              disabled={
                klineQuery
                  .isFetching
              }
              title={
                isZh
                  ? "刷新"
                  : "Refresh"
              }
              onClick={() => {
                void (
                  klineQuery
                    .refetch()
                );
              }}
            >
              <RefreshCw
                size={14}
                className={
                  klineQuery
                    .isFetching
                    ? "spin"
                    : undefined
                }
              />
            </button>
          </div>
        </div>


        {latestCandle ? (
          <div
            style={{
              display:
                "flex",

              gap:
                "20px",

              flexWrap:
                "wrap",

              padding:
                "0 0 14px",

              fontSize:
                "13px",

              color:
                "#64748b",
            }}
          >
            <span>
              {isZh
                ? "最新价"
                : "Latest"}
              {" "}

              <strong
                style={{
                  color:
                    "#0f172a",
                }}
              >
                {formatPrice(
                  latestCandle.close,
                )}
              </strong>
            </span>


            <span>
              O{" "}
              {formatPrice(
                latestCandle.open,
              )}
            </span>


            <span>
              H{" "}
              {formatPrice(
                latestCandle.high,
              )}
            </span>


            <span>
              L{" "}
              {formatPrice(
                latestCandle.low,
              )}
            </span>


            <span>
              C{" "}
              {formatPrice(
                latestCandle.close,
              )}
            </span>


            <span>
              {isZh
                ? "更新时间"
                : "Updated"}
              {" "}
              {updatedAt}
            </span>
          </div>
        ) : null}


        {klineQuery.isPending ? (
          <div
            className="dashboard-empty-state"
            style={{
              minHeight:
                "180px",
            }}
          >
            <Activity
              size={25}
            />

            <strong>
              {isZh
                ? "正在加载 K 线数据"
                : "Loading candlestick data"}
            </strong>

            <span>
              Twelve Data
            </span>
          </div>
        ) : null}


        {klineQuery.isError ? (
          <div
            className="dashboard-empty-state"
            style={{
              minHeight:
                "180px",
            }}
          >
            <strong>
              {isZh
                ? "K 线服务暂时不可用"
                : "Candlestick service unavailable"}
            </strong>


            <span>
              {isZh
                ? (
                  "FastAPI 或 Twelve Data "
                  + "本次请求失败。"
                )
                : (
                  "The FastAPI or Twelve Data "
                  + "request failed."
                )}
            </span>


            {errorMessage ? (
              <small
                style={{
                  maxWidth:
                    "680px",

                  textAlign:
                    "center",

                  color:
                    "#94a3b8",
                }}
              >
                {errorMessage}
              </small>
            ) : null}


            <button
              type="button"
              className="range-button"
              onClick={() => {
                void (
                  klineQuery
                    .refetch()
                );
              }}
            >
              {isZh
                ? "重新加载"
                : "Retry"}
            </button>
          </div>
        ) : null}


        {klineQuery.isSuccess
        &&
        chartData.length === 0 ? (
          <div
            className="dashboard-empty-state"
            style={{
              minHeight:
                "180px",
            }}
          >
            <strong>
              {isZh
                ? "暂无 K 线数据"
                : "No candlestick data"}
            </strong>

            <span>
              {isZh
                ? (
                  "当前股票在所选范围内"
                  + "没有可显示的数据。"
                )
                : (
                  "No data is available "
                  + "for the selected range."
                )}
            </span>
          </div>
        ) : null}


        <div
          ref={
            containerRef
          }
          style={{
            width:
              "100%",

            height:
              "300px",

            display:
              klineQuery.isSuccess
              &&
              chartData.length > 0
                ? "block"
                : "none",
          }}
        />
      </div>
    </section>
  );
}