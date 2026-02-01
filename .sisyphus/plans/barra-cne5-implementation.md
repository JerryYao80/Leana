# Barra CNE5 计算程序实现计划

**目标**: 创建5个Python脚本，利用4核CPU完成Barra CNE5完整计算流程，并与LEAN框架紧密集成

**执行方式**: 用户手动按顺序执行5个脚本，然后在LEAN中回测

---

## 文件结构

```
/home/project/ccleana/
├── scripts/barra/                    # 【新增】预处理工具链
│   ├── step1_calculate_factors.py    # 第1步: 计算因子暴露矩阵X
│   ├── step2_transpose_factors.py    # 第2步: 转置数据（按日期重组）
│   ├── step3_factor_returns.py       # 第3步: 横截面回归计算因子收益
│   ├── step4_risk_model.py           # 第4步: 估计协方差和特质风险
│   ├── step5_validate.py             # 第5步: 验证结果并生成报告
│   └── README.md                     # 执行说明
│
├── data/
│   ├── tushare_data/                 # 原始Tushare数据（已存在）
│   ├── barra_factors/                # 【新增】预计算因子Parquet
│   │   ├── by_stock/                 # 按股票存储（5000个文件）
│   │   └── by_date/                  # 按日期存储（1000个文件）
│   ├── barra_risk/                   # 【新增】风险参数JSON
│   ��   ├── factor_returns.parquet    # 因子收益率时间序列
│   │   ├── residuals.parquet         # 股票残差
│   │   ├── risk_params_latest.json   # 最新风险参数
│   │   └── specific_risks.parquet    # 特质风险
│   └── barra_config/                 # 【新增】配置文件
│       └── industry.json             # 行业分类配置
│
└── Leana/                            # LEAN框架
    ├── Common/Data/
    │   └── BarraFactorData.cs        # 【新增】因子数据类型
    ├── Engine/HistoricalData/
    │   └── FactorHistoryProvider.cs  # 【新增】因子数据提供者
    └── Algorithm.Python/
        ├── BarraCNE5Algorithm.py     # 【新增】主策略
        ├── BarraAlphaModel.py        # 【新增】Alpha模型
        ├── BarraPortfolioConstructionModel.py  # 【新增】组合构建
        ├── BarraRiskManagementModel.py         # 【新增】风险管理
        └── BarraExecutionModel.py    # 【新增】执行模型
```

---

## 执行流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        人工预处理阶段                           │
│  (离线执行，一次性或定期更新)                                   │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   step1:              step2:              step3:
   计算因子             转置数据            计算因子收益
   (按股票)            (按日期)            (横截面回归)
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                     step4:
                     估计风险模型
                     (协方差矩阵)
                            │
                            ▼
                     step5:
                     验证数据质量
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        LEAN回测阶段                             │
│  (系统自动执行，使用预计算数据)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## TODOs

### Task 1: 编写step1_calculate_factors.py

**功能**: 计算因子暴露矩阵X（按股票并行）

**输入**:
- `/data/tushare_data/daily/{ts_code}.parquet`
- `/data/tushare_data/daily_basic/{ts_code}.parquet`
- `/data/tushare_data/index_daily/000300.SH.parquet` (基准指数)
- `/data/tushare_data/stock_basic/data.parquet`

**输出**:
- `/data/barra_factors/by_stock/{ts_code}.parquet` (每只股票一个文件)
- `/data/barra_config/industry.json` (行业分类配置)
- `/data/barra_reports/step1_factor_calculation.log`

**核心逻辑**:
```python
# 1. 加载辅助数据（stock_basic, benchmark, industry_map）
# 2. ��义FactorCalculator类计算10个因子：
#    - Size: ln(total_mv)
#    - Beta: 252天滚动回归
#    - Momentum: (P_t-21 / P_t-252) - 1
#    - Volatility: 收益率标准差
#    - Non-linear Size: Size^3
#    - Book-to-Price: 1/PB
#    - Liquidity: 加权换手率
#    - Earnings Yield: 1/PE_TTM
#    - Growth: 固定值0.0（简化版）
#    - Leverage: 固定值0.5（简化版）
# 3. 添加30个行业哑变量
# 4. 使用multiprocessing.Pool(4)并行处理5000只股票
# 5. 保存为Parquet格式（每只股票一个文件）
```

**数据格式**:
```
Columns: ['trade_date', 'size', 'beta', 'momentum', 'volatility',
          'non_linear_size', 'book_to_price', 'liquidity',
          'earnings_yield', 'growth', 'leverage',
          'ind_petrochemical', 'ind_coal', ..., 'ind_comprehensive']
Rows: ~1000 (交易日数量)
```

**性能要求**:
- 并行度: 4核
- 预估时间: ~15分钟（4核）
- 内存占用: < 2GB

**错误处理**:
- 如果某只股票数据缺失，记录warning并跳过
- 如果基准指数找不到，抛出FileNotFoundError
- 所有异常写入日志文件

**LEAN集成点**:
- 输出的Parquet文件将被`FactorHistoryProvider`读取
- 行业分类配置将被LEAN策略用于行业中性约束

**Parallelization**:
- **Can Run In Parallel**: NO (必须先于其他步骤)
- **Blocks**: Task 2, 3, 4, 5
- **Blocked By**: None

**Acceptance Criteria**:
- [ ] 脚本文件创建: `/home/project/ccleana/scripts/barra/step1_calculate_factors.py`
- [ ] 运行后生成5000+个parquet文件到 `/data/barra_factors/by_stock/`
- [ ] 每个文件包含40列（10因子+30行业）
- [ ] 日志文件存在且记录成功/失败统计
- [ ] industry.json配置文件生成

---

### Task 2: 编写step2_transpose_factors.py

**功能**: 转置因子数据（从按股票存储 → 按日期存储）

**输入**:
- `/data/barra_factors/by_stock/*.parquet` (5000个文件)

**输出**:
- `/data/barra_factors/by_date/{date}.parquet` (1000个文件)
- `/data/barra_reports/step2_transpose.log`

**核心逻辑**:
```python
# 1. 读取所有股票的因子数据
# 2. 按交易日期分组重组
# 3. 每个日期生成一个文件，包含当天所有股票的因子暴露
# 4. 使用分批处理避免内存溢出
```

**数据格式**:
```
# 每个文件（例如20200101.parquet）
Columns: ['ts_code', 'size', 'beta', ..., 'ind_comprehensive']
Rows: ~5000 (当天有数据的股票数量)
```

**LEAN集成点**:
- 按日期存储的数据便于LEAN在回测时快速加载特定日期的横截面数据

**性能要求**:
- 并行度: 4核（按日期批次并行）
- 预估时间: ~2分钟
- 内存占用: < 1GB（分批处理）

**Parallelization**:
- **Can Run In Parallel**: NO
- **Blocks**: Task 3
- **Blocked By**: Task 1

**Acceptance Criteria**:
- [ ] 脚本文件创建: `/home/project/ccleana/scripts/barra/step2_transpose_factors.py`
- [ ] 运行后生成1000+个parquet文件到 `/data/barra_factors/by_date/`
- [ ] 每个文件包含~5000行（股票数量）
- [ ] 日志记录转置进度

---

### Task 3: 编写step3_factor_returns.py

**功能**: 横截面回归计算因子收益率f

**输入**:
- `/data/barra_factors/by_date/*.parquet` (因子暴露矩阵X)
- `/data/tushare_data/daily/{ts_code}.parquet` (股票收益率)

**输出**:
- `/data/barra_risk/factor_returns.parquet` (因子收益率时间序列)
- `/data/barra_risk/residuals.parquet` (股票残差)
- `/data/barra_reports/step3_factor_returns.log`

**核心逻辑**:
```python
# 每个交易日t:
# 1. 加载当天所有股票的因子暴露 X_t (5000 × 40)
# 2. 计算当天所有股票的收益率 R_t (5000 × 1)
# 3. 横截面回归: R_t = X_t @ f_t + u_t
#    使用加权最小二乘（WLS），权重 = sqrt(market_cap)
# 4. 求解因子收益率 f_t (40 × 1)
# 5. 计算残差 u_t = R_t - X_t @ f_t
# 6. 保存因子收益率和残差
```

**数学公式**:
```
f_t = (X_t^T @ W @ X_t)^(-1) @ X_t^T @ W @ R_t

其中:
- X_t: 因子暴露矩阵 (N × K)
- R_t: 股票收益率向量 (N × 1)
- W: 权重矩阵 diag(sqrt(market_cap)) (N × N)
- f_t: 因子收益率 (K × 1)
```

**数据格式**:
```
# factor_returns.parquet
Columns: ['trade_date', 'size', 'beta', ..., 'ind_comprehensive']
Rows: ~1000 (交易日数量)

# residuals.parquet
Columns: ['trade_date', 'ts_code', 'residual']
Rows: ~5,000,000 (1000天 × 5000股票)
```

**LEAN集成点**:
- 因子收益率用于LEAN的组合优化（风险预测）
- 残差用于特质风险估计

**性能要求**:
- 并行度: 单线程（横截面回归不易并行）
- 预估时间: ~10秒
- 内存占用: < 500MB

**Parallelization**:
- **Can Run In Parallel**: NO
- **Blocks**: Task 4
- **Blocked By**: Task 2

**Acceptance Criteria**:
- [ ] 脚本文件创建: `/home/project/ccleana/scripts/barra/step3_factor_returns.py`
- [ ] 生成factor_returns.parquet（1000行 × 40列）
- [ ] 生成residuals.parquet（~500万行）
- [ ] 因子收益率均值接近0（横截面回归特性）
- [ ] 日志记录每日回归状态

---

### Task 4: 编写step4_risk_model.py

**功能**: 估计因子协方差矩阵F和特质风险Δ

**输入**:
- `/data/barra_risk/factor_returns.parquet` (因子收益率)
- `/data/barra_risk/residuals.parquet` (股票残差)
- `/data/tushare_data/daily_basic/{ts_code}.parquet` (市值数据)

**输出**:
- `/data/barra_risk/risk_params_latest.json` (风险参数)
- `/data/barra_risk/specific_risks.parquet` (特质风险)
- `/data/barra_reports/step4_risk_model.log`

**核心逻辑**:
```python
# 第一步: 计算因子协方差矩阵F (40 × 40)
# 1. 加载因子收益率时间序列 f (T × K)
# 2. 指数加权协方差（半衰期90天）
#    decay = 0.5^(1/90)
#    weights = [decay^i for i in range(T-1, -1, -1)]
# 3. 加权协方差: F = sum(weights * (f - mean(f))^T @ (f - mean(f)))
# 4. 特征值调整（确保正定）
# 5. Newey-West调整（处理自相关）

# 第二步: 计算特质风险Δ (N × 1)
# 1. 对每只股票i，加载残差序列 u_i (T × 1)
# 2. 计算252天滚动标准差（指数加权）
# 3. 结构化调整（根据市值、行业调整）
# 4. 贝叶斯收缩（向横截面中位数收缩）
```

**数学公式**:
```
# 因子协方差
F = sum_{t=1}^{T} w_t * (f_t - mean(f))^T @ (f_t - mean(f))

# 特质风险
Δ_i = sqrt(sum_{t=1}^{252} w_t * u_{i,t}^2)
```

**数据格式**:
```json
// risk_params_latest.json
{
  "estimation_date": "2024-12-31",
  "estimation_window": 252,
  "half_life": 90,

  "factor_covariance": {
    "size": {"size": 0.0001, "beta": 0.00005, ...},
    "beta": {"size": 0.00005, "beta": 0.0002, ...},
    ...
  },

  "factor_volatility": {
    "size": 0.01,
    "beta": 0.015,
    ...
  }
}
```

```
# specific_risks.parquet
Columns: ['ts_code', 'specific_risk']
Rows: ~5000
```

**LEAN集成点**:
- 风险参数JSON将被LEAN的`BarraPortfolioConstructionModel`加载
- 用于组合优化时的风险预测

**性能要求**:
- 并行度: 4核（计算特质风险时按股票并行）
- 预估时间: ~5秒
- 内存占用: < 200MB

**Parallelization**:
- **Can Run In Parallel**: NO
- **Blocks**: Task 5
- **Blocked By**: Task 3

**Acceptance Criteria**:
- [ ] 脚本文件创建: `/home/project/ccleana/scripts/barra/step4_risk_model.py`
- [ ] 生成risk_params_latest.json（包含40×40协方差矩阵）
- [ ] 生成specific_risks.parquet（5000行）
- [ ] 协方差矩阵正定（所有特征值>0）
- [ ] 特质风险均值在0.01-0.05范围内

---

### Task 5: 编写step5_validate.py

**功能**: 验证结果并生成HTML报告

**输入**:
- `/data/barra_factors/by_stock/*.parquet`
- `/data/barra_factors/by_date/*.parquet`
- `/data/barra_risk/factor_returns.parquet`
- `/data/barra_risk/risk_params_latest.json`
- `/data/barra_risk/specific_risks.parquet`

**输出**:
- `/data/barra_reports/validation_report.html`
- `/data/barra_reports/step5_validation.log`

**验证项**:
```python
# 1. 数据完整性
#    - 因子文件数量（应 >= 4000）
#    - 日期文件数量（应 >= 900）
#    - 因子收益率行数（应 >= 900）

# 2. 数据质量
#    - 因子缺失值比例（应 < 5%）
#    - 因子异常值比例（应 < 2%）
#    - 因子相关性检查（避免多重共线性）

# 3. 数学性质
#    - 协方差矩阵正定性
#    - 因子收益率均值接近0
#    - 特质风险分布合理

# 4. 可视化
#    - 因子分布直方图
#    - 因子相关性热力图
#    - 因子收益率时间序列图
#    - 特质风险分布图
```

**HTML报告结构**:
```html
<!DOCTYPE html>
<html>
<head><title>Barra CNE5 Validation Report</title></head>
<body>
  <h1>Barra CNE5 Validation Report</h1>

  <h2>1. Data Completeness</h2>
  <table>...</table>

  <h2>2. Data Quality</h2>
  <table>...</table>

  <h2>3. Mathematical Properties</h2>
  <table>...</table>

  <h2>4. Visualizations</h2>
  <img src="data:image/png;base64,..." />
  ...
</body>
</html>
```

**性能要求**:
- 预估时间: ~30秒
- 内存占用: < 1GB

**LEAN集成点**:
- 验证通过是运行LEAN回测的前提
- 报告帮助用户了解数据质量

**Parallelization**:
- **Can Run In Parallel**: NO
- **Blocks**: None
- **Blocked By**: Task 1, 2, 3, 4

**Acceptance Criteria**:
- [ ] 脚本文件创建: `/home/project/ccleana/scripts/barra/step5_validate.py`
- [ ] 生成validation_report.html（可在浏览器打开）
- [ ] 报告包含数据完整性统计
- [ ] 报告包含至少4张可视化图表
- [ ] 验证失败时在日志中明确指出问题

---

### Task 6: 编写README.md执行说明

**功能**: 提供详细的执行步骤和说明

**输出**:
- `/home/project/ccleana/scripts/barra/README.md`

**内容结构**:
```markdown
# Barra CNE5 计算程序执行指南

## 环境要求
- Python 3.8+
- 依赖包: pandas, numpy, pyarrow, tqdm, matplotlib, seaborn

## 执行步骤

### 第1步: 计算因子暴露矩阵X
```bash
cd /home/project/ccleana/scripts/barra
python step1_calculate_factors.py
```
预估时间: 15分钟（4核）
输出: `/data/barra_factors/by_stock/*.parquet`

### 第2步: 转置数据
...

### 第3步: 计算因子收益率
...

### 第4步: 估计风险模型
...

### 第5步: 验证结果
...

### 第6步: 运行LEAN回测
```bash
cd /home/project/ccleana/Leana
dotnet run --project Launcher \
    --config config/config-barra-cne5-backtest.json
```

## 故障排查
...

## 输出文件说明
...
```

**Parallelization**:
- **Can Run In Parallel**: YES
- **Blocks**: None
- **Blocked By**: None

**Acceptance Criteria**:
- [ ] README.md文件创建
- [ ] 包含完整的执行步骤（6个步骤，含LEAN回测）
- [ ] 包含环境要求和依赖安装说明
- [ ] 包含故障排查章节
- [ ] 包含输出文件说明

---

## Execution Strategy

### Sequential Execution (推荐)
```
Task 1 (step1) → Task 2 (step2) → Task 3 (step3) → Task 4 (step4) → Task 5 (step5)
             ↘
              Task 6 (README) - 可随时执行
```

**Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

**Total Time Estimate**:
- Task 1: ~15分钟
- Task 2: ~2分钟
- Task 3: ~10秒
- Task 4: ~5秒
- Task 5: ~30秒
- **Total**: ~18分钟

---

## Success Criteria

验收标准:
- ✅ 所有6个文件成功创建
- ✅ step1运行后生成5000+个因子文件
- ✅ step2运行后生成1000+个日期文件
- ✅ step3生成因子收益率和残差文件
- ✅ step4生成风险参数JSON
- ✅ step5生成HTML验证报告
- ✅ 所有日志文件记录详细执行信息
- ✅ 验证通过后可运行LEAN回测

---

## Notes

**重要提示**:
1. 必须按顺序执行（step1 → step2 → step3 → step4 → step5）
2. 每步执行前检查上一步的输出文件是否存在
3. 如果某步失败，查看对应的日志文件排查问题
4. 所有脚本支持中断后重新运行（幂等性）
5. Growth和Leverage因子使用简化版（固定值），如需完整版需补充财务数据处理

**数据依赖**:
- 必须有基准指数数据（000300.SH）
- stock_basic.parquet必须包含industry字段
- daily和daily_basic数据必须完整

**性能调优**:
- 如果内存不足，可在step1中减少并行度（改为2核）
- 如果磁盘空间不足，可删除by_stock或by_date其中一个（保留by_date用于后续计算）

---

## 与LEAN集成

完成预处理步骤后，LEAN将使用以下组件读取预计算数据:

1. **FactorHistoryProvider.cs** - 读取因子Parquet文件
2. **BarraFactorData.cs** - 因子数据容器
3. **BarraCNE5Algorithm.py** - 主策略
4. **BarraAlphaModel.py** - Alpha生成
5. **BarraPortfolioConstructionModel.py** - 组合优化（使用risk_params_latest.json）
6. **BarraRiskManagementModel.py** - 风险管理
7. **BarraExecutionModel.py** - 订单执行

LEAN配置文件示例:
```json
{
  "algorithm-type-name": "BarraCNE5Algorithm",
  "algorithm-language": "Python",
  "algorithm-location": "Algorithm.Python/BarraCNE5Algorithm.py",
  "data-folder": "/data",
  "factor-data-root": "/data/barra_factors",
  "risk-params-file": "/data/barra_risk/risk_params_latest.json"
}
```
