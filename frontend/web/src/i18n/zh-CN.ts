export const zhCN = {
  common: {
    language: "语言",
    chinese: "中文",
    english: "English",
    viewAll: "查看全部",
    viewDetails: "查看详情",
    healthy: "正常",
    loading: "加载中...",
  },

  brand: {
    name: "RealStock Enterprise",
    tagline: "智慧投资，构建未来。",
    version: "RealStock Enterprise v1.0",
    footer: "为更好的未来而构建",
  },

  nav: {
    dashboard: "仪表盘",
    marketData: "市场数据",
    portfolios: "投资组合",
    watchlist: "自选列表",
    news: "实时新闻",
    systemHealth: "系统状态",
    outboxEvents: "Outbox 事件",
    settings: "设置",
  },

  dashboard: {
    title: "仪表盘",

    welcome:
      "欢迎回来！这里展示您的投资概览与系统运行状态。",

    totalPortfolioValue:
      "投资组合总价值",

    totalGainLoss:
      "总盈亏",

    activePositions:
      "当前持仓",

    watchlistItems:
      "自选股票",

    vsLastMonth:
      "较上月",

    acrossSectors:
      "覆盖 3 个行业",

    stocksTracking:
      "正在关注的股票",

    portfolioPerformance:
      "投资组合表现",

    marketOverview:
      "市场概览",

    recentPortfolios:
      "最近投资组合",

    recentOutboxEvents:
      "最近 Outbox 事件",

    systemHealth:
      "系统状态",

    allSystemsOperational:
      "所有系统运行正常",
  },

  market: {
    symbol: "股票代码",
    price: "价格",
    change: "涨跌额",
    changePercent: "涨跌幅",
    marketOpen: "市场交易中",
    marketClosed: "市场已休市",
    apiConnected: "API 正常",
  },

  portfolio: {
    name: "名称",
    totalValue: "总价值",
    gainLoss: "盈亏",
    positions: "持仓数",
    updated: "更新时间",

    growthPortfolio:
      "成长型投资组合",

    dividendPortfolio:
      "股息投资组合",

    techFocus:
      "科技精选",
  },

  news: {
    title:
      "实时新闻",

    description:
      "实时市场新闻，每 60 秒自动刷新。",

    refresh:
      "刷新",

    refreshing:
      "刷新中",

    total:
      "共 {{count}} 条",

    lastUpdated:
      "最后更新：",

    loadingTitle:
      "正在加载实时新闻",

    loadingDescription:
      "正在读取最新市场资讯。",

    unavailableTitle:
      "新闻服务暂时不可用",

    unavailableDescription:
      "请确认 FastAPI、Redis 和新闻数据源状态。",

    emptyTitle:
      "暂无实时新闻",

    emptyDescription:
      "当前没有可显示的新闻数据。",
  },

  system: {
    apiServer: "API 服务",

    fastApiApplication:
      "FastAPI 应用",

    postgresql:
      "PostgreSQL",

    database:
      "数据库",

    redis:
      "Redis",

    cacheSession:
      "缓存与会话",

    localstack:
      "LocalStack",

    awsServices:
      "AWS 服务",

    outboxWorker:
      "Outbox Worker",

    eventDispatcher:
      "事件分发器",

    connected:
      "LocalStack 已连接",
  },

  outbox: {
    id: "ID",
    eventType: "事件类型",
    status: "状态",
    createdAt: "创建时间",
    publishedAt: "发布时间",

    published:
      "已发布",

    pending:
      "待处理",

    failed:
      "失败",
  },
} as const;