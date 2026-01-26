# LEAN A股量化框架 - 快速开始指南

## 🚀 5分钟快速开始

### 1. 环境准备

```bash
# 激活Python环境
source /root/miniconda3/envs/quant311/bin/activate

# 安装依赖
pip install akshare pandas numpy
```

### 2. 运行示例策略

```bash
cd /home/project/ccleana/Leana/Launcher
dotnet run --project QuantConnect.Lean.Launcher.csproj \
  --config ../config-a-share-test.json
```

### 3. 查看结果

运行完成后，查看输出日志和统计结果。

## 📝 编写你的第一个A股策略

创建文件 `/home/project/ccleana/Algorithm.Python/MyStrategy.py`:

```python
from AlgorithmImports import *

class MyAShareStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(1000000)  # 100万CNY
        
        # 添加A股
        self.AddEquity("000001", Resolution.Daily)
        self.SetBenchmark("000001")
    
    def OnData(self, data):
        # 你的交易逻辑
        if not self.Portfolio.Invested:
            self.MarketOrder("000001", 100)  # 买入100股
```

## 🎯 A股特殊规则

| 规则 | 说明 |
|------|------|
| **T+1** | 当天买入次日才能卖 |
| **涨跌停** | ±10% (普通), ±5% (ST), ±20% (科创/创业) |
| **交易单位** | 100股整数倍 |
| **费用** | 佣金0.03%(最低5元) + 印花税0.1%(卖出) + 过户费0.002%(上海) |

## 📚 更多文档

- 完整总结: `/home/project/ccleana/misc/final-completion-summary.md`
- 集成测试: `/home/project/ccleana/misc/integration-test-preparation.md`
- 编译修复: `/home/project/ccleana/misc/compilation-fixes-summary.md`

## ✨ 关键特性

✅ 支持回测和实盘Paper模式
✅ T+1交易规则自动执行
✅ 涨跌停自动检查
✅ 费用精确计算
✅ 100股单位验证
✅ 详细日志输出

**就绪可用！** 🎉
