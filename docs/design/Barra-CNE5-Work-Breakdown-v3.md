# Barra CNE5 量化交易系统 - 第三版工作分解

**文档版本**: 3.0
**创建日期**: 2026-01-31
**项目代号**: Leana-Barra-V3
**总工期估算**: 3周（相比第二版减少50%）
**核心策略**: 预计算 + LEAN原生集成 + 极简代码

---

## 目录

1. [项目概览](#1-项目概览)
2. [与第二版的关键差异](#2-与第二版的关键差异)
3. [阶段零：预计算工具开发（Week 1）](#3-阶段零预计算工具开发week-1)
4. [阶段一：LEAN策略实现（Week 2）](#4-阶段一lean策略实现week-2)
5. [阶段二：测试与优化（Week 3）](#5-阶段二测试与优化week-3)
6. [人工执行任务清单](#6-人工执行任务清单)
7. [系统执行任务清单](#7-系统���行任务清单)
8. [里程碑与交付物](#8-里程碑与交付物)

---

## 1. 项目概览

### 1.1 设计理念

第三版采用**"预计算 + LEAN原生集成"**架构：

```
人工（离线大计算） → 预计算结果（Parquet/JSON） → LEAN（内存加载+极简策略）
```

**核心原则**：
1. **计算密集型工作前置** - 因子计算、风险估计在LEAN外完成
2. **LEAN专注组合优化** - 只做Alpha生成和组合优化
3. **零C#代码** - 完全使用Python实现策略
4. **复用LEAN内置模块** - PortfolioConstruction、RiskManagement等

### 1.2 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **预处理** | Python 3.11 + Pandas + NumPy | 因子计算、风险估计 |
| **数据存储** | Apache Parquet + JSON | 因子数据、风险参数 |
| **策略实现** | Python (LEAN内) | AlphaModel |
| **组合优化** | LEAN内置MeanVariance | 二次规划求解 |

### 1.3 项目结构

```
/home/project/ccleana/
├── scripts/barra/                 # 预处理工具链
│   ├── step1_calculate_factors.py
│   ├── step2_transpose_factors.py
│   ├── step3_factor_returns.py
│   ├── step4_risk_model.py
│   ├── step5_validate.py
│   └── README.md
│
├── data/
│   ├── barra_factors/
│   │   ├── by_stock/              # 按股票存储
│   │   └── by_date/               # 按日期存储
│   ├── barra_risk/
│   │   └── risk_params_latest.json
│   └── barra_config/
│       ├── factor_weights.json
│       └── csi300.txt
│
└── Leana/
    └── Algorithm.Python/
        └── BarraCNE5Algorithm.py  # 主策略（~200行）
```

---

## 2. 与第二版的关键差异

### 2.1 架构对比

| 维度 | 第二版 | 第三版 | 改进 |
|------|--------|--------|------|
| **因子数据读取** | 自定义C# FactorHistoryProvider | Python内存加载 | ✅ 零C#代码 |
| **BarraFactorData** | C#类定义 | Python字典 | ✅ 简化 |
| **PortfolioConstruction** | 自定义CVXPY实现 | LEAN内置模型 | ✅ 复用 |
| **RiskManagement** | 自定义实现 | LEAN内置模型 | ✅ 复用 |
| **ExecutionModel** | 自定义A股规则 | LEAN内置模型 | ✅ 复用 |
| **代码量** | ~1000行 | ~200行 | ✅ 减少80% |

### 2.2 工作量对比

| 阶段 | 第二版工期 | 第三版工期 | 节省 |
|------|-----------|-----------|------|
| 预处理工具 | 2周 | 1周 | 50% |
| C#扩展开发 | 1周 | 0周 | 100% |
| Python策略开发 | 2周 | 0.5周 | 75% |
| 测试与优化 | 1周 | 0.5周 | 50% |
| 配置与文档 | 1周 | 1周 | 0% |
| **总计** | **7周** | **3周** | **57%** |

### 2.3 Token消耗对比

| 任务 | 第二版 | 第三版 | 节省 |
|------|--------|--------|------|
| 预处理脚本 | 1100行Python | 1100行Python（外部） | 0% |
| C# HistoryProvider | 300行C# | 0行 | 100% |
| C# BarraFactorData | 100行C# | 0行 | 100% |
| Python AlphaModel | 80行Python | 40行Python | 50% |
| Python PortfolioConstruction | 200行Python | 0行（复用） | 100% |
| Python RiskManagement | 100行Python | 0行（复用） | 100% |
| Python ExecutionModel | 80行Python | 0行（复用） | 100% |
| 主算法 | 150行Python | 80行Python | 47% |
| **LEAN内代码总计** | **~610行** | **~120行** | **~80%** |

---

## 3. 阶段零：预计算工具开发（Week 1）

**目标**: 开发离线预处理工具链，生成因子Parquet和风险JSON

### 3.1 Task 0.1: 因子计算脚本

**负责人**: 人工开发
**工期**: 3天
**优先级**: P0（关键路径）

**详细任务**:
1. 创建 `/scripts/barra/step1_calculate_factors.py`
2. 实现10个Barra风格因子计算器
3. 实现行业哑变量（30个中信一级行业）
4. 实现因子标准化（去极值、Z-score、中性化）
5. 支持并行处理（multiprocessing.Pool(4)）

**输入**:
- `/data/tushare_data/daily/*.parquet`
- `/data/tushare_data/daily_basic/*.parquet`
- `/data/tushare_data/index_daily/000300.SH.parquet`
- `/data/tushare_data/stock_basic/data.parquet`

**输出**:
- `/data/barra_factors/by_stock/{ts_code}.parquet`
- `/data/barra_config/industry.json`

**验收标准**:
- 成功生成5000+只股票的因子文件
- 单只股票处理时间 < 2秒
- 因子值分布合理（无异常值、无大量NaN）

---

### 3.2 Task 0.2: 转置脚本

**负责人**: 人工开发
**工期**: 0.5天
**优先级**: P0

**详细任务**:
1. 创建 `/scripts/barra/step2_transpose_factors.py`
2. 按日期重组因子数据
3. 支持分批处理避免内存溢出

**输出**:
- `/data/barra_factors/by_date/{date}.parquet`

---

### 3.3 Task 0.3: 因子收益率计算脚本

**负责人**: 人工开发
**工期**: 1天
**优先级**: P0

**详细任务**:
1. 创建 `/scripts/barra/step3_factor_returns.py`
2. 实现横截面回归计算因子收益率
3. 计算股票残差

**输出**:
- `/data/barra_risk/factor_returns.parquet`
- `/data/barra_risk/residuals.parquet`

---

### 3.4 Task 0.4: 风险模型估计脚本

**负责人**: 人工开发
**工期**: 1天
**优先级**: P0

**详细任务**:
1. 创建 `/scripts/barra/step4_risk_model.py`
2. 实现因子协方差矩阵估计（指数加权）
3. 实现特质风险估计
4. 输出JSON格式风险参数

**输出**:
- `/data/barra_risk/risk_params_latest.json`
- `/data/barra_risk/specific_risks.parquet`

---

### 3.5 Task 0.5: 数据验证工具

**负责人**: 人工开发
**工期**: 0.5天
**优先级**: P1

**详细任务**:
1. 创建 `/scripts/barra/step5_validate.py`
2. 检查因子文件完整性
3. 生成数据质量报告（HTML）

**输出**:
- `/data/barra_reports/validation_report.html`

---

### 3.6 Task 0.6: README文档

**负责人**: 人工编写
**工期**: 0.5天
**优先级**: P1

**详细任务**:
1. 创建 `/scripts/barra/README.md`
2. 包含执行步骤、环境要求、故障排查

---

## 4. 阶段一：LEAN策略实现（Week 2）

**目标**: 实现极简的LEAN策略，复用内置模块

### 4.1 Task 1.1: 主算法框架

**负责人**: AI辅助开发
**工期**: 0.5天
**优先级**: P0（关键路径）

**详细任务**:
1. 创建 `/Algorithm.Python/BarraCNE5Algorithm.py`
2. 实现Initialize方法
3. 实现因子数据加载（内存缓存）
4. 实现风险参数加载
5. 配置调仓定时任务

**代码框架**:
```python
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

        # 添加股票池
        self._add_csi300_universe()

        # 设置Alpha模型
        self.SetAlpha(BarraAlphaModel(...))

        # 使用LEAN内置的组合构建模型
        self.SetPortfolioConstruction(
            MeanVariancePortfolioConstructionModel()
        )

        # 定时调仓
        self.Schedule.On(...)
```

**验收标准**:
- 编译通过
- 能成功加载因子数据
- 能成功添加股票

---

### 4.2 Task 1.2: Alpha模型

**负责人**: AI辅助开发
**工期**: 1天
**优先级**: P0（关键路径）

**详细任务**:
1. 创建BarraAlphaModel类
2. 实现Update方法
3. 实现Alpha计算逻辑

**核心代码**:
```python
class BarraAlphaModel(AlphaModel):
    def __init__(self, factor_weights, factor_data):
        self.factor_weights = factor_weights
        self.factor_data = factor_data

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
            insights.append(Insight.Price(symbol, timedelta(days=30), direction, abs(alpha)))

        return insights
```

**验收标准**:
- Alpha分数分布合理
- 生成正确格式的Insight对象

---

### 4.3 Task 1.3: 配置文件

**负责人**: 人工配置
**工期**: 0.5天
**优先级**: P1

**详细任务**:
1. 创建 `/data/barra_config/factor_weights.json`
2. 创建 `/data/barra_config/csi300.txt`
3. 创建 `/Launcher/config/config-barra-cne5-backtest.json`

---

## 5. 阶段二：测试与优化（Week 3）

**目标**: 完成系统测试、参数优化

### 5.1 Task 2.1: 端到端回测

**负责人**: AI辅助测试
**工期**: 1天
**优先级**: P0

**详细任务**:
1. 运行��整回测（2020-2024）
2. 生成回测报告
3. 分析关键指标

**验收指标**:
- 年化收益率 > 基准 + 5%
- 夏普比率 > 1.0
- 最大回撤 < 20%

---

### 5.2 Task 2.2: 参数优化

**负责人**: 人工分析
**工期**: 1天
**优先级**: P1

**详细任务**:
1. 测试不同因子权重组合
2. 测试不同调仓频率
3. 找出最优参数

---

### 5.3 Task 2.3: Live-paper配置

**负责人**: AI辅助配置
**工期**: 1天
**优先级**: P1

**详细任务**:
1. 创建Live-paper配置文件
2. 配置信号导出

---

## 6. 人工执行任务清单

### 6.1 一次性任务（初始化）

| 任务 | 脚本 | 耗时 |
|------|------|------|
| 历史因子全量计算 | `step1_calculate_factors.py` | 15分钟 |
| 转置数据 | `step2_transpose_factors.py` | 2分钟 |
| 计算因子收益率 | `step3_factor_returns.py` | 10秒 |
| 估计风险参数 | `step4_risk_model.py` | 5秒 |
| 验证数据 | `step5_validate.py` | 30秒 |
| **总计** | | **~18分钟** |

### 6.2 日常任务（定期执行）

| 任务 | 频率 | 脚本 | 耗时 |
|------|------|------|------|
| 更新因子数据 | 每日 | `step1_calculate_factors.py --incremental` | 2分钟 |
| 更新风险参数 | 每月 | `step4_risk_model.py` | 5秒 |

---

## 7. 系统执行任务清单

### 7.1 LEAN回测

```bash
cd /home/project/ccleana/Leana

dotnet run --project Launcher \
    --config config/config-barra-cne5-backtest.json
```

### 7.2 LEAN Live-Paper

```bash
dotnet run --project Launcher \
    --config config/config-barra-cne5-live-paper.json \
    --live
```

---

## 8. 里程碑与交付物

### 8.1 总体里程碑

| 里程碑 | 时间 | 验收标准 |
|-------|------|---------|
| M0: 预计算工具完成 | Week 1 | 因子Parquet + 风险JSON生成 |
| M1: LEAN策略完成 | Week 2 | 完整回测运行成功 |
| M2: 系统测试完成 | Week 3 | 回测达标 + Live-paper可用 |

### 8.2 最终交付物清单

#### 预处理工具（外部脚本）
- `step1_calculate_factors.py` (~300行)
- `step2_transpose_factors.py` (~100行)
- `step3_factor_returns.py` (~150行)
- `step4_risk_model.py` (~200行)
- `step5_validate.py` (~150行)
- `README.md`

#### LEAN策略（Python）
- `BarraCNE5Algorithm.py` (~120行)
  - 主算法类 (~60行)
  - BarraAlphaModel (~40行)
  - 辅助函数 (~20行)

#### 配置文件
- `config-barra-cne5-backtest.json`
- `config-barra-cne5-live-paper.json`
- `factor_weights.json`
- `csi300.txt`
- `industry.json`

#### 报告
- 回测结果报告
- 因子有效性报告
- 验证报告

---

## 附录

### A. 快速启动指南

**Step 1: 预计算因子（人工，一次性）**
```bash
cd /home/project/ccleana/scripts/barra

# 按顺序执行5个脚本
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
| 因子计算失败 | 原始数据缺失 | 检查 `/data/tushare_data/` |
| LEAN读取因子失败 | Parquet格式错误 | 运行 `step5_validate.py` |
| 优化求解失败 | 风险参数异常 | 重新运行 `step4_risk_model.py` |

### C. 性能基准

| 指标 | 目标值 |
|------|-------|
| 因子计算速度 | 5000股/15分钟 |
| 回测速度（2020-2024） | < 10分钟 |
| 内存占用 | < 2GB |
| 夏普比率 | > 1.0 |
| 最大回撤 | < 20% |

---

**文档结束**

*第三版工作分解通过"零C#代码 + 复用LEAN内置模块"的策略，将工作量减少57%，开发周期缩短至3周。*
