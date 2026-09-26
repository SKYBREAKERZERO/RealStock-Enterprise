import {
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import {
  AppLayout,
} from "../layouts/AppLayout";

import {
  DashboardPage,
} from "../pages/DashboardPage";

import {
  MarketDataPage,
} from "../pages/MarketDataPage";

import {
  NewsPage,
} from "../pages/NewsPage";

import {
  OutboxEventsPage,
} from "../pages/OutboxEventsPage";

import {
  PortfoliosPage,
} from "../pages/PortfoliosPage";

import {
  SettingsPage,
} from "../pages/SettingsPage";

import {
  SystemHealthPage,
} from "../pages/SystemHealthPage";

import {
  TradingPage,
} from "../pages/TradingPage";

import {
  WatchlistPage,
} from "../pages/WatchlistPage";


export function AppRouter() {
  return (
    <Routes>
      <Route
        element={
          <AppLayout />
        }
      >
        <Route
          index
          element={
            <Navigate
              to="/dashboard"
              replace
            />
          }
        />

        <Route
          path="/dashboard"
          element={
            <DashboardPage />
          }
        />

        <Route
          path="/market"
          element={
            <MarketDataPage />
          }
        />

        <Route
          path="/portfolios"
          element={
            <PortfoliosPage />
          }
        />

        <Route
          path="/trading"
          element={
            <TradingPage />
          }
        />

        <Route
          path="/watchlist"
          element={
            <WatchlistPage />
          }
        />

        <Route
          path="/news"
          element={
            <NewsPage />
          }
        />

        <Route
          path="/system-health"
          element={
            <SystemHealthPage />
          }
        />

        <Route
          path="/outbox-events"
          element={
            <OutboxEventsPage />
          }
        />

        <Route
          path="/settings"
          element={
            <SettingsPage />
          }
        />
      </Route>

      <Route
        path="*"
        element={
          <Navigate
            to="/dashboard"
            replace
          />
        }
      />
    </Routes>
  );
}