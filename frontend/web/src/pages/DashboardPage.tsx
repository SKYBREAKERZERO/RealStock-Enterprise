import {



  useState,



} from "react";







import type {



  FormEvent,



} from "react";







import {



  useMutation,



  useQueries,



  useQuery,



  useQueryClient,



} from "@tanstack/react-query";







import {



  Activity,



  BriefcaseBusiness,



  CircleDollarSign,



  Clock3,



  Plus,



  RadioTower,



  Star,



  TrendingDown,



  TrendingUp,



  Users,



  X,



} from "lucide-react";







import {



  Area,



  AreaChart,



  CartesianGrid,



  ResponsiveContainer,



  Tooltip,



  XAxis,



  YAxis,



} from "recharts";







import {



  useTranslation,



} from "react-i18next";







import {

  RealtimeKlineCard,

} from "../components/RealtimeKlineCard";





import {



  ApiError,



  apiUrl,



} from "../api/client";







import {



  CURRENT_USER_ID,



} from "../api/userIdentity";







import {



  getMarketQuotes,



} from "../services/market";





import {



  getOutboxEvents,



  getOutboxSummary,



} from "../services/outbox";







import {



  getPortfolios,



  getPortfolioValuation,



} from "../services/portfolio";







import {



  addWatchlistItem,



  deleteWatchlistItem,



  getWatchlist,



} from "../services/watchlist";











const PERFORMANCE_DATA = [



  {



    name: "Jan",



    value: 100000,



  },



  {



    name: "Feb",



    value: 104500,



  },



  {



    name: "Mar",



    value: 102800,



  },



  {



    name: "Apr",



    value: 110400,



  },



  {



    name: "May",



    value: 116900,



  },



  {



    name: "Jun",



    value: 121600,



  },



  {



    name: "Jul",



    value: 124832,



  },



];











interface ReadinessResponse {



  status: string;







  dependencies: Record<



    string,



    string



  >;



}











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











async function getReadiness():



  Promise<ReadinessResponse> {



  const response =



    await fetch(



      apiUrl(

        "/health/ready",

      ),



      {



        headers: {



          Accept:



            "application/json",



        },



      },



    );







  if (!response.ok) {



    throw new Error(



      "Readiness request failed",



    );



  }







  return response.json() as Promise<



    ReadinessResponse



  >;



}











export function DashboardPage() {



  const {



    t,



    i18n,



  } = useTranslation();







  const queryClient =



    useQueryClient();







  const isZh =



    i18n.language



      .startsWith("zh");











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











  /*



   * ==========================================================



   * Watchlist



   * ==========================================================



   */







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











  /*



   * ==========================================================



   * Market Data



   * ==========================================================



   */







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











  /*



   * ==========================================================



   * Portfolios



   * ==========================================================



   */







  const portfoliosQuery =



    useQuery({



      queryKey: [



        "portfolios",



        CURRENT_USER_ID,



      ],







      queryFn: ({



        signal,



      }) =>



        getPortfolios(



          signal,



        ),







      staleTime:



        15_000,







      retry: 1,



    });











  const portfolios =



    portfoliosQuery.data



    ?? [];











  /*



   * Each portfolio receives one valuation request.



   *



   * Backend valuation performs batched market-price lookup for



   * positions, so this is not one Twelve Data request per



   * individual position.



   */



  const valuationQueries =



    useQueries({



      queries:



        portfolios.map(



          (



            portfolio,



          ) => ({



            queryKey: [



              "portfolio-valuation",



              CURRENT_USER_ID,



              portfolio



                .portfolio_id,



            ],







            queryFn: ({



              signal,



            }) =>



              getPortfolioValuation(



                portfolio



                  .portfolio_id,



                signal,



              ),







            staleTime:



              30_000,







            refetchInterval:



              60_000,







            retry: 1,



          }),



        ),



    });











  /*



   * ==========================================================



   * Portfolio Aggregation



   * ==========================================================



   */







  const loadedValuations =



    valuationQueries



      .flatMap(



        (



          query,



        ) =>



          query.data



            ? [



              query.data,



            ]



            : [],



      );











  const activePositions =



    portfolios.reduce(



      (



        total,



        portfolio,



      ) =>



        (



          total



          + portfolio



            .positions



            .length



        ),



      0,



    );











  const portfolioCurrencies =



    new Set(



      portfolios.map(



        (



          portfolio,



        ) =>



          portfolio.currency,



      ),



    );











  /*



   * Money is aggregated only when every portfolio uses



   * the same currency.



   */



  const aggregateCurrency =



    portfolioCurrencies.size



      === 1



      ? (



        portfolios[0]



          ?.currency



        ?? null



      )



      : null;











  const valuationLoading =



    (



      portfoliosQuery



        .isPending



      ||



      valuationQueries.some(



        (



          query,



        ) =>



          query.isPending,



      )



    );











  const valuationError =



    (



      portfoliosQuery



        .isError



      ||



      valuationQueries.some(



        (



          query,



        ) =>



          query.isError,



      )



    );











  const allValuationsLoaded =



    (



      loadedValuations.length



      === portfolios.length



    );











  const totalMarketValue =



    loadedValuations.reduce(



      (



        total,



        valuation,



      ) =>



        (



          total



          + Number(



            valuation



              .total_market_value,



          )



        ),



      0,



    );











  const totalUnrealizedPnl =



    loadedValuations.reduce(



      (



        total,



        valuation,



      ) =>



        (



          total



          + Number(



            valuation



              .total_unrealized_pnl,



          )



        ),



      0,



    );











  const missingQuotes =



    loadedValuations.reduce(



      (



        total,



        valuation,



      ) =>



        (



          total



          + valuation



            .missing_quotes



        ),



      0,



    );











  const valuationComplete =



    (



      portfolios.length > 0



      &&



      allValuationsLoaded



      &&



      loadedValuations.every(



        (



          valuation,



        ) =>



          valuation



            .valuation_complete,



      )



    );











  /*



   * Map valuation back to its portfolio.



   *



   * useQueries() preserves the same ordering as the portfolio



   * query array.



   */



  const valuationByPortfolioId =



    new Map(



      portfolios.map(



        (



          portfolio,



          index,



        ) => [



          portfolio



            .portfolio_id,



          valuationQueries[



            index



          ]?.data



          ?? null,



        ],



      ),



    );











  const recentPortfolios =



    [



      ...portfolios,



    ]



      .sort(



        (



          first,



          second,



        ) =>



          (



            Date.parse(



              second.created_at,



            )



            -



            Date.parse(



              first.created_at,



            )



          ),



      )



      .slice(



        0,



        4,



      );











  /*



   * ==========================================================



   * Portfolio Value KPI



   * ==========================================================



   */







  const portfolioValueDisplay =



    valuationLoading



      ? "…"



      : valuationError



        ? "—"



        : portfolios.length === 0



          ? "—"



          : aggregateCurrency === null



            ? (



              isZh



                ? "多币种"



                : "Multiple"



            )



            : formatPrice(



              String(



                totalMarketValue,



              ),



              aggregateCurrency,



              isZh,



            );











  const portfolioValueDetail =



    valuationLoading



      ? (



        isZh



          ? "正在读取实时估值"



          : "Loading live valuation"



      )



      : valuationError



        ? (



          isZh



            ? "投资组合估值暂时不可用"



            : "Portfolio valuation unavailable"



        )



        : portfolios.length === 0



          ? (



            isZh



              ? "当前用户暂无投资组合"



              : "No portfolios for the current user"



          )



          : portfolioCurrencies.size > 1



            ? (



              isZh



                ? "不同币种不会直接加总"



                : "Different currencies are not aggregated"



            )



            : (



              !valuationComplete



              &&



              missingQuotes > 0



            )



              ? (



                isZh



                  ? (



                    "部分估值 · "



                    + `${missingQuotes} 个行情缺失`



                  )



                  : (



                    "Partial valuation · "



                    + `${missingQuotes} quotes missing`



                  )



              )



              : (



                isZh



                  ? "实时投资组合市值"



                  : "Live portfolio market value"



              );











  /*



   * ==========================================================



   * Gain / Loss KPI



   * ==========================================================



   */







  const gainLossDisplay =



    valuationLoading



      ? "…"



      : valuationError



        ? "—"



        : portfolios.length === 0



          ? "—"



          : aggregateCurrency === null



            ? (



              isZh



                ? "多币种"



                : "Multiple"



            )



            : formatPrice(



              String(



                totalUnrealizedPnl,



              ),



              aggregateCurrency,



              isZh,



            );











  const gainLossDetail =



    valuationLoading



      ? (



        isZh



          ? "正在读取实时损益"



          : "Loading live P&L"



      )



      : valuationError



        ? (



          isZh



            ? "损益数据暂时不可用"



            : "P&L data unavailable"



        )



        : portfolios.length === 0



          ? (



            isZh



              ? "当前用户暂无持仓"



              : "No positions for the current user"



          )



          : portfolioCurrencies.size > 1



            ? (



              isZh



                ? "不同币种损益不会直接加总"



                : "P&L is not aggregated across currencies"



            )



            : (



              !valuationComplete



              &&



              missingQuotes > 0



            )



              ? (



                isZh



                  ? "当前为部分未实现损益"



                  : "Partial unrealized P&L"



              )



              : (



                isZh



                  ? "当前未实现损益"



                  : "Current unrealized gain / loss"



              );











  /*



   * ==========================================================



   * Watchlist Mutations



   * ==========================================================



   */







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











  /*



   * ==========================================================



   * System Readiness



   * ==========================================================



   */







  const readinessQuery =



    useQuery({



      queryKey: [



        "system",



        "readiness",



      ],







      queryFn:



        getReadiness,







      refetchInterval:



        30_000,







      retry: 1,



    });







  /*

   * ==========================================================

   * Outbox Observability

   * ==========================================================

   */



  const outboxSummaryQuery =

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



      staleTime:

        10_000,



      refetchInterval:

        15_000,



      retry: 1,

    });





  const recentOutboxQuery =

    useQuery({

      queryKey: [

        "outbox-events",

        CURRENT_USER_ID,

        "dashboard",

        "all",

        3,

      ],



      queryFn: ({

        signal,

      }) =>

        getOutboxEvents({

          status: "all",

          limit: 3,

          signal,

        }),



      staleTime:

        10_000,



      refetchInterval:

        15_000,



      retry: 1,

    });











  /*



   * ==========================================================



   * Watchlist Actions



   * ==========================================================



   */







  function addSymbol(



    event:



      FormEvent<



        HTMLFormElement



      >,



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











  /*



   * ==========================================================



   * System Health



   * ==========================================================



   */







  const dependencies =



    readinessQuery



      .data



      ?.dependencies



    ?? {};











  const healthItems = [



    {



      key:



        "postgresql",







      label:



        "PostgreSQL",







      detail:



        isZh



          ? "数据库"



          : "Database",



    },







    {



      key:



        "redis",







      label:



        "Redis",







      detail:



        isZh



          ? "缓存与会话"



          : "Cache & Session",



    },







    {



      key:



        "localstack",







      label:



        "LocalStack",







      detail:



        isZh



          ? "AWS 服务"



          : "AWS Services",



    },







    {



      key:



        "s3",







      label:



        "S3",







      detail:



        isZh



          ? "对象存储"



          : "Object Storage",



    },







    {



      key:



        "dynamodb",







      label:



        "DynamoDB",







      detail:



        isZh



          ? "NoSQL 服务"



          : "NoSQL Service",



    },



  ];











  return (



    <div



      className="dashboard-page"



    >



            {/*



       * ======================================================



       * Realtime Candlestick



       * ======================================================



       */}



      <RealtimeKlineCard



        symbol={



          symbols[0]



          ?? "AAPL"



        }



      />







{/*



       * ======================================================



       * KPI



       * ======================================================



       */}







      <section



        className="dashboard-kpi-grid"



      >



        {/*



         * Total Portfolio Value



         */}



        <article



          className="dashboard-kpi-card"



        >



          <div



            className="kpi-card-header"



          >



            <span>



              {t(



                "dashboard.totalPortfolioValue",



              )}



            </span>







            <CircleDollarSign



              size={18}



            />



          </div>







          <strong>



            {portfolioValueDisplay}



          </strong>







          <small>



            {portfolioValueDetail}



          </small>



        </article>











        {/*



         * Total Gain / Loss



         */}



        <article



          className="dashboard-kpi-card"



        >



          <div



            className="kpi-card-header"



          >



            <span>



              {t(



                "dashboard.totalGainLoss",



              )}



            </span>







            {totalUnrealizedPnl



            >= 0 ? (



              <TrendingUp



                size={18}



              />



            ) : (



              <TrendingDown



                size={18}



              />



            )}



          </div>







          <strong



            className={



              (



                !valuationLoading



                &&



                !valuationError



                &&



                portfolios.length > 0



                &&



                aggregateCurrency !== null



              )



                ? (



                  totalUnrealizedPnl



                    >= 0



                    ? "market-positive"



                    : "market-negative"



                )



                : undefined



            }



          >



            {gainLossDisplay}



          </strong>







          <small>



            {gainLossDetail}



          </small>



        </article>











        {/*



         * Active Positions



         */}



        <article



          className="dashboard-kpi-card"



        >



          <div



            className="kpi-card-header"



          >



            <span>



              {t(



                "dashboard.activePositions",



              )}



            </span>







            <BriefcaseBusiness



              size={18}



            />



          </div>







          <strong>



            {portfoliosQuery



              .isPending



              ? "…"



              : portfoliosQuery



                  .isError



                ? "—"



                : activePositions}



          </strong>







          <small>



            {portfoliosQuery



              .isPending



              ? (



                isZh



                  ? "正在读取 PostgreSQL"



                  : "Loading from PostgreSQL"



              )



              : portfoliosQuery



                  .isError



                ? (



                  isZh



                    ? "投资组合服务暂时不可用"



                    : "Portfolio service unavailable"



                )



                : (



                  isZh



                    ? "当前用户持仓"



                    : "Current user positions"



                )}



          </small>



        </article>











        {/*



         * Watchlist



         */}



        <article



          className="dashboard-kpi-card"



        >



          <div



            className="kpi-card-header"



          >



            <span>



              {t(



                "dashboard.watchlistItems",



              )}



            </span>







            <Star



              size={18}



            />



          </div>







          <strong>



            {watchlistQuery



              .data



              ?.count



            ?? 0}



          </strong>







          <small>



            {watchlistQuery



              .isPending



              ? (



                isZh



                  ? "正在读取 PostgreSQL"



                  : "Loading from PostgreSQL"



              )



              : t(



                "dashboard.stocksTracking",



              )}



          </small>



        </article>



      </section>











      {/*



       * ======================================================



       * Portfolio Performance



       *



       * Historical valuation storage does not exist yet.



       * Keep this explicitly marked as DEMO.



       * ======================================================



       */}







      <section



        className={



          "dashboard-card "



          + "performance-card"



        }



      >



        <div



          className="dashboard-card-header"



        >



          <div>



            <h2>



              {t(



                "dashboard.portfolioPerformance",



              )}



            </h2>







            <p>



              {isZh



                ? "正式估值历史接口接入前使用演示曲线。"



                : "Demo curve until portfolio valuation history is connected."}



            </p>



          </div>







          <span



            className="demo-badge"



          >



            DEMO



          </span>



        </div>











        <div



          className="performance-chart"



        >



          <ResponsiveContainer



            width="100%"



            height={270}



          >



            <AreaChart



              data={



                PERFORMANCE_DATA



              }



              margin={{



                top: 10,



                right: 10,



                left: 0,



                bottom: 0,



              }}



            >



              <defs>



                <linearGradient



                  id="portfolioGradient"



                  x1="0"



                  y1="0"



                  x2="0"



                  y2="1"



                >



                  <stop



                    offset="5%"



                    stopColor="#22c55e"



                    stopOpacity={0.28}



                  />







                  <stop



                    offset="95%"



                    stopColor="#22c55e"



                    stopOpacity={0}



                  />



                </linearGradient>



              </defs>







              <CartesianGrid



                strokeDasharray="3 3"



                vertical={false}



                stroke="#e2e8f0"



              />







              <XAxis



                dataKey="name"



                axisLine={false}



                tickLine={false}



              />







              <YAxis



                axisLine={false}



                tickLine={false}



                width={70}



              />







              <Tooltip />







              <Area



                type="monotone"



                dataKey="value"



                stroke="#16a34a"



                strokeWidth={2}



                fill={



                  "url(#portfolioGradient)"



                }



              />



            </AreaChart>



          </ResponsiveContainer>



        </div>



      </section>











      {/*



       * ======================================================



       * Market Overview



       * ======================================================



       */}







      <section



        className="dashboard-card"



      >



        <div



          className={



            "dashboard-card-header "



            + "market-overview-header"



          }



        >



          <div>



            <h2>



              {t(



                "dashboard.marketOverview",



              )}



            </h2>







            <p>



              {isZh



                ? "PostgreSQL 自选股 · Twelve Data 行情 · Redis 缓存"



                : "PostgreSQL watchlist · Twelve Data · Redis cache"}



            </p>



          </div>











          <form



            className="stock-picker"



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



                  ? "输入股票代码，如 NVDA"



                  : "Enter symbol, e.g. NVDA"



              }



              maxLength={20}



              disabled={



                addMutation



                  .isPending



              }



            />







            <button



              type="submit"



              disabled={



                addMutation



                  .isPending



              }



            >



              <Plus



                size={16}



              />







              {addMutation



                .isPending



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



        </div>











        {symbolError ? (



          <p



            className="stock-picker-error"



          >



            {symbolError}



          </p>



        ) : null}











        {watchlistQuery



          .isPending ? (



          <div



            className="dashboard-empty-state"



          >



            <Activity



              size={25}



            />







            <strong>



              {isZh



                ? "正在读取自选股"



                : "Loading watchlist"}



            </strong>







            <span>



              PostgreSQL



            </span>



          </div>



        ) : null}











        {watchlistQuery



          .isError ? (



          <div



            className="dashboard-empty-state"



          >



            <strong>



              {isZh



                ? "自选股服务暂时不可用"



                : "Watchlist service unavailable"}



            </strong>







            <span>



              {isZh



                ? "请确认 FastAPI 与 PostgreSQL 状态。"



                : "Check FastAPI and PostgreSQL."}



            </span>



          </div>



        ) : null}











        {watchlistQuery



          .isSuccess



        &&



        symbols.length



          === 0 ? (



          <div



            className="dashboard-empty-state"



          >



            <Star



              size={25}



            />







            <strong>



              {isZh



                ? "自选股为空"



                : "Your watchlist is empty"}



            </strong>







            <span>



              {isZh



                ? "在右上方输入股票代码即可添加到 PostgreSQL。"



                : "Enter a symbol above to persist it in PostgreSQL."}



            </span>



          </div>



        ) : null}











        {symbols.length



          > 0



        &&



        marketQuery



          .isPending ? (



          <div



            className="dashboard-empty-state"



          >



            <Activity



              size={25}



            />







            <strong>



              {isZh



                ? "正在加载市场行情"



                : "Loading market data"}



            </strong>



          </div>



        ) : null}











        {marketQuery



          .isError ? (



          <div



            className="dashboard-empty-state"



          >



            <strong>



              {isZh



                ? "市场行情服务暂时不可用"



                : "Market data service unavailable"}



            </strong>







            <span>



              {isZh



                ? "请确认 FastAPI、Redis 和市场数据配置。"



                : "Check FastAPI, Redis and market data configuration."}



            </span>



          </div>



        ) : null}











        {marketQuery



          .data ? (



          <div



            className="market-table-wrapper"



          >



            <table



              className="market-table"



            >



              <thead>



                <tr>



                  <th>



                    {t(



                      "market.symbol",



                    )}



                  </th>







                  <th>



                    {t(



                      "market.price",



                    )}



                  </th>







                  <th>



                    {t(



                      "market.change",



                    )}



                  </th>







                  <th>



                    {t(



                      "market.changePercent",



                    )}



                  </th>







                  <th>



                    {isZh



                      ? "交易所"



                      : "Exchange"}



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



                        row.status



                          === "error"



                        ||



                        row.quote



                          === null



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



                              colSpan={4}



                              className="market-error"



                            >



                              {isZh



                                ? "暂时无法获取行情"



                                : "Market data unavailable"}



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











                          <td>



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



                                quote.change



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











                          <td>



                            {



                              quote.exchange



                            }







                            {row.status



                              === "stale" ? (



                              <span



                                className="stale-badge"



                              >



                                {isZh



                                  ? "缓存"



                                  : "Cached"}



                              </span>



                            ) : null}



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



      </section>











      {/*



       * ======================================================



       * Bottom Grid



       * ======================================================



       */}







      <section



        className="dashboard-bottom-grid"



      >



        {/*



         * ----------------------------------------------------



         * Recent Portfolios



         * ----------------------------------------------------



         */}







        <article



          className="dashboard-card"



        >



          <div



            className="dashboard-card-header"



          >



            <div>



              <h2>



                {t(



                  "dashboard.recentPortfolios",



                )}



              </h2>







              <p>



                {isZh



                  ? "PostgreSQL 投资组合 · 实时估值"



                  : "PostgreSQL portfolios · Live valuation"}



              </p>



            </div>







            <BriefcaseBusiness



              size={19}



            />



          </div>











          {portfoliosQuery



            .isPending ? (



            <div



              className="dashboard-empty-state"



            >



              <Activity



                size={26}



              />







              <strong>



                {isZh



                  ? "正在读取投资组合"



                  : "Loading portfolios"}



              </strong>







              <span>



                PostgreSQL



              </span>



            </div>



          ) : null}











          {portfoliosQuery



            .isError ? (



            <div



              className="dashboard-empty-state"



            >



              <BriefcaseBusiness



                size={26}



              />







              <strong>



                {isZh



                  ? "投资组合服务暂时不可用"



                  : "Portfolio service unavailable"}



              </strong>







              <span>



                {isZh



                  ? "请确认 FastAPI 与 PostgreSQL 状态。"



                  : "Check FastAPI and PostgreSQL."}



              </span>



            </div>



          ) : null}











          {portfoliosQuery



            .isSuccess



          &&



          portfolios.length



            === 0 ? (



            <div



              className="dashboard-empty-state"



            >



              <Users



                size={26}



              />







              <strong>



                {isZh



                  ? "暂无投资组合"



                  : "No portfolios yet"}



              </strong>







              <span>



                {isZh



                  ? "当前用户尚未创建投资组合。"



                  : "The current user has no portfolios yet."}



              </span>



            </div>



          ) : null}











          {recentPortfolios



            .length > 0 ? (



            <div



              className="health-list"



            >



              {recentPortfolios



                .map(



                  (



                    portfolio,



                  ) => {



                    const valuation =



                      valuationByPortfolioId



                        .get(



                          portfolio



                            .portfolio_id,



                        );







                    const currentValue =



                      valuation



                        ? valuation



                            .total_market_value



                        : portfolio



                            .total_cost_basis;







                    const valueLabel =



                      valuation



                        ? (



                          valuation



                            .valuation_complete



                            ? (



                              isZh



                                ? "实时市值"



                                : "Live market value"



                            )



                            : (



                              isZh



                                ? "部分实时市值"



                                : "Partial market value"



                            )



                        )



                        : (



                          isZh



                            ? "成本基础"



                            : "Cost basis"



                        );







                    return (



                      <div



                        key={



                          portfolio



                            .portfolio_id



                        }



                        className="health-list-item"



                      >



                        <div>



                          <strong>



                            {



                              portfolio.name



                            }



                          </strong>







                          <span>



                            {



                              portfolio



                                .positions



                                .length



                            }



                            {" "}



                            {isZh



                              ? "个持仓"



                              : "positions"}



                            {" · "}



                            {



                              portfolio.currency



                            }



                          </span>



                        </div>







                        <div>



                          <strong>



                            {formatPrice(



                              currentValue,



                              portfolio



                                .currency,



                              isZh,



                            )}



                          </strong>







                          <span>



                            {valueLabel}



                          </span>



                        </div>



                      </div>



                    );



                  },



                )}



            </div>



          ) : null}



        </article>











        {/*



         * ----------------------------------------------------



         * System Health



         * ----------------------------------------------------



         */}







        <article



          className="dashboard-card"



        >



          <div



            className="dashboard-card-header"



          >



            <div>



              <h2>



                {t(



                  "dashboard.systemHealth",



                )}



              </h2>



            </div>







            <Activity



              size={19}



            />



          </div>











          <div



            className="health-list"



          >



            {healthItems.map(



              (



                item,



              ) => {



                const state =



                  dependencies[



                    item.key



                  ];







                const healthy =



                  state === "ok";







                return (



                  <div



                    key={



                      item.key



                    }



                    className="health-list-item"



                  >



                    <div>



                      <strong>



                        {



                          item.label



                        }



                      </strong>







                      <span>



                        {



                          item.detail



                        }



                      </span>



                    </div>







                    <span



                      className={



                        healthy



                          ? "health-badge healthy"



                          : "health-badge degraded"



                      }



                    >



                      {healthy



                        ? (



                          isZh



                            ? "正常"



                            : "Healthy"



                        )



                        : (



                          isZh



                            ? "异常"



                            : "Degraded"



                        )}



                    </span>



                  </div>



                );



              },



            )}



          </div>



        </article>











        {/*



         * ----------------------------------------------------



         * Outbox



         * ----------------------------------------------------



         */}







        <article



          className={



            "dashboard-card "



            + "outbox-summary-card"



          }



        >



          <div



            className="dashboard-card-header"



          >



            <div>



              <h2>



                {t(



                  "dashboard.recentOutboxEvents",



                )}



              </h2>



            </div>







            <RadioTower



              size={19}



            />



          </div>







          {outboxSummaryQuery.isPending

          || recentOutboxQuery.isPending ? (

            <div

              className="dashboard-empty-state"

            >

              <Clock3

                size={26}

              />



              <strong>

                {isZh

                  ? "正在读取 Outbox"

                  : "Loading Outbox"}

              </strong>



              <span>

                {isZh

                  ? "正在同步事件投递状态。"

                  : "Synchronizing event delivery state."}

              </span>

            </div>

          ) : null}





          {outboxSummaryQuery.isError

          || recentOutboxQuery.isError ? (

            <div

              className="dashboard-empty-state"

            >

              <RadioTower

                size={26}

              />



              <strong>

                {isZh

                  ? "Outbox 数据暂时不可用"

                  : "Outbox data unavailable"}

              </strong>



              <span>

                {isZh

                  ? "请确认 FastAPI 与 PostgreSQL 状态。"

                  : "Check FastAPI and PostgreSQL."}

              </span>

            </div>

          ) : null}





          {outboxSummaryQuery.data

          && recentOutboxQuery.data ? (

            <div

              className="health-list"

            >

              <div

                className="health-list-item"

              >

                <div>

                  <strong>

                    {isZh

                      ? "事件投递"

                      : "Event delivery"}

                  </strong>



                  <span>

                    {isZh

                      ? "15 秒自动刷新"

                      : "Auto-refresh every 15s"}

                  </span>

                </div>



                <div>

                  <strong>

                    {

                      outboxSummaryQuery

                        .data

                        .published_count

                    }

                  </strong>



                  <span>

                    {isZh

                      ? "已发布"

                      : "Published"}

                  </span>

                </div>

              </div>





              <div

                className="health-list-item"

              >

                <div>

                  <strong>

                    {

                      outboxSummaryQuery

                        .data

                        .pending_count

                    }

                  </strong>



                  <span>

                    {isZh

                      ? "待处理"

                      : "Pending"}

                  </span>

                </div>



                <div>

                  <strong>

                    {

                      outboxSummaryQuery

                        .data

                        .failed_count

                    }

                  </strong>



                  <span>

                    {isZh

                      ? "失败"

                      : "Failed"}

                  </span>

                </div>

              </div>





              {recentOutboxQuery

                .data

                .items

                .map(

                  (

                    event,

                  ) => (

                    <div

                      key={

                        event.event_id

                      }

                      className="health-list-item"

                    >

                      <div>

                        <strong>

                          {

                            event.event_type

                          }

                        </strong>



                        <span>

                          {

                            event.aggregate_type

                          }

                          {" · "}

                          {

                            `v${event.schema_version}`

                          }

                        </span>

                      </div>



                      <div>

                        <strong>

                          {

                            event.status

                            === "published"

                              ? (

                                isZh

                                  ? "已发布"

                                  : "Published"

                              )

                              : event.status

                                === "pending"

                                ? (

                                  isZh

                                    ? "待处理"

                                    : "Pending"

                                )

                                : (

                                  isZh

                                    ? "失败"

                                    : "Failed"

                                )

                          }

                        </strong>



                        <span>

                          {

                            new Date(

                              event.created_at,

                            )

                              .toLocaleTimeString(

                                isZh

                                  ? "zh-CN"

                                  : "en-US",

                                {

                                  hour: "2-digit",

                                  minute: "2-digit",

                                },

                              )

                          }

                        </span>

                      </div>

                    </div>

                  ),

                )}





              {recentOutboxQuery

                .data

                .items

                .length === 0 ? (

                <div

                  className="dashboard-empty-state"

                >

                  <Clock3

                    size={22}

                  />



                  <strong>

                    {isZh

                      ? "暂无 Outbox 事件"

                      : "No Outbox events"}

                  </strong>

                </div>

              ) : null}

            </div>

          ) : null}



        </article>



      </section>



    </div>



  );



}