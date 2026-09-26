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
  Check,
  ChevronUp,
  CircleDollarSign,
  Pencil,
  Plus,
  Trash2,
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
  addPortfolioPosition,
  createPortfolio,
  deletePortfolioPosition,
  getPortfolios,
  getPortfolioValuation,
  updatePortfolioPosition,
} from "../services/portfolio";

import type {
  PortfolioPosition,
} from "../types/portfolio";

import "../portfolio.css";

interface AddPositionMutationInput {
  portfolioId: string;
  symbol: string;
  market: string;
  quantity: string;
  averageCost: string;
}

interface UpdatePositionMutationInput {
  portfolioId: string;
  positionId: string;
  quantity: string;
  averageCost: string;
}

interface DeletePositionMutationInput {
  portfolioId: string;
  positionId: string;
}

function normalizeSymbol(
  value: string,
): string {
  return value
    .trim()
    .toUpperCase();
}

function isPositiveNumber(
  value: string,
): boolean {
  const number =
    Number(value);

  return (
    Number.isFinite(number)
    &&
    number > 0
  );
}

function formatCurrency(
  value: string,
  currency: string,
  isZh: boolean,
): string {
  const number =
    Number(value);

  if (
    !Number.isFinite(number)
  ) {
    return "—";
  }

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
    number,
  );
}

function formatQuantity(
  value: string,
): string {
  const number =
    Number(value);

  if (
    !Number.isFinite(number)
  ) {
    return value;
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      maximumFractionDigits: 8,
    },
  ).format(
    number,
  );
}

function formatEditableDecimal(
  value: string,
): string {
  const normalized =
    value.trim();

  if (
    !normalized.includes(".")
  ) {
    return normalized;
  }

  const [
    integerPart = "",
    fractionPart = "",
  ] = normalized.split(
    ".",
    2,
  );

  const trimmedFraction =
    fractionPart.replace(
      /0+$/,
      "",
    );

  if (
    trimmedFraction.length
    === 0
  ) {
    return integerPart;
  }

  return (
    `${integerPart}.`
    + trimmedFraction
  );
}

function getApiErrorMessage(
  error: unknown,
  isZh: boolean,
): string {
  if (
    error instanceof ApiError
  ) {
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
      === 404
    ) {
      return isZh
        ? "投资组合或持仓不存在。"
        : "Portfolio or position not found.";
    }

    if (
      error.status
      === 409
    ) {
      return isZh
        ? "该股票已经存在于这个投资组合中。"
        : "This position already exists.";
    }

    if (
      error.status
      === 422
    ) {
      return isZh
        ? "输入数据无效，请检查数量和平均成本。"
        : "Invalid input. Check quantity and average cost.";
    }

    return error.message;
  }

  return isZh
    ? "请求失败，请稍后重试。"
    : "Request failed. Please try again.";
}

export function PortfoliosPage() {
  const {
    i18n,
  } = useTranslation();

  const queryClient =
    useQueryClient();

  const isZh =
    i18n.language
      .startsWith("zh");

  const [
    portfolioName,
    setPortfolioName,
  ] = useState("");

  const [
    expandedPortfolioId,
    setExpandedPortfolioId,
  ] = useState<
    string | null
  >(null);

  const [
    symbol,
    setSymbol,
  ] = useState("");

  const [
    quantity,
    setQuantity,
  ] = useState("");

  const [
    averageCost,
    setAverageCost,
  ] = useState("");

  const [
    createError,
    setCreateError,
  ] = useState<
    string | null
  >(null);

  const [
    positionError,
    setPositionError,
  ] = useState<
    string | null
  >(null);

  const [
    editingPosition,
    setEditingPosition,
  ] = useState<{
    portfolioId: string;
    position: PortfolioPosition;
  } | null>(null);

  const [
    editQuantity,
    setEditQuantity,
  ] = useState("");

  const [
    editAverageCost,
    setEditAverageCost,
  ] = useState("");

  const [
    deleteTarget,
    setDeleteTarget,
  ] = useState<{
    portfolioId: string;
    position: PortfolioPosition;
  } | null>(null);

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

  async function refreshPortfolio(
    portfolioId: string,
  ): Promise<void> {
    await Promise.all([
      queryClient
        .invalidateQueries({
          queryKey: [
            "portfolios",
            CURRENT_USER_ID,
          ],
        }),

      queryClient
        .invalidateQueries({
          queryKey: [
            "portfolio-valuation",
            CURRENT_USER_ID,
            portfolioId,
          ],
        }),
    ]);
  }

  const createMutation =
    useMutation({
      mutationFn:
        () =>
          createPortfolio({
            name:
              portfolioName
                .trim(),

            currency:
              "USD",
          }),

      onSuccess:
        async (
          created,
        ) => {
          setPortfolioName("");
          setCreateError(null);

          setExpandedPortfolioId(
            created.portfolio_id,
          );

          await (
            queryClient
              .invalidateQueries({
                queryKey: [
                  "portfolios",
                  CURRENT_USER_ID,
                ],
              })
          );
        },

      onError:
        (
          error,
        ) => {
          setCreateError(
            getApiErrorMessage(
              error,
              isZh,
            ),
          );
        },
    });

  const addMutation =
    useMutation({
      mutationFn:
        (
          input:
            AddPositionMutationInput,
        ) =>
          addPortfolioPosition(
            input.portfolioId,
            {
              symbol:
                input.symbol,

              market:
                input.market,

              quantity:
                input.quantity,

              average_cost:
                input.averageCost,
            },
          ),

      onSuccess:
        async (
          _position,
          variables,
        ) => {
          setSymbol("");
          setQuantity("");
          setAverageCost("");
          setPositionError(null);

          await refreshPortfolio(
            variables.portfolioId,
          );
        },

      onError:
        (
          error,
        ) => {
          setPositionError(
            getApiErrorMessage(
              error,
              isZh,
            ),
          );
        },
    });

  const updateMutation =
    useMutation({
      mutationFn:
        (
          input:
            UpdatePositionMutationInput,
        ) =>
          updatePortfolioPosition(
            input.portfolioId,
            input.positionId,
            {
              quantity:
                input.quantity,

              average_cost:
                input.averageCost,
            },
          ),

      onSuccess:
        async (
          _position,
          variables,
        ) => {
          setEditingPosition(null);
          setPositionError(null);

          await refreshPortfolio(
            variables.portfolioId,
          );
        },

      onError:
        (
          error,
        ) => {
          setPositionError(
            getApiErrorMessage(
              error,
              isZh,
            ),
          );
        },
    });

  const deleteMutation =
    useMutation({
      mutationFn:
        (
          input:
            DeletePositionMutationInput,
        ) =>
          deletePortfolioPosition(
            input.portfolioId,
            input.positionId,
          ),

      onSuccess:
        async (
          _result,
          variables,
        ) => {
          setDeleteTarget(null);
          setPositionError(null);

          await refreshPortfolio(
            variables.portfolioId,
          );
        },

      onError:
        (
          error,
        ) => {
          setPositionError(
            getApiErrorMessage(
              error,
              isZh,
            ),
          );
        },
    });

  function submitPortfolio(
    event:
      FormEvent<
        HTMLFormElement
      >,
  ) {
    event.preventDefault();

    setCreateError(null);

    if (
      !portfolioName
        .trim()
    ) {
      setCreateError(
        isZh
          ? "请输入投资组合名称。"
          : "Enter a portfolio name.",
      );

      return;
    }

    createMutation.mutate();
  }

  function submitPosition(
    event:
      FormEvent<
        HTMLFormElement
      >,
    portfolioId: string,
  ) {
    event.preventDefault();

    setPositionError(null);

    const normalizedSymbol =
      normalizeSymbol(
        symbol,
      );

    if (
      !/^[A-Z0-9.^-]{1,20}$/
        .test(
          normalizedSymbol,
        )
    ) {
      setPositionError(
        isZh
          ? "请输入有效股票代码。"
          : "Enter a valid stock symbol.",
      );

      return;
    }

    if (
      !isPositiveNumber(
        quantity,
      )
    ) {
      setPositionError(
        isZh
          ? "持仓数量必须大于 0。"
          : "Quantity must be greater than zero.",
      );

      return;
    }

    if (
      !isPositiveNumber(
        averageCost,
      )
    ) {
      setPositionError(
        isZh
          ? "平均成本必须大于 0。"
          : "Average cost must be greater than zero.",
      );

      return;
    }

    addMutation.mutate({
      portfolioId,
      symbol:
        normalizedSymbol,
      market:
        "US",
      quantity:
        quantity.trim(),
      averageCost:
        averageCost.trim(),
    });
  }

  function beginEdit(
    portfolioId: string,
    position: PortfolioPosition,
  ) {
    setDeleteTarget(null);

    setEditingPosition({
      portfolioId,
      position,
    });

    setEditQuantity(
      formatEditableDecimal(
        position.quantity,
      ),
    );

    setEditAverageCost(
      formatEditableDecimal(
        position.average_cost,
      ),
    );

    setPositionError(null);
  }

  function submitEdit(
    event:
      FormEvent<
        HTMLFormElement
      >,
  ) {
    event.preventDefault();

    if (
      editingPosition
      === null
    ) {
      return;
    }

    setPositionError(null);

    if (
      !isPositiveNumber(
        editQuantity,
      )
    ) {
      setPositionError(
        isZh
          ? "持仓数量必须大于 0。"
          : "Quantity must be greater than zero.",
      );

      return;
    }

    if (
      !isPositiveNumber(
        editAverageCost,
      )
    ) {
      setPositionError(
        isZh
          ? "平均成本必须大于 0。"
          : "Average cost must be greater than zero.",
      );

      return;
    }

    updateMutation.mutate({
      portfolioId:
        editingPosition
          .portfolioId,

      positionId:
        editingPosition
          .position
          .position_id,

      quantity:
        editQuantity.trim(),

      averageCost:
        editAverageCost
          .trim(),
    });
  }

  if (
    portfoliosQuery.isPending
  ) {
    return (
      <section
        className="page-section"
      >
        <div
          className="page-card"
        >
          <div
            className="dashboard-empty-state"
          >
            <Activity
              size={30}
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
        </div>
      </section>
    );
  }

  if (
    portfoliosQuery.isError
  ) {
    return (
      <section
        className="page-section"
      >
        <div
          className="page-card"
        >
          <div
            className="dashboard-empty-state"
          >
            <BriefcaseBusiness
              size={30}
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
        </div>
      </section>
    );
  }

  return (
    <section
      className={
        "page-section "
        + "portfolio-page"
      }
    >
      <div
        className={
          "page-card "
          + "portfolio-create-card"
        }
      >
        <div
          className="portfolio-create-header"
        >
          <div>
            <h2>
              {isZh
                ? "投资组合"
                : "Portfolios"}
            </h2>

            <p>
              {isZh
                ? "PostgreSQL 持仓 · Twelve Data 实时估值"
                : "PostgreSQL positions · Twelve Data live valuation"}
            </p>
          </div>

          <BriefcaseBusiness
            size={21}
          />
        </div>

        <form
          className="portfolio-create-form"
          onSubmit={
            submitPortfolio
          }
        >
          <input
            value={
              portfolioName
            }
            onChange={(
              event,
            ) => {
              setPortfolioName(
                event.target.value,
              );

              setCreateError(null);
            }}
            placeholder={
              isZh
                ? "投资组合名称，例如 Growth Portfolio"
                : "Portfolio name, e.g. Growth Portfolio"
            }
            maxLength={100}
            disabled={
              createMutation.isPending
            }
          />

          <button
            type="submit"
            className="portfolio-secondary-button"
            disabled={
              createMutation.isPending
            }
          >
            <Plus
              size={16}
            />

            {createMutation.isPending
              ? (
                isZh
                  ? "创建中"
                  : "Creating"
              )
              : (
                isZh
                  ? "新建投资组合"
                  : "New Portfolio"
              )}
          </button>
        </form>

        <p
          className="portfolio-scope-note"
        >
          {isZh
            ? "当前正式行情估值链路使用 USD / US 市场。"
            : "The current live valuation flow uses USD / US market."}
        </p>

        {createError ? (
          <p
            className="portfolio-inline-error"
          >
            {createError}
          </p>
        ) : null}
      </div>

      {portfolios.length
      === 0 ? (
        <div
          className="page-card"
        >
          <div
            className="dashboard-empty-state"
          >
            <BriefcaseBusiness
              size={30}
            />

            <strong>
              {isZh
                ? "暂无投资组合"
                : "No portfolios yet"}
            </strong>

            <span>
              {isZh
                ? "在上方创建投资组合，然后添加第一只股票。"
                : "Create a portfolio above, then add your first position."}
            </span>
          </div>
        </div>
      ) : null}

      {portfolios.map(
        (
          portfolio,
          portfolioIndex,
        ) => {
          const valuationQuery =
            valuationQueries[
              portfolioIndex
            ];

          const valuation =
            valuationQuery?.data;

          const valuationLoading =
            valuationQuery
              ?.isPending
            ?? false;

          const valuationError =
            valuationQuery
              ?.isError
            ?? false;

          const unrealizedPnl =
            Number(
              valuation
                ?.total_unrealized_pnl
              ?? "0",
            );

          const expanded =
            expandedPortfolioId
            === portfolio
              .portfolio_id;

          const editingThisPortfolio =
            editingPosition
              ?.portfolioId
            === portfolio
              .portfolio_id;

          const deletingThisPortfolio =
            deleteTarget
              ?.portfolioId
            === portfolio
              .portfolio_id;

          return (
            <div
              key={
                portfolio
                  .portfolio_id
              }
              className={
                "page-card "
                + "portfolio-card"
              }
            >
              <div
                className="portfolio-card-header"
              >
                <div>
                  <h2>
                    {portfolio.name}
                  </h2>

                  <p>
                    {
                      portfolio.currency
                    }
                    {" · "}
                    {
                      portfolio
                        .positions
                        .length
                    }
                    {" "}
                    {isZh
                      ? "个持仓"
                      : "positions"}
                  </p>
                </div>

                <CircleDollarSign
                  size={20}
                />
              </div>

              <div
                className={
                  "dashboard-kpi-grid "
                  + "portfolio-summary-grid"
                }
              >
                <article
                  className="dashboard-kpi-card"
                >
                  <div
                    className="kpi-card-header"
                  >
                    <span>
                      {isZh
                        ? "实时市值"
                        : "Market Value"}
                    </span>
                  </div>

                  <strong>
                    {valuationLoading
                      ? "…"
                      : valuationError
                        ? "—"
                        : valuation
                          ? formatCurrency(
                            valuation
                              .total_market_value,
                            portfolio
                              .currency,
                            isZh,
                          )
                          : "—"}
                  </strong>

                  <small>
                    {valuation
                    &&
                    !valuation
                      .valuation_complete
                      ? (
                        isZh
                          ? (
                            "部分估值 · "
                            + `${valuation.missing_quotes} 个行情缺失`
                          )
                          : (
                            "Partial valuation · "
                            + `${valuation.missing_quotes} quotes missing`
                          )
                      )
                      : (
                        isZh
                          ? "实时估值"
                          : "Live valuation"
                      )}
                  </small>
                </article>

                <article
                  className="dashboard-kpi-card"
                >
                  <div
                    className="kpi-card-header"
                  >
                    <span>
                      {isZh
                        ? "未实现损益"
                        : "Unrealized P/L"}
                    </span>

                    {unrealizedPnl
                    >= 0 ? (
                      <TrendingUp
                        size={17}
                      />
                    ) : (
                      <TrendingDown
                        size={17}
                      />
                    )}
                  </div>

                  <strong
                    className={
                      valuation
                        ? (
                          unrealizedPnl
                            >= 0
                            ? "market-positive"
                            : "market-negative"
                        )
                        : undefined
                    }
                  >
                    {valuationLoading
                      ? "…"
                      : valuationError
                        ? "—"
                        : valuation
                          ? formatCurrency(
                            valuation
                              .total_unrealized_pnl,
                            portfolio
                              .currency,
                            isZh,
                          )
                          : "—"}
                  </strong>

                  <small>
                    {isZh
                      ? "当前持仓未实现损益"
                      : "Current unrealized P/L"}
                  </small>
                </article>

                <article
                  className="dashboard-kpi-card"
                >
                  <div
                    className="kpi-card-header"
                  >
                    <span>
                      {isZh
                        ? "成本基础"
                        : "Cost Basis"}
                    </span>
                  </div>

                  <strong>
                    {formatCurrency(
                      portfolio
                        .total_cost_basis,
                      portfolio
                        .currency,
                      isZh,
                    )}
                  </strong>

                  <small>
                    PostgreSQL
                  </small>
                </article>

                <article
                  className="dashboard-kpi-card"
                >
                  <div
                    className="kpi-card-header"
                  >
                    <span>
                      {isZh
                        ? "持仓数量"
                        : "Positions"}
                    </span>
                  </div>

                  <strong>
                    {
                      portfolio
                        .positions
                        .length
                    }
                  </strong>

                  <small>
                    {isZh
                      ? "当前投资组合"
                      : "Current portfolio"}
                  </small>
                </article>
              </div>

              {portfolio
                .positions
                .length > 0 ? (
                <div
                  className={
                    "market-table-wrapper "
                    + "portfolio-table"
                  }
                >
                  <table
                    className="market-table"
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
                            ? "数量"
                            : "Quantity"}
                        </th>

                        <th>
                          {isZh
                            ? "平均成本"
                            : "Avg. Cost"}
                        </th>

                        <th>
                          {isZh
                            ? "成本基础"
                            : "Cost Basis"}
                        </th>

                        <th>
                          {isZh
                            ? "市场价格"
                            : "Market Price"}
                        </th>

                        <th>
                          {isZh
                            ? "市值"
                            : "Market Value"}
                        </th>

                        <th>
                          P/L
                        </th>

                        <th>
                          {isZh
                            ? "操作"
                            : "Actions"}
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {portfolio
                        .positions
                        .map(
                          (
                            position,
                          ) => {
                            const valuedPosition =
                              valuation
                                ?.positions
                                .find(
                                  (
                                    item,
                                  ) =>
                                    (
                                      item
                                        .position_id
                                      === position
                                        .position_id
                                    ),
                                );

                            const positionPnl =
                              Number(
                                valuedPosition
                                  ?.unrealized_pnl
                                ?? "0",
                              );

                            return (
                              <tr
                                key={
                                  position
                                    .position_id
                                }
                              >
                                <td>
                                  <div
                                    className="symbol-cell"
                                  >
                                    <strong>
                                      {
                                        position
                                          .symbol
                                      }
                                    </strong>

                                    <span>
                                      {
                                        position
                                          .market
                                      }
                                    </span>
                                  </div>
                                </td>

                                <td>
                                  {formatQuantity(
                                    position
                                      .quantity,
                                  )}
                                </td>

                                <td>
                                  {formatCurrency(
                                    position
                                      .average_cost,
                                    portfolio
                                      .currency,
                                    isZh,
                                  )}
                                </td>

                                <td>
                                  {formatCurrency(
                                    position
                                      .cost_basis,
                                    portfolio
                                      .currency,
                                    isZh,
                                  )}
                                </td>

                                <td>
                                  {valuedPosition
                                    ?.quote_available
                                    &&
                                    valuedPosition
                                      .market_price
                                    ? formatCurrency(
                                      valuedPosition
                                        .market_price,
                                      portfolio
                                        .currency,
                                      isZh,
                                    )
                                    : "—"}
                                </td>

                                <td>
                                  {valuedPosition
                                    ?.quote_available
                                    &&
                                    valuedPosition
                                      .market_value
                                    ? formatCurrency(
                                      valuedPosition
                                        .market_value,
                                      portfolio
                                        .currency,
                                      isZh,
                                    )
                                    : "—"}
                                </td>

                                <td>
                                  {valuedPosition
                                    ?.quote_available
                                    &&
                                    valuedPosition
                                      .unrealized_pnl
                                    ? (
                                      <span
                                        className={
                                          positionPnl
                                            >= 0
                                            ? "market-positive"
                                            : "market-negative"
                                        }
                                      >
                                        {positionPnl
                                        >= 0 ? (
                                          <TrendingUp
                                            size={14}
                                          />
                                        ) : (
                                          <TrendingDown
                                            size={14}
                                          />
                                        )}

                                        {" "}

                                        {formatCurrency(
                                          valuedPosition
                                            .unrealized_pnl,
                                          portfolio
                                            .currency,
                                          isZh,
                                        )}
                                      </span>
                                    )
                                    : "—"}
                                </td>

                                <td>
                                  <div
                                    className="portfolio-row-actions"
                                  >
                                    <button
                                      type="button"
                                      className="portfolio-icon-button"
                                      title={
                                        isZh
                                          ? "编辑持仓"
                                          : "Edit position"
                                      }
                                      aria-label={
                                        isZh
                                          ? "编辑持仓"
                                          : "Edit position"
                                      }
                                      onClick={() =>
                                        beginEdit(
                                          portfolio
                                            .portfolio_id,
                                          position,
                                        )
                                      }
                                    >
                                      <Pencil
                                        size={15}
                                      />
                                    </button>

                                    <button
                                      type="button"
                                      className={
                                        "portfolio-icon-button "
                                        + "danger"
                                      }
                                      title={
                                        isZh
                                          ? "删除持仓"
                                          : "Delete position"
                                      }
                                      aria-label={
                                        isZh
                                          ? "删除持仓"
                                          : "Delete position"
                                      }
                                      onClick={() => {
                                        setEditingPosition(
                                          null,
                                        );

                                        setDeleteTarget({
                                          portfolioId:
                                            portfolio
                                              .portfolio_id,

                                          position,
                                        });

                                        setPositionError(
                                          null,
                                        );
                                      }}
                                    >
                                      <Trash2
                                        size={15}
                                      />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          },
                        )}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div
                  className="dashboard-empty-state"
                >
                  <BriefcaseBusiness
                    size={25}
                  />

                  <strong>
                    {isZh
                      ? "这个投资组合还没有持仓"
                      : "This portfolio has no positions"}
                  </strong>

                  <span>
                    {isZh
                      ? "点击“添加持仓”加入第一只股票。"
                      : "Use Add Position to add the first stock."}
                  </span>
                </div>
              )}

              {editingThisPortfolio
              &&
              editingPosition ? (
                <div
                  className="portfolio-position-panel"
                >
                  <div
                    className="portfolio-panel-header"
                  >
                    <strong>
                      {isZh
                        ? `编辑 ${editingPosition.position.symbol}`
                        : `Edit ${editingPosition.position.symbol}`}
                    </strong>
                  </div>

                  <form
                    className={
                      "portfolio-position-form "
                      + "edit-form"
                    }
                    onSubmit={
                      submitEdit
                    }
                  >
                    <div
                      className="portfolio-field"
                    >
                      <label>
                        {isZh
                          ? "数量"
                          : "Quantity"}
                      </label>

                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={
                          editQuantity
                        }
                        onChange={(
                          event,
                        ) => {
                          setEditQuantity(
                            event.target.value,
                          );

                          setPositionError(
                            null,
                          );
                        }}
                        disabled={
                          updateMutation
                            .isPending
                        }
                      />
                    </div>

                    <div
                      className="portfolio-field"
                    >
                      <label>
                        {isZh
                          ? "平均成本"
                          : "Average Cost"}
                      </label>

                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={
                          editAverageCost
                        }
                        onChange={(
                          event,
                        ) => {
                          setEditAverageCost(
                            event.target.value,
                          );

                          setPositionError(
                            null,
                          );
                        }}
                        disabled={
                          updateMutation
                            .isPending
                        }
                      />
                    </div>

                    <button
                      type="submit"
                      className="portfolio-secondary-button"
                      disabled={
                        updateMutation
                          .isPending
                      }
                    >
                      <Check
                        size={16}
                      />

                      {updateMutation
                        .isPending
                        ? (
                          isZh
                            ? "保存中"
                            : "Saving"
                        )
                        : (
                          isZh
                            ? "保存修改"
                            : "Save"
                        )}
                    </button>

                    <button
                      type="button"
                      className="portfolio-cancel-button"
                      onClick={() =>
                        setEditingPosition(
                          null,
                        )
                      }
                      disabled={
                        updateMutation
                          .isPending
                      }
                    >
                      <X
                        size={16}
                      />

                      {isZh
                        ? "取消"
                        : "Cancel"}
                    </button>
                  </form>
                </div>
              ) : null}

              {deletingThisPortfolio
              &&
              deleteTarget ? (
                <div
                  className="portfolio-delete-confirm"
                >
                  <strong>
                    {isZh
                      ? `确认删除 ${deleteTarget.position.symbol}？`
                      : `Delete ${deleteTarget.position.symbol}?`}
                  </strong>

                  <p>
                    {isZh
                      ? "删除后该持仓会从 PostgreSQL 中移除，并重新计算投资组合估值。"
                      : "This removes the position from PostgreSQL and recalculates the portfolio valuation."}
                  </p>

                  <div
                    className="portfolio-delete-actions"
                  >
                    <button
                      type="button"
                      className="portfolio-danger-button"
                      disabled={
                        deleteMutation
                          .isPending
                      }
                      onClick={() =>
                        deleteMutation.mutate({
                          portfolioId:
                            deleteTarget
                              .portfolioId,

                          positionId:
                            deleteTarget
                              .position
                              .position_id,
                        })
                      }
                    >
                      <Trash2
                        size={16}
                      />

                      {deleteMutation
                        .isPending
                        ? (
                          isZh
                            ? "删除中"
                            : "Deleting"
                        )
                        : (
                          isZh
                            ? "确认删除"
                            : "Delete"
                        )}
                    </button>

                    <button
                      type="button"
                      className="portfolio-cancel-button"
                      disabled={
                        deleteMutation
                          .isPending
                      }
                      onClick={() =>
                        setDeleteTarget(
                          null,
                        )
                      }
                    >
                      {isZh
                        ? "取消"
                        : "Cancel"}
                    </button>
                  </div>
                </div>
              ) : null}

              <div
                className="portfolio-card-footer"
              >
                <button
                  type="button"
                  className="portfolio-toggle-button"
                  onClick={() => {
                    if (expanded) {
                      setExpandedPortfolioId(
                        null,
                      );
                    } else {
                      setExpandedPortfolioId(
                        portfolio
                          .portfolio_id,
                      );
                    }

                    setPositionError(
                      null,
                    );
                  }}
                >
                  {expanded ? (
                    <ChevronUp
                      size={16}
                    />
                  ) : (
                    <Plus
                      size={16}
                    />
                  )}

                  {expanded
                    ? (
                      isZh
                        ? "收起添加表单"
                        : "Collapse"
                    )
                    : (
                      isZh
                        ? "添加持仓"
                        : "Add Position"
                    )}
                </button>
              </div>

              {expanded ? (
                <div
                  className="portfolio-position-panel"
                >
                  <div
                    className="portfolio-panel-header"
                  >
                    <strong>
                      {isZh
                        ? "添加新持仓"
                        : "Add New Position"}
                    </strong>

                    <button
                      type="button"
                      className="portfolio-icon-button"
                      aria-label={
                        isZh
                          ? "收起"
                          : "Collapse"
                      }
                      title={
                        isZh
                          ? "收起"
                          : "Collapse"
                      }
                      onClick={() =>
                        setExpandedPortfolioId(
                          null,
                        )
                      }
                    >
                      <ChevronUp
                        size={16}
                      />
                    </button>
                  </div>

                  <form
                    className="portfolio-position-form"
                    onSubmit={(
                      event,
                    ) =>
                      submitPosition(
                        event,
                        portfolio
                          .portfolio_id,
                      )
                    }
                  >
                    <div
                      className="portfolio-field"
                    >
                      <label>
                        {isZh
                          ? "股票代码"
                          : "Symbol"}
                      </label>

                      <input
                        value={
                          symbol
                        }
                        onChange={(
                          event,
                        ) => {
                          setSymbol(
                            event
                              .target
                              .value
                              .toUpperCase(),
                          );

                          setPositionError(
                            null,
                          );
                        }}
                        placeholder="AAPL"
                        maxLength={20}
                        disabled={
                          addMutation
                            .isPending
                        }
                      />
                    </div>

                    <div
                      className="portfolio-field"
                    >
                      <label>
                        {isZh
                          ? "市场"
                          : "Market"}
                      </label>

                      <select
                        value="US"
                        disabled
                      >
                        <option
                          value="US"
                        >
                          US
                        </option>
                      </select>
                    </div>

                    <div
                      className="portfolio-field"
                    >
                      <label>
                        {isZh
                          ? "数量"
                          : "Quantity"}
                      </label>

                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={
                          quantity
                        }
                        onChange={(
                          event,
                        ) => {
                          setQuantity(
                            event.target.value,
                          );

                          setPositionError(
                            null,
                          );
                        }}
                        placeholder="10"
                        disabled={
                          addMutation
                            .isPending
                        }
                      />
                    </div>

                    <div
                      className="portfolio-field"
                    >
                      <label>
                        {isZh
                          ? "平均成本"
                          : "Average Cost"}
                      </label>

                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={
                          averageCost
                        }
                        onChange={(
                          event,
                        ) => {
                          setAverageCost(
                            event.target.value,
                          );

                          setPositionError(
                            null,
                          );
                        }}
                        placeholder="200"
                        disabled={
                          addMutation
                            .isPending
                        }
                      />
                    </div>

                    <button
                      type="submit"
                      className="portfolio-secondary-button"
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
                            ? "添加持仓"
                            : "Add Position"
                        )}
                    </button>
                  </form>
                </div>
              ) : null}

              {positionError ? (
                <p
                  className="portfolio-inline-error"
                >
                  {positionError}
                </p>
              ) : null}
            </div>
          );
        },
      )}
    </section>
  );
}
