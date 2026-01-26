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
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Securities;
using QuantConnect.Util;

namespace QuantConnect.Securities
{
    /// <summary>
    /// A股购买力模型 - 考虑100股交易单位和T+1规则
    /// </summary>
    public class AShareBuyingPowerModel : CashBuyingPowerModel
    {
        /// <summary>
        /// A股最小交易单位（1手 = 100股）
        /// </summary>
        public const int LOT_SIZE = 100;

        /// <summary>
        /// 检查是否有足够的购买力执行订单
        /// </summary>
        public override HasSufficientBuyingPowerForOrderResult HasSufficientBuyingPowerForOrder(
            HasSufficientBuyingPowerForOrderParameters parameters)
        {
            var order = parameters.Order;
            var security = parameters.Security;
            var portfolio = parameters.Portfolio;

            // 检查订单数量是否为100股的整数倍
            var absoluteQuantity = order.AbsoluteQuantity;
            if (absoluteQuantity % LOT_SIZE != 0)
            {
                return new HasSufficientBuyingPowerForOrderResult(
                    false,
                    $"A股订单数量必须是{LOT_SIZE}股的整数倍。当前数量: {absoluteQuantity}, " +
                    $"余数: {absoluteQuantity % LOT_SIZE}"
                );
            }

            // 计算需要的资金（考虑费用）
            var requiredAmount = absoluteQuantity * order.Price;

            // 获取订单费用
            var fee = security.FeeModel.GetOrderFee(
                new OrderFeeParameters(security, order));

            requiredAmount += fee.Value.Amount;

            // 检查资金是否足够
            var availableCash = portfolio.CashBook[Currencies.CNY].Amount;

            if (requiredAmount > availableCash)
            {
                return new HasSufficientBuyingPowerForOrderResult(
                    false,
                    $"资金不足。需要: {requiredAmount:CNY} (含费用), 可用: {availableCash:CNY}, " +
                    $"缺口: {requiredAmount - availableCash:CNY}"
                );
            }

            // T+1检查：卖出时需要检查是否有可卖数量
            if (order.Quantity < 0) // 卖出订单
            {
                // 检查是否是T+1结算模型
                if (security.SettlementModel is TPlusOneSettlementModel tPlusOne)
                {
                    // 从Portfolio获取当前时间
                    var currentTime = security.LocalTime;

                    var sellableQuantity = tPlusOne.GetSellableQuantity(
                        order.Symbol,
                        currentTime.Date);

                    if (Math.Abs(order.Quantity) > sellableQuantity)
                    {
                        return new HasSufficientBuyingPowerForOrderResult(
                            false,
                            $"T+1限制：可卖数量不足。需要卖出: {Math.Abs(order.Quantity)}, " +
                            $"可卖数量: {sellableQuantity}, " +
                            $"缺口: {Math.Abs(order.Quantity) - sellableQuantity}"
                        );
                    }
                }
            }

            // 所有检查通过，使用基类实现
            return base.HasSufficientBuyingPowerForOrder(parameters);
        }

        /// <summary>
        /// 调整订单数量到100股的整数倍
        /// </summary>
        public static decimal AdjustToLotSize(decimal quantity)
        {
            return Math.Floor(quantity / LOT_SIZE) * LOT_SIZE;
        }

        /// <summary>
        /// 检查数量是否为100股的整数倍
        /// </summary>
        public static bool IsValidLotSize(decimal quantity)
        {
            return quantity % LOT_SIZE == 0;
        }

        /// <summary>
        /// 计算购买指定数量股票需要的总金额（含费用）
        /// </summary>
        public static decimal GetTotalAmountIncludingFee(Security security, decimal quantity, decimal price)
        {
            var amount = quantity * price;

            // 获取费用
            var fee = security.FeeModel.GetOrderFee(
                new OrderFeeParameters(security, null));

            return amount + fee.Value.Amount;
        }

        /// <summary>
        /// 根据可用资金计算可购买的最大数量（100股整数倍）
        /// </summary>
        public static decimal GetMaxAffordableQuantity(decimal availableCash, decimal price, Security security)
        {
            // 估算费用（使用最低佣金5元）
            var estimatedFee = 5m;

            // 可用于购买股票的资金
            var fundsForStock = availableCash - estimatedFee;

            if (fundsForStock <= 0)
            {
                return 0;
            }

            // 计算可购买的数量
            var quantity = fundsForStock / price;

            // 调整为100股的整数倍
            return Math.Floor(quantity / LOT_SIZE) * LOT_SIZE;
        }
    }
}
