import {
  FormEvent,
  useState,
} from "react";

import {
  useQuery,
} from "@tanstack/react-query";

import {
  Activity,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  getMarketQuote,
} from "../services/market";


export function MarketDataPage() {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language.startsWith("zh");

  const [
    input,
    setInput,
  ] = useState(
    "AAPL",
  );

  const [
    symbol,
    setSymbol,
  ] = useState(
    "AAPL",
  );


  const quoteQuery =
    useQuery({
      queryKey: [
        "market-quote",
        symbol,
      ],

      queryFn: ({
        signal,
      }) =>
        getMarketQuote(
          symbol,
          signal,
        ),

      refetchInterval:
        60_000,
    });


  function submit(
    event:
      FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const normalized =
      input
        .trim()
        .toUpperCase();

    if (!normalized) {
      return;
    }

    setSymbol(
      normalized,
    );
  }


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
            <h2>
              {isZh
                ? "股票行情查询"
                : "Market Quote Search"}
            </h2>

            <p>
              {isZh
                ? (
                  "通过 RealStock FastAPI "
                  + "查询真实市场行情。"
                )
                : (
                  "Search live market data "
                  + "through the RealStock FastAPI."
                )}
            </p>
          </div>
        </div>


        <form
          className="market-search-form"
          onSubmit={
            submit
          }
        >
          <div
            className="market-search-input"
          >
            <Search
              size={17}
            />

            <input
              value={
                input
              }
              onChange={(
                event,
              ) => {
                setInput(
                  event
                    .target
                    .value,
                );
              }}
              placeholder={
                isZh
                  ? "输入股票代码，例如 AAPL"
                  : "Enter symbol, e.g. AAPL"
              }
            />
          </div>

          <button
            type="submit"
          >
            {isZh
              ? "查询"
              : "Search"}
          </button>
        </form>


        {quoteQuery.isPending ? (
          <div
            className="dashboard-empty-state"
          >
            <Activity
              size={26}
            />

            <strong>
              {isZh
                ? "正在加载行情"
                : "Loading market data"}
            </strong>
          </div>
        ) : null}


        {quoteQuery.isError ? (
          <div
            className="dashboard-empty-state"
          >
            <strong>
              {isZh
                ? "无法获取该股票行情"
                : "Unable to load market data"}
            </strong>

            <span>
              {isZh
                ? (
                  "请检查股票代码或"
                  + "后端市场数据服务。"
                )
                : (
                  "Check the symbol or "
                  + "market data backend."
                )}
            </span>
          </div>
        ) : null}


        {quoteQuery.data ? (
          <div
            className="market-detail-grid"
          >
            <article
              className="market-detail-main"
            >
              <div
                className="symbol-row"
              >
                <h2>
                  {
                    quoteQuery
                      .data
                      .symbol
                  }
                </h2>

                <span>
                  {
                    quoteQuery
                      .data
                      .exchange
                  }
                </span>
              </div>

              <p>
                {
                  quoteQuery
                    .data
                    .name
                }
              </p>

              <strong
                className="market-detail-price"
              >
                $
                {
                  Number(
                    quoteQuery
                      .data
                      .close,
                  )
                    .toFixed(2)
                }
              </strong>

              <div
                className={
                  Number(
                    quoteQuery
                      .data
                      .change,
                  ) >= 0
                    ? "market-positive"
                    : "market-negative"
                }
              >
                {Number(
                  quoteQuery
                    .data
                    .change,
                ) >= 0 ? (
                  <TrendingUp
                    size={17}
                  />
                ) : (
                  <TrendingDown
                    size={17}
                  />
                )}

                {
                  quoteQuery
                    .data
                    .change
                }

                {" / "}

                {
                  quoteQuery
                    .data
                    .percent_change
                }
                %
              </div>
            </article>


            <article
              className="market-detail-stats"
            >
              <dl>
                <div>
                  <dt>
                    {isZh
                      ? "开盘"
                      : "Open"}
                  </dt>

                  <dd>
                    {
                      quoteQuery
                        .data
                        .open
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    {isZh
                      ? "最高"
                      : "High"}
                  </dt>

                  <dd>
                    {
                      quoteQuery
                        .data
                        .high
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    {isZh
                      ? "最低"
                      : "Low"}
                  </dt>

                  <dd>
                    {
                      quoteQuery
                        .data
                        .low
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    {isZh
                      ? "成交量"
                      : "Volume"}
                  </dt>

                  <dd>
                    {
                      quoteQuery
                        .data
                        .volume
                        .toLocaleString()
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    MIC
                  </dt>

                  <dd>
                    {
                      quoteQuery
                        .data
                        .mic_code
                    }
                  </dd>
                </div>

                <div>
                  <dt>
                    {isZh
                      ? "市场状态"
                      : "Market"}
                  </dt>

                  <dd>
                    {
                      quoteQuery
                        .data
                        .is_market_open
                        ? (
                          isZh
                            ? "交易中"
                            : "Open"
                        )
                        : (
                          isZh
                            ? "已休市"
                            : "Closed"
                        )
                    }
                  </dd>
                </div>
              </dl>
            </article>
          </div>
        ) : null}
      </div>
    </section>
  );
}