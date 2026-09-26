import {
  useQuery,
} from "@tanstack/react-query";

import {
  Activity,
  CircleAlert,
} from "lucide-react";

import {
  Outlet,
  useLocation,
} from "react-router-dom";

import {
  useTranslation,
} from "react-i18next";

import {
  apiUrl,
} from "../api/client";

import {
  LanguageSwitcher,
} from "../components/LanguageSwitcher";

import {
  Sidebar,
} from "../components/Sidebar";


interface HealthResponse {
  status: string;
}


interface ReadinessResponse {
  status: string;

  dependencies: {
    postgresql?: string;
    redis?: string;
    localstack?: string;
    s3?: string;
    dynamodb?: string;

    [key: string]:
      | string
      | undefined;
  };
}


async function getHealth():
  Promise<HealthResponse> {
  const response =
    await fetch(
      apiUrl(
        "/health",
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
      "Health endpoint failed",
    );
  }

  return response.json() as Promise<
    HealthResponse
  >;
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

  /*
   * Readiness deliberately returns
   * HTTP 503 when dependencies are
   * unavailable.
   *
   * We still want the response body
   * so the UI can show the individual
   * dependency states.
   */
  return response.json() as Promise<
    ReadinessResponse
  >;
}


function getPageTitleKey(
  pathname: string,
): string {
  if (
    pathname.startsWith(
      "/market",
    )
  ) {
    return "nav.marketData";
  }

  if (
    pathname.startsWith(
      "/portfolios",
    )
  ) {
    return "nav.portfolios";
  }

  if (
    pathname.startsWith(
      "/watchlist",
    )
  ) {
    return "nav.watchlist";
  }

  if (
    pathname.startsWith(
      "/news",
    )
  ) {
    return "nav.news";
  }

  if (
    pathname.startsWith(
      "/system-health",
    )
  ) {
    return "nav.systemHealth";
  }

  if (
    pathname.startsWith(
      "/outbox-events",
    )
  ) {
    return "nav.outboxEvents";
  }

  if (
    pathname.startsWith(
      "/settings",
    )
  ) {
    return "nav.settings";
  }

  return "nav.dashboard";
}


export function AppLayout() {
  const {
    t,
    i18n,
  } = useTranslation();

  const location =
    useLocation();

  const isZh =
    i18n.language
      .startsWith(
        "zh",
      );


  const healthQuery =
    useQuery({
      queryKey: [
        "system",
        "health",
      ],

      queryFn:
        getHealth,

      refetchInterval:
        30_000,

      retry: 1,
    });


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


  const apiHealthy =
    healthQuery.data?.status
      === "ok";


  const localStackHealthy =
    readinessQuery
      .data
      ?.dependencies
      .localstack
      === "ok";


  const pageTitle =
    t(
      getPageTitleKey(
        location.pathname,
      ),
    );


  return (
    <div
      className="enterprise-shell"
    >
      <Sidebar />


      <div
        className="enterprise-main"
      >
        <header
          className={
            "enterprise-header"
          }
        >
          <div
            className={
              "enterprise-header-title"
            }
          >
            <h1>
              {pageTitle}
            </h1>

            <p>
              {location.pathname
                === "/dashboard"
                ? (
                  isZh
                    ? (
                      "欢迎回来！"
                      + "这里展示您的投资概览"
                      + "与系统运行状态。"
                    )
                    : (
                      "Welcome back! "
                      + "Here's an overview "
                      + "of your investments "
                      + "and system status."
                    )
                )
                : (
                  isZh
                    ? (
                      "RealStock Enterprise "
                      + "投资管理平台"
                    )
                    : (
                      "RealStock Enterprise "
                      + "investment platform"
                    )
                )}
            </p>
          </div>


          <div
            className={
              "enterprise-header-actions"
            }
          >
            <div
              className={
                apiHealthy
                  ? (
                    "header-status "
                    + "healthy"
                  )
                  : (
                    "header-status "
                    + "degraded"
                  )
              }
            >
              {apiHealthy ? (
                <Activity
                  size={15}
                />
              ) : (
                <CircleAlert
                  size={15}
                />
              )}

              <span>
                {apiHealthy
                  ? (
                    isZh
                      ? "API 正常"
                      : "API Healthy"
                  )
                  : (
                    isZh
                      ? "API 异常"
                      : "API Unavailable"
                  )}
              </span>
            </div>


            <div
              className={
                localStackHealthy
                  ? (
                    "header-status "
                    + "healthy"
                  )
                  : (
                    "header-status "
                    + "degraded"
                  )
              }
            >
              <span
                className={
                  "header-status-dot"
                }
              />

              <span>
                {localStackHealthy
                  ? (
                    isZh
                      ? (
                        "LocalStack "
                        + "已连接"
                      )
                      : (
                        "LocalStack "
                        + "Connected"
                      )
                  )
                  : (
                    isZh
                      ? (
                        "LocalStack "
                        + "未就绪"
                      )
                      : (
                        "LocalStack "
                        + "Degraded"
                      )
                  )}
              </span>
            </div>


            <LanguageSwitcher />


            <div
              className={
                "user-avatar"
              }
              aria-label={
                "RealStock user"
              }
            >
              RS
            </div>
          </div>
        </header>


        <main
          className={
            "enterprise-content"
          }
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}