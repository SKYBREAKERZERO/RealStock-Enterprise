import {
  useQuery,
} from "@tanstack/react-query";

import {
  Activity,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  apiUrl,
} from "../api/client";


interface ReadinessResponse {
  status: string;

  dependencies: Record<
    string,
    string
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

  return response.json() as Promise<
    ReadinessResponse
  >;
}


export function SystemHealthPage() {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language.startsWith(
      "zh",
    );


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
    });


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
                ? "系统状态"
                : "System Health"}
            </h2>

            <p>
              {isZh
                ? "实时检查核心基础设施依赖。"
                : "Live status of core infrastructure dependencies."}
            </p>
          </div>

          <Activity
            size={20}
          />
        </div>


        <div
          className="health-list"
        >
          {Object.entries(
            readinessQuery
              .data
              ?.dependencies
              ?? {},
          ).map(
            ([
              name,
              state,
            ]) => (
              <div
                key={
                  name
                }
                className="health-list-item"
              >
                <div>
                  <strong>
                    {name}
                  </strong>
                </div>

                <span
                  className={
                    state === "ok"
                      ? "health-badge healthy"
                      : "health-badge degraded"
                  }
                >
                  {state === "ok"
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
            ),
          )}
        </div>
      </div>
    </section>
  );
}