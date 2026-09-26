import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  HeartPulse,
  LayoutDashboard,
  Newspaper,
  RadioTower,
  Settings,
  Star,
} from "lucide-react";

import type {
  LucideIcon,
} from "lucide-react";

import {
  NavLink,
} from "react-router-dom";

import {
  useTranslation,
} from "react-i18next";


interface NavigationItem {
  to: string;

  translationKey: string;

  icon: LucideIcon;
}


const NAVIGATION_ITEMS:
  NavigationItem[] = [
    {
      to:
        "/dashboard",

      translationKey:
        "nav.dashboard",

      icon:
        LayoutDashboard,
    },

    {
      to:
        "/market",

      translationKey:
        "nav.marketData",

      icon:
        BarChart3,
    },

    {
      to:
        "/portfolios",

      translationKey:
        "nav.portfolios",

      icon:
        BriefcaseBusiness,
    },

    {
      to:
        "/watchlist",

      translationKey:
        "nav.watchlist",

      icon:
        Star,
    },

    {
      to:
        "/news",

      translationKey:
        "nav.news",

      icon:
        Newspaper,
    },

    {
      to:
        "/system-health",

      translationKey:
        "nav.systemHealth",

      icon:
        HeartPulse,
    },

    {
      to:
        "/outbox-events",

      translationKey:
        "nav.outboxEvents",

      icon:
        RadioTower,
    },

    {
      to:
        "/settings",

      translationKey:
        "nav.settings",

      icon:
        Settings,
    },
  ];


export function Sidebar() {
  const {
    t,
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language
      .startsWith(
        "zh",
      );


  return (
    <aside
      className={
        "enterprise-sidebar"
      }
    >
      <div>
        <div
          className={
            "sidebar-brand"
          }
        >
          <div
            className={
              "sidebar-brand-mark"
            }
          >
            <Activity
              size={23}
            />
          </div>

          <div>
            <strong>
              RealStock
            </strong>

            <span>
              Enterprise
            </span>
          </div>
        </div>


        <p
          className={
            "sidebar-tagline"
          }
        >
          {isZh
            ? (
              "智慧投资，"
              + "构建未来。"
            )
            : (
              "Invest Smarter. "
              + "Build Tomorrow."
            )}
        </p>


        <nav
          className={
            "sidebar-navigation"
          }
          aria-label={
            isZh
              ? "主导航"
              : "Main navigation"
          }
        >
          {NAVIGATION_ITEMS
            .map(
              (
                item,
              ) => {
                const Icon =
                  item.icon;

                return (
                  <NavLink
                    key={
                      item.to
                    }
                    to={
                      item.to
                    }
                    className={({
                      isActive,
                    }) =>
                      isActive
                        ? (
                          "sidebar-link "
                          + "active"
                        )
                        : (
                          "sidebar-link"
                        )
                    }
                  >
                    <Icon
                      size={18}
                    />

                    <span>
                      {t(
                        item
                          .translationKey,
                      )}
                    </span>
                  </NavLink>
                );
              },
            )}
        </nav>
      </div>


      <div
        className={
          "sidebar-footer"
        }
      >
        <div
          className={
            "sidebar-operational"
          }
        >
          <span
            className={
              "operational-dot"
            }
          />

          <div>
            <strong>
              {t(
                "dashboard.allSystemsOperational",
              )}
            </strong>

            <span>
              {isZh
                ? (
                  "核心服务状态"
                  + "实时监控"
                )
                : (
                  "Core services "
                  + "monitored"
                )}
            </span>
          </div>
        </div>


        <div
          className={
            "sidebar-version"
          }
        >
          RealStock Enterprise
          <br />
          v1.0
        </div>
      </div>
    </aside>
  );
}