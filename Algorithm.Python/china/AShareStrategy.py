# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from AlgorithmImports import *

### <summary>
### A股示例策略
### 演示如何使用LEAN框架进行A股量化交易
### </summary>
class AShareStrategyAlgorithm(QCAlgorithm):

    def Initialize(self):
        '''策略初始化'''
        self.SetStartDate(2024, 1, 1)    # 设置回测开始日期
        self.SetEndDate(2024, 12, 31)      # 设置回测结束日期
        self.SetCash(1000000)              # 设置初始资金：100万人民币

        # 添加A股股票
        # 000001.SZ - 平安银行（深圳）
        # 600000.SH - 浦发银行（上海）
        self.AddEquity("000001", Resolution.Daily)
        self.AddEquity("600000", Resolution.Daily)

        # 设置Benchmark为沪深300
        self.SetBenchmark("000300")

        # 设置A股市场
        self.SetSecurityInitializer(lambda security:
            security.SetMarket(Market.China)
        )

        # 设置WarmUp（预热）期
        self.SetWarmUp(30)

        # 设置交易手续费模型（可选）
        # self.SetSecurityInitializer(lambda security: self.SetFeeModel(ConstantFeeModel(0)))

        # 日志输出
        self.Log(f"A股策略初始化完成 - 起始资金: {self.Portfolio.TotalPortfolioValue}")

    def OnData(self, data):
        '''数据处理'''
        # 只在第一个数据点进行操作
        if not self.Portfolio.Invested:
            # 买入50%仓位的平安银行
            self.SetHoldings("000001", 0.5)
            self.Log(f"买入 000001 @ {data['000001'].Price if '000001' in data else 'N/A'}")

            # 买入30%仓位的浦发银行
            self.SetHoldings("600000", 0.3)
            self.Log(f"买入 600000 @ {data['600000'].Price if '600000' in data else 'N/A'}")

        elif self.Time.day % 30 == 0:  # 每30天重新平衡一次
            # 获取当前持仓
            holdings = self.Portfolio.TotalPortfolioValue

            # 如果持有000001，卖出10%
            if self.Portfolio["000001"].Invested:
                self.SetHoldings("000001", self.Portfolio["000001"].HoldingsValue * 0.9 / holdings)
                self.Log(f"减少000001持仓至90%")

    def OnOrderEvent(self, orderEvent):
        '''订单事件处理'''
        if orderEvent.Status == OrderStatus.Filled:
            self.Log(f"订单成交: {orderEvent.Symbol} - " +
                    f"价格: {orderEvent.FillPrice:.2f}, " +
                    f"数量: {orderEvent.FillQuantity}, " +
                    f"费用: {orderEvent.OrderFee.Value.Amount:.2f} CNY")

        elif orderEvent.Status == OrderStatus.Invalid:
            self.Log(f"订单被拒绝: {orderEvent.Symbol} - {orderEvent.Message}")

    def OnEndOfDay(self):
        '''每日结束时调用'''
        self.Log(f"交易日结束: {self.Time} - " +
                f"组合价值: {self.Portfolio.TotalPortfolioValue:.2f} CNY")
