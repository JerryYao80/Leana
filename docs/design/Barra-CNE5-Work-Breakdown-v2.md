# Barra CNE5 量化交易系统 - 第二版工作分解

**文档版本**: 2.0  
**创建日期**: 2026-01-31  
**项目代号**: Leana-Barra-V2  
**总工期估算**: 7周（相比第一版减少50%）  
**核心策略**: 预计算 + 轻量耦合 + 人机分工

---

## 目录

1. [项目概览](#1-项目概览)
2. [与第一版的关键差异](#2-与第一版的关键差异)
3. [阶段零：预计算工具开发（Week 1-2）](#3-阶段零预计算工具开发week-1-2)
4. [阶段一：LEAN数据层扩展（Week 2-3）](#4-阶段一lean数据层扩展week-2-3)
5. [阶段二：LEAN策略层实现（Week 4-6）](#5-阶段二lean策略层实现week-4-6)
6. [阶段三：测试与优化（Week 7）](#6-阶段三测试与优化week-7)
7. [人工执行任务清单](#7-人工执行任务清单)
8. [系统执行任务清单](#8-系统执行任务清单)
9. [人机接口规范](#9-人机接口规范)
10. [里程碑与交付物](#10-里程碑与交付物)

---

## 1. 项目概览

### 1.1 设计理念

第二版采用**"预计算 + 轻量耦合"**架构：

```
人工（离线大计算） → 预计算结果（Parquet/JSON） → LEAN（轻量读取+优化）
```

**核心原则**：
1. **计算密集型工作前置** - 因子计算、风险估计在LEAN外完成
2. **LEAN专注核心逻辑** - 只做组合优化、订单执行
3. **清晰的人机接口** - 标准化的数据格式（Parquet、JSON）

### 1.2 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **预处理** | Python 3.11 + Pandas + NumPy | 因子计算、风险估计 |
| **数据存储** | Apache Parquet | 因子数据持久化 |
| **配置管理** | JSON | 风险参数、策略配置 |
| **LEAN扩展** | C# (.NET 10.0) | FactorHistoryProvider |
| **策略实现** | Python (LEAN内) | AlphaModel, PortfolioConstruction |
| **组合优化** | CVXPY | 二次规划求解 |

### 1.3 项目结构

```
/home/project/ccleana/
├── data/
│   ├── tushare_data/          # 原始Tushare数据（已存在）
│   ├── barra_factors/         # 【新增】预计算因子Parquet
│   ├── barra_risk/            # 【新增】风险参数JSON
│   └── barra_config/          # 【新增】配置文件
│
├── scripts/barra/             # 【新增】预处理工具链
│   ├── factor_calculator.py
│   ├── risk_estimator.py
│   ├── industry_classifier.py
│   └── validate_factors.py
│
└── Leana/
    ├── Common/Data/
    │   └── BarraFactorData.cs  # 【新增】因子数据类型
    │
    ├── Engine/HistoricalData/
    │   └── FactorHistoryProvider.cs  # 【新增】因子数据提供者
    │
    └── Algorithm.Python/
        ├── BarraCNE5Algorithm.py      # 【新增】主策略
        ├── BarraAlphaModel.py
        ├── BarraPortfolioConstructionModel.py
        ├── BarraRiskManagementModel.py
        └── BarraExecutionModel.py
```

---

## 2. 与第一版的关键差异

### 2.1 架构对比

| 维度 | 第一版 | 第二版 | 改进 |
|------|--------|--------|------|
| **因子计算** | LEAN内实时计算（Python） | 预计算脚本（离线） | ✅ 回测速度提升100倍 |
| **风险模型** | 每次调仓估计协方差矩阵 | 预估计JSON配置 | ✅ 减少90%计算量 |
| **数据读取** | TushareHistoryProvider（多表join） | FactorHistoryProvider（单Parquet） | ✅ I/O优化50倍 |
| **代码量** | ~2500行（Python+C#） | ~800行（Python+C#） | ✅ 简化68% |
| **LEAN耦合** | 自定义数据类型+多个Provider | 复用FactorFile基础设施 | ✅ 利用现有架构 |

### 2.2 工作量对比

| 阶段 | 第一版工期 | 第二版工期 | 节省 |
|------|-----------|-----------|------|
| 数据层 | 2周 | 1周 | 50% |
| 因子引擎 | 4周 | 2周（脚本） | 50% |
| 风险模型 | 2周 | 1周（脚本） | 50% |
| 策略框架 | 2周 | 2周 | 0% |
| 组合优化 | 2周 | 1周 | 50% |
| 测试 | 2周 | 1周 | 50% |
| **总计** | **14周** | **7周** | **50%** |

### 2.3 Token消耗对比

| 任务 | 第一版 | 第二版 | 节省 |
|------|--------|--------|------|
| 因子计算代码 | 800行Python | 外部脚本（不占LEAN） | 100% |
| 风险模型代码 | 500行Python | JSON配置 | 100% |
| 数据层代码 | 600行C# | 300行C#（复用） | 50% |
| 策略层代码 | 600行Python | 200行Python（简化） | 67% |
| **总计** | **~2500行** | **~500行** | **80%** |

---

## 3. 阶段零：预计算工具开发（Week 1-2）

**目标**: 开发离线预处理工具链，生成因子Parquet和风险JSON

### 3.1 Task 0.1: 因子计算脚本（核心）

**负责人**: 人工开发  
**工期**: 5天  
**优先级**: P0（关键路径）

**详细任务**:
1. 创建 `/scripts/barra/factor_calculator.py`
2. 实现10个Barra风格因子计算器：
   - Size (市值)
   - Beta (市场风险)
   - Momentum (动量)
   - Volatility (残差波动)
   - Non-linear Size (非线性市值)
   - Value (价值)
   - Liquidity (流动性)
   - Earnings Yield (盈利)
   - Growth (成长)
   - Leverage (杠杆)
3. 实现行业哑变量（30个中信一级行业）
4. 实现因子标准化（去极值、Z-score、中性化）
5. 支持并行处理（multiprocessing）

**输入**:
- `/data/tushare_data/daily/*.parquet` (OHLCV)
- `/data/tushare_data/daily_basic/*.parquet` (市值、PE、PB)
- `/data/tushare_data/fina_indicator/*.parquet` (财务指标)
- `/data/tushare_data/income/*.parquet` (利润表)
- `/data/tushare_data/balancesheet/*.parquet` (资产负债表)
- `/data/tushare_data/cashflow/*.parquet` (现金流量表)

**输出**:
- `/data/barra_factors/{ts_code}.parquet` (每只股票一个文件)
- 数据格式：
  ```
  trade_date: datetime64[ns]
  size: float64
  beta: float64
  momentum: float64
  ...（共10个风格因子）
  ind_petrochemical: int8  # 行业哑变量1
  ind_coal: int8           # 行业哑变量2
  ...（共30个行业哑变量）
  ```

**验证标准**:
- 成功生成5000+只股票的因子文件
- 单只股票处理时间 < 2秒
- 因子值分布合理（无异常值、无大量NaN）
- 与手工计算的3个样本股票对比，误差 < 0.1%

**脚本模板**:
```bash
python factor_calculator.py \
    --input /data/tushare_data \
    --output /data/barra_factors \
    --start-date 2020-01-01 \
    --end-date 2024-12-31 \
    --parallel 8 \
    --log-level INFO
```

---

### 3.2 Task 0.2: 风险模型估计脚本

**负责人**: 人工开发  
**工期**: 3天  
**优先级**: P0

**详细任务**:
1. 创建 `/scripts/barra/risk_estimator.py`
2. 实现因子收益率计算（横截面回归）
3. 实现因子协方差矩阵估计（指数加权）
4. 实现特质风险估计
5. 输出JSON格式风险参数

**输入**:
- `/data/barra_factors/*.parquet` (预计算因子)

**输出**:
- `/data/barra_risk/risk_params_{date}.json`
- `/data/barra_risk/risk_params_latest.json` (软链接)

**JSON格式**:
```json
{
  "estimation_date": "2024-12-31",
  "estimation_window": 252,
  "half_life": 90,
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

**验证标准**:
- 协方差矩阵正定（所有特征值 > 0）
- 特质风险在合理范围（0.01 ~ 0.10）
- 与第三方Barra风险估计对比（若有参考数据）

---

### 3.3 Task 0.3: 行业分类配置

**负责人**: 人工配置  
**工期**: 1天  
**优先级**: P1

**详细任务**:
1. 创建 `/data/barra_config/industry.json`
2. 定义30个中信一级行业代码
3. 维护股票→行业映射表

**输出格式**:
```json
{
  "industry_list": [
    "ind_petrochemical",
    "ind_coal",
    ...  // 共30个
  ],
  "industry_mapping": {
    "000001.SZ": "ind_bank",
    "000002.SZ": "ind_real_estate",
    ...
  }
}
```

---

### 3.4 Task 0.4: 数据验证工具

**负责人**: 人工开发  
**工期**: 2天  
**优先级**: P2

**详细任务**:
1. 创建 `/scripts/barra/validate_factors.py`
2. 检查因子文件完整性
3. 生成数据质量报告（HTML）

**验证项**:
- 缺失值比例（应 < 5%）
- 因子值分布（偏度、峰度）
- 因子间相关性（检测多重共线性）
- 时间序列连续性

**输出**:
- `/data/barra_reports/validation_{date}.html`

---

### 3.5 阶段零里程碑

**验收标准**:
- ✅ `/data/barra_factors/` 包含5000+个Parquet文件
- ✅ `/data/barra_risk/risk_params_latest.json` 存在且格式正确
- ✅ `/data/barra_config/industry.json` 配置完整
- ✅ 数据验证报告显示质量合格

**交付物**:
- `factor_calculator.py` (500行)
- `risk_estimator.py` (300行)
- `industry_classifier.py` (100行)
- `validate_factors.py` (200行)
- 因子数据 (5000+ Parquet文件)
- 风险参数 (risk_params_latest.json)
- 验证报告 (validation.html)

---

## 4. 阶段一：LEAN数据层扩展（Week 2-3）

**目标**: 在LEAN中实现因子数据读取，复用现有FactorFile基础设施

### 4.1 Task 1.1: BarraFactorData数据类型

**负责人**: AI辅助开发  
**工期**: 1天  
**优先级**: P0

**详细任务**:
1. 创建 `/Common/Data/BarraFactorData.cs`
2. 继承 `BaseData`
3. 定义10个因子属性 + 30个行业哑变量

**实现要点**:
```csharp
public class BarraFactorData : BaseData
{
    // 10个风格因子
    public decimal Size { get; set; }
    public decimal Beta { get; set; }
    public decimal Momentum { get; set; }
    public decimal Volatility { get; set; }
    public decimal NonLinearSize { get; set; }
    public decimal Value { get; set; }
    public decimal Liquidity { get; set; }
    public decimal EarningsYield { get; set; }
    public decimal Growth { get; set; }
    public decimal Leverage { get; set; }
    
    // 行业哑变量（30个）
    public Dictionary<string, int> IndustryExposures { get; set; }
    
    public override BaseData Reader(...)
    {
        // 占位实现（实际读取在FactorHistoryProvider）
        return new BarraFactorData();
    }
}
```

**验证标准**:
- 编译通过
- 可在Python中通过 `AddData(BarraFactorData, symbol)` 订阅

---

### 4.2 Task 1.2: FactorHistoryProvider实现

**负责人**: AI辅助开发  
**工期**: 3天  
**优先级**: P0（关键路径）

**详细任务**:
1. 创建 `/Engine/HistoricalData/FactorHistoryProvider.cs`
2. 继承 `HistoryProviderBase`
3. 实现从Parquet读取因子数据
4. 复用LEAN现有的FactorFile基础设施

**关键代码**:
```csharp
public class FactorHistoryProvider : HistoryProviderBase
{
    private string _factorDataRoot;
    private ParquetReader _reader;
    
    public override void Initialize(HistoryProviderInitializeParameters parameters)
    {
        _factorDataRoot = Config.Get("factor-data-root");
        _reader = new ParquetReader();
    }
    
    public override IEnumerable<Slice> GetHistory(
        IEnumerable<HistoryRequest> requests, 
        DateTimeZone sliceTimeZone)
    {
        // 读取因子Parquet文件
        // 转换为BarraFactorData
        // 组装Slice
    }
}
```

**输入**:
- 配置项：`factor-data-root = /data/barra_factors`

**输出**:
- `IEnumerable<Slice>` 包含 `BarraFactorData`

**验证标准**:
- 单元测试：读取测试Parquet → 验证因子值正确
- 集成测试：在简单Algorithm中订阅因子数据 → `OnData`中能访问

**复用现有代码**:
- 参考 `/Common/Data/Auxiliary/LocalDiskFactorFileProvider.cs`
- 参考 `/Engine/HistoricalData/SubscriptionDataReaderHistoryProvider.cs`

---

### 4.3 Task 1.3: Parquet读取工具类

**负责人**: AI辅助开发  
**工期**: 2天  
**优先级**: P0

**详细任务**:
1. 添加 `Apache.Arrow.Parquet` NuGet包依赖
2. 创建 `ParquetReader` 工具类
3. 实现高效读取和时间范围过滤

**实现要点**:
```csharp
public class ParquetReader
{
    public IEnumerable<T> ReadParquet<T>(string filePath, DateTime start, DateTime end)
        where T : BaseData, new()
    {
        using var stream = File.OpenRead(filePath);
        using var reader = new ParquetFileReader(stream);
        
        // 读取、过滤、转换
        ...
    }
}
```

**验证标准**:
- 单元测试：读取测试Parquet → 验证时间范围过滤正确
- 性能测试：读取1年数据（~250行） < 100ms

---

### 4.4 Task 1.4: 配置文件更新

**负责人**: AI辅助配置  
**工期**: 0.5天  
**优先级**: P1

**详细任务**:
1. 创建 `/Launcher/config/config-barra-cne5-backtest.json`
2. 注册 `FactorHistoryProvider`

**配置示例**:
```json
{
  "environment": "backtesting",
  "algorithm-location": "Algorithm.Python/BarraCNE5Algorithm.py",
  
  "data-folder": "/data",
  "factor-data-root": "/data/barra_factors",
  "risk-params-file": "/data/barra_risk/risk_params_latest.json",
  
  "history-provider": [
    "QuantConnect.Lean.Engine.HistoricalData.FactorHistoryProvider"
  ]
}
```

---

### 4.5 阶段一里程碑

**验收标准**:
- ✅ `BarraFactorData.cs` 实现并编译通过
- ✅ `FactorHistoryProvider.cs` 能成功读取因子Parquet
- ✅ 单元测试覆盖率 > 80%
- ✅ 简单Algorithm能订阅并接收因子数据

**交付物**:
- `BarraFactorData.cs` (~100行)
- `FactorHistoryProvider.cs` (~300行)
- `ParquetReader.cs` (~200行)
- `config-barra-cne5-backtest.json`
- 单元测试文件

---

## 5. 阶段二：LEAN策略层实现（Week 4-6）

**目标**: 实现AlgorithmFramework各模块，完成策略逻辑

### 5.1 Task 2.1: 主算法框架

**负责人**: AI辅助开发  
**工期**: 1天  
**优先级**: P0

**详细任务**:
1. 创建 `/Algorithm.Python/BarraCNE5Algorithm.py`
2. 配置Algorithm Framework
3. 实现调仓定时任务

**代码框架**:
```python
class BarraCNE5Algorithm(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(10000000)
        self.SetBenchmark("000300")
        
        # 加载风险参数
        with open('/data/barra_risk/risk_params_latest.json') as f:
            self.risk_params = json.load(f)
        
        # 设置Framework
        self.SetUniverseSelection(CSI300UniverseSelectionModel())
        self.SetAlpha(BarraAlphaModel())
        self.SetPortfolioConstruction(BarraPortfolioConstructionModel(self.risk_params))
        self.SetRiskManagement(BarraRiskManagementModel())
        self.SetExecution(BarraExecutionModel())
        
        # 定时调仓（每月第一个交易日）
        self.Schedule.On(
            self.DateRules.MonthStart("000300"),
            self.TimeRules.AfterMarketOpen("000300", 30),
            self.Rebalance
        )
        
        # 预热
        self.SetWarmUp(252, Resolution.Daily)
```

---

### 5.2 Task 2.2: CSI300UniverseSelectionModel

**负责人**: AI辅助开发  
**工期**: 1天  
**优先级**: P0

**详细任务**:
1. 创建股票池选择模型
2. 从Tushare数据读取沪深300成分股
3. 实现过滤规则（剔除ST、停牌、新股）

**实现要点**:
```python
class CSI300UniverseSelectionModel(UniverseSelectionModel):
    def SelectCoarse(self, algorithm, coarse):
        # 从 /data/tushare_data/index_weight/000300.SH.parquet 读取
        csi300 = self._load_csi300_constituents(algorithm.Time)
        
        # 过滤
        filtered = [s for s in csi300 if not self._is_excluded(s)]
        
        return filtered
```

---

### 5.3 Task 2.3: BarraAlphaModel

**负责人**: AI辅助开发  
**工期**: 2天  
**优先级**: P0

**详细任务**:
1. 创建 `/Algorithm.Python/BarraAlphaModel.py`
2. 实现Alpha生成：`Alpha = Σ w_k * f_k`
3. 从配置读取因子权重

**关键代码**:
```python
class BarraAlphaModel(AlphaModel):
    def __init__(self):
        self.factor_weights = {
            'momentum': 0.15,
            'value': 0.15,
            'earnings_yield': 0.15,
            'growth': 0.15,
            'liquidity': 0.10,
            'volatility': -0.10,
            'leverage': -0.05,
        }
    
    def Update(self, algorithm, data):
        insights = []
        
        for symbol in algorithm.ActiveSecurities.Keys:
            # 获取因子数据（预计算）
            factor_data = data.Get(BarraFactorData, symbol)
            if not factor_data: continue
            
            # 计算Alpha
            alpha = sum(
                self.factor_weights[k] * getattr(factor_data, k.capitalize())
                for k in self.factor_weights
            )
            
            # 生成Insight
            direction = InsightDirection.Up if alpha > 0 else InsightDirection.Down
            insights.append(Insight.Price(
                symbol, 
                timedelta(days=30), 
                direction, 
                abs(alpha)
            ))
        
        return insights
```

**验证标准**:
- Alpha分数分布合理（均值≈0, 标准差≈1）
- Top 20%股票平均Alpha > 0.3

---

### 5.4 Task 2.4: BarraPortfolioConstructionModel

**负责人**: AI辅助开发  
**工期**: 4天  
**优先级**: P0（核心）

**详细任务**:
1. 创建 `/Algorithm.Python/BarraPortfolioConstructionModel.py`
2. 实现CVXPY组合优化
3. 使用预加载的风险参数

**核心逻辑**:
```python
class BarraPortfolioConstructionModel(PortfolioConstructionModel):
    def __init__(self, risk_params):
        self.risk_params = risk_params  # 预加载
        self.optimizer = BarraPortfolioOptimizer(risk_params)
    
    def CreateTargets(self, algorithm, insights):
        # 提取Alpha
        alphas = {i.Symbol: i.Magnitude for i in insights}
        
        # 提取因子暴露（从BarraFactorData）
        factor_exposures = self._get_factor_exposures(algorithm, alphas.keys())
        
        # 获取基准权重
        benchmark_weights = self._get_benchmark_weights()
        
        # 优化（使用预估计的风险参数）
        optimal_weights = self.optimizer.optimize(
            alphas, 
            factor_exposures, 
            benchmark_weights
        )
        
        return [PortfolioTarget(s, w) for s, w in optimal_weights.items()]
```

**CVXPY优化器**:
```python
class BarraPortfolioOptimizer:
    def optimize(self, alphas, factor_exposures, benchmark_weights):
        # 从预估计参数加载协方差矩阵
        F = self._load_factor_covariance()
        specific_risks = self._load_specific_risks()
        
        # CVXPY求解
        h = cp.Variable(N)
        objective = cp.Maximize(alpha_vec @ h - lambda_risk * portfolio_risk)
        constraints = [
            cp.sum(h) == 1,
            h >= 0,
            h <= 0.05,
            cp.norm(h - h_prev, 1) <= 0.3,
            # ... 因子中性约束
        ]
        
        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.ECOS)
        
        return optimal_weights
```

**验证标准**:
- 优化问题在10秒内求解成功
- 所有约束条件满足
- 预期Alpha > 等权组合

---

### 5.5 Task 2.5: BarraRiskManagementModel

**负责人**: AI辅助开发  
**工期**: 2天  
**优先级**: P1

**详细任务**:
1. 创建风险管理模块
2. 实现风控检查（波动率、回撤、涨跌停）

**实现要点**:
```python
class BarraRiskManagementModel(RiskManagementModel):
    def ManageRisk(self, algorithm, targets):
        # 检查组合风险
        if portfolio_risk > 0.15:
            targets = self._scale_targets(targets, 0.8)
        
        # 检查回撤
        if drawdown > 0.10:
            targets = self._scale_targets(targets, 0.5)
        
        # 过滤涨跌停
        targets = self._filter_limit_stocks(targets)
        
        return targets
```

---

### 5.6 Task 2.6: BarraExecutionModel

**负责人**: AI辅助开发  
**工期**: 2天  
**优先级**: P1

**详细任务**:
1. 创建执行模块
2. 实现A股规则（100股单位、T+1检查）

**实现要点**:
```python
class BarraExecutionModel(ExecutionModel):
    def Execute(self, algorithm, targets):
        for target in targets:
            delta = target.Quantity - current_quantity
            
            # 调整为100股整数倍
            delta = round(delta / 100) * 100
            
            # T+1检查
            if delta < 0 and not self._can_sell(symbol, -delta):
                continue
            
            algorithm.MarketOrder(symbol, delta)
```

---

### 5.7 阶段二里程碑

**验收标准**:
- ✅ 主算法能成功运行回测（2020-2024）
- ✅ Alpha生成、组合优化、风控、执行模块全部工作
- ✅ 调仓频率正确（每月1次）
- ✅ A股规则得到遵守（100股、T+1）

**交付物**:
- `BarraCNE5Algorithm.py` (~150行)
- `CSI300UniverseSelectionModel.py` (~100行)
- `BarraAlphaModel.py` (~80行)
- `BarraPortfolioConstructionModel.py` (~200行)
- `BarraRiskManagementModel.py` (~100行)
- `BarraExecutionModel.py` (~80行)

---

## 6. 阶段三：测试与优化（Week 7）

**目标**: 完成系统测试、参数优化、Live-paper配置

### 6.1 Task 3.1: 端到端回测

**负责人**: AI辅助测试  
**工期**: 2天  
**优先级**: P0

**详细任务**:
1. 运行完整回测（2020-2024）
2. 生成回测报告
3. 分析关键指标

**验收指标**:
- 年化收益率 > 基准 + 5%
- 夏普比率 > 1.0
- 最大回撤 < 20%
- 换手率 < 50%/年
- 信息比率 > 0.5

---

### 6.2 Task 3.2: 参数敏感性分析

**负责人**: 人工分析  
**工期**: 2天  
**优先级**: P1

**详细任务**:
1. 测试不同因子权重组合
2. 测试不同风险厌恶系数
3. 测试不同调仓频率
4. 找出最优参数

**测试矩阵**:
- 因子权重：30种组合
- 风险厌恶λ：[0.5, 1.0, 2.0]
- 调仓频率：[月度、双周、周度]

---

### 6.3 Task 3.3: 因子有效性验证

**负责人**: 人工分析  
**工期**: 1天  
**优先级**: P1

**详细任务**:
1. 计算各因子IC（信息系数）
2. 分层回测（按因子值分5组）
3. 因子相关性分析

**验证标准**:
- Momentum, Value, Earnings Yield IC > 0.05
- 因子间相关性 < 0.6

---

### 6.4 Task 3.4: A股规则合规性测试

**负责人**: AI辅助测试  
**工期**: 1天  
**优先级**: P0

**测试用例**:
```python
def test_t_plus_one():
    """验证T+1规则"""
    # Day 1: 买入
    algorithm.MarketOrder("000001", 100)
    
    # Day 1: 立即卖出（应失败）
    with pytest.raises(Exception):
        algorithm.MarketOrder("000001", -100)
    
    # Day 2: 卖出（应成功）
    algorithm.SetDateTime(algorithm.Time + timedelta(days=1))
    order = algorithm.MarketOrder("000001", -100)
    assert order.Status == OrderStatus.Filled

def test_lot_size():
    """验证100股单位"""
    order = algorithm.MarketOrder("000001", 150)
    assert order.FilledQuantity % 100 == 0
```

---

### 6.5 Task 3.5: Live-paper配置

**负责人**: AI辅助配置  
**工期**: 1天  
**优先级**: P1

**详细任务**:
1. 创建Live-paper配置文件
2. 配置信号导出

**配置示例**:
```json
{
  "environment": "live-paper",
  "live-mode": true,
  "live-mode-brokerage": "ASharePaperBrokerage",
  
  "signal-export": {
    "enabled": true,
    "output-path": "/output/signals",
    "format": "csv"
  }
}
```

---

### 6.6 阶段三里程碑

**验收标准**:
- ✅ 回测性能达标（夏普 > 1.0）
- ✅ 参数优化完成
- ✅ 因子有效性验证通过
- ✅ A股规则合规性100%
- ✅ Live-paper模式配置完成

**交付物**:
- 回测报告 (HTML)
- 参数敏感性分析报告
- 因子有效性报告
- 单元测试套件
- Live-paper配置文件

---

## 7. 人工执行任务清单

### 7.1 日常任务

| 任务 | 频率 | 脚本 | 耗时 |
|------|------|------|------|
| 更新因子数据 | 每日 | `factor_calculator.py --incremental` | 10分钟 |
| 更新风险参数 | 每月 | `risk_estimator.py` | 30分钟 |
| 数据质量检查 | 每周 | `validate_factors.py` | 5分钟 |

### 7.2 一次性任务

| 任务 | 时机 | 脚本 | 耗时 |
|------|------|------|------|
| 历史因子全量计算 | 初始化 | `factor_calculator.py --full` | 2-4小时 |
| 初始风险参数估计 | 初始化 | `risk_estimator.py --historical` | 1小时 |
| 行业分类配置 | 初始化 | 手动编辑JSON | 30分钟 |

### 7.3 Cron任务配置

```bash
# /etc/crontab

# 每日17:00更新因子数据
0 17 * * * python /scripts/barra/factor_calculator.py --incremental

# 每月1日更新风险参数
0 2 1 * * python /scripts/barra/risk_estimator.py

# 每周日数据验证
0 3 * * 0 python /scripts/barra/validate_factors.py
```

---

## 8. 系统执行任务清单

### 8.1 LEAN回测

```bash
cd /home/project/ccleana/Leana

dotnet run --project Launcher \
    --config config/config-barra-cne5-backtest.json
```

### 8.2 LEAN Live-Paper

```bash
dotnet run --project Launcher \
    --config config/config-barra-cne5-live-paper.json \
    --live
```

---

## 9. 人机接口规范

### 9.1 因子数据格式（Parquet）

**文件路径**: `/data/barra_factors/{ts_code}.parquet`

**Schema**:
```
trade_date: datetime64[ns]
size: float64
beta: float64
momentum: float64
volatility: float64
non_linear_size: float64
value: float64
liquidity: float64
earnings_yield: float64
growth: float64
leverage: float64
ind_petrochemical: int8
ind_coal: int8
...  (共30个行业哑变量)
```

**质量要求**:
- 缺失值比例 < 5%
- 时间序列连续（除停牌日）
- 因子值在合理范围（无极端异常值）

---

### 9.2 风险参数格式（JSON）

**文件路径**: `/data/barra_risk/risk_params_latest.json`

**Schema**:
```json
{
  "estimation_date": "YYYY-MM-DD",
  "estimation_window": 252,
  "half_life": 90,
  "factor_covariance": {
    "size": {"size": float, "beta": float, ...},
    ...
  },
  "specific_risks": {
    "ts_code": float,
    ...
  }
}
```

**质量要求**:
- 协方差矩阵必须正定
- 特质风险在0.01 ~ 0.10范围

---

### 9.3 配置文件格式（JSON）

**策略配置**: `/Launcher/config/config-barra-cne5-backtest.json`

```json
{
  "barra": {
    "factor_weights": {
      "momentum": 0.15,
      ...
    },
    "optimizer": {
      "risk_aversion": 1.0,
      "max_weight": 0.05,
      ...
    }
  }
}
```

---

## 10. 里程碑与交付物

### 10.1 总体里程碑

| 里程碑 | 时间 | 验收标准 |
|-------|------|---------|
| M0: 预计算工具完成 | Week 2 | 因子Parquet + 风险JSON生成 |
| M1: LEAN数据层完成 | Week 3 | FactorHistoryProvider读取成功 |
| M2: LEAN策略层完成 | Week 6 | 完整回测运行成功 |
| M3: 系统测试完成 | Week 7 | 回测达标 + Live-paper可用 |

### 10.2 最终交付物清单

#### 预处理工具
- `factor_calculator.py` (~500行)
- `risk_estimator.py` (~300行)
- `industry_classifier.py` (~100行)
- `validate_factors.py` (~200行)

#### LEAN扩展（C#）
- `BarraFactorData.cs` (~100行)
- `FactorHistoryProvider.cs` (~300行)
- `ParquetReader.cs` (~200行)

#### LEAN策略（Python）
- `BarraCNE5Algorithm.py` (~150行)
- `CSI300UniverseSelectionModel.py` (~100行)
- `BarraAlphaModel.py` (~80行)
- `BarraPortfolioConstructionModel.py` (~200行)
- `BarraRiskManagementModel.py` (~100行)
- `BarraExecutionModel.py` (~80行)

#### 配置文件
- `config-barra-cne5-backtest.json`
- `config-barra-cne5-live-paper.json`
- `industry.json`

#### 测试代码
- 单元测试 (~10个文件)
- 集成测试 (~5个文件)

#### 文档
- 用户手册
- 运维手册
- API文档

#### 报告
- 回测结果报告
- 因子有效性报告
- 参数敏感性分析报告

---

## 附录

### A. 快速启动指南

**Step 1: 预计算因子（人工，一次性）**
```bash
cd /home/project/ccleana/scripts/barra
python factor_calculator.py --full
python risk_estimator.py
python validate_factors.py
```

**Step 2: 运行回测（系统）**
```bash
cd /home/project/ccleana/Leana
dotnet run --project Launcher \
    --config config/config-barra-cne5-backtest.json
```

**Step 3: 每日更新（人工，定时）**
```bash
# 每日17:00自动执行
python /scripts/barra/factor_calculator.py --incremental
```

---

### B. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 因子计算失败 | 原始数据缺失 | 检查 `/data/tushare_data/` |
| LEAN读取因子失败 | Parquet格式错误 | 运行 `validate_factors.py` |
| 优化求解失败 | 风险参数异常 | 重新运行 `risk_estimator.py` |
| 回测性能差 | 因子权重不合理 | 调整配置 + 重新回测 |

---

### C. 性能基准

| 指标 | 目标值 | 实际值（填写） |
|------|-------|--------------|
| 因子计算速度 | 5000股/5分钟 | ______ |
| 回测速度（2020-2024） | < 15分钟 | ______ |
| 内存占用 | < 2GB | ______ |
| 夏普比率 | > 1.0 | ______ |
| 最大回撤 | < 20% | ______ |

---

**文档结束**

*第二版工作分解通过清晰的人机分工，将工作量减半至7周，同时保持与LEAN的紧密耦合。预计算架构显著提升了系统性能和可维护性。*
