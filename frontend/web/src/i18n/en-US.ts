export const enUS = {
  common: {
    language: "Language",
    chinese: "中文",
    english: "English",
    viewAll: "View All",
    viewDetails: "View Details",
    healthy: "Healthy",
    loading: "Loading...",
  },

  brand: {
    name: "RealStock Enterprise",
    tagline: "Invest Smarter. Build Tomorrow.",
    version: "RealStock Enterprise v1.0",
    footer:
      "Built with ❤️ for a better tomorrow",
  },

  nav: {
    dashboard: "Dashboard",
    marketData: "Market Data",
    portfolios: "Portfolios",
    trading: "Paper Trading",
    watchlist: "Watchlist",
    news: "Live News",
    systemHealth: "System Health",
    outboxEvents: "Outbox Events",
    settings: "Settings",
  },

  dashboard: {
    title: "Dashboard",

    welcome:
      "Welcome back! Here's an overview "
      + "of your investments and system status.",

    totalPortfolioValue:
      "Total Portfolio Value",

    totalGainLoss:
      "Total Gain/Loss",

    activePositions:
      "Active Positions",

    watchlistItems:
      "Watchlist Items",

    vsLastMonth:
      "vs. last month",

    acrossSectors:
      "Across 3 sectors",

    stocksTracking:
      "Stocks you're tracking",

    portfolioPerformance:
      "Portfolio Performance",

    marketOverview:
      "Market Overview",

    recentPortfolios:
      "Recent Portfolios",

    recentOutboxEvents:
      "Recent Outbox Events",

    systemHealth:
      "System Health",

    allSystemsOperational:
      "All Systems Operational",
  },

  market: {
    symbol: "Symbol",
    price: "Price",
    change: "Change",
    changePercent: "Change %",
    marketOpen: "Market Open",
    marketClosed: "Market Closed",
    apiConnected: "API Healthy",
  },

  portfolio: {
    name: "Name",
    totalValue: "Total Value",
    gainLoss: "Gain/Loss",
    positions: "Positions",
    updated: "Updated",

    growthPortfolio:
      "Growth Portfolio",

    dividendPortfolio:
      "Dividend Portfolio",

    techFocus:
      "Tech Focus",
  },

  news: {
    title:
      "Live News",

    description:
      "Live market news, refreshed every 60 seconds.",

    refresh:
      "Refresh",

    refreshing:
      "Refreshing",

    total:
      "{{count}} articles",

    lastUpdated:
      "Last updated:",

    loadingTitle:
      "Loading live news",

    loadingDescription:
      "Fetching the latest market news.",

    unavailableTitle:
      "News service unavailable",

    unavailableDescription:
      "Check FastAPI, Redis and the news provider.",

    emptyTitle:
      "No live news",

    emptyDescription:
      "No news items are currently available.",
  },

  system: {
    apiServer: "API Server",

    fastApiApplication:
      "FastAPI application",

    postgresql:
      "PostgreSQL",

    database:
      "Database",

    redis:
      "Redis",

    cacheSession:
      "Cache & Session",

    localstack:
      "LocalStack",

    awsServices:
      "AWS Services",

    outboxWorker:
      "Outbox Worker",

    eventDispatcher:
      "Event Dispatcher",

    connected:
      "LocalStack Connected",
  },

  outbox: {
    id: "ID",
    eventType: "Event Type",
    status: "Status",
    createdAt: "Created At",
    publishedAt: "Published At",

    published:
      "Published",

    pending:
      "Pending",

    failed:
      "Failed",
  },
} as const;