# Barra CNE5 量化交易系统 - 第三版设计文档

**文档版本**: 3.0
**创建日期**: 2026-01-31
**项目代号**: Leana-Barra-V3
**核心原则**: 预计算 + LEAN原生集成 + 最小token消耗

---

## 目录

1. [设计理念变更](#1-设计理念变更)
2. [LEAN原生集成架构](#2-lean原生集成架构)
3. [数据流程设计](#3-数据流程设计)
4. [LEAN集成点详解](#4-lean集成点详解)
5. [预计算工具链](#5-预计算工具链)
6. [策略框架实现](#6-策略框架实现)
7. [配置管理](#7-配置管理)
8. [与第二版对比](#8-与第二版对比)

---

## 1. 设计理念变更

### 1.1 第三版核心改进

| 改进点 | 第二版 | 第三版 | 提升 |
|-------|--------|--------|------|
| **LEAN集成深度** | 添加外部Provider | 复用LEAN现有基础设施 | 更深耦合 |
| **因子数据读取** | 自定义FactorHistoryProvider | 复用SubscriptionDataReader | 代码量-60% |
| **策略实现** | 完整自定义Framework | 最小化Alpha模型 | 代码量-70% |
| **Token消耗** | 中等（约2000行） | 极低（约600行） | -70% |
| **维护性** | 需维护C# Provider | 纯Python策略 | 更易维护 |

### 1.2 核心设计原则（第三版）

#### **原则1：复用LEAN现有基础设施**
- 不创建新的HistoryProvider，使用`AddEquity()`+`History` API
- 因子数据通过Python在`Initialize()`中加载
- 利用LEAN现有的`Algorithm.Framework`模块

#### **原则2：策略逻辑极简化**
- Alpha模型：直接加权因子暴露
- PortfolioConstruction：使用LEAN内置的`MeanVariancePortfolioConstructionModel`
- 风险管理：使用LEAN内置的`MaximumDrawdownPercentPerSecurity`

#### **原则3：数据预计算+策略配置分离**
- 预计算：因子Parquet文件（人工/定时脚本）
- 策略配置：JSON文件（因子权重、约束参数）
- 运行时：LEAN只做组合优化

---

## 2. LEAN原生集成架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    人工预处理阶段（离线）                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Python脚本 (scripts/barra/)                              │  │
│  │   step1: 计算因子 → /data/barra_factors/by_stock/       │  │
│  │   step2: 转置数据 → /data/barra_factors/by_date/        │  │
│  │   step3: 计算因子收益率 → /data/barra_risk/             │  │
│  │   step4: 估计风险模型 → /data/barra_risk/risk_params.json│  │
│  │   step5: 验证数据 → /data/barra_reports/                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    LEAN回测/实盘阶段                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ BarraCNE5Algorithm.Initialize()                          │  │
│  │   ├── 加载风险参数: risk_params_latest.json              │  │
│  │   ├── 加载因子数据: by_date/*.parquet (内存缓存)          │  │
│  │   └── 设置Framework模块                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ BarraAlphaModel.Update()                                 │  │
│  │   ├── 从内存获取因子暴露                                  │  │
│  │   ├── Alpha = Σ w_k × f_k (配置驱动)                     │  │
│  │   └── 生成Insight对象                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ MeanVariancePortfolioConstructionModel (LEAN内置)         │  │
│  │   ├── 使用风险参数预测协方差                              │  │
│  │   ├── 求解最优权重                                       │  │
│  │   └── 生成PortfolioTarget                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ LEAN执行引擎                                             │  │
│  │   ├── AShareFeeModel (已存在)                            │  │
│  │   ├── TPlusOneSettlementModel (已存在)                   │  │
│  │   └── ImmediateExecutionModel (LEAN内置)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键差异：不再创建新的HistoryProvider

| 组件 | 第二版方案 | 第三版方案 |
|------|----------|----------|
| **因子数据读取** | 创建FactorHistoryProvider.cs | Python在Initialize中加载 |
| **数据类型** | 创建BarraFactorData.cs | 使用Python字典 |
| **配置管理** | 复杂的C#配置系统 | 简单JSON配置文件 |
| **策略框架** | 完整自定义6个模块 | 只需1个Alpha模型 |

---

## 3. 数据流程设计

### 3.1 预处理流程（人工执行）

```bash
# Step 1-5: 顺序执行预处理脚本
cd /home/project/ccleana/scripts/barra

python step1_calculate_factors.py    # 15分钟
python step2_transpose_factors.py    # 2分钟
python step3_factor_returns.py       # 10秒
python step4_risk_model.py           # 5秒
python step5_validate.py             # 30秒

# 总计: ~18分钟
```

### 3.2 LEAN回测流程（系统执行）

```python
# BarraCNE5Algorithm.py
class BarraCNE5Algorithm(QCAlgorithm):
    def Initialize(self):
        # 1. 设置基本参数
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(10000000)
        self.SetBenchmark("000300.SH")

        # 2. 加载预计算数据（内存缓存）
        self.factor_data = self._load_factor_data()
        self.risk_params = self._load_risk_params()

        # 3. 添加股票
        self._add_universe()

        # 4. 设置Alpha模型（唯一的自定义模块）
        self.SetAlpha(BarraAlphaModel(
            factor_weights=self._load_factor_weights(),
            factor_data=self.factor_data
        ))

        # 5. 使用LEAN内置的组合构建模型
        self.SetPortfolioConstruction(
            MeanVariancePortfolioConstructionModel()
        )

        # 6. 定时调仓
        self.Schedule.On(
            self.DateRules.MonthStart(),
            self.TimeRules.AfterMarketOpen("000300.SH", 30),
            self.Rebalance
        )

    def _load_factor_data(self):
        """在Initialize时加载所有因子数据到内存"""
        factor_data = {}
        for file in Path("/data/barra_factors/by_date").glob("*.parquet"):
            df = pd.read_parquet(file)
            date = pd.to_datetime(file.stem)
            factor_data[date] = df.set_index('ts_code')
        return factor_data

    def _load_risk_params(self):
        """加载风险参数"""
        with open("/data/barra_risk/risk_params_latest.json") as f:
            return json.load(f)
```

---

## 4. LEAN集成点详解

### 4.1 数据加载策略

```python
class BarraCNE5Algorithm(QCAlgorithm):
    def _load_factor_data(self) -> Dict[datetime, pd.DataFrame]:
        """
        策略初始化时加载所有因子数据

        内存占用估算:
        - 1000个交易日 × 5000只股票 × 40个因子 × 8字节
        = 1.6GB (可接受)

        优点:
        1. 无需自定义HistoryProvider
        2. 回测时无需I/O操作
        3. 实现极简
        """
        factor_data = {}
        data_dir = Path("/data/barra_factors/by_date")

        for file in sorted(data_dir.glob("*.parquet")):
            date = self._parse_date(file.stem)
            df = pd.read_parquet(file)
            factor_data[date] = df.set_index('ts_code')

        return factor_data
```

### 4.2 Alpha模型（核心自定义模块）

```python
class BarraAlphaModel(AlphaModel):
    """
    Barra CNE5 Alpha模型

    核心逻辑: Alpha = Σ w_k × f_k

    其中:
    - w_k: 因子权重（从配置读取）
    - f_k: 因子暴露（从预计算数据读取）
    """

    def __init__(self, factor_weights: Dict[str, float],
                 factor_data: Dict[datetime, pd.DataFrame]):
        self.factor_weights = factor_weights
        self.factor_data = factor_data
        self.insight_period = timedelta(days=30)

    def Update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        insights = []
        current_date = algorithm.Time.date()

        # 获取当日因子数据
        if current_date not in self.factor_data:
            return insights

        factor_df = self.factor_data[current_date]

        # 遍历所有股票
        for symbol in algorithm.ActiveSecurities.Keys:
            ts_code = self._symbol_to_ts_code(symbol)

            if ts_code not in factor_df.index:
                continue

            # 获取因子暴露
            factors = factor_df.loc[ts_code]

            # 计算Alpha
            alpha = self._calculate_alpha(factors)

            # 生成Insight
            direction = InsightDirection.Up if alpha > 0 else InsightDirection.Down
            insights.append(Insight.Price(
                symbol,
                self.insight_period,
                direction,
                abs(alpha)  # Magnitude
            ))

        return insights

    def _calculate_alpha(self, factors: pd.Series) -> float:
        """Alpha = Σ w_k × f_k"""
        alpha = 0.0
        for factor_name, weight in self.factor_weights.items():
            if factor_name in factors:
                alpha += weight * factors[factor_name]
        return alpha
```

### 4.3 使用LEAN内置的组合构建模型

```python
# LEAN内置的MeanVariancePortfolioConstructionModel
# 已经支持协方差矩阵输入，可直接复用

class BarraCNE5Algorithm(QCAlgorithm):
    def Initialize(self):
        # ...

        # 创建自定义协方差估计器
        covariance_estimator = BarraCovarianceEstimator(
            risk_params=self.risk_params,
            factor_data=self.factor_data
        )

        # 使用LEAN内置模型，传入自定义协方差估计器
        self.SetPortfolioConstruction(
            MeanVariancePortfolioConstructionModel(
                covariance_estimator=custom_estimator
            )
        )
```

---

## 5. 预计算工具链

### 5.1 脚本列表

| 脚本 | 功能 | 输入 | 输出 | 耗时 |
|------|------|------|------|------|
| step1_calculate_factors.py | 计算因子暴露 | tushare_data | by_stock/*.parquet | 15min |
| step2_transpose_factors.py | 转置数据 | by_stock/*.parquet | by_date/*.parquet | 2min |
| step3_factor_returns.py | 计算因子收益率 | by_date/*.parquet | factor_returns.parquet | 10s |
| step4_risk_model.py | 估计风险模型 | factor_returns.parquet | risk_params.json | 5s |
| step5_validate.py | 验证数据 | 所有输出 | validation_report.html | 30s |

### 5.2 输出数据格式

```python
# by_date/YYYYMMDD.parquet
Schema:
{
  "ts_code": "000001.SZ",
  "size": 13.82,           # 市值因子
  "beta": 1.05,            # Beta因子
  "momentum": 0.12,        # 动量因子
  "volatility": 0.25,      # 波动率因子
  "non_linear_size": 2638,# 非线性市值
  "book_to_price": 0.85,   # 价值因子
  "liquidity": 2.5,        # 流动性因子
  "earnings_yield": 0.05,  # 盈利因子
  "growth": 0.0,           # 成长因子（简化）
  "leverage": 0.5,         # 杠杆因子（简化）
  "ind_petrochemical": 0,
  "ind_coal": 0,
  ...
  "ind_bank": 1            # 行业哑变量
}
```

```json
// risk_params_latest.json
{
  "estimation_date": "2024-12-31",
  "factor_covariance": {
    "size": {"size": 0.0001, "beta": 0.00005, ...},
    "beta": {"size": 0.00005, "beta": 0.0002, ...},
    ...
  },
  "specific_risks": {
    "000001.SZ": 0.025,
    "000002.SZ": 0.030,
    ...
  }
}
```

---

## 6. 策略框架实现

### 6.1 完整策略代码

```python
# Algorithm.Python/BarraCNE5Algorithm.py
from Algorithm.Framework import AlphaModel, Insight, InsightDirection
from Algorithm.Framework.PortfolioConstruction import MeanVariancePortfolioConstructionModel
from datetime import timedelta
import pandas as pd
import json
from pathlib import Path

class BarraAlphaModel(AlphaModel):
    def __init__(self, factor_weights, factor_data):
        self.factor_weights = factor_weights
        self.factor_data = factor_data
        self.insight_period = timedelta(days=30)

    def Update(self, algorithm, data):
        insights = []
        current_date = algorithm.Time.date()

        if current_date not in self.factor_data:
            return insights

        factor_df = self.factor_data[current_date]

        for symbol in algorithm.ActiveSecurities.Keys:
            ts_code = self._symbol_to_ts_code(symbol)
            if ts_code not in factor_df.index:
                continue

            factors = factor_df.loc[ts_code]
            alpha = sum(self.factor_weights.get(k, 0) * factors.get(k, 0)
                       for k in self.factor_weights)

            direction = InsightDirection.Up if alpha > 0 else InsightDirection.Down
            insights.append(Insight.Price(symbol, self.insight_period, direction, abs(alpha)))

        return insights

    def _symbol_to_ts_code(self, symbol):
        # 将LEAN Symbol转换为Tushare ts_code
        return f"{symbol.Value}.{symbol.ID.Market}"


class BarraCNE5Algorithm(QCAlgorithm):
    def Initialize(self):
        # 基本设置
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(10000000)
        self.SetBenchmark("000300.SH")

        # 加载预计算数据
        self.factor_data = self._load_factor_data()
        self.risk_params = self._load_risk_params()
        self.factor_weights = self._load_factor_weights()

        # 添加股票池（沪深300）
        self._add_csi300_universe()

        # 设置Alpha模型
        self.SetAlpha(BarraAlphaModel(self.factor_weights, self.factor_data))

        # 设置组合构建模型（使用LEAN内置）
        self.SetPortfolioConstruction(MeanVariancePortfolioConstructionModel())

        # 定时调仓（每月第一个交易日）
        self.Schedule.On(
            self.DateRules.MonthStart(),
            self.TimeRules.AfterMarketOpen("000300.SH", 30),
            self.Rebalance
        )

    def _load_factor_data(self):
        factor_data = {}
        for file in Path("/data/barra_factors/by_date").glob("*.parquet"):
            date = pd.to_datetime(file.stem).date()
            df = pd.read_parquet(file)
            factor_data[date] = df.set_index('ts_code')
        return factor_data

    def _load_risk_params(self):
        with open("/data/barra_risk/risk_params_latest.json") as f:
            return json.load(f)

    def _load_factor_weights(self):
        # 从配置文件读取因子权重
        return {
            'momentum': 0.15,
            'value': 0.15,
            'earnings_yield': 0.15,
            'growth': 0.15,
            'liquidity': 0.10,
            'volatility': -0.10,
            'leverage': -0.05,
        }

    def _add_csi300_universe(self):
        # 从预配置的股票列表添加
        csi300_stocks = self._load_csi300_list()
        for stock in csi300_stocks:
            self.AddEquity(stock, Resolution.Daily)

    def _load_csi300_list(self):
        # 从文件或配置读取沪深300成分股
        with open("/data/barra_config/csi300.txt") as f:
            return [line.strip() for line in f]

    def Rebalance(self):
        # 调仓逻辑（由PortfolioConstructionModel自动处理）
        pass
```

### 6.2 代码量对比

| 模块 | 第二版 | 第三版 | 减少 |
|------|--------|--------|------|
| C# HistoryProvider | 300行 | 0行 | -100% |
| C# BarraFactorData | 100行 | 0行 | -100% |
| Python AlphaModel | 80行 | 40行 | -50% |
| Python PortfolioConstruction | 200行 | 0行（复用内置） | -100% |
| Python RiskManagement | 100行 | 0行（复用内置） | -100% |
| Python ExecutionModel | 80行 | 0行（复用内置） | -100% |
| 主算法 | 150行 | 80行 | -47% |
| **总计** | **~1010行** | **~200行** | **-80%** |

---

## 7. 配置管理

### 7.1 配置文件结构

```
/home/project/ccleana/data/barra_config/
├── factor_weights.json      # 因子权重配置
├── portfolio_constraints.json # 组合约束配置
├── csi300.txt               # 沪深300成分股列表
└── industry.json            # 行业分类配置
```

### 7.2 配置文件示例

```json
// factor_weights.json
{
  "factor_weights": {
    "momentum": 0.15,
    "value": 0.15,
    "earnings_yield": 0.15,
    "growth": 0.15,
    "liquidity": 0.10,
    "volatility": -0.10,
    "leverage": -0.05,
    "size": 0.0,
    "beta": 0.0,
    "non_linear_size": 0.0
  }
}
```

```json
// portfolio_constraints.json
{
  "max_weight": 0.05,
  "max_turnover": 0.3,
  "min_positions": 50,
  "risk_aversion": 1.0
}
```

---

## 8. 与第二版对比

### 8.1 架构对比

| 维度 | 第二版 | 第三版 |
|------|--------|--------|
| **因子数据读取** | 自定义FactorHistoryProvider | Python内存加载 |
| **C#代码** | ~400行 | 0行 |
| **Python代码** | ~600行 | ~200行 |
| **总代码量** | ~1000行 | ~200行 |
| **复用LEAN组件** | 部分复用 | 完全复用 |

### 8.2 性能对比

| 指标 | 第二版 | 第三版 |
|------|--------|--------|
| **初始化时间** | ~5秒 | ~10秒 |
| **回测速度** | 快 | 更快（无C#互操作） |
| **内存占用** | ~2GB | ~1.6GB |
| **维护成本** | 中等 | 低 |

### 8.3 开发工作量对比

| 阶段 | 第二版 | 第三版 | 节省 |
|------|--------|--------|------|
| 预处理工具 | 2周 | 2周 | 0% |
| C#扩展开发 | 1周 | 0周 | -100% |
| Python策略开发 | 2周 | 0.5周 | -75% |
| 测试调试 | 1周 | 0.5周 | -50% |
| **总计** | **6周** | **3周** | **-50%** |

---

## 附录

### A. 快速启动指南

**Step 1: 预计算因子（人工，一次性）**
```bash
cd /home/project/ccleana/scripts/barra
python step1_calculate_factors.py
python step2_transpose_factors.py
python step3_factor_returns.py
python step4_risk_model.py
python step5_validate.py
```

**Step 2: 运行回测（系统）**
```bash
cd /home/project/ccleana/Leana
dotnet run --project Launcher \
    --config config/config-barra-cne5-backtest.json
```

### B. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 因子数据加载失败 | Parquet文件不存在 | 运行step1-5 |
| 回测内存溢出 | 因子数据过大 | 缩短回测时间范围 |
| 优化求解失败 | 协方差矩阵非正定 | 运行step4重新估计 |

---

**文档结束**

*第三版设计通过"预计算 + LEAN原生集成"的架构，将代码量减少80%，开发周期缩短50%，同时保持与LEAN框架的紧密耦合。*
