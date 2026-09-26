import {
  useQuery,
} from "@tanstack/react-query";

import {
  Clock3,
  Newspaper,
  RefreshCw,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  getNews,
} from "../services/news";

import type {
  NewsItem,
} from "../services/news";


function formatNewsTime(
  value: string,
  language: string,
): string {
  const date =
    new Date(
      value,
    );

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value;
  }

  const locale =
    language.startsWith(
      "zh",
    )
      ? "zh-CN"
      : "en-US";

  return date.toLocaleString(
    locale,
    {
      month:
        "2-digit",

      day:
        "2-digit",

      hour:
        "2-digit",

      minute:
        "2-digit",
    },
  );
}


function formatUpdatedTime(
  value: number,
  language: string,
): string {
  if (!value) {
    return "—";
  }

  const locale =
    language.startsWith(
      "zh",
    )
      ? "zh-CN"
      : "en-US";

  return new Date(
    value,
  ).toLocaleTimeString(
    locale,
    {
      hour:
        "2-digit",

      minute:
        "2-digit",

      second:
        "2-digit",
    },
  );
}


function NewsItemRow({
  item,
  language,
}: {
  item: NewsItem;

  language: string;
}) {
  return (
    <article
      className={
        "health-list-item"
      }
    >
      <div>
        <div
          style={{
            display:
              "flex",

            alignItems:
              "center",

            gap:
              "8px",

            marginBottom:
              "6px",
          }}
        >
          <Clock3
            size={14}
          />

          <span>
            {formatNewsTime(
              item.published_at,
              language,
            )}
          </span>
        </div>


        <strong>
          {item.title}
        </strong>


        <p
          style={{
            margin:
              "8px 0 0",

            lineHeight:
              1.6,
          }}
        >
          {item.summary}
        </p>


        {item.source ? (
          <div
            style={{
              marginTop:
                "8px",

              fontSize:
                "12px",

              opacity:
                0.65,
            }}
          >
            {item.source}
          </div>
        ) : null}
      </div>
    </article>
  );
}


export function NewsPage() {
  const {
    t,
    i18n,
  } = useTranslation();


  const newsQuery =
    useQuery({
      queryKey: [
        "news",
        "latest",
      ],

      queryFn: ({
        signal,
      }) =>
        getNews(
          signal,
        ),

      staleTime:
        30_000,

      refetchInterval:
        60_000,

      retry: 1,

      refetchOnWindowFocus:
        false,
    });


  const items =
    newsQuery
      .data
      ?.items
      ?? [];


  const lastUpdated =
    formatUpdatedTime(
      newsQuery
        .dataUpdatedAt,
      i18n.language,
    );


  return (
    <section
      className={
        "page-section"
      }
    >
      <div
        className={
          "page-card"
        }
      >
        <div
          className={
            "page-card-header"
          }
        >
          <div>
            <h2>
              {t(
                "news.title",
              )}
            </h2>

            <p>
              {t(
                "news.description",
              )}
            </p>
          </div>


          <button
            type="button"
            onClick={() => {
              void newsQuery.refetch();
            }}
            disabled={
              newsQuery.isFetching
            }
          >
            <RefreshCw
              size={16}
            />

            {newsQuery.isFetching
              ? t(
                "news.refreshing",
              )
              : t(
                "news.refresh",
              )}
          </button>
        </div>


        <div
          style={{
            display:
              "flex",

            justifyContent:
              "space-between",

            alignItems:
              "center",

            gap:
              "16px",

            marginBottom:
              "18px",
          }}
        >
          <span>
            {t(
              "news.total",
              {
                count:
                  items.length,
              },
            )}
          </span>

          <span>
            {t(
              "news.lastUpdated",
            )}

            {" "}

            {lastUpdated}
          </span>
        </div>


        {newsQuery.isPending ? (
          <div
            className={
              "dashboard-empty-state"
            }
          >
            <Newspaper
              size={26}
            />

            <strong>
              {t(
                "news.loadingTitle",
              )}
            </strong>

            <span>
              {t(
                "news.loadingDescription",
              )}
            </span>
          </div>
        ) : null}


        {newsQuery.isError ? (
          <div
            className={
              "dashboard-empty-state"
            }
          >
            <Newspaper
              size={26}
            />

            <strong>
              {t(
                "news.unavailableTitle",
              )}
            </strong>

            <span>
              {t(
                "news.unavailableDescription",
              )}
            </span>
          </div>
        ) : null}


        {newsQuery.isSuccess
        && items.length === 0 ? (
          <div
            className={
              "dashboard-empty-state"
            }
          >
            <Newspaper
              size={26}
            />

            <strong>
              {t(
                "news.emptyTitle",
              )}
            </strong>

            <span>
              {t(
                "news.emptyDescription",
              )}
            </span>
          </div>
        ) : null}


        {items.length > 0 ? (
          <div
            className={
              "health-list"
            }
          >
            {items.map(
              (
                item,
              ) => (
                <NewsItemRow
                  key={
                    item.id
                  }
                  item={
                    item
                  }
                  language={
                    i18n.language
                  }
                />
              ),
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}