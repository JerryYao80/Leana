# Barra CNE5 因子计算数据需求映射文档

**文档版本**: 1.0  
**创建日期**: 2026-01-31  
**目的**: 记录计算Barra CNE5所有因子所需的数据项及其在Tushare数据中的位置，标记数据缺失情况

---

## 目录

1. [数据需求总览](#1-数据需求总览)
2. [因子详细计算公式与数据映射](#2-因子详细计算公式与数据映射)
3. [行业分类数据](#3-行业分类数据)
4. [数据完整性分析](#4-数据完整性分析)
5. [数据质量要求](#5-数据质量要求)
6. [数据缺失处理方案](#6-数据缺失处理方案)

---

## 1. 数据需求总览

### 1.1 Barra CNE5 因子列表

| 因子编号 | 因子名称 | 英文名称 | 因子类型 |
|---------|---------|---------|---------|
| 1 | 市值 | Size | 风格因子 |
| 2 | 市场风险 | Beta | 风格因子 |
| 3 | 动量 | Momentum | 风格因子 |
| 4 | 残差波动率 | Residual Volatility | 风格因子 |
| 5 | 非线性市值 | Non-linear Size | 风格因子 |
| 6 | 价值 | Book-to-Price (Value) | 风格因子 |
| 7 | 流动性 | Liquidity | 风格因子 |
| 8 | 盈利收益率 | Earnings Yield | 风格因子 |
| 9 | 成长 | Growth | 风格因子 |
| 10 | 杠杆 | Leverage | 风格因子 |
| 11 | 行业因子 | Industry Factors | 行业因子(30个) |

### 1.2 Tushare 数据表索引

| Tushare表名 | 文件路径 | 数据频率 | 用途 | 数据状态 |
|------------|---------|---------|------|---------|
| `stock_basic` | `/data/tushare_data/stock_basic/data.parquet` | 静态 | 股票基本信息、行业分类 | ✅ 存在 |
| `daily` | `/data/tushare_data/daily/{ts_code}.parquet` | 日频 | OHLCV价格数据 | ✅ 存在 |
| `daily_basic` | `/data/tushare_data/daily_basic/{ts_code}.parquet` | 日频 | 市值、PE、PB、换手率 | ✅ 存在 |
| `adj_factor` | `/data/tushare_data/adj_factor/{ts_code}.parquet` | 日频 | 复权因子 | ✅ 存在 |
| `index_daily` | `/data/tushare_data/index_daily/{index_code}.parquet` | 日频 | 指数行情（基准：000300.SH） | ⚠️ 需验证 |
| `fina_indicator` | `/data/tushare_data/fina_indicator/{ts_code}.parquet` | 季频 | 财务指标（ROE、EPS等） | ⚠️ 需验证 |
| `balancesheet` | `/data/tushare_data/balancesheet/{ts_code}.parquet` | 季频 | 资产负债表 | ⚠️ 需验证 |
| `income` | `/data/tushare_data/income/{ts_code}.parquet` | 季频 | 利润表 | ⚠️ 需验证 |
| `cashflow` | `/data/tushare_data/cashflow/{ts_code}.parquet` | 季频 | 现金流量表 | ⚠️ 需验证 |
| `index_classify` | `/data/tushare_data/index_classify/data.parquet` | 静态 | 行业分类（中信、申万） | ✅ 存在 |

**图例说明**:
- ✅ 存在: 数据目录已确认存在
- ⚠️ 需验证: 目录存在但需验证数据完整性
- ❌ 缺失: 数据不存在，需要替代方案

---

## 2. 因子详细计算公式与数据映射

### 2.1 因子1: Size (市值因子)

**计算公式**:
```
Size = ln(total_mv)
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 总市值 | `daily_basic` | `total_mv` | 单位：万元 | ✅ 可用 |
| 交易日期 | `daily_basic` | `trade_date` | YYYYMMDD格式 | ✅ 可用 |

**计算逻辑**:
```python
def calc_size(daily_basic: pd.DataFrame) -> pd.Series:
    """
    计算市值因子
    
    Args:
        daily_basic: Tushare daily_basic数据
        
    Returns:
        Size因子序列
    """
    return np.log(daily_basic['total_mv'])
```

**数据质量要求**:
- `total_mv` 应 > 0（市值必须为正）
- 缺失值比例 < 1%

---

### 2.2 因子2: Beta (市场风险因子)

**计算公式**:
```
Beta_t = Cov(R_stock, R_benchmark) / Var(R_benchmark)
使用252个交易日滚动窗口回归
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 股票收盘价 | `daily` | `close` | 前复权价格 | ✅ 可用 |
| 复权因子 | `adj_factor` | `adj_factor` | 用于复权计算 | ✅ 可用 |
| 基准指数价格 | `index_daily` (000300.SH) | `close` | 沪深300指数 | ⚠️ 需验证路径 |
| 交易日期 | `daily` | `trade_date` | YYYYMMDD格式 | ✅ 可用 |

**计算逻辑**:
```python
def calc_beta(daily: pd.DataFrame, index_daily: pd.DataFrame, window=252) -> pd.Series:
    """
    计算Beta因子（252日滚动回归）
    
    Args:
        daily: 股票日行情数据
        index_daily: 沪深300指数日行情
        window: 滚动窗口长度（默认252）
        
    Returns:
        Beta因子序列
    """
    # 计算收益率
    stock_returns = daily['close'].pct_change()
    benchmark_returns = index_daily.set_index('trade_date')['close'].pct_change()
    
    # 滚动回归计算Beta
    betas = []
    for i in range(window, len(stock_returns)):
        y = stock_returns.iloc[i-window:i].values
        x = benchmark_returns.iloc[i-window:i].values
        
        # 过滤NaN
        mask = ~(np.isnan(x) | np.isnan(y))
        if mask.sum() < window * 0.8:  # 至少80%有效数据
            betas.append(np.nan)
            continue
            
        beta = np.polyfit(x[mask], y[mask], 1)[0]
        betas.append(beta)
    
    return pd.Series([np.nan] * window + betas, index=daily.index)
```

**数据质量要求**:
- 价格序列完整性 ≥ 80%
- 基准指数数据必须完整
- Beta值合理范围: [-2, 3]

**潜在问题**:
- ⚠️ **数据路径不确定**: 需确认沪深300指数数据存储格式
  - 可能路径1: `/data/tushare_data/index_daily/000300.SH.parquet`
  - 可能路径2: `/data/tushare_data/index_daily/data.parquet` (所有指数合并)
  - **解决方案**: 创建脚本验证实际路径

---

### 2.3 因子3: Momentum (动量因子)

**计算公式**:
```
Momentum_t = (P_{t-21} / P_{t-252}) - 1
(最近1个月相对11个月前的收益率)
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 股票收盘价 | `daily` | `close` | 前复权价格 | ✅ 可用 |
| 交易日期 | `daily` | `trade_date` | YYYYMMDD格式 | ✅ 可用 |

**计算逻辑**:
```python
def calc_momentum(daily: pd.DataFrame) -> pd.Series:
    """
    计算动量因子
    
    Args:
        daily: 股票日行情数据
        
    Returns:
        Momentum因子序列
    """
    close = daily['close']
    return (close.shift(21) / close.shift(252)) - 1
```

**数据质量要求**:
- 至少需要252个交易日历史数据
- 缺失值比例 < 5%

---

### 2.4 因子4: Residual Volatility (残差波动率)

**计算公式**:
```
Volatility_t = std(residuals_{t-252:t})
其中 residuals = R_stock - Beta * R_benchmark
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 股票收盘价 | `daily` | `close` | 计算收益率 | ✅ 可用 |
| 基准指数价格 | `index_daily` (000300.SH) | `close` | 沪深300指数 | ⚠️ 需验证 |
| Beta因子 | - | - | 来自因子2 | 依赖因子2 |

**计算逻辑**:
```python
def calc_residual_volatility(daily: pd.DataFrame, index_daily: pd.DataFrame, 
                            beta: pd.Series, window=252) -> pd.Series:
    """
    计算残差波动率
    
    Args:
        daily: 股票日行情数据
        index_daily: 基准指数数据
        beta: Beta因子序列
        window: 滚动窗口长度
        
    Returns:
        Volatility因子序列
    """
    # 计算收益率
    stock_returns = daily['close'].pct_change()
    benchmark_returns = index_daily.set_index('trade_date')['close'].pct_change()
    
    # 计算残差
    residuals = stock_returns - beta * benchmark_returns
    
    # 滚动标准差
    return residuals.rolling(window).std()
```

**数据质量要求**:
- Beta因子可用
- 至少252个交易日数据
- 残差波动率合理范围: [0.01, 0.15]

---

### 2.5 因子5: Non-linear Size (非线性市值)

**计算公式**:
```
Non-linear Size_t = Size³ - proj(Size³ on Size)
(市值三次方对市值的正交分量)
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| Size因子 | - | - | 来自因子1 | 依赖因子1 |

**计算逻辑**:
```python
def calc_non_linear_size(size: pd.Series) -> pd.Series:
    """
    计算非线性市值因子
    
    Args:
        size: Size因子序列
        
    Returns:
        Non-linear Size因子序列
    """
    size_cubed = size ** 3
    
    # 横截面正交化（每个时间点）
    # 完整实现需要在每个日期对所有股票做回归
    # 简化版：直接返回立方值
    return size_cubed
    
    # 完整版实现：
    # for date in size.index.get_level_values('trade_date').unique():
    #     cross_section = size.loc[date]
    #     cross_section_cubed = cross_section ** 3
    #     # 回归 cross_section_cubed ~ cross_section
    #     # 提取残差作为非线性成分
```

**数据质量要求**:
- Size因子可用
- 需要横截面数据（所有股票同一日期）

**实现注意**:
- ⚠️ **横截面正交化**: 需要同一日期所有股票数据，因此需要在预计算阶段处理

---

### 2.6 因子6: Book-to-Price (价值因子)

**计算公式**:
```
Book-to-Price = Book Value / Market Value = 1 / PB
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 市净率 | `daily_basic` | `pb` | 市净率（总市值/净资产） | ✅ 可用 |
| 交易日期 | `daily_basic` | `trade_date` | YYYYMMDD格式 | ✅ 可用 |

**计算逻辑**:
```python
def calc_book_to_price(daily_basic: pd.DataFrame) -> pd.Series:
    """
    计算账面市值比（价值因子）
    
    Args:
        daily_basic: Tushare daily_basic数据
        
    Returns:
        Book-to-Price因子序列
    """
    # PB = Price / Book，所以 B/P = 1/PB
    pb = daily_basic['pb']
    return pb.apply(lambda x: 1/x if x > 0 else np.nan)
```

**数据质量要求**:
- `pb` > 0（剔除负值和零值）
- 缺失值比例 < 10%（部分ST股可能没有PB）

**潜在问题**:
- ⚠️ **负净资产**: ST股票可能有负净资产，导致PB为负，需要特殊处理

---

### 2.7 因子7: Liquidity (流动性因子)

**计算公式**:
```
Liquidity = 0.35 * TO_1M + 0.35 * TO_3M + 0.30 * TO_12M
其中 TO_nM = 过去n个月平均换手率
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 换手率 | `daily_basic` | `turnover_rate` | 换手率（%） | ✅ 可用 |
| 交易日期 | `daily_basic` | `trade_date` | YYYYMMDD格式 | ✅ 可用 |

**计算逻辑**:
```python
def calc_liquidity(daily_basic: pd.DataFrame) -> pd.Series:
    """
    计算流动性因子
    
    Args:
        daily_basic: Tushare daily_basic数据
        
    Returns:
        Liquidity因子序列
    """
    turnover = daily_basic['turnover_rate']
    
    to_1m = turnover.rolling(21).mean()   # 1个月 ≈ 21个交易日
    to_3m = turnover.rolling(63).mean()   # 3个月 ≈ 63个交易日
    to_12m = turnover.rolling(252).mean() # 12个月 ≈ 252个交易日
    
    return 0.35 * to_1m + 0.35 * to_3m + 0.30 * to_12m
```

**数据质量要求**:
- 至少需要252个交易日数据
- 换手率合理范围: [0, 100]

---

### 2.8 因子8: Earnings Yield (盈利收益率)

**计算公式**:
```
Earnings Yield = (0.68 * EPIBS + 0.21 * CETOP + 0.11 * ETOP)

其中：
- EPIBS = EPS (TTM) / Price  （基本每股收益/价格）
- CETOP = Operating Cash Flow / Market Value （经营现金流/市值）
- ETOP = EBIT / Enterprise Value （息税前利润/企业价值）
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 市盈率TTM | `daily_basic` | `pe_ttm` | 市盈率（TTM） | ✅ 可用 |
| 总市值 | `daily_basic` | `total_mv` | 单位：万元 | ✅ 可用 |
| 基本每股收益 | `fina_indicator` | `eps` | 每股收益 | ⚠️ 需验证 |
| 经营现金流 | `cashflow` | `n_cashflow_act` | 经营活动现金流净额 | ⚠️ 需验证 |
| EBIT | `fina_indicator` | `ebit` | 息税前利润 | ⚠️ 需验证 |
| 公告日期 | `fina_indicator` | `ann_date` | 财报公告日期 | ⚠️ 需验证 |

**计算逻辑**:
```python
def calc_earnings_yield(daily_basic: pd.DataFrame, 
                       fina_indicator: pd.DataFrame,
                       cashflow: pd.DataFrame) -> pd.Series:
    """
    计算盈利收益率因子
    
    Args:
        daily_basic: 日频基本数据
        fina_indicator: 财务指标数据（季频）
        cashflow: 现金流量表数据（季频）
        
    Returns:
        Earnings Yield因子序列
    """
    # 方法1：简化版（只用PE_TTM）
    pe_ttm = daily_basic['pe_ttm']
    epibs = pe_ttm.apply(lambda x: 1/x if x > 0 else np.nan)
    
    # 方法2：完整版（需要匹配财务数据到每个交易日）
    # - 使用point-in-time数据（避免未来函数）
    # - 将季度财报数据扩展到每个交易日
    # - 计算CETOP和ETOP
    
    return epibs  # 简化版先返回E/P
```

**数据质量要求**:
- PE_TTM > 0（剔除亏损股）
- 缺失值比例 < 15%

**潜在问题**:
- ⚠️ **财务数据匹配**: 季度财报需要匹配到每个交易日，需要Point-in-Time机制
- ⚠️ **数据延迟**: 财报公告日（`ann_date`）是真实可用时间，不能用`end_date`
- ❌ **数据缺失**: 部分字段可能需要手动计算（如Enterprise Value = Market Value + Net Debt）

**替代方案**:
- 简化版：只用 `1 / PE_TTM` 作为Earnings Yield
- 完整版：需要实现财务数据Point-in-Time匹配

---

### 2.9 因子9: Growth (成长因子)

**计算公式**:
```
Growth = (0.18 * EGRO + 0.11 * SGRO + 0.24 * EGRLF + 0.47 * EGRSF)

其中：
- EGRO = 5年营业总收入CAGR（复合年增长率）
- SGRO = 5年营收增长率
- EGRLF = 长期预期盈利增长率
- EGRSF = 短期预期盈利增长率
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 营业总收入 | `income` | `total_revenue` | 季度营收（元） | ⚠️ 需验证 |
| 净利润 | `income` | `n_income` | 季度净利润（元） | ⚠️ 需验证 |
| 报告期 | `income` | `end_date` | YYYYMMDD格式 | ⚠️ 需验证 |
| 公告日期 | `income` | `ann_date` | 财报公告日期 | ⚠️ 需验证 |

**计算逻辑**:
```python
def calc_growth(income: pd.DataFrame) -> float:
    """
    计算成长因子
    
    Args:
        income: 利润表数据（季频）
        
    Returns:
        Growth因子（单值，应用到所有交易日）
    """
    # 获取最近5年营收数据
    revenue = income.sort_values('end_date')['total_revenue']
    
    if len(revenue) < 20:  # 至少5年 * 4季度 = 20个数据点
        return np.nan
    
    # 计算CAGR
    revenue_recent = revenue.iloc[-20:]  # 最近20个季度
    start_revenue = revenue_recent.iloc[0]
    end_revenue = revenue_recent.iloc[-1]
    
    if start_revenue <= 0:
        return np.nan
    
    years = 5.0
    cagr = (end_revenue / start_revenue) ** (1 / years) - 1
    
    return cagr
```

**数据质量要求**:
- 至少5年财务数据（20个季度）
- 营收为正

**潜在问题**:
- ⚠️ **数据不足**: 上市不足5年的股票无法计算
- ⚠️ **财务重述**: 财报可能被修正，需要使用最终版本
- ❌ **分析师预期数据缺失**: Tushare不提供EGRLF和EGRSF（分析师预期数据）

**替代方案**:
- 简化版：只用历史营收CAGR作为Growth因子
- 扩展版：从第三方数据源获取分析师预期（如Wind、Choice）

---

### 2.10 因子10: Leverage (杠杆因子)

**计算公式**:
```
Leverage = (0.38 * MLEV + 0.35 * DTOA + 0.27 * BLEV)

其中：
- MLEV = (Market Value + Preferred Stock + Long-term Debt + Short-term Debt) / Market Value
- DTOA = Total Debt / Total Assets  （资产负债率）
- BLEV = Book Value of Equity / (Book Equity + Long-term Debt + Short-term Debt)
```

**数据来源**:

| 所需字段 | Tushare表 | Tushare字段 | 说明 | 数据状态 |
|---------|----------|------------|------|---------|
| 总市值 | `daily_basic` | `total_mv` | 单位：万元 | ✅ 可用 |
| 资产负债率 | `fina_indicator` | `debt_to_assets` | 资产负债率 | ⚠️ 需验证 |
| 总资产 | `balancesheet` | `total_assets` | 总资产（元） | ⚠️ 需验证 |
| 总负债 | `balancesheet` | `total_liab` | 总负债（元） | ⚠️ 需验证 |
| 长期借款 | `balancesheet` | `lt_borr` | 长期借款（元） | ⚠️ 需验证 |
| 短期借款 | `balancesheet` | `st_borr` | 短期借款（元） | ⚠️ 需验证 |
| 股东权益 | `balancesheet` | `total_hldr_eqy_inc_min_int` | 股东权益合计（元） | ⚠️ 需验证 |
| 公告日期 | `balancesheet` | `ann_date` | 财报公告日期 | ⚠️ 需验证 |

**计算逻辑**:
```python
def calc_leverage(daily_basic: pd.DataFrame, 
                 balancesheet: pd.DataFrame,
                 fina_indicator: pd.DataFrame) -> pd.Series:
    """
    计算杠杆因子
    
    Args:
        daily_basic: 日频基本数据
        balancesheet: 资产负债表数据（季频）
        fina_indicator: 财务指标数据（季频）
        
    Returns:
        Leverage因子序列
    """
    # 简化版：直接使用资产负债率（DTOA）
    # 完整版需要匹配财务数据到每个交易日
    
    # 从fina_indicator获取资产负债率
    dtoa = fina_indicator.sort_values('ann_date')['debt_to_assets'].iloc[-1]
    
    return dtoa
```

**数据质量要求**:
- 财务数据可用
- 资产负债率合理范围: [0, 1]

**潜在问题**:
- ⚠️ **财务数据匹配**: 季度财报需要匹配到每个交易日
- ⚠️ **优先股数据缺失**: Tushare可能没有优先股数据

**替代方案**:
- 简化版：直接使用 `debt_to_assets` 作为Leverage因子

---

## 3. 行业分类数据

### 3.1 数据来源

**Tushare数据表**: `index_classify` 和 `stock_basic`

| 字段名 | Tushare字段 | 说明 | 数据状态 |
|-------|-----------|------|---------|
| 股票代码 | `ts_code` | 格式：000001.SZ | ✅ 可用 |
| 行业名称 | `industry` (stock_basic) | 所属行业 | ✅ 可用 |
| 行业分类标准 | `src` (index_classify) | SW（申万）、ZX（中信） | ✅ 可用 |
| 行业代码 | `industry_code` (index_classify) | 行业编码 | ✅ 可用 |

### 3.2 Barra CNE5 行业分类

Barra CNE5使用**中信一级行业分类**（共30个行业）：

| 行业编号 | 行业代码 | 行业名称 | 英文名称 |
|---------|---------|---------|---------|
| 1 | `ind_petrochemical` | 石油石化 | Petrochemical |
| 2 | `ind_coal` | 煤炭 | Coal |
| 3 | `ind_nonferrous` | 有色金属 | Non-ferrous Metals |
| 4 | `ind_utilities` | 电力及公用事业 | Utilities |
| 5 | `ind_steel` | 钢铁 | Steel |
| 6 | `ind_chemicals` | 基础化工 | Chemicals |
| 7 | `ind_building_materials` | 建材 | Building Materials |
| 8 | `ind_construction` | 建筑 | Construction |
| 9 | `ind_transportation` | 交通运输 | Transportation |
| 10 | `ind_automobiles` | 汽车 | Automobiles |
| 11 | `ind_machinery` | 机械 | Machinery |
| 12 | `ind_defense` | 国防军工 | Defense & Military |
| 13 | `ind_electrical_equipment` | 电力设备 | Electrical Equipment |
| 14 | `ind_electronics` | 电子 | Electronics |
| 15 | `ind_computers` | 计算机 | Computers |
| 16 | `ind_communications` | 通信 | Communications |
| 17 | `ind_consumer_appliances` | 家电 | Consumer Appliances |
| 18 | `ind_light_manufacturing` | 轻工制造 | Light Manufacturing |
| 19 | `ind_textiles_apparel` | 纺织服装 | Textiles & Apparel |
| 20 | `ind_food_beverage` | 食品饮料 | Food & Beverage |
| 21 | `ind_agriculture` | 农林牧渔 | Agriculture |
| 22 | `ind_banking` | 银行 | Banking |
| 23 | `ind_non_bank_finance` | 非银行金融 | Non-bank Finance |
| 24 | `ind_real_estate` | 房地产 | Real Estate |
| 25 | `ind_commerce_retail` | 商贸零售 | Commerce & Retail |
| 26 | `ind_social_services` | 社会服务 | Social Services |
| 27 | `ind_media` | 传媒 | Media |
| 28 | ind_pharmaceuticals` | 医药 | Pharmaceuticals |
| 29 | `ind_environmental` | 环保 | Environmental |
| 30 | `ind_comprehensive` | 综合 | Comprehensive |

### 3.3 数据映射逻辑

```python
def create_industry_mapping() -> dict:
    """
    创建股票→行业映射表
    
    Returns:
        {ts_code: industry_code} 字典
    """
    # 读取Tushare行业分类数据
    stock_basic = pd.read_parquet('/data/tushare_data/stock_basic/data.parquet')
    index_classify = pd.read_parquet('/data/tushare_data/index_classify/data.parquet')
    
    # 提取中信一级行业（src='ZX', level='L1'）
    zx_l1 = index_classify[(index_classify['src'] == 'ZX') & 
                          (index_classify['level'] == 'L1')]
    
    # 构建Tushare行业名→Barra行业代码映射
    tushare_to_barra = {
        '石油石化': 'ind_petrochemical',
        '煤炭': 'ind_coal',
        # ... 其他29个行业
        '综合': 'ind_comprehensive'
    }
    
    # 构建股票→行业映射
    industry_map = {}
    for _, row in stock_basic.iterrows():
        ts_code = row['ts_code']
        industry_name = row['industry']
        
        # 映射到Barra行业代码
        barra_industry = tushare_to_barra.get(industry_name, 'ind_comprehensive')
        industry_map[ts_code] = barra_industry
    
    return industry_map
```

### 3.4 行业哑变量生成

```python
def get_industry_dummies(ts_code: str, industry_map: dict) -> Dict[str, int]:
    """
    生成行业哑变量（30个）
    
    Args:
        ts_code: 股票代码
        industry_map: 股票→行业映射字典
        
    Returns:
        {industry_code: 1 or 0} 字典
    """
    industry_list = [
        'ind_petrochemical', 'ind_coal', 'ind_nonferrous',
        'ind_utilities', 'ind_steel', 'ind_chemicals',
        # ... 共30个
    ]
    
    stock_industry = industry_map.get(ts_code, 'ind_comprehensive')
    
    return {
        ind: 1 if ind == stock_industry else 0 
        for ind in industry_list
    }
```

**潜在问题**:
- ⚠️ **行业分类更新**: 行业分类可能随时间变化（公司转型），需要维护时间序列版本
- ⚠️ **行业名称不一致**: Tushare行业名称可能与中信标准不完全一致

---

## 4. 数据完整性分析

### 4.1 数据存在性验证

**已验证存在** (✅):
| 数据表 | 文件路径 | 用途 |
|-------|---------|------|
| `stock_basic` | `/data/tushare_data/stock_basic/data.parquet` | 股票列表、行业 |
| `daily` | `/data/tushare_data/daily/{ts_code}.parquet` | 价格数据 |
| `daily_basic` | `/data/tushare_data/daily_basic/{ts_code}.parquet` | 市值、PE、PB |
| `adj_factor` | `/data/tushare_data/adj_factor/{ts_code}.parquet` | 复权因子 |
| `index_classify` | `/data/tushare_data/index_classify/data.parquet` | 行业分类 |
| `monthly` | `/data/tushare_data/monthly/{ts_code}.parquet` | 月度数据 |
| `weekly` | `/data/tushare_data/weekly/{ts_code}.parquet` | 周度数据 |

**需要验证** (⚠️):
| 数据表 | 预期路径 | 验证项 | 优先级 |
|-------|---------|-------|-------|
| `index_daily` | `/data/tushare_data/index_daily/*.parquet` | 是否包含000300.SH | P0 |
| `fina_indicator` | `/data/tushare_data/fina_indicator/{ts_code}.parquet` | 字段完整性 | P1 |
| `balancesheet` | `/data/tushare_data/balancesheet/{ts_code}.parquet` | 字段完整性 | P1 |
| `income` | `/data/tushare_data/income/{ts_code}.parquet` | 字段完整性 | P1 |
| `cashflow` | `/data/tushare_data/cashflow/{ts_code}.parquet` | 字段完整性 | P1 |

**验证脚本**:
```bash
# 创建数据验证脚本
cat > /scripts/barra/verify_tushare_data.py << 'EOF'
#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

DATA_DIR = Path("/data/tushare_data")

# 验证index_daily
index_daily_file = DATA_DIR / "index_daily" / "000300.SH.parquet"
if not index_daily_file.exists():
    print(f"❌ Missing: {index_daily_file}")
else:
    print(f"✅ Found: {index_daily_file}")
    df = pd.read_parquet(index_daily_file)
    print(f"   Columns: {list(df.columns)}")
    print(f"   Rows: {len(df)}")

# 验证fina_indicator
test_stock = "000001.SZ"
fina_file = DATA_DIR / "fina_indicator" / f"{test_stock}.parquet"
if not fina_file.exists():
    print(f"❌ Missing: {fina_file}")
else:
    print(f"✅ Found: {fina_file}")
    df = pd.read_parquet(fina_file)
    required_fields = ['eps', 'ebit', 'debt_to_assets', 'roe']
    for field in required_fields:
        if field in df.columns:
            print(f"   ✅ {field}")
        else:
            print(f"   ❌ Missing field: {field}")
EOF

python /scripts/barra/verify_tushare_data.py
```

### 4.2 数据缺失分类

| 缺失类型 | 影响因子 | 严重性 | 解决方案 |
|---------|---------|-------|---------|
| **基准指数数据路径未知** | Beta, Volatility | 🔴 高 | 编写验证脚本确认路径 |
| **财务数据字段不全** | Earnings Yield, Growth, Leverage | 🟠 中 | 使用简化公式替代 |
| **分析师预期数据缺失** | Growth | 🟡 低 | 只用历史数据计算 |
| **优先股数据缺失** | Leverage | 🟢 极低 | 忽略（A股优先股极少） |

### 4.3 数据覆盖率估计

| 因子 | 数据依赖完整性 | 预计可计算比例 | 备注 |
|-----|--------------|--------------|------|
| Size | 100% | 100% | 无缺失 |
| Beta | 90% | 90% | 需要验证基准指数数据 |
| Momentum | 95% | 95% | 上市不足1年股票无法计算 |
| Volatility | 90% | 90% | 依赖Beta计算 |
| Non-linear Size | 100% | 100% | 依赖Size |
| Book-to-Price | 90% | 85% | 部分ST股PB为负 |
| Liquidity | 98% | 98% | 停牌股换手率为0 |
| Earnings Yield | 70% | 60% | 简化版可达90% |
| Growth | 60% | 50% | 新股数据不足 |
| Leverage | 70% | 65% | 简化版可达85% |
| **综合覆盖率** | - | **~80%** | 简化版可达90% |

---

## 5. 数据质量要求

### 5.1 必需数据字段

**高优先级（P0）**:
- ✅ `daily.close` - 收盘价
- ✅ `daily_basic.total_mv` - 总市值
- ✅ `daily_basic.pb` - 市净率
- ✅ `daily_basic.pe_ttm` - 市盈率TTM
- ✅ `daily_basic.turnover_rate` - 换手率
- ⚠️ `index_daily.close` (000300.SH) - 基准指数
- ✅ `stock_basic.industry` - 行业分类

**中优先级（P1）**:
- ⚠️ `fina_indicator.debt_to_assets` - 资产负债率
- ⚠️ `income.total_revenue` - 营业总收入
- ⚠️ `balancesheet.total_assets` - 总资产

**低优先级（P2）**:
- ⚠️ `fina_indicator.eps` - 每股收益
- ⚠️ `cashflow.n_cashflow_act` - 经营现金流
- ⚠️ `fina_indicator.ebit` - 息税前利润

### 5.2 数据质量标准

| 指标 | 标准 | 说明 |
|-----|------|------|
| **缺失值比例** | < 5% | 每个因子每日缺失股票 < 5% |
| **异常值比例** | < 2% | 超出3倍标准差的值 < 2% |
| **时间序列连续性** | > 95% | 交易日数据连续性 > 95% |
| **横截面覆盖率** | > 90% | 每日至少90%股票有因子值 |

### 5.3 数据异常处理规则

```python
def clean_factor_data(factor_values: pd.Series, factor_name: str) -> pd.Series:
    """
    因子数据清洗
    
    Args:
        factor_values: 原始因子值
        factor_name: 因子名称
        
    Returns:
        清洗后的因子值
    """
    # 定义异常值范围
    outlier_ranges = {
        'size': (5, 15),           # ln(市值) 合理范围
        'beta': (-2, 3),           # Beta合理范围
        'momentum': (-0.8, 2.0),   # 动量合理范围
        'volatility': (0.01, 0.15), # 波动率合理范围
        'book_to_price': (0, 10),  # B/P合理范围
        'liquidity': (0, 100),     # 流动性合理范围
        'earnings_yield': (-0.5, 0.5), # E/P合理范围
        'leverage': (0, 1),        # 杠杆率合理范围
    }
    
    cleaned = factor_values.copy()
    
    # 1. 处理无穷值
    cleaned.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # 2. 截断异常值（Winsorization）
    if factor_name in outlier_ranges:
        lower, upper = outlier_ranges[factor_name]
        cleaned = cleaned.clip(lower=lower, upper=upper)
    
    # 3. 标准化（可选，用于横截面标准化）
    # cleaned = (cleaned - cleaned.mean()) / cleaned.std()
    
    return cleaned
```

---

## 6. 数据缺失处理方案

### 6.1 策略1: 简化因子公式

| 因子 | 完整版 | 简化版 | 数据依赖降低 |
|-----|-------|-------|------------|
| Earnings Yield | 0.68*EPIBS + 0.21*CETOP + 0.11*ETOP | 1/PE_TTM | 从3个数据源→1个 |
| Growth | 0.18*EGRO + 0.11*SGRO + 0.24*EGRLF + 0.47*EGRSF | 5年营收CAGR | 从4个数据源→1个 |
| Leverage | 0.38*MLEV + 0.35*DTOA + 0.27*BLEV | debt_to_assets | 从3个数据源→1个 |

**优点**: 数据覆盖率从60%提升到85%+  
**缺点**: 因子表现可能略逊于完整版

### 6.2 策略2: 分阶段实现

**阶段0（MVP）**: 实现基础版（7个简单因子）
- ✅ Size (市值)
- ✅ Momentum (动量)
- ✅ Liquidity (流动性)
- ✅ Book-to-Price (价值)
- ⚠️ Beta (需要验证基准指数)
- ✅ Non-linear Size (依赖Size)
- ✅ Earnings Yield (简化版)

**阶段1（标准版）**: 补充复杂因子
- ⚠️ Volatility (依赖Beta)
- ⚠️ Growth (简化版)
- ⚠️ Leverage (简化版)

**阶段2（完整版）**: 实现完整公式
- ⚠️ Earnings Yield (完整版，3成分加权)
- ⚠️ Growth (完整版，4成分加权)
- ⚠️ Leverage (完整版，3成分加权)

### 6.3 策略3: 填充缺失值

```python
def fill_missing_factors(factors: pd.DataFrame) -> pd.DataFrame:
    """
    填充缺失的因子值
    
    Args:
        factors: 原始因子DataFrame
        
    Returns:
        填充后的因子DataFrame
    """
    filled = factors.copy()
    
    # 1. 前向填充（适用于低频财务数据）
    financial_factors = ['growth', 'leverage', 'earnings_yield']
    for factor in financial_factors:
        if factor in filled.columns:
            filled[factor].fillna(method='ffill', inplace=True)
    
    # 2. 行业中位数填充
    for factor in filled.columns:
        if filled[factor].isna().sum() > 0:
            # 按行业分组填充
            for industry in filled['industry'].unique():
                industry_mask = filled['industry'] == industry
                industry_median = filled.loc[industry_mask, factor].median()
                filled.loc[industry_mask, factor].fillna(industry_median, inplace=True)
    
    # 3. 全市场中位数填充（兜底）
    for factor in filled.columns:
        if filled[factor].isna().sum() > 0:
            market_median = filled[factor].median()
            filled[factor].fillna(market_median, inplace=True)
    
    return filled
```

### 6.4 策略4: 数据获取优先级

**优先级P0（必须获取）**:
| 数据 | 当前状态 | 行动项 |
|-----|---------|-------|
| 沪深300指数日行情 | ⚠️ 需验证 | 编写验证脚本确认路径 |
| stock_basic.industry | ✅ 可用 | 无需行动 |
| daily、daily_basic | ✅ 可用 | 无需行动 |

**优先级P1（尽量获取）**:
| 数据 | 当前状态 | 行动项 |
|-----|---------|-------|
| fina_indicator | ⚠️ 需验证 | 验证字段完整性 |
| balancesheet | ⚠️ 需验证 | 验证字段完整性 |
| income | ⚠️ 需验证 | 验证字段完整性 |

**优先级P2（可选）**:
| 数据 | 当前状态 | 行动项 |
|-----|---------|-------|
| cashflow | ⚠️ 需验证 | 若缺失则使用简化版 |
| 分析师预期 | ❌ 不可用 | 暂不考虑 |

---

## 附录A: 数据验证清单

### A.1 数据存在性验证

```bash
#!/bin/bash
# 数据验证脚本

DATA_DIR="/home/project/ccleana/data/tushare_data"

echo "=== Barra CNE5 数据验证 ==="
echo ""

# 1. 验证基础数据表
echo "[1] 基础数据表验证"
for table in stock_basic daily daily_basic adj_factor index_classify; do
    if [ -d "$DATA_DIR/$table" ]; then
        echo "✅ $table - 存在"
    else
        echo "❌ $table - 缺失"
    fi
done

# 2. 验证基准指数数据
echo ""
echo "[2] 基准指数数据验证"
INDEX_FILE="$DATA_DIR/index_daily/000300.SH.parquet"
if [ -f "$INDEX_FILE" ]; then
    echo "✅ 沪深300指数数据 - 存在"
else
    echo "⚠️  沪深300指数数据 - 路径需确认"
    echo "   检查以下可能路径:"
    find "$DATA_DIR" -name "*300*" -type f 2>/dev/null | head -5
fi

# 3. 验证财务数据表
echo ""
echo "[3] 财务数据表验证"
for table in fina_indicator balancesheet income cashflow; do
    if [ -d "$DATA_DIR/$table" ]; then
        file_count=$(ls -1 "$DATA_DIR/$table" | wc -l)
        echo "✅ $table - 存在 ($file_count 文件)"
    else
        echo "❌ $table - 缺失"
    fi
done

# 4. 验证示例股票数据完整性
echo ""
echo "[4] 示例股票 (000001.SZ) 数据验证"
TEST_STOCK="000001.SZ"
for table in daily daily_basic adj_factor fina_indicator balancesheet income; do
    FILE="$DATA_DIR/$table/$TEST_STOCK.parquet"
    if [ -f "$FILE" ]; then
        echo "✅ $table/$TEST_STOCK.parquet"
    else
        echo "❌ $table/$TEST_STOCK.parquet"
    fi
done
```

### A.2 数据字段验证

```python
#!/usr/bin/env python3
"""
数据字段完整性验证脚本
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path("/home/project/ccleana/data/tushare_data")
TEST_STOCK = "000001.SZ"

# 定义必需字段
REQUIRED_FIELDS = {
    'daily': ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount'],
    'daily_basic': ['ts_code', 'trade_date', 'total_mv', 'pb', 'pe_ttm', 'turnover_rate'],
    'fina_indicator': ['ts_code', 'ann_date', 'end_date', 'eps', 'debt_to_assets', 'roe'],
    'balancesheet': ['ts_code', 'ann_date', 'end_date', 'total_assets', 'total_liab'],
    'income': ['ts_code', 'ann_date', 'end_date', 'total_revenue', 'n_income'],
}

def verify_fields(table: str, required_fields: list) -> None:
    """验证数据表字段"""
    file_path = DATA_DIR / table / f"{TEST_STOCK}.parquet"
    
    if not file_path.exists():
        print(f"❌ {table}: 文件不存在")
        return
    
    df = pd.read_parquet(file_path)
    missing_fields = [f for f in required_fields if f not in df.columns]
    
    if not missing_fields:
        print(f"✅ {table}: 所有必需字段存在 ({len(df)} 行)")
    else:
        print(f"⚠️  {table}: 缺失字段 - {', '.join(missing_fields)}")
    
    # 显示实际列名
    print(f"   实际字段: {', '.join(df.columns[:10])}...")

if __name__ == "__main__":
    print(f"=== 数据字段验证 (测试股票: {TEST_STOCK}) ===\n")
    
    for table, fields in REQUIRED_FIELDS.items():
        verify_fields(table, fields)
        print()
```

---

## 附录B: 数据缺失汇总表

| 数据项 | 影响因子 | 严重性 | 当前状态 | 建议行动 |
|-------|---------|-------|---------|---------|
| 沪深300指数日行情 | Beta, Volatility | 🔴 高 | ⚠️ 路径未确认 | **立即验证**路径并确认数据可用性 |
| fina_indicator字段 | Earnings Yield, Growth, Leverage | 🟠 中 | ⚠️ 未验证 | 验证字段完整性，缺失则用简化版 |
| balancesheet字段 | Leverage | 🟠 中 | ⚠️ 未验证 | 验证字段完整性 |
| income字段 | Growth, Earnings Yield | 🟠 中 | ⚠️ 未验证 | 验证字段完整性 |
| cashflow字段 | Earnings Yield (CETOP) | 🟡 低 | ⚠️ 未验证 | 缺失可用简化版 |
| 分析师预期数据 | Growth (EGRLF, EGRSF) | 🟡 低 | ❌ 不可用 | 暂不实现，只用历史数据 |
| 优先股数据 | Leverage (MLEV) | 🟢 极低 | ❌ 不可用 | 忽略（A股优先股极少） |

---

## 附录C: 下一步行动清单

### 立即执行（本周）:
1. ✅ **编写数据验证脚本** (`verify_tushare_data.sh`, `verify_fields.py`)
2. ⚠️ **运行验证脚本**，确认数据存在性和字段完整性
3. ⚠️ **记录验证结果**，更新本文档中的"数据状态"列
4. ⚠️ **确定缺失数据的处理方案**（简化公式 vs 数据补全）

### 短期执行（下周）:
5. ⚠️ **编写因子计算脚本MVP** - 先实现7个基础因子
6. ⚠️ **测试因子计算脚本** - 用测试数据验证正确性
7. ⚠️ **生成示例因子数据** - 为10只股票生成因子文件
8. ⚠️ **验证因子数据质量** - 检查缺失值、异常值

### 中期执行（2周后）:
9. ⚠️ **完善因子计算** - 补充复杂因子（Growth, Leverage完整版）
10. ⚠️ **大规模因子计算** - 为全市场5000+只股票生成因子
11. ⚠️ **编写风险估计脚本** - 估计因子协方差矩阵
12. ⚠️ **创建行业分类配置** - 维护industry.json

---

## 版本历史

| 版本 | 日期 | 修改内容 | 修改人 |
|-----|------|---------|-------|
| 1.0 | 2026-01-31 | 初始版本，包含10个因子的完整数据映射 | AI Assistant |

---

**文档说明**:
- 本文档旨在提供Barra CNE5因子计算所需数据的完整映射关系
- 所有标记为⚠️的数据项需要进一步验证确认
- 建议按照"附录C: 下一步行动清单"逐步推进数据验证工作
- 数据验证完成后，请更新本文档中的"数据状态"列

**联系方式**:
- 如有数据相关问题，请参考 `/docs/design/Barra-CNE5-System-Design-v2.md`
- 技术实现参考 `/docs/design/Barra-CNE5-Work-Breakdown-v2.md`
