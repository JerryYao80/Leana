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
using QuantConnect.Data;
using QuantConnect.Data.Market;
using QuantConnect.Logging;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Securities;
using QuantConnect.Securities.Equity;

namespace QuantConnect.Orders.Fills
{
    /// <summary>
    /// A股成交模型 - 实现涨跌停检查
    /// </summary>
    public class AShareFillModel : EquityFillModel
    {
        /// <summary>
        /// 模拟订单成交（核心方法）
        /// </summary>
        public override Fill Fill(FillModelParameters parameters)
        {
            var security = parameters.Security;
            var order = parameters.Order;

            // 获取当前价格（昨收价作为参考）
            var lastPrice = security.Price;
            if (lastPrice <= 0)
            {
                // 如果没有价格数据，无法成交
                var utcTime = security.LocalTime.ConvertToUtc(security.Exchange.TimeZone);
                var orderEvent = new OrderEvent(order, utcTime, OrderFee.Zero, "没有价格数据")
                {
                    Status = OrderStatus.Invalid
                };
                return new Fill(orderEvent);
            }

            // 检查涨跌停限制
            if (!IsPriceWithinLimit(order, security, lastPrice))
            {
                var limit = security.GetPriceLimit();
                var upperLimit = lastPrice * (1 + limit);
                var lowerLimit = lastPrice * (1 - limit);
                var message = $"价格超出涨跌停范围。当前价格: {lastPrice:CNY}, " +
                             $"涨停价: {upperLimit:CNY}, 跌停价: {lowerLimit:CNY}, " +
                             $"订单价格: {order.Price:CNY}";

                Log.Trace($"AShareFillModel.Fill: {order.Symbol} {message}");

                var utcTime = security.LocalTime.ConvertToUtc(security.Exchange.TimeZone);
                var orderEvent = new OrderEvent(order, utcTime, OrderFee.Zero, message)
                {
                    Status = OrderStatus.Invalid
                };
                return new Fill(orderEvent);
            }

            // 通过涨跌停检查，使用基类成交逻辑
            return base.Fill(parameters);
        }

        /// <summary>
        /// 检查订单价格是否在涨跌停范围内
        /// </summary>
        private bool IsPriceWithinLimit(Order order, Security security, decimal referencePrice)
        {
            // 使用扩展方法获取涨跌停限制
            var limit = security.GetPriceLimit();
            var upperLimit = referencePrice * (1 + limit);
            var lowerLimit = referencePrice * (1 - limit);

            var orderPrice = order.Price;

            // 检查订单价格是否在范围内
            return orderPrice >= lowerLimit && orderPrice <= upperLimit;
        }

        /// <summary>
        /// 检查价格是否在涨跌停范围内（公开方法，供其他模块调用）
        /// </summary>
        public static bool IsPriceWithinLimit(Security security, decimal price, decimal referencePrice)
        {
            // 使用扩展方法检查
            return security.IsPriceWithinLimit(price, referencePrice);
        }

        /// <summary>
        /// 获取涨停价
        /// </summary>
        public static decimal GetUpperLimitPrice(Security security, decimal referencePrice)
        {
            // 使用扩展方法获取
            return security.GetUpperLimitPrice(referencePrice);
        }

        /// <summary>
        /// 获取跌停价
        /// </summary>
        public static decimal GetLowerLimitPrice(Security security, decimal referencePrice)
        {
            // 使用扩展方法获取
            return security.GetLowerLimitPrice(referencePrice);
        }

        /// <summary>
        /// 检查订单数量是否为100股的整数倍（公开方法，供外部调用）
        /// </summary>
        public bool IsValidLotSize(Security security, decimal quantity)
        {
            const int LOT_SIZE = 100; // A股最小交易单位

            // 检查是否为100股的整数倍
            var absoluteQuantity = Math.Abs(quantity);
            if (absoluteQuantity % LOT_SIZE != 0)
            {
                Log.Error($"AShareFillModel.IsValidLotSize: {security.Symbol} 订单数量 {quantity} 不是100股的整数倍");
                return false;
            }

            return true;
        }
    }
}
