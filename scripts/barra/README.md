# Barra CNE5 计算程序执行指南

**版本**: 1.0
**更新日期**: 2026-01-31
**目的**: 提供Barra CNE5因子计算和风险估计的完整执行流程

---

## 环境要求

- Python 3.8+
- 依赖包:
  ```
  pandas>=1.5.0
  numpy>=1.20.0
  pyarrow>=10.0.0
  tqdm>=4.60.0
  matplotlib>=3.3.0
  seaborn>=0.11.0
  scipy>=1.5.0
  ```

### 安装依赖

```bash
# 激活conda环境
source /root/miniconda3/bin/activate quant311

# 安装依赖包
pip install pandas numpy pyarrow tqdm matplotlib seaborn scipy
```

---

## 执行步骤

### 概览

```
Step 1: 计算因子暴露矩阵 → Step 2: 转置数据 → Step 3: 计算因子收益率 → Step 4: 估计风险模型 → Step 5: 验证数据
```

**总耗时**: 约 18 分钟 (取决于CPU核心数)

---

### Step 1: 计算因子暴露矩阵

**功能**: 计算10个Barra风格因子 + 30个行业哑变量

**执行**:
```bash
cd /home/project/ccleana/scripts/barra
python step1_calculate_factors.py --parallel 4
```

**参数**:
- `--parallel N`: 并行进程数 (默认: 4)

**输出**:
- `/data/barra_factors/by_stock/*.parquet` - 每只股票一个文件
- `/data/barra_config/industry.json` - 行业分类配置
- `/data/barra_reports/step1_factor_calculation.log` - 执行日志
- `/data/barra_reports/step1_results.json` - 统计结果

**预计耗时**: 15分钟 (4核)

**成功标准**:
- 生成 5000+ 个parquet文件
- 日志显示成功率 > 95%

---

### Step 2: 转置数据

**功能**: 将按股票存储的数据转置为按日期存储

**执行**:
```bash
cd /home/project/ccleana/scripts/barra
python step2_transpose_factors.py
```

**输出**:
- `/data/barra_factors/by_date/*.parquet` - 每个交易日一个文件
- `/data/barra_reports/step2_transpose.log` - 执行日志

**预计耗时**: 2分钟

**成功标准**:
- 生成 1000+ 个日期文件
- 每个文件包含 ~5000 只股票

---

### Step 3: 计算因子收益率

**功能**: 通过横截面回归计算因子收益率

**执行**:
```bash
cd /home/project/ccleana/scripts/barra
python step3_factor_returns.py
```

**输出**:
- `/data/barra_risk/factor_returns.parquet` - 因子收益率时间序列
- `/data/barra_risk/residuals.parquet` - 股票残差
- `/data/barra_reports/step3_factor_returns.log` - 执行日志

**预计耗时**: 10秒

**成功标准**:
- 因子收益率文件包含 900+ 条记录
- 残差文件包含 ~500万 条记录

---

### Step 4: 估计风险模型

**功能**: 估计因子协方差矩阵和特质风险

**执行**:
```bash
cd /home/project/ccleana/scripts/barra
python step4_risk_model.py --estimation-window 252 --half-life 90
```

**参数**:
- `--estimation-window N`: 估计窗口 (默认: 252天)
- `--half-life N`: 指数衰减半衰期 (默认: 90天)

**输出**:
- `/data/barra_risk/risk_params_latest.json` - 风险参数
- `/data/barra_risk/specific_risks.parquet` - 特质风险
- `/data/barra_reports/step4_risk_model.log` - 执行日志

**预计耗时**: 5秒

**成功标准**:
- 协方差矩阵正定 (所有特征值 > 0)
- 特质风险均值在 0.01-0.05 范围内

---

### Step 5: 验证数据

**功能**: 验证数据质量并生成HTML报告

**执行**:
```bash
cd /home/project/ccleana/scripts/barra
python step5_validate.py
```

**输出**:
- `/data/barra_reports/validation_report.html` - 验证报告

**预计耗时**: 30秒

**成功标准**:
- 验证通过 (无严重问题)
- 生成4张可视化图表

---

## 一次性执行 (全部步骤)

```bash
cd /home/project/ccleana/scripts/barra

# 按顺序执行所有步骤
python step1_calculate_factors.py --parallel 4
python step2_transpose_factors.py
python step3_factor_returns.py
python step4_risk_model.py
python step5_validate.py

# 查看验证报告
# 在浏览器中打开: /data/barra_reports/validation_report.html
```

---

## 输出文件说明

### 目录结构

```
/data/barra_factors/
├── by_stock/              # 按股票存储
│   ├── 000001.SZ.parquet
│   ├── 000002.SZ.parquet
│   └── ...
├── by_date/               # 按日期存储
│   ├── 20200101.parquet
│   ├── 20200102.parquet
│   └── ...

/data/barra_risk/
├── factor_returns.parquet    # 因子收益率
├── residuals.parquet         # 残差
├── risk_params_latest.json   # 风险参数 (主要输出)
└── specific_risks.parquet    # 特质风险

/data/barra_config/
└── industry.json             # 行业分类配置

/data/barra_reports/
├── step1_factor_calculation.log
├── step1_results.json
├── step2_transpose.log
├── step2_results.json
├── step3_factor_returns.log
├── step3_results.json
├── step4_risk_model.log
├── step4_results.json
├── step5_validation.log
├── step5_results.json
└── validation_report.html   # 验证报告
```

### 数据格式

#### 因子文件 (by_stock/{ts_code}.parquet)

| 列名 | 类型 | 说明 |
|------|------|------|
| trade_date | datetime | 交易日期 |
| size | float | 市值因子 (ln(总市值)) |
| beta | float | Beta因子 (市场风险) |
| momentum | float | 动量因子 |
| volatility | float | 波动率因子 |
| non_linear_size | float | 非线性市值 |
| book_to_price | float | 价值因子 (1/PB) |
| liquidity | float | 流动性因子 |
| earnings_yield | float | 盈利收益率 (1/PE_TTM) |
| growth | float | 成长因子 (简化版: 0.0) |
| leverage | float | 杠杆因子 (简化版: 0.5) |
| ind_* | int | 行业哑变量 (30个) |

#### 风险参数 (risk_params_latest.json)

```json
{
  "estimation_date": "2024-12-31",
  "estimation_window": 252,
  "half_life": 90,
  "num_factors": 40,
  "num_stocks": 5000,
  "factor_covariance": {
    "size": {"size": 0.0001, "beta": 0.00005, ...},
    ...
  },
  "factor_volatility": {
    "size": 0.01,
    "beta": 0.015,
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

## 故障排查

### 问题1: 找不到数据文件

**症状**: `FileNotFoundError: /data/tushare_data/...`

**解决方案**:
```bash
# 检查数据目录
ls /home/project/ccleana/data/tushare_data/

# 检查特定数据类型
ls /home/project/ccleana/data/tushare_data/daily/ | head
ls /home/project/ccleana/data/tushare_data/daily_basic/ | head
```

---

### 问题2: 内存不足

**症状**: `MemoryError` 或 系统卡顿

**解决方案**:
```bash
# 减少并行度
python step1_calculate_factors.py --parallel 2

# 或分批处理
# 修改脚本中的批次大小
```

---

### 问题3: 协方差矩阵非正定

**症状**: 日志显示 "协方差矩阵非正定"

**解决方案**:
```bash
# 脚本会自动调整, 但如果调整失败:
# 增加估计窗口
python step4_risk_model.py --estimation-window 500

# 或减少因子数量 (修改脚本)
```

---

### 问题4: 因子缺失值过多

**症状**: 验证报告显示缺失值比例 > 5%

**解决方案**:
- 检查原始数据是否完整
- 可能某些股票数据缺失严重
- 查看日志中具体哪些因子缺失值多

---

## 后续操作: 运行LEAN回测

完成预处理步骤后，可以运行LEAN回测:

```bash
cd /home/project/ccleana/Leana

# 确保策略文件存在
ls Algorithm.Python/BarraCNE5Algorithm.py

# 运行回测
dotnet run --project Launcher \
    --config config/config-barra-cne5-backtest.json
```

---

## 定期更新

### 每日更新 (收盘后)

```bash
# 只需要更新最新的因子数据
python step1_calculate_factors.py --parallel 4
python step2_transpose_factors.py
```

### 每月更新 (月初)

```bash
# 更新风险模型
python step3_factor_returns.py
python step4_risk_model.py
```

### 自动化 (Cron)

```bash
# 编辑crontab
crontab -e

# 每日17:30更新因子数据
30 17 * * * cd /home/project/ccleana/scripts/barra && /root/miniconda3/envs/quant311/bin/python step1_calculate_factors.py --parallel 4
35 17 * * * cd /home/project/ccleana/scripts/barra && /root/miniconda3/envs/quant311/bin/python step2_transpose_factors.py

# 每月1日02:00更新风险模型
0 2 1 * * cd /home/project/ccleana/scripts/barra && /root/miniconda3/envs/quant311/bin/python step3_factor_returns.py
5 2 1 * * cd /home/project/ccleana/scripts/barra && /root/miniconda3/envs/quant311/bin/python step4_risk_model.py
```

---

## 附录

### A. 因子说明

| 因子 | 计算方法 | 数据来源 |
|------|---------|---------|
| Size | ln(总市值) | daily_basic.total_mv |
| Beta | 252天滚动回归 vs 沪深300 | daily.close, sw_daily |
| Momentum | (P-21 / P-252) - 1 | daily.close |
| Volatility | 收益率标准差(252天) | daily.close |
| Non-linear Size | Size^3 | Size因子 |
| Book-to-Price | 1/PB | daily_basic.pb |
| Liquidity | 加权换手率 | daily_basic.turnover_rate |
| Earnings Yield | 1/PE_TTM | daily_basic.pe_ttm |
| Growth | 固定值 0.0 (简化) | - |
| Leverage | 固定值 0.5 (简化) | - |

### B. 性能参考

| 环境 | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 | 总计 |
|------|--------|--------|--------|--------|--------|------|
| 4核CPU | 15分钟 | 2分钟 | 10秒 | 5秒 | 30秒 | ~18分钟 |
| 内存占用 | < 2GB | < 1GB | < 500MB | < 200MB | < 1GB | - |

### C. 联系与支持

如有问题, 请查看:
- 执行日志: `/data/barra_reports/step*.log`
- 验证报告: `/data/barra_reports/validation_report.html`

---

**文档结束**
