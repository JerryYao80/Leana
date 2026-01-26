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

class AShareSimpleStrategy(QCAlgorithm):
    """
    A股简单策略示例
    演示A股市场的T+1规则、涨跌停限制、100股交易单位等特性
    """

    def Initialize(self):
        """初始化策略"""
        # 设置回测时间范围
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(1000000)  # 初始资金100万CNY

        # 添加A股股票
        # 000001.SZ - 平安银行（深圳交易所）
        # 600000.SH - 浦发银行（上海交易所）
        self.AddEquity("000001", Resolution.Daily)
        self.AddEquity("600000", Resolution.Daily)

        # 设置Warmup预热期
        self.SetWarmUp(TimeSpan.FromDays(30))

        # 设置Benchmark
        self.SetBenchmark("000001")

        # 输出策略信息
        self.Log(f"策略初始化完成 - 初始资金: 1000000 CNY")

    def OnData(self, data):
        """
        数据更新事件处理
        当有新数据到达时调用
        """
        # 只在交易日执行
        if not self.Time.day == self.UtcTime.day:
            return

        # 检查是否有数据
        if "000001" not in data or "600000" not in data:
            return

        # 获取当前价格
        price_000001 = data["000001"].Price
        price_600000 = data["600000"].Price

        # 检查是否已投资
        if not self.Portfolio.Invested:
            # 第一次买入 - 买入100股（A股最小交易单位）
            self.Log(f"{self.Time} - 首次买入 000001 @ {price_000001:CNY}, 100股")
            self.MarketOrder("000001", 100)

            self.Log(f"{self.Time} - 首次买入 600000 @ {price_600000:CNY}, 100股")
            self.MarketOrder("600000", 100)

        else:
            # 检查持仓
            holdings_000001 = self.Portfolio["000001"]
            holdings_600000 = self.Portfolio["600000"]

            # T+1规则测试：尝试当天买入后卖出（应该失败）
            if holdings_000001.Invested and holdings_000001.UnrealizedProfitPercent > 0.05:
                # 尝试卖出 - 如果是当天买入的，会被T+1规则拒绝
                self.Log(f"{self.Time} - 尝试卖出 000001 (持仓: {holdings_000001.Quantity}股)")
                self.MarketOrder("000001", -100)

            # 简单的均值回归策略
            if holdings_000001.Invested:
                # 如果涨幅超过10%，考虑卖出（注意涨跌停限制）
                if holdings_000001.UnrealizedProfitPercent > 0.10:
                    self.Log(f"{self.Time} - 涨幅超过10%，考虑卖出 000001")
                    # 注意：涨停时无法卖出
                    if data["000001"].Price < holdings_000001.AveragePrice * 1.10:
                        self.MarketOrder("000001", -100)

                # 如果跌幅超过5%，考虑补仓
                elif holdings_000001.UnrealizedProfitPercent < -0.05:
                    self.Log(f"{self.Time} - 跌幅超过5%，考虑补仓 000001")
                    self.MarketOrder("000001", 100)

    def OnOrderEvent(self, orderEvent):
        """
        订单事件处理
        """
        if orderEvent.Status == OrderStatus.Filled:
            self.Log(f"订单成交: {orderEvent.Symbol} " +
                    f"数量: {orderEvent.FillQuantity} " +
                    f"价格: {orderEvent.FillPrice:CNY} " +
                    f"费用: {orderEvent.OrderFee.Value.Amount:CNY}")

        elif orderEvent.Status == OrderStatus.Invalid:
            self.Log(f"订单被拒绝: {orderEvent.Symbol} - {orderEvent.Message}")

        elif orderEvent.Status == OrderStatus.Canceled:
            self.Log(f"订单取消: {orderEvent.Symbol}")

    def OnEndOfDay(self):
        """
        每日收盘后调用
        """
        # 输出当日持仓情况
        self.Log(f"=== {self.Time} 收盘 ===")
        for symbol, holdings in self.Portfolio.items():
            if holdings.Invested:
                self.Log(f"{symbol} 持仓: {holdings.Quantity}股, " +
                        f"成本: {holdings.AveragePrice:CNY}, " +
                        f"现价: {holdings.Price:CNY}, " +
                        f"盈亏: {holdings.UnrealizedProfitPercent:P2}")

        # 输出账户总览
        self.Log(f"总资产: {self.Portfolio.TotalPortfolioValue:CNY}")
        self.Log(f"可用资金: {self.Portfolio.CashBook[Currencies.CNY].Amount:CNY}")
