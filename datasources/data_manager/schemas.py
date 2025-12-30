"""
数据库表结构定义模块
"""

# 股票基础信息表
STOCKS_TABLE = """
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    exchange TEXT,
    industry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# 利润表
PROFIT_STATEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS profit_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    report_period TEXT NOT NULL,  -- 报告期，如"2024"
    report_type TEXT NOT NULL,    -- "annual" 或 "quarter"
    data_source TEXT,             -- "ths", "em", "sina"
    
    -- 核心指标（数值型，存储为亿为单位的浮点数）
    net_profit REAL,              -- 净利润
    total_revenue REAL,           -- 营业总收入
    total_cost REAL,              -- 营业总成本
    parent_net_profit REAL,       -- 归属于母公司所有者的净利润
    
    -- 详细指标
    operating_revenue REAL,       -- 营业收入
    operating_cost REAL,          -- 营业成本
    sales_expense REAL,           -- 销售费用
    admin_expense REAL,           -- 管理费用
    rd_expense REAL,              -- 研发费用
    financial_expense REAL,       -- 财务费用
    operating_profit REAL,        -- 营业利润
    total_profit REAL,            -- 利润总额
    income_tax REAL,              -- 所得税费用
    basic_eps REAL,               -- 基本每股收益
    diluted_eps REAL,             -- 稀释每股收益
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (symbol) REFERENCES stocks(symbol),
    UNIQUE(symbol, report_period, report_type, data_source)
);
"""

# 资产负债表
BALANCE_SHEETS_TABLE = """
CREATE TABLE IF NOT EXISTS balance_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    report_period TEXT NOT NULL,
    report_type TEXT NOT NULL,
    data_source TEXT,
    
    -- 核心指标
    total_assets REAL,            -- 资产合计
    total_liabilities REAL,       -- 负债合计
    total_equity REAL,            -- 所有者权益合计
    parent_equity REAL,           -- 归属于母公司所有者权益合计
    
    -- 流动资产
    cash_equivalents REAL,        -- 货币资金
    accounts_receivable REAL,     -- 应收账款
    inventory REAL,               -- 存货
    current_assets REAL,          -- 流动资产合计
    
    -- 非流动资产
    fixed_assets REAL,            -- 固定资产
    intangible_assets REAL,       -- 无形资产
    long_term_investments REAL,  -- 长期投资
    non_current_assets REAL,      -- 非流动资产合计
    
    -- 流动负债
    accounts_payable REAL,        -- 应付账款
    contract_liabilities REAL,    -- 合同负债
    taxes_payable REAL,           -- 应交税费
    current_liabilities REAL,     -- 流动负债合计
    
    -- 权益构成
    share_capital REAL,           -- 实收资本
    capital_reserve REAL,         -- 资本公积
    retained_earnings REAL,       -- 未分配利润
    surplus_reserve REAL,         -- 盈余公积
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (symbol) REFERENCES stocks(symbol),
    UNIQUE(symbol, report_period, report_type, data_source)
);
"""

# 现金流量表
CASH_FLOW_STATEMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS cash_flow_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    report_period TEXT NOT NULL,
    report_type TEXT NOT NULL,
    data_source TEXT,
    
    -- 核心指标
    net_cash_increase REAL,       -- 现金及现金等价物净增加额
    operating_cash_flow REAL,     -- 经营活动产生的现金流量净额
    investing_cash_flow REAL,     -- 投资活动产生的现金流量净额
    financing_cash_flow REAL,      -- 筹资活动产生的现金流量净额
    ending_cash REAL,             -- 期末现金及现金等价物余额
    
    -- 经营活动现金流
    cash_from_sales REAL,         -- 销售商品、提供劳务收到的现金
    cash_paid_for_supplies REAL,  -- 购买商品、接受劳务支付的现金
    cash_paid_for_employees REAL, -- 支付给职工的现金
    cash_paid_for_taxes REAL,     -- 支付的各项税费
    
    -- 投资活动现金流
    cash_from_investment_return REAL, -- 收回投资收到的现金
    cash_for_fixed_assets REAL,   -- 购建固定资产支付的现金
    cash_for_investments REAL,    -- 投资支付的现金
    
    -- 筹资活动现金流
    cash_from_borrowing REAL,     -- 取得借款收到的现金
    cash_for_debt_repayment REAL, -- 偿还债务支付的现金
    cash_for_dividends REAL,      -- 分配股利支付的现金
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (symbol) REFERENCES stocks(symbol),
    UNIQUE(symbol, report_period, report_type, data_source)
);
"""

# 宏观新闻表
MACRO_NEWS_TABLE = """
CREATE TABLE IF NOT EXISTS macro_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    publish_time TEXT,
    url TEXT,
    original_source TEXT,
    data_source TEXT NOT NULL,     -- "cctv", "baidu" 等
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(title, data_source, publish_time)
);
"""

# 北向资金流向表（每次查询保存一条整体记录）
NORTHBOUND_MONEY_FLOW_TABLE = """
CREATE TABLE IF NOT EXISTS northbound_money_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    value TEXT NOT NULL,           -- 如"净流入 15.23 亿元"
    flow_status TEXT,              -- "净流入" 或 "净流出"
    amount_yi REAL,                -- 金额（亿元）
    date TEXT,
    source TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# 核心指数表现表
GLOBAL_INDICES_TABLE = """
CREATE TABLE IF NOT EXISTS global_indices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,           -- 指数名称
    code TEXT NOT NULL,            -- 指数代码
    price REAL NOT NULL,           -- 最新价
    change TEXT NOT NULL,          -- 涨跌幅字符串
    change_pct REAL,               -- 涨跌幅数值
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, created_at)
);
"""

# 汇率信息表（每次查询保存一条整体记录）
CURRENCY_EXCHANGE_RATE_TABLE = """
CREATE TABLE IF NOT EXISTS currency_exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency_pair TEXT NOT NULL,   -- 如"USD/CNY"
    price REAL,                    -- 汇率数值
    change TEXT,                   -- 涨跌幅字符串
    change_pct REAL,               -- 涨跌幅数值
    description TEXT,              -- 完整描述
    date TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# 表名映射
TABLE_SCHEMAS = {
    "stocks": STOCKS_TABLE,
    "profit_statements": PROFIT_STATEMENTS_TABLE,
    "balance_sheets": BALANCE_SHEETS_TABLE,
    "cash_flow_statements": CASH_FLOW_STATEMENTS_TABLE,
    "macro_news": MACRO_NEWS_TABLE,
    "northbound_money_flow": NORTHBOUND_MONEY_FLOW_TABLE,
    "global_indices": GLOBAL_INDICES_TABLE,
    "currency_exchange_rates": CURRENCY_EXCHANGE_RATE_TABLE,
}

# 字段映射关系（原始字段名 -> 数据库字段名）
PROFIT_FIELD_MAPPING = {
    "*净利润": "net_profit",
    "*营业总收入": "total_revenue",
    "*营业总成本": "total_cost",
    "*归属于母公司所有者的净利润": "parent_net_profit",
    "其中：营业收入": "operating_revenue",
    "其中：营业成本": "operating_cost",
    "销售费用": "sales_expense",
    "管理费用": "admin_expense",
    "研发费用": "rd_expense",
    "财务费用": "financial_expense",
    "三、营业利润": "operating_profit",
    "四、利润总额": "total_profit",
    "减：所得税费用": "income_tax",
    "（一）基本每股收益": "basic_eps",
    "（二）稀释每股收益": "diluted_eps",
}

BALANCE_FIELD_MAPPING = {
    "*资产合计": "total_assets",
    "*负债合计": "total_liabilities",
    "*所有者权益（或股东权益）合计": "total_equity",
    "*归属于母公司所有者权益合计": "parent_equity",
    "货币资金": "cash_equivalents",
    "应收账款": "accounts_receivable",
    "存货": "inventory",
    "流动资产合计": "current_assets",
    "固定资产合计": "fixed_assets",
    "无形资产": "intangible_assets",
    "非流动资产合计": "non_current_assets",
    "应付账款": "accounts_payable",
    "合同负债": "contract_liabilities",
    "应交税费": "taxes_payable",
    "流动负债合计": "current_liabilities",
    "实收资本（或股本）": "share_capital",
    "资本公积": "capital_reserve",
    "未分配利润": "retained_earnings",
    "盈余公积": "surplus_reserve",
}

CASH_FLOW_FIELD_MAPPING = {
    "*现金及现金等价物净增加额": "net_cash_increase",
    "*经营活动产生的现金流量净额": "operating_cash_flow",
    "*投资活动产生的现金流量净额": "investing_cash_flow",
    "*筹资活动产生的现金流量净额": "financing_cash_flow",
    "*期末现金及现金等价物余额": "ending_cash",
    "销售商品、提供劳务收到的现金": "cash_from_sales",
    "购买商品、接受劳务支付的现金": "cash_paid_for_supplies",
    "支付给职工以及为职工支付的现金": "cash_paid_for_employees",
    "支付的各项税费": "cash_paid_for_taxes",
    "收回投资收到的现金": "cash_from_investment_return",
    "购建固定资产、无形资产和其他长期资产支付的现金": "cash_for_fixed_assets",
    "投资支付的现金": "cash_for_investments",
    "偿还债务支付的现金": "cash_for_debt_repayment",
    "分配股利、利润或偿付利息支付的现金": "cash_for_dividends",
}

# 字段映射表
FIELD_MAPPINGS = {
    "profit_statements": PROFIT_FIELD_MAPPING,
    "balance_sheets": BALANCE_FIELD_MAPPING,
    "cash_flow_statements": CASH_FLOW_FIELD_MAPPING,
}
