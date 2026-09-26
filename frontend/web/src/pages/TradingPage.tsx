import {
  FormEvent,
  useMemo,
  useState,
} from "react";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  RefreshCw,
  ShieldCheck,
  WalletCards,
  X,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  ApiError,
} from "../api/client";

import {
  cancelTradingOrder,
  createTradingAccount,
  getOpenTradingOrders,
  getSimulatedTradingQuote,
  getTradingAccount,
  getTradingExecutions,
  getTradingPositions,
  placeLimitOrder,
  placeMarketOrder,
  setSimulatedTradingQuote,
} from "../services/trading";

import type {
  TradingOrderType,
  TradingSide,
} from "../types/trading";

import "../trading.css";


const RUNTIME_ENV = (
  import.meta.env.VITE_RUNTIME_ENV
  ?? "local"
)
  .trim()
  .toLowerCase();

const QUOTE_SOURCE = (
  import.meta.env.VITE_TRADING_QUOTE_SOURCE
  ?? (
    RUNTIME_ENV === "local"
      ? "simulated"
      : "alpaca"
  )
)
  .trim()
  .toLowerCase();


function money(
  value: string | number,
): string {
  const numeric = Number(value);

  if (!Number.isFinite(numeric)) {
    return String(value);
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    },
  ).format(numeric);
}


function getErrorText(
  error: unknown,
  fallback: string,
): string {
  if (
    error instanceof Error
    && error.message.trim()
  ) {
    return error.message;
  }

  return fallback;
}


export function TradingPage() {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language
      .startsWith("zh");

  const queryClient =
    useQueryClient();

  const [
    initialCash,
    setInitialCash,
  ] = useState("100000");

  const [
    side,
    setSide,
  ] = useState<TradingSide>("BUY");

  const [
    orderType,
    setOrderType,
  ] = useState<TradingOrderType>("MARKET");

  const [
    symbol,
    setSymbol,
  ] = useState("AAPL");

  const [
    quantity,
    setQuantity,
  ] = useState("1");

  const [
    limitPrice,
    setLimitPrice,
  ] = useState("320.00");

  const [
    simSymbol,
    setSimSymbol,
  ] = useState("AAPL");

  const [
    simBid,
    setSimBid,
  ] = useState("319.00");

  const [
    simAsk,
    setSimAsk,
  ] = useState("319.10");

  const [
    simTtl,
    setSimTtl,
  ] = useState("1800");

  const localSimulationEnabled =
    RUNTIME_ENV === "local"
    && QUOTE_SOURCE === "simulated";

  const accountQuery =
    useQuery({
      queryKey: [
        "trading",
        "account",
      ],
      queryFn: ({
        signal,
      }) =>
        getTradingAccount(
          signal,
        ),
      retry: false,
      refetchInterval: 5_000,
    });

  const accountMissing =
    accountQuery.error
      instanceof ApiError
    && accountQuery.error.status
      === 404;

  const hasAccount =
    Boolean(
      accountQuery.data,
    );

  const positionsQuery =
    useQuery({
      queryKey: [
        "trading",
        "positions",
      ],
      queryFn: ({
        signal,
      }) =>
        getTradingPositions(
          signal,
        ),
      enabled: hasAccount,
      refetchInterval: 2_000,
    });

  const openOrdersQuery =
    useQuery({
      queryKey: [
        "trading",
        "open-orders",
      ],
      queryFn: ({
        signal,
      }) =>
        getOpenTradingOrders(
          signal,
        ),
      enabled: hasAccount,
      refetchInterval: 2_000,
    });

  const executionsQuery =
    useQuery({
      queryKey: [
        "trading",
        "executions",
      ],
      queryFn: ({
        signal,
      }) =>
        getTradingExecutions(
          signal,
        ),
      enabled: hasAccount,
      refetchInterval: 3_000,
    });

  const simulatedQuoteQuery =
    useQuery({
      queryKey: [
        "trading",
        "simulation-quote",
        simSymbol,
      ],
      queryFn: ({
        signal,
      }) =>
        getSimulatedTradingQuote(
          simSymbol
            .trim()
            .toUpperCase(),
          signal,
        ),
      enabled:
        localSimulationEnabled
        && Boolean(
          simSymbol.trim(),
        ),
      retry: false,
      refetchInterval: 2_000,
    });

  async function refreshTrading() {
    await queryClient
      .invalidateQueries({
        queryKey: [
          "trading",
        ],
      });
  }

  const createAccountMutation =
    useMutation({
      mutationFn: () =>
        createTradingAccount(
          initialCash,
        ),
      onSuccess: refreshTrading,
    });

  const orderMutation =
    useMutation({
      mutationFn:
        async () => {
          const normalized =
            symbol
              .trim()
              .toUpperCase();

          const parsedQuantity =
            Number.parseInt(
              quantity,
              10,
            );

          if (
            !normalized
            || !Number.isInteger(
              parsedQuantity,
            )
            || parsedQuantity <= 0
          ) {
            throw new Error(
              isZh
                ? "请输入有效的股票代码和数量。"
                : "Enter a valid symbol and quantity.",
            );
          }

          if (
            orderType === "MARKET"
          ) {
            return placeMarketOrder(
              side,
              normalized,
              parsedQuantity,
            );
          }

          const parsedPrice =
            Number(limitPrice);

          if (
            !Number.isFinite(
              parsedPrice,
            )
            || parsedPrice <= 0
          ) {
            throw new Error(
              isZh
                ? "请输入有效的限价。"
                : "Enter a valid limit price.",
            );
          }

          return placeLimitOrder(
            side,
            normalized,
            parsedQuantity,
            limitPrice,
          );
        },
      onSuccess: refreshTrading,
    });

  const cancelMutation =
    useMutation({
      mutationFn:
        cancelTradingOrder,
      onSuccess: refreshTrading,
    });

  const quoteMutation =
    useMutation({
      mutationFn:
        async () => {
          const normalized =
            simSymbol
              .trim()
              .toUpperCase();

          const bid =
            Number(simBid);

          const ask =
            Number(simAsk);

          const ttl =
            Number.parseInt(
              simTtl,
              10,
            );

          if (
            !normalized
            || !Number.isFinite(bid)
            || !Number.isFinite(ask)
            || bid <= 0
            || ask <= 0
            || bid > ask
            || !Number.isInteger(ttl)
            || ttl <= 0
          ) {
            throw new Error(
              isZh
                ? "请输入有效的 Bid、Ask 和 TTL。"
                : "Enter a valid bid, ask and TTL.",
            );
          }

          return setSimulatedTradingQuote({
            symbol: normalized,
            bid_price: simBid,
            ask_price: simAsk,
            bid_size: 100,
            ask_size: 100,
            ttl_seconds: ttl,
          });
        },
      onSuccess:
        async (quote) => {
          setSimSymbol(
            quote.symbol,
          );
          await refreshTrading();
        },
    });

  const realizedPnl =
    useMemo(
      () =>
        (
          positionsQuery.data
          ?? []
        ).reduce(
          (
            total,
            position,
          ) =>
            total
            + Number(
              position.realized_pnl,
            ),
          0,
        ),
      [
        positionsQuery.data,
      ],
    );

  function submitAccount(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    createAccountMutation.mutate();
  }

  function submitOrder(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    orderMutation.mutate();
  }

  function submitQuote(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    quoteMutation.mutate();
  }

  if (accountQuery.isPending) {
    return (
      <section className="page-section">
        <div className="page-card">
          <div className="dashboard-empty-state">
            <Activity className="spin" size={26} />
            <strong>
              {isZh
                ? "正在加载模拟交易账户"
                : "Loading paper trading account"}
            </strong>
          </div>
        </div>
      </section>
    );
  }

  if (accountMissing) {
    return (
      <section className="page-section">
        <div className="page-card trading-account-onboarding">
          <WalletCards size={32} />

          <h2>
            {isZh
              ? "创建模拟交易账户"
              : "Create Paper Trading Account"}
          </h2>

          <p>
            {isZh
              ? "使用虚拟资金进行 MARKET / LIMIT 买卖，不会产生真实交易。"
              : "Trade MARKET and LIMIT orders with virtual cash only."}
          </p>

          <form
            className="trading-create-account-form"
            onSubmit={submitAccount}
          >
            <label>
              <span>
                {isZh
                  ? "初始虚拟资金"
                  : "Initial virtual cash"}
              </span>

              <input
                type="number"
                min="1"
                step="0.01"
                value={initialCash}
                onChange={(event) =>
                  setInitialCash(
                    event.target.value,
                  )}
              />
            </label>

            <button
              type="submit"
              disabled={
                createAccountMutation.isPending
              }
            >
              {createAccountMutation.isPending
                ? (
                  isZh
                    ? "创建中..."
                    : "Creating..."
                )
                : (
                  isZh
                    ? "创建账户"
                    : "Create Account"
                )}
            </button>
          </form>

          {createAccountMutation.isError ? (
            <div className="trading-error">
              {getErrorText(
                createAccountMutation.error,
                isZh
                  ? "创建账户失败"
                  : "Unable to create account",
              )}
            </div>
          ) : null}
        </div>
      </section>
    );
  }

  if (
    accountQuery.isError
    || !accountQuery.data
  ) {
    return (
      <section className="page-section">
        <div className="page-card">
          <div className="dashboard-empty-state">
            <strong>
              {isZh
                ? "模拟交易服务不可用"
                : "Paper trading unavailable"}
            </strong>

            <span>
              {getErrorText(
                accountQuery.error,
                isZh
                  ? "请检查 FastAPI 和 PostgreSQL。"
                  : "Check FastAPI and PostgreSQL.",
              )}
            </span>
          </div>
        </div>
      </section>
    );
  }

  const account =
    accountQuery.data;

  const currentQuote =
    simulatedQuoteQuery.data;

  return (
    <section className="page-section">
      <div className="trading-runtime-bar">
        <div>
          <strong>
            {isZh ? "运行环境" : "Environment"}
          </strong>
          <span>{RUNTIME_ENV.toUpperCase()}</span>
        </div>

        <div>
          <strong>
            {isZh ? "行情源" : "Quote Source"}
          </strong>
          <span>{QUOTE_SOURCE.toUpperCase()}</span>
        </div>

        <div>
          <strong>
            {isZh ? "交易模式" : "Trading"}
          </strong>
          <span>PAPER</span>
        </div>

        <div className="trading-runtime-safe">
          <ShieldCheck size={15} />
          <span>
            {isZh
              ? "仅模拟交易"
              : "No real-money execution"}
          </span>
        </div>
      </div>

      <div className="trading-kpi-grid">
        <article className="trading-kpi">
          <span>
            {isZh ? "现金余额" : "Cash Balance"}
          </span>
          <strong>{money(account.cash_balance)}</strong>
        </article>

        <article className="trading-kpi">
          <span>
            {isZh ? "初始资金" : "Initial Cash"}
          </span>
          <strong>{money(account.initial_cash)}</strong>
        </article>

        <article className="trading-kpi">
          <span>
            {isZh ? "当前持仓" : "Open Positions"}
          </span>
          <strong>
            {
              positionsQuery.data
                ?.filter(
                  (position) =>
                    position.quantity > 0,
                )
                .length
              ?? 0
            }
          </strong>
        </article>

        <article className="trading-kpi">
          <span>
            {isZh ? "已实现盈亏" : "Realized PnL"}
          </span>
          <strong
            className={
              realizedPnl >= 0
                ? "trading-positive"
                : "trading-negative"
            }
          >
            {money(realizedPnl)}
          </strong>
        </article>
      </div>

      <div className="trading-main-grid">
        <div className="page-card">
          <div className="page-card-header">
            <div>
              <h2>{isZh ? "下单" : "Order Entry"}</h2>
              <p>
                {isZh
                  ? "MARKET 买单按 Ask 成交，卖单按 Bid 成交。"
                  : "MARKET buys execute at Ask; sells execute at Bid."}
              </p>
            </div>
          </div>

          <form
            className="trading-order-form"
            onSubmit={submitOrder}
          >
            <div className="trading-segmented">
              <button
                type="button"
                className={
                  side === "BUY"
                    ? "active buy"
                    : ""
                }
                onClick={() =>
                  setSide("BUY")}
              >
                <ArrowUpRight size={15} />
                BUY
              </button>

              <button
                type="button"
                className={
                  side === "SELL"
                    ? "active sell"
                    : ""
                }
                onClick={() =>
                  setSide("SELL")}
              >
                <ArrowDownRight size={15} />
                SELL
              </button>
            </div>

            <div className="trading-segmented">
              <button
                type="button"
                className={
                  orderType === "MARKET"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setOrderType("MARKET")}
              >
                MARKET
              </button>

              <button
                type="button"
                className={
                  orderType === "LIMIT"
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setOrderType("LIMIT")}
              >
                LIMIT
              </button>
            </div>

            <div className="trading-field-grid">
              <label>
                <span>{isZh ? "股票代码" : "Symbol"}</span>
                <input
                  value={symbol}
                  onChange={(event) =>
                    setSymbol(
                      event.target.value.toUpperCase(),
                    )}
                />
              </label>

              <label>
                <span>{isZh ? "数量" : "Quantity"}</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={quantity}
                  onChange={(event) =>
                    setQuantity(
                      event.target.value,
                    )}
                />
              </label>

              {orderType === "LIMIT" ? (
                <label>
                  <span>{isZh ? "限价" : "Limit Price"}</span>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={limitPrice}
                    onChange={(event) =>
                      setLimitPrice(
                        event.target.value,
                      )}
                  />
                </label>
              ) : null}
            </div>

            <button
              type="submit"
              className={
                side === "BUY"
                  ? "trading-submit buy"
                  : "trading-submit sell"
              }
              disabled={
                orderMutation.isPending
              }
            >
              {orderMutation.isPending
                ? (
                  isZh
                    ? "提交中..."
                    : "Submitting..."
                )
                : `${side} ${orderType}`}
            </button>

            {orderMutation.isError ? (
              <div className="trading-error">
                {getErrorText(
                  orderMutation.error,
                  isZh
                    ? "下单失败"
                    : "Order failed",
                )}
              </div>
            ) : null}
          </form>
        </div>

        {localSimulationEnabled ? (
          <div className="page-card">
            <div className="page-card-header">
              <div>
                <h2>
                  {isZh
                    ? "本地行情模拟器"
                    : "Local Quote Simulator"}
                </h2>
                <p>
                  {isZh
                    ? "仅本地环境可用，显式写入 Redis bid/ask。"
                    : "Local-only control for explicit Redis bid/ask quotes."}
                </p>
              </div>
            </div>

            <form
              className="trading-simulation-form"
              onSubmit={submitQuote}
            >
              <div className="trading-field-grid">
                <label>
                  <span>Symbol</span>
                  <input
                    value={simSymbol}
                    onChange={(event) =>
                      setSimSymbol(
                        event.target.value.toUpperCase(),
                      )}
                  />
                </label>

                <label>
                  <span>Bid</span>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={simBid}
                    onChange={(event) =>
                      setSimBid(event.target.value)}
                  />
                </label>

                <label>
                  <span>Ask</span>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={simAsk}
                    onChange={(event) =>
                      setSimAsk(event.target.value)}
                  />
                </label>

                <label>
                  <span>TTL (s)</span>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={simTtl}
                    onChange={(event) =>
                      setSimTtl(event.target.value)}
                  />
                </label>
              </div>

              <button
                type="submit"
                disabled={
                  quoteMutation.isPending
                }
              >
                {quoteMutation.isPending
                  ? (
                    isZh
                      ? "更新中..."
                      : "Updating..."
                  )
                  : (
                    isZh
                      ? "更新模拟行情"
                      : "Update Simulated Quote"
                  )}
              </button>
            </form>

            {quoteMutation.isError ? (
              <div className="trading-error">
                {getErrorText(
                  quoteMutation.error,
                  isZh
                    ? "更新行情失败"
                    : "Quote update failed",
                )}
              </div>
            ) : null}

            <div className="trading-quote-panel">
              <div>
                <span>Bid</span>
                <strong>
                  {currentQuote
                    ? money(currentQuote.bid_price)
                    : "—"}
                </strong>
              </div>

              <div>
                <span>Ask</span>
                <strong>
                  {currentQuote
                    ? money(currentQuote.ask_price)
                    : "—"}
                </strong>
              </div>
            </div>
          </div>
        ) : (
          <div className="page-card trading-real-mode-card">
            <div className="trading-real-mode">
              <ShieldCheck size={30} />
              <strong>
                {QUOTE_SOURCE.toUpperCase()}
              </strong>
              <span>
                {isZh
                  ? "网页模拟行情控制已关闭，后端负责真实 bid/ask。"
                  : "Simulation controls are disabled; backend real bid/ask is active."}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="page-card trading-section-card">
        <div className="page-card-header">
          <div>
            <h2>{isZh ? "持仓" : "Positions"}</h2>
            <p>
              {isZh
                ? "当前模拟账户持仓与已实现盈亏。"
                : "Current paper positions and realized PnL."}
            </p>
          </div>

          <button
            className="trading-icon-button"
            type="button"
            onClick={() => {
              void refreshTrading();
            }}
            aria-label="Refresh trading state"
          >
            <RefreshCw size={15} />
          </button>
        </div>

        <div className="market-table-wrapper">
          <table className="market-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>{isZh ? "数量" : "Quantity"}</th>
                <th>{isZh ? "平均成本" : "Average Cost"}</th>
                <th>{isZh ? "已实现盈亏" : "Realized PnL"}</th>
              </tr>
            </thead>
            <tbody>
              {(positionsQuery.data ?? []).map(
                (position) => (
                  <tr key={position.symbol}>
                    <td><strong>{position.symbol}</strong></td>
                    <td>{position.quantity}</td>
                    <td>{money(position.average_cost)}</td>
                    <td
                      className={
                        Number(position.realized_pnl) >= 0
                          ? "trading-positive"
                          : "trading-negative"
                      }
                    >
                      {money(position.realized_pnl)}
                    </td>
                  </tr>
                ),
              )}

              {(positionsQuery.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={4}>
                    {isZh ? "暂无持仓" : "No positions"}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="page-card trading-section-card">
        <div className="page-card-header">
          <div>
            <h2>{isZh ? "待成交订单" : "Open Orders"}</h2>
            <p>
              {isZh
                ? "Worker 自动处理 PENDING LIMIT 订单。"
                : "The worker automatically processes PENDING LIMIT orders."}
            </p>
          </div>
        </div>

        <div className="market-table-wrapper">
          <table className="market-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Type</th>
                <th>Qty</th>
                <th>Limit</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(openOrdersQuery.data ?? []).map(
                (order) => (
                  <tr key={order.order_id}>
                    <td><strong>{order.symbol}</strong></td>
                    <td>{order.side}</td>
                    <td>{order.order_type}</td>
                    <td>{order.quantity}</td>
                    <td>
                      {order.limit_price
                        ? money(order.limit_price)
                        : "—"}
                    </td>
                    <td>
                      <span className="trading-status pending">
                        {order.status}
                      </span>
                    </td>
                    <td>
                      <button
                        className="trading-cancel-button"
                        type="button"
                        disabled={
                          cancelMutation.isPending
                        }
                        onClick={() =>
                          cancelMutation.mutate(
                            order.order_id,
                          )}
                      >
                        <X size={14} />
                        {isZh ? "取消" : "Cancel"}
                      </button>
                    </td>
                  </tr>
                ),
              )}

              {(openOrdersQuery.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    {isZh
                      ? "当前没有待成交订单"
                      : "No open orders"}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="page-card trading-section-card">
        <div className="page-card-header">
          <div>
            <h2>{isZh ? "成交记录" : "Executions"}</h2>
            <p>
              {isZh
                ? "最近 50 笔模拟成交。"
                : "Latest 50 paper executions."}
            </p>
          </div>
        </div>

        <div className="market-table-wrapper">
          <table className="market-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Execution ID</th>
              </tr>
            </thead>
            <tbody>
              {(executionsQuery.data ?? []).map(
                (execution) => (
                  <tr key={execution.execution_id}>
                    <td><strong>{execution.symbol}</strong></td>
                    <td>{execution.side}</td>
                    <td>{execution.quantity}</td>
                    <td>{money(execution.price)}</td>
                    <td className="trading-id-cell">
                      {execution.execution_id}
                    </td>
                  </tr>
                ),
              )}

              {(executionsQuery.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    {isZh
                      ? "暂无成交记录"
                      : "No executions"}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
