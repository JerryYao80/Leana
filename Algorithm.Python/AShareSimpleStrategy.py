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
import sys
import os

# 动态导入基类（兼容LEAN的模块系统）
try:
    from china.AShareBaseStrategy import AShareBaseStrategy
except ImportError:
    # 如果导入失败，尝试从当前目录导入
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _china_dir = os.path.join(_script_dir, 'china')
    if _china_dir not in sys.path:
        sys.path.insert(0, _china_dir)
    from AShareBaseStrategy import AShareBaseStrategy

### <summary>
### A股简单策略
### 继承自AShareBaseStrategy，自动获得交易信号记录功能
### </summary>
class AShareSimpleStrategy(AShareBaseStrategy):
    """
    A股简单策略示例
    演示A股市场的T+1规则、涨跌停限制、100股交易单位等特性
    """

    def Initialize(self):
        """初始化策略"""
        # 设置回测时��范围
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(1000000)  # 初始资金100万

        # 设置时区为中国时区
        self.SetTimeZone("Asia/Shanghai")

        # 添加A股股票
        # 000001 - 平安银行（深圳交易所）
        # 600000 - 浦发银行（上海交易所）
        self.AddEquity("000001", Resolution.Daily, Market.China)
        self.AddEquity("600000", Resolution.Daily, Market.China)

        # 设置A股费用模型：使用5元固定费用作为交易成本
        for symbol in ["000001", "600000"]:
            self.Securities[symbol].FeeModel = ConstantFeeModel(5)

        # 设置Warmup预热期
        self.SetWarmUp(TimeSpan.FromDays(30))

        # 设置Benchmark
        self.SetBenchmark("000001")

        # 初始化交易信号记录器（继承自AShareBaseStrategy）
        self._init_signal_recorder()

        # 输出策略信息
        self.Log(f"策略初始化完成 - 初始资金: 1000000")

    def OnData(self, data):
        """
        数据更新事件处理
        当有新数据到达时调用
        """
        # 预热期内不交易
        if self.IsWarmingUp:
            return

        # 只在交易日执行
        if not self.Time.day == self.UtcTime.day:
            return

        # 检查是否有数据
        if "000001" not in data or "600000" not in data:
            return

        # 获取当前价格
        price_000001 = data["000001"].Price
        price_600000 = data["600000"].Price

        # 标记是否有交易信号
        has_signal = False

        # 检查是否已投资
        if not self.Portfolio.Invested:
            # 第一次买入 - 买入100股（A股最小交易单位）
            # 使用基类提供的信号记录方法
            self._record_trading_signal("000001", "买入", 100, price_000001)
            self.MarketOrder("000001", 100)

            self._record_trading_signal("600000", "买入", 100, price_600000)
            self.MarketOrder("600000", 100)

            has_signal = True

        else:
            # 检查持仓
            holdings_000001 = self.Portfolio["000001"]
            holdings_600000 = self.Portfolio["600000"]

            # 简单的均值回归策略 - 000001
            if holdings_000001.Invested:
                # 如果涨幅超过3%，止盈卖出
                if holdings_000001.UnrealizedProfitPercent > 0.03:
                    self._record_trading_signal("000001", "卖出", 100, price_000001)
                    self.MarketOrder("000001", -100)
                    has_signal = True

                # 如果跌幅超过3%，补仓
                elif holdings_000001.UnrealizedProfitPercent < -0.03:
                    self._record_trading_signal("000001", "买入", 100, price_000001)
                    self.MarketOrder("000001", 100)
                    has_signal = True

            # 600000同样逻辑
            if holdings_600000.Invested:
                if holdings_600000.UnrealizedProfitPercent > 0.03:
                    self._record_trading_signal("600000", "卖出", 100, price_600000)
                    self.MarketOrder("600000", -100)
                    has_signal = True

                elif holdings_600000.UnrealizedProfitPercent < -0.03:
                    self._record_trading_signal("600000", "买入", 100, price_600000)
                    self.MarketOrder("600000", 100)
                    has_signal = True

        # 如果没有交易信号，输出资产明细
        if not has_signal:
            self._log_no_signal_and_portfolio(price_000001, price_600000)

    def _log_no_signal_and_portfolio(self, price_000001, price_600000):
        """输出无交易信号和资产明细"""
        # 输出无交易信号提示
        self.Log("=" * 60)
        self.Log("【无交易信号】市场条件不符合交易策略")
        self.Log("=" * 60)

        # 输出资产明细
        total_portfolio_value = self.Portfolio.TotalPortfolioValue
        total_cash = self.Portfolio.Cash
        total_holdings_value = total_portfolio_value - total_cash

        self.Log(f"【资产明细】总资产: {total_portfolio_value:.2f} CNY")
        self.Log(f"  - 可用资金: {total_cash:.2f} CNY")
        self.Log(f"  - 持仓市值: {total_holdings_value:.2f} CNY")
        self.Log(f"  - 总盈亏: {self.Portfolio.TotalPortfolioValue - self.Portfolio.TotalCashBookValue:.2f} CNY")

        # 输出各股票持仓情况
        for symbol in ["000001", "600000"]:
            holding = self.Portfolio[symbol]
            if holding.Invested:
                self.Log(f"  - {symbol}: 持仓 {holding.Quantity} 股, "
                        f"成本价 {holding.AveragePrice:.2f}, "
                        f"现价 {holding.Price:.2f}, "
                        f"盈亏 {holding.UnrealizedProfitPercent*100:.2f}%")
            else:
                self.Log(f"  - {symbol}: 无持仓")

        # 输出当前市场价格
        self.Log(f"【市场价格】000001: {price_000001:.2f}, 600000: {price_600000:.2f}")
        self.Log("=" * 60)

    def OnOrderEvent(self, orderEvent):
        """
        订单事件处理
        """
        if orderEvent.Status == OrderStatus.Filled:
            self.Log(f"订单成交: {orderEvent.Symbol} " +
                    f"数量: {int(orderEvent.FillQuantity)} " +
                    f"价格: {orderEvent.FillPrice:.2f} " +
                    f"费用: {orderEvent.OrderFee.Value.Amount:.2f}")

        elif orderEvent.Status == OrderStatus.Invalid:
            self.Log(f"订单被拒绝: {orderEvent.Symbol} - {orderEvent.Message}")

        elif orderEvent.Status == OrderStatus.Canceled:
            self.Log(f"订单取消: {orderEvent.Symbol}")
