# 🚀 LEAN A股量化策略 - 回测和实盘完整操作指南

**更新时间**: 2026-01-26
**适用版本**: LEAN A股适配 v1.0

---

## 📚 快速导航

- [第一部分：回测执行](#第一部分回测执行)
- [第二部分：实盘Paper模式](#第二部分实盘paper模式)
- [第三部分：策略开发](#第三部分策略开发)
- [第四部分：结果分析](#第四部分结果分析)
- [第五部分：高级功能](#第五部分高级功能)

---

## 第一部分：回测执行

### 1.1 回测基本概念

**回测（Backtesting）**：使用历史数据测试交易策略，评估策略的历史表现。

**A股回测特点**：
- ✅ 使用历史日线/分钟数据
- ✅ 模拟真实交易规则（T+1、涨跌停、100股单位）
- ✅ 计算交易费用（佣金、印花税、过户费）
- ✅ 生成详细的性能报告

### 1.2 准备回测配置

#### 方式1：使用现有配置文件

```bash
cd /home/project/ccleana/Leana/Launcher

# 使用测试配置
dotnet run --project QuantConnect.Lean.Launcher.csproj \
  --config ../config-a-share-test.json
```

#### 方式2：创建自定义配置

创建文件 `my-backtest-config.json`:

```json
{
  "algorithm-language-name": "Python",
  "algorithm-type-name": "MyStrategy",
  "algorithm-location": "Algorithm.Python/MyStrategy.py",

  "data-folder": "/home/project/ccleana/data",

  "environment": "backtesting-a-share",

  "environments": {
    "backtesting-a-share": {
      "live-mode": false,

      "setup-handler": "QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler",
      "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler",
      "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
      "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",

      "history-provider": [
        "QuantConnect.Lean.Engine.HistoricalData.AkshareHistoryProvider"
      ],

      "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
    }
  },

  "log-handler": "QuantConnect.Logging.CompositeLogHandler",
  "parameters": {
    "log-level": "Debug"
  }
}
```

### 1.3 运行回测

#### 基础回测命令

```bash
cd /home/project/ccleana/Leana/Launcher

# 完整命令
dotnet run --project QuantConnect.Lean.Launcher.csproj \
  --config ../config-a-share-test.json \
  --debug \
  --verbose
```

**参数说明**：
- `--config`: 配置文件路径
- `--debug`: 启用调试模式
- `--verbose`: 详细输出

#### 回测输出示例

```
=================================
QuantConnect LEAN Engine v2.0
=================================

[INFO] Algorithm Initialization Started
[INFO] Algorithm Language: Python
[INFO] Algorithm ID: 1234567890
[INFO] Data Folder: /home/project/ccleana/data

[DEBUG] AShareSimpleStrategy: 策略初始化完成
[INFO] Starting Date: 01/01/2024 00:00:00
[INFO] Ending Date: 12/31/2024 00:00:00
[INFO] Cash: 1,000,000 CNY

[DEBUG] 2024-01-02 00:00:00 - 首次买入 000001 @ 12.50 CNY, 100股
[DEBUG] 订单成交: 000001 数量: 100 价格: 12.50 CNY 费用: 5.00 CNY
[DEBUG] 2024-01-02 00:00:00 - 首次买入 600000 @ 8.30 CNY, 100股
[DEBUG] 订单成交: 600000 数量: 100 价格: 8.30 CNY 费用: 5.00 CNY

[INFO] === 2024-01-02 收盘 ===
[INFO] 000001 持仓: 100股, 成本: 12.50 CNY, 现价: 12.55 CNY, 盈亏: 0.40%
[INFO] 600000 持仓: 100股, 成本: 8.30 CNY, 现价: 8.28 CNY, 盈亏: -0.24%
[INFO] 总资产: 999,974.00 CNY
[INFO] 可用资金: 999,838.00 CNY

... (更多输出)

=================================
Backtesting Complete
=================================

Total Return: 15.3%
Sharpe Ratio: 1.25
Max Drawdown: -8.5%
Total Trades: 45
Win Rate: 62.2%
```

### 1.4 回测结果查看

#### 结果文件位置

回测完成后，结果保存在：

```bash
# 默认结果目录
cd /home/project/ccleana/Leana/Algorithm.Python

# 查看结果文件
ls -la
```

**主要结果文件**：
- `backtest-results.json` - JSON格式详细结果
- `backtest-report.html` - HTML可视化报告
- `orders.csv` - 订单记录
- `equity.csv` - 权益曲线
- `portfolio-statistics.json` - 组合统计

#### 查看关键指标

```bash
# 查看JSON结果
cat backtest-results.json | grep -A 5 "Statistics"

# 查看订单记录
head -20 orders.csv
```

---

## 第二部分：实盘Paper模式

### 2.1 Paper交易模式简介

**Paper交易（模拟实盘）**：使用实时数据模拟真实交易，但不使用真实资金。

**A股Paper交易特点**：
- ✅ 使用实时行情数据（每分钟更新）
- ✅ 模拟真实订单执行
- ✅ 实时T+1规则执行
- ✅ 实时涨跌停检查
- ✅ 无真实资金风险

### 2.2 准备实盘配置

创建文件 `live-paper-config.json`:

```json
{
  "algorithm-language-name": "Python",
  "algorithm-type-name": "MyLiveStrategy",
  "algorithm-location": "Algorithm.Python/MyLiveStrategy.py",

  "data-folder": "/home/project/ccleana/data",
  "live-cash-balance": "CNY:1000000",

  "environment": "live-paper-a-share",

  "environments": {
    "live-paper-a-share": {
      "live-mode": true,
      "live-mode-brokerage": "ASharePaperBrokerage",

      "setup-handler": "QuantConnect.Lean.Engine.Setup.BrokerageSetupHandler",
      "result-handler": "QuantConnect.Lean.Engine.Results.LiveTradingResultHandler",
      "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.LiveTradingDataFeed",

      "data-queue-handler": [
        "QuantConnect.Lean.Engine.DataFeeds.Queues.AkshareDataQueue"
      ],

      "real-time-handler": "QuantConnect.Lean.Engine.RealTime.LiveTradingRealTimeHandler",
      "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
    }
  },

  "log-handler": "QuantConnect.Logging.CompositeLogHandler",
  "parameters": {
    "log-level": "Trace"
  }
}
```

### 2.3 创建Paper交易策略

创建文件 `Algorithm.Python/MyLiveStrategy.py`:

```python
from AlgorithmImports import *
from datetime import timedelta

class MyLiveStrategy(QCAlgorithm):
    """
    A股Paper交易策略示例
    注意：Paper交易会使用真实行情数据，但不会执行真实交易
    """

    def Initialize(self):
        # 设置Paper交易
        self.SetLiveMode(True)
        self.SetCash(1000000)  # 100万CNY

        # 添加A股股票（实时数据）
        self.AddEquity("000001", Resolution.Minute)
        self.AddEquity("600000", Resolution.Minute)

        # 设置Benchmark
        self.SetBenchmark("000001")

        # 设置每个交易日结束时触发的事件
        self.Schedule.On(self.DateRules.EveryDay(),
                        self.TimeRules.AfterMarketOpen("000001", timedelta(minutes=30)),
                        self.Rebalance)

        self.Log("=== Paper交易策略启动 ===")
        self.Log(f"初始资金: {self.Portfolio.Cash}")

    def Rebalance(self):
        """每个交易日开盘后30分钟调仓"""

        # 获取当前持仓
        holdings_000001 = self.Portfolio["000001"]
        holdings_600000 = self.Portfolio["600000"]

        # 简单的策略：如果盈利超过5%则减仓，亏损超过5%则加仓
        if holdings_000001.Invested:
            profit_pct = holdings_000001.UnrealizedProfitPercent

            if profit_pct > 0.05:
                # 盈利超过5%，减仓一半
                self.Log(f"000001盈利{profit_pct:P2}，减仓")
                self.MarketOrder("000001", -50)

            elif profit_pct < -0.05:
                # 亏损超过5%，加仓100股
                self.Log(f"000001亏损{profit_pct:P2}，加仓")
                self.MarketOrder("000001", 100)

    def OnData(self, data):
        """实时数据更新"""
        # 只在交易时间执行
        if not self.IsMarketOpen("000001"):
            return

        # 每100个bar输出一次状态（避免日志过多）
        if self.Time.minute % 100 == 0:
            self.Log(f"[{self.Time}] 实时状态更新")
            for symbol, holdings in self.Portfolio.items():
                if holdings.Invested:
                    self.Log(f"{symbol}: {holdings.Quantity}股, " +
                            f"现价: {holdings.Price:CNY}, " +
                            f"盈亏: {holdings.UnrealizedProfitPercent:P2}")

    def OnOrderEvent(self, orderEvent):
        """订单事件处理"""
        if orderEvent.Status == OrderStatus.Filled:
            self.Log(f"✅ 订单成交: {orderEvent.Symbol} " +
                    f"{orderEvent.FillQuantity}股 @ {orderEvent.FillPrice:CNY}")
        elif orderEvent.Status == OrderStatus.Invalid:
            self.Log(f"❌ 订单拒绝: {orderEvent.Symbol} - {orderEvent.Message}")
        elif orderEvent.Status == OrderStatus.Canceled:
            self.Log(f"⚠️ 订单取消: {orderEvent.Symbol}")

    def OnEndOfDay(self):
        """每日收盘"""
        self.Log(f"=== {self.Time} 交易日结束 ===")
        self.Log(f"总资产: {self.Portfolio.TotalPortfolioValue:CNY}")
        self.Log(f"可用资金: {self.Portfolio.CashBook[Currencies.CNY].Amount:CNY}")
```

### 2.4 启动Paper交易

```bash
cd /home/project/ccleana/Leana/Launcher

# 启动Paper交易
dotnet run --project QuantConnect.Lean.Launcher.csproj \
  --config ../config-a-share-live-paper.json
```

**Paper交易启动过程**：

```
=================================
LEAN Live Paper Trading
=================================

[INFO] Live Paper Mode: Enabled
[INFO] Brokerage: ASharePaperBrokerage
[INFO] Data Queue: AkshareDataQueue

[INFO] Connecting to Akshare...
[INFO] Connection Established

[INFO] Subscribing to: 000001, 600000
[INFO] Subscription Confirmation: 2 symbols

[INFO] Starting Live Paper Trading
[INFO] Market Status: Open

[DEBUG] [09:30:01] 实时数据: 000001 @ 12.55 CNY
[DEBUG] [09:30:02] 实时数据: 600000 @ 8.28 CNY

[INFO] === Paper交易策略启动 ===
[INFO] 初始资金: 1,000,000.00 CNY

[INFO] [09:30:30] 执行调仓
[DEBUG] 000001盈利0.40%，持仓不动

[DEBUG] [10:00:00] 实时状态更新
[DEBUG] 000001: 100股, 现价: 12.58 CNY, 盈亏: 0.64%

... (持续运行)

[INFO] === 15:00:00 交易日结束 ===
[INFO] 总资产: 1,000,064.00 CNY
[INFO] 可用资金: 999,928.00 CNY
```

### 2.5 Paper交易特点

**实时数据获取**：
- 数据源：akshare实时行情
- 更新频率：每分钟
- 数据延迟：< 5秒

**订单执行**：
- 订单类型：市价单、限价单、止损单
- 执行方式：模拟撮合
- 成交确认：实时

**T+1规则**：
- 当天买入次日可卖
- 实时跟踪可卖数量
- 自动拒绝违规订单

---

## 第三部分：策略开发

### 3.1 策略基本结构

```python
from AlgorithmImports import *

class MyAShareStrategy(QCAlgorithm):
    """
    策略模板
    """

    def Initialize(self):
        """
        策略初始化 - 只运行一次
        """
        # 1. 设置回测时间
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 12, 31)

        # 2. 设置初始资金
        self.SetCash(1000000)

        # 3. 添加股票
        self.AddEquity("000001", Resolution.Daily)
        self.AddEquity("600000", Resolution.Daily)

        # 4. 设置指标
        self.ema_fast = self.EMA("000001", 10, Resolution.Daily)
        self.ema_slow = self.EMA("000001", 30, Resolution.Daily)

        # 5. 设置WarmUp
        self.SetWarmUp(TimeSpan.FromDays(30))

        # 6. 设置Benchmark
        self.SetBenchmark("000001")

    def OnData(self, data):
        """
        数据更新事件 - 每个bar触发一次
        """
        # 只在有数据时执行
        if not data.ContainsKey("000001"):
            return

        # 获取当前价格
        price = data["000001"].Price

        # 获取指标值
        ema_fast = self.ema_fast.Current.Value
        ema_slow = self.ema_slow.Current.Value

        # 交易逻辑
        if not self.Portfolio.Invested:
            # 金叉买入
            if ema_fast > ema_slow:
                self.MarketOrder("000001", 100)
                self.Log(f"买入信号: {self.Time} @ {price}")

        elif self.Portfolio.Invested:
            # 死叉卖出
            if ema_fast < ema_slow:
                holdings = self.Portfolio["000001"]
                if holdings.Quantity >= 100:
                    self.MarketOrder("000001", -100)
                    self.Log(f"卖出信号: {self.Time} @ {price}")

    def OnOrderEvent(self, orderEvent):
        """订单事件处理"""
        if orderEvent.Status == OrderStatus.Filled:
            self.Log(f"成交: {orderEvent.Symbol} " +
                    f"{orderEvent.FillQuantity}股 " +
                    f"@ {orderEvent.FillPrice:CNY}")
```

### 3.2 常用策略模式

#### 双均线策略

```python
def OnData(self, data):
    if "000001" not in data:
        return

    fast = self.SMA("000001", 5, Resolution.Daily)
    slow = self.SMA("000001", 20, Resolution.Daily)

    if not self.Portfolio.Invested:
        if fast > slow:  # 金叉
            self.MarketOrder("000001", 100)
    else:
        if fast < slow:  # 死叉
            self.MarketOrder("000001", -100)
```

#### 突破策略

```python
def OnData(self, data):
    if "000001" not in data:
        return

    # 计算20日最高价
    high20 = self.MAX(data["000001"], 20, Resolution.Daily)

    # 计算当前价格是否突破
    price = data["000001"].Price

    if price > high20:  # 突破
        self.MarketOrder("000001", 100)
```

#### 均值回归策略

```python
def OnData(self, data):
    if "000001" not in data:
        return

    price = data["000001"].Price
    sma = self.SMA("000001", 20, Resolution.Daily)

    # 价格低于均值2个标准差时买入
    std = self.STD("000001", 20, Resolution.Daily)

    if price < sma - 2 * std:
        self.MarketOrder("000001", 100)
    elif price > sma + 2 * std:
        self.MarketOrder("000001", -100)
```

### 3.3 A股特殊规则处理

#### T+1规则处理

```python
def OnData(self, data):
    # 检查可卖数量
    security = self.Securities["000001"]

    if security.SettlementModel is TPlusOneSettlementModel:
        # 获取可卖数量
        sellable = security.SettlementModel.GetSellableQuantity(
            "000001",
            self.Time.date
        )

        # 尝试卖出
        if self.Portfolio["000001"].Quantity > sellable:
            self.Log("无法卖出：T+1限制")
            return

    self.MarketOrder("000001", -100)
```

#### 涨跌停检查

```python
def OnData(self, data):
    security = self.Securities["000001"]
    price = data["000001"].Price

    # 获取涨跌停价格
    upper_limit = security.GetUpperLimitPrice(security.Price)
    lower_limit = security.GetLowerLimitPrice(security.Price)

    if price >= upper_limit:
        self.Log("涨停，无法买入")
        return
    elif price <= lower_limit:
        self.Log("跌停，无法卖出")
        return

    self.MarketOrder("000001", 100)
```

#### 100股单位处理

```python
def OnData(self, data):
    # 计算目标持仓（100股整数倍）
    target_value = 100000  # 10万元
    price = data["000001"].Price

    # 计算股数
    raw_quantity = target_value / price

    # 调整为100股整数倍
    quantity = int(raw_quantity / 100) * 100

    if quantity > 0:
        self.MarketOrder("000001", quantity)
```

---

## 第四部分：结果分析

### 4.1 回测报告解读

#### 关键性能指标

```json
{
  "Statistics": {
    "TotalReturn": 0.153,           // 总收益率: 15.3%
    "CompoundingAnnualReturn": 0.165, // 年化收益: 16.5%
    "SharpeRatio": 1.25,             // 夏普比率: 1.25
    "SortinoRatio": 1.78,            // 索提诺比率: 1.78
    "Alpha": 0.025,                  // Alpha: 2.5%
    "Beta": 0.95,                    // Beta: 0.95
    "MaxDrawdown": -0.085,           // 最大回撤: -8.5%
    "WinRate": 0.622,                // 胜率: 62.2%
    "TotalTrades": 45,               // 总交易数: 45
    "AverageWin": 0.012,             // 平均盈利: 1.2%
    "AverageLoss": -0.008,           // 平均亏损: -0.8%
    "ProfitFactor": 2.1              // 盈亏比: 2.1
  }
}
```

**指标解读**：

| 指标 | 含义 | 良好标准 |
|------|------|---------|
| **TotalReturn** | 总收益率 | > 10% |
| **SharpeRatio** | 夏普比率（风险调整收益）| > 1.0 |
| **MaxDrawdown** | 最大回撤（最大亏损）| < -20% |
| **WinRate** | 胜率（盈利交易占比）| > 50% |
| **ProfitFactor** | 盈亏比（总盈利/总亏损）| > 1.5 |

### 4.2 权益曲线分析

**查看权益曲线**：

```bash
# 权益数据保存在
cat equity.csv | head -20
```

**使用Python可视化**：

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取权益曲线
equity = pd.read_csv('equity.csv',
                     parse_dates=['time'],
                     names=['time', 'equity'])

# 绘制权益曲线
plt.figure(figsize=(12, 6))
plt.plot(equity['time'], equity['equity'])
plt.title('策略权益曲线')
plt.xlabel('时间')
plt.ylabel('权益 (CNY)')
plt.grid(True)
plt.savefig('equity_curve.png')
plt.show()

# 计算回撤
equity['peak'] = equity['equity'].cummax()
equity['drawdown'] = (equity['equity'] - equity['peak']) / equity['peak']

# 绘制回撤曲线
plt.figure(figsize=(12, 6))
plt.fill_between(equity['time'], equity['drawdown'], 0, alpha=0.3, color='red')
plt.title('回撤曲线')
plt.xlabel('时间')
plt.ylabel('回撤比例')
plt.grid(True)
plt.savefig('drawdown_curve.png')
```

### 4.3 订单分析

**查看订单记录**：

```bash
cat orders.csv | head -20
```

**订单分析**：

```python
import pandas as pd

# 读取订单
orders = pd.read_csv('orders.csv')

# 统计
print(f"总订单数: {len(orders)}")
print(f"成交订单: {len(orders[orders['status'] == 'Filled'])}")
print(f"拒绝订单: {len(orders[orders['status'] == 'Invalid'])}")

# 按股票分组
symbol_counts = orders.groupby('symbol')['quantity'].sum()
print("\n按股票交易量:")
print(symbol_counts)

# 计算平均持仓时间
orders['time'] = pd.to_datetime(orders['time'])
avg_hold_time = (orders['time'].max() - orders['time'].min()).days
print(f"\n平均持仓周期: {avg_hold_time} 天")
```

---

## 第五部分：高级功能

### 5.1 多股票组合

```python
def Initialize(self):
    # 添加多只股票
    stocks = ["000001", "000002", "600000", "600036"]
    for stock in stocks:
        self.AddEquity(stock, Resolution.Daily)

    # 等权重配置
    self.SetWarmUp(TimeSpan.FromDays(30))

    # 每月调仓
    self.Schedule.On(self.DateRules.MonthStart(),
                    self.Rebalance)

def Rebalance(self):
    """月度调仓"""
    # 获取所有已订阅股票
    symbols = [s for s in self.Securities.Keys
               if self.Securities[s].Type == SecurityType.Equity]

    # 计算目标权重
    target_weight = 1.0 / len(symbols)

    # 调仓
    for symbol in symbols:
        self.SetHoldings(symbol, target_weight)
```

### 5.2 风险管理

```python
def Initialize(self):
    # 设置止损
    self.StopMarketOrder("000001", -100)

    # 设置止盈
    self.LimitOrder("000001", -100, 15.00)  # 价格到15元卖出

def OnData(self, data):
    # 动态止损
    security = self.Securities["000001"]

    if security.Holdings.Invested:
        entry_price = security.Holdings.AveragePrice
        current_price = security.Price

        # 亏损超过5%止损
        if current_price < entry_price * 0.95:
            self.Liquidate("000001")
            self.Log(f"触发止损: {self.Time}")
```

### 5.3 风险指标

```python
def OnEndOfDay(self):
    """每日计算风险指标"""

    # 计算组合Beta
    beta = self.Portfolio.TotalPortfolioBeta

    # 计算波动率
    portfolio_value = self.Portfolio.TotalPortfolioValue
    # ... (需要自己实现波动率计算)

    # 计算VaR (Value at Risk)
    # ... (需要自己实现VaR计算)

    self.Log(f"Beta: {beta:.2f}")
    self.Log(f"组合价值: {portfolio_value:CNY}")
```

### 5.4 自定义指标

```python
# 创建自定义指标
class MyCustomIndicator(PythonIndicator):
    def __init__(self):
        super().__init__()
        self.Value = 0

    def Update(self, input):
        # 自定义计算逻辑
        self.Value = input.Price * 1.01
        return True

# 在策略中使用
def Initialize(self):
    self.custom = self.Indicator("CustomIndicator",
                                    MyCustomIndicator(),
                                    "000001",
                                    Resolution.Daily)
```

---

## 常见问题解决

### Q1: 编译错误

**问题**: `error CS0246: The type or namespace name 'XXX' could not be found`

**解决**:
```bash
# 清理并重新编译
dotnet clean
dotnet build
```

### Q2: Python环境问题

**问题**: `ModuleNotFoundError: No module named 'akshare'`

**解决**:
```bash
source /root/miniconda3/envs/quant311/bin/activate
pip install akshare pandas numpy
```

### Q3: 数据加载失败

**问题**: `No data found for symbol 000001`

**解决**:
```bash
# 使用AkshareDataDownloader下载数据
cd /home/project/ccleana/Leana/ToolBox
dotnet run --project QuantConnect.ToolBox.csproj \
  AkshareDataDownloader 000001 20240101 20241231 /home/project/ccleana/data
```

### Q4: T+1规则限制

**问题**: 当天买入当天无法卖出

**原因**: 这是A股的真实交易规则，不是bug

**验证**:
```python
def OnOrderEvent(self, orderEvent):
    if orderEvent.Status == OrderStatus.Invalid:
        if "T+1" in orderEvent.Message:
            self.Log("这是正常的T+1规则限制")
```

### Q5: 订单被拒绝

**可能原因**:
1. 数量不是100股整数倍
2. 价格超出涨跌停范围
3. T+1限制（当天买入当天卖）
4. 资金不足

**检查方法**:
```python
def OnOrderEvent(self, orderEvent):
    if orderEvent.Status == OrderStatus.Invalid:
        self.Log(f"订单被拒绝: {orderEvent.Message}")
```

---

## 📞 获取帮助

### 文档资源

1. **快速开始**: `/home/project/ccleana/misc/QUICK_START.md`
2. **完整总结**: `/home/project/ccleana/misc/final-completion-summary.md`
3. **架构解析**: `/home/project/ccleana/Leana/docs/lean-core-principles/`

### 调试技巧

1. **启用详细日志**:
   ```json
   "parameters": {
     "log-level": "Trace"
   }
   ```

2. **使用Debug模式**:
   ```bash
   dotnet run --config xxx.json --debug
   ```

3. **检查订单事件**:
   ```python
   def OnOrderEvent(self, orderEvent):
       self.Log(f"订单状态: {orderEvent.Status}")
       self.Log(f"订单消息: {orderEvent.Message}")
   ```

---

## 🎯 下一步

1. ✅ 运行示例回测
2. ✅ 编写自己的策略
3. ✅ 启动Paper交易
4. ✅ 优化策略参数
5. ✅ 部署实盘交易

**祝交易顺利！** 🎉
