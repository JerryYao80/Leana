/*
 * QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
 * Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect Corporation.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
*/

using System;
using System.Collections.Generic;
using System.Linq;
using QuantConnect.Brokerages.Backtesting;
using QuantConnect.Data.Market;
using QuantConnect.Interfaces;
using QuantConnect.Logging;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Securities;
using QuantConnect.Securities.Equity;

namespace QuantConnect.Brokerages.Paper
{
    /// <summary>
    /// A股Paper交易经纪商
    /// 实现T+1交易规则和涨跌停限制
    /// </summary>
    public class ASharePaperBrokerage : BacktestingBrokerage
    {
        /// <summary>
        /// 构造A股Paper经纪商
        /// </summary>
        /// <param name="algorithm">算法实例</param>
        public ASharePaperBrokerage(IAlgorithm algorithm)
            : base(algorithm, "A股Paper经纪商")
        {
            Log.Trace("ASharePaperBrokerage: 已创建");
        }

        /// <summary>
        /// 下单
        /// </summary>
        public override bool PlaceOrder(Order order)
        {
            Log.Trace($"ASharePaperBrokerage.PlaceOrder: 开始处理订单 {order.Id} - {order.Symbol} {order.Direction} {order.AbsoluteQuantity}股 @ {order.Price}");

            // 获取证券
            var security = Algorithm.Securities[order.Symbol];

            // 1. T+1检查：卖出时需要检查是否有可卖数量
            if (order.Quantity < 0) // 卖出订单（Quantity为负值）
            {
                var sellableQuantity = GetSellableQuantity(order.Symbol, Algorithm.UtcTime.Date);

                var quantityToSell = Math.Abs(order.Quantity);

                if (quantityToSell > sellableQuantity)
                {
                    var message = $"T+1限制：可卖数量不足。需要卖出: {quantityToSell}股, 可卖数量: {sellableQuantity}股, 缺口: {quantityToSell - sellableQuantity}股";

                    Log.Trace($"ASharePaperBrokerage.PlaceOrder: {message}");

                    // 触发订单事件
                    OnOrderEvent(new OrderEvent(order, Algorithm.UtcTime, OrderFee.Zero)
                    {
                        Status = OrderStatus.Invalid,
                        Message = message
                    });

                    return false;
                }

                Log.Trace($"ASharePaperBrokerage.PlaceOrder: T+1检查通过，可卖数量: {sellableQuantity}股");
            }

            // 2. 涨跌停检查
            var lastPrice = security.Price;
            if (lastPrice > 0)
            {
                var upperLimit = security.GetUpperLimitPrice(lastPrice);
                var lowerLimit = security.GetLowerLimitPrice(lastPrice);

                // 对于限价单，检查订单价格是否在涨跌停范围内
                if (order is LimitOrder limitOrder)
                {
                    if (limitOrder.LimitPrice > upperLimit || limitOrder.LimitPrice < lowerLimit)
                    {
                        var message = $"价格超出涨跌停范围。订单价格: {limitOrder.LimitPrice:CNY}, " +
                                     $"涨停价: {upperLimit:CNY}, 跌停价: {lowerLimit:CNY}";

                        Log.Trace($"ASharePaperBrokerage.PlaceOrder: {message}");

                        OnOrderEvent(new OrderEvent(order, Algorithm.UtcTime, OrderFee.Zero)
                        {
                            Status = OrderStatus.Invalid,
                            Message = message
                        });

                        return false;
                    }
                }

                // 对于止损单，检查触发价格是否在涨跌停范围内
                if (order is StopMarketOrder stopOrder)
                {
                    if (stopOrder.StopPrice > upperLimit || stopOrder.StopPrice < lowerLimit)
                    {
                        var message = $"止损价格超出涨跌停范围。止损价格: {stopOrder.StopPrice:CNY}, " +
                                     $"涨停价: {upperLimit:CNY}, 跌停价: {lowerLimit:CNY}";

                        Log.Trace($"ASharePaperBrokerage.PlaceOrder: {message}");

                        OnOrderEvent(new OrderEvent(order, Algorithm.UtcTime, OrderFee.Zero)
                        {
                            Status = OrderStatus.Invalid,
                            Message = message
                        });

                        return false;
                    }
                }

                Log.Trace($"ASharePaperBrokerage.PlaceOrder: 涨跌停检查通过");
            }

            // 3. 100股单位检查（已在AShareFillModel中实现，这里仅记录日志）
            var absoluteQuantity = order.AbsoluteQuantity;
            if (absoluteQuantity % AShareBuyingPowerModel.LOT_SIZE != 0)
            {
                Log.Trace($"ASharePaperBrokerage.PlaceOrder: {order.Symbol} 订单数量 {absoluteQuantity} 不是100股的整数倍");
            }

            // 所有检查通过，使用基类下单
            Log.Trace($"ASharePaperBrokerage.PlaceOrder: 所有检查通过，执行下单");
            var result = base.PlaceOrder(order);

            if (result)
            {
                Log.Trace($"ASharePaperBrokerage.PlaceOrder: 订单 {order.Id} 已成功提交");
            }
            else
            {
                Log.Trace($"ASharePaperBrokerage.PlaceOrder: 订单 {order.Id} 提交失败");
            }

            return result;
        }

        /// <summary>
        /// 扫描并处理结算
        /// </summary>
        public override void Scan()
        {
            Log.Trace($"ASharePaperBrokerage.Scan: 开始扫描 {Algorithm.UtcTime:yyyy-MM-dd HH:mm:ss}");

            // 调用基类扫描
            base.Scan();

            // 执行T+1结算扫描
            foreach (var kvp in Algorithm.Portfolio.Securities)
            {
                var security = kvp.Value;

                if (security.SettlementModel is TPlusOneSettlementModel tPlusOne)
                {
                    try
                    {
                        tPlusOne.Scan(new ScanSettlementModelParameters(
                            Algorithm.Portfolio,
                            security,
                            Algorithm.UtcTime
                        ));

                        Log.Trace($"ASharePaperBrokerage.Scan: {security.Symbol} T+1结算扫描完成");
                    }
                    catch (Exception ex)
                    {
                        Log.Error($"ASharePaperBrokerage.Scan: {security.Symbol} T+1结算扫描失败 - {ex.Message}");
                    }
                }
            }

            Log.Trace($"ASharePaperBrokerage.Scan: 扫描完成");
        }

        /// <summary>
        /// 获取指定股票的可卖数量
        /// </summary>
        /// <param name="symbol">股票代码</param>
        /// <param name="currentDate">当前日期</param>
        /// <returns>可卖数量</returns>
        private decimal GetSellableQuantity(Symbol symbol, DateTime currentDate)
        {
            var security = Algorithm.Securities[symbol];

            if (security.SettlementModel is TPlusOneSettlementModel tPlusOne)
            {
                return tPlusOne.GetSellableQuantity(symbol, currentDate);
            }

            // 如果不是T+1结算模型，返回当前持仓数量（可以立即卖出）
            return Math.Abs(security.Holdings.Quantity);
        }

        /// <summary>
        /// 更新订单状态
        /// </summary>
        protected override void OnOrderEvent(OrderEvent orderEvent)
        {
            base.OnOrderEvent(orderEvent);

            // 记录订单事件
            Log.Trace($"ASharePaperBrokerage.OnOrderEvent: 订单 {orderEvent.OrderId} - " +
                      $"状态: {orderEvent.Status}, " +
                      $"价格: {orderEvent.FillPrice:CNY}, " +
                      $"数量: {orderEvent.FillQuantity}");

            // 如果订单成交，且是买入订单，需要记录T+1可卖时间
            if (orderEvent.Status == OrderStatus.Filled)
            {
                // 通过OrderId获取订单
                var order = Algorithm.Transactions.GetOrderById(orderEvent.OrderId);
                if (order != null)
                {
                    var security = Algorithm.Securities[order.Symbol];

                    if (security.SettlementModel is TPlusOneSettlementModel tPlusOne)
                    {
                        if (order.Quantity < 0) // 买入（Quantity为负值）
                        {
                            var settlementDate = Algorithm.UtcTime.Date.AddDays(1);
                            Log.Trace($"ASharePaperBrokerage.OnOrderEvent: {order.Symbol} 买入 {Math.Abs(order.Quantity)}股, 可卖日期: {settlementDate:yyyy-MM-dd}");
                        }
                    }
                }
            }
        }

        /// <summary>
        /// 获取账户现金余额
        /// </summary>
        public override List<CashAmount> GetCashBalance()
        {
            var cashBalance = base.GetCashBalance();

            // 添加未结算资金信息（用于调试）
            if (Algorithm.Portfolio.CashBook.ContainsKey(Currencies.CNY))
            {
                var cash = Algorithm.Portfolio.CashBook[Currencies.CNY];
                Log.Trace($"ASharePaperBrokerage.GetCashBalance: " +
                          $"可用资金: {cash.Amount:CNY}, " +
                          $" Currency: {Currencies.CNY}");
            }

            return cashBalance;
        }

        /// <summary>
        /// 获取账户持仓
        /// </summary>
        public override List<Holding> GetAccountHoldings()
        {
            var holdings = base.GetAccountHoldings();

            // 添加T+1可卖数量信息（用于调试）
            foreach (var holding in holdings)
            {
                var symbol = holding.Symbol;
                var security = Algorithm.Securities[symbol];

                if (security.SettlementModel is TPlusOneSettlementModel tPlusOne)
                {
                    var sellableQuantity = tPlusOne.GetSellableQuantity(symbol, Algorithm.UtcTime.Date);
                    var totalQuantity = Math.Abs(security.Holdings.Quantity);

                    Log.Trace($"ASharePaperBrokerage.GetAccountHoldings: {symbol} - " +
                              $"总持仓: {totalQuantity}股, 可卖: {sellableQuantity}股, 冻结: {totalQuantity - sellableQuantity}股");
                }
            }

            return holdings;
        }
    }
}
