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
using QuantConnect.Logging;
using QuantConnect.Orders;
using QuantConnect.Securities;
using QuantConnect.Util;

namespace QuantConnect.Orders.Fees
{
    /// <summary>
    /// A股费用模型
    ///
    /// A股交易费用包括：
    /// 1. 佣金：成交金额的0.03%（万分之三），最低5元
    /// 2. 印花税：成交金额的0.1%��千分之一），仅卖出收取
    /// 3. 过户费：成交金额的0.002%（万分之0.2），仅上海交易所收取
    ///
    /// 费用说明：
    /// - 佣金双向收取（买入和卖出都收）
    /// - 印花税仅卖出收取
    /// - 过户费双向收取（仅上海交易所）
    /// - 深圳交易所不收取过户费
    /// </summary>
    public class AShareFeeModel : FeeModel
    {
        // 费用参数
        /// <summary>
        /// 佣金费率：0.03%（万分之三）
        /// </summary>
        public const decimal CommissionRate = 0.0003m;

        /// <summary>
        /// 最低佣金：5元
        /// </summary>
        public const decimal MinCommission = 5m;

        /// <summary>
        /// 印花税率：0.1%（千分之一）
        /// </summary>
        public const decimal StampDutyRate = 0.001m;

        /// <summary>
        /// 过户费率：0.002%（万分之0.2）
        /// </summary>
        public const decimal TransferFeeRate = 0.00002m;

        // 可配置的费率（用于不同券商的费率调整）
        private readonly decimal _commissionRate;
        private readonly decimal _minCommission;
        private readonly bool _includeStampDuty;
        private readonly bool _includeTransferFee;

        /// <summary>
        /// 使用默认费率构造A股费用模型
        /// </summary>
        public AShareFeeModel()
            : this(CommissionRate, MinCommission, true, true)
        {
        }

        /// <summary>
        /// 使用自定义费率构造A股费用模型
        /// </summary>
        /// <param name="commissionRate">佣金费率</param>
        /// <param name="minCommission">最低佣金</param>
        /// <param name="includeStampDuty">是否包含印花税</param>
        /// <param name="includeTransferFee">是否包含过户费</param>
        public AShareFeeModel(
            decimal commissionRate,
            decimal minCommission,
            bool includeStampDuty = true,
            bool includeTransferFee = true)
        {
            _commissionRate = commissionRate;
            _minCommission = minCommission;
            _includeStampDuty = includeStampDuty;
            _includeTransferFee = includeTransferFee;
        }

        /// <summary>
        /// 获取订单费用
        /// </summary>
        /// <param name="parameters">订单费用参数</param>
        /// <returns>订单费用</returns>
        public override OrderFee GetOrderFee(OrderFeeParameters parameters)
        {
            var order = parameters.Order;
            var security = parameters.Security;

            // 如果订单为null，返回零费用
            if (order == null)
            {
                return OrderFee.Zero;
            }

            // 计算成交金额
            var price = order.Price;
            var quantity = order.AbsoluteQuantity;
            var amount = price * quantity;

            if (amount <= 0)
            {
                return OrderFee.Zero;
            }

            var totalFee = 0m;

            // 1. 计算佣金（双向收取）
            var commission = amount * _commissionRate;
            commission = Math.Max(commission, _minCommission); // 最低5元
            totalFee += commission;

            // 2. 计算印花税（仅卖出收取）
            if (_includeStampDuty && order.Quantity > 0) // 卖出订单Quantity为正值
            {
                var stampDuty = amount * StampDutyRate;
                totalFee += stampDuty;
            }

            // 3. 计算过户费（双向收取，仅上海交易所）
            if (_includeTransferFee && IsShanghaiExchange(security))
            {
                var transferFee = amount * TransferFeeRate;
                totalFee += transferFee;
            }

            // 创建费用对象（使用CNY货币）
            var fee = new OrderFee(new CashAmount(totalFee, Currencies.CNY));

            // 记录费用明细（用于调试）
            LogFeeDetails(order, commission, _includeStampDuty && order.Quantity > 0, _includeTransferFee && IsShanghaiExchange(security), totalFee);

            return fee;
        }

        /// <summary>
        /// 判断是否为上海交易所
        /// </summary>
        /// <param name="security">证券</param>
        /// <returns>True if Shanghai exchange, false otherwise</returns>
        private bool IsShanghaiExchange(Security security)
        {
            var symbol = security.Symbol.Value;

            // 上海交易所股票代码以6开头（60xxxx, 688xxx等）
            if (symbol.StartsWith("6"))
            {
                return true;
            }

            // 也可以通过市场判断
            if (security.Symbol.ID.Market == Market.China)
            {
                // 如果Symbol包含市场信息，可以进一步判断
                // 暂时使用股票代码判断
            }

            return false;
        }

        /// <summary>
        /// 记录费用明细
        /// </summary>
        private void LogFeeDetails(Order order, decimal commission, bool hasStampDuty, bool hasTransferFee, decimal totalFee)
        {
            var message = $"AShareFeeModel: {order.Symbol} {order.Direction} " +
                         $"{order.AbsoluteQuantity}股 @ {order.Price:CNY} - " +
                         $"佣金: {commission:CNY}";

            if (hasStampDuty)
            {
                var stampDuty = order.Price * order.AbsoluteQuantity * StampDutyRate;
                message += $", 印花税: {stampDuty:CNY}";
            }

            if (hasTransferFee)
            {
                var transferFee = order.Price * order.AbsoluteQuantity * TransferFeeRate;
                message += $", 过户费: {transferFee:CNY}";
            }

            message += $", 总费用: {totalFee:CNY}";

            Log.Trace(message);
        }

        /// <summary>
        /// 计算佣金
        /// </summary>
        /// <param name="amount">成交金额</param>
        /// <returns>佣金费用</returns>
        public decimal CalculateCommission(decimal amount)
        {
            var commission = amount * _commissionRate;
            return Math.Max(commission, _minCommission);
        }

        /// <summary>
        /// 计算印花税
        /// </summary>
        /// <param name="amount">成交金额</param>
        /// <returns>印花税费用</returns>
        public decimal CalculateStampDuty(decimal amount)
        {
            return amount * StampDutyRate;
        }

        /// <summary>
        /// 计算过户费
        /// </summary>
        /// <param name="amount">成交金额</param>
        /// <returns>过户费</returns>
        public decimal CalculateTransferFee(decimal amount)
        {
            return amount * TransferFeeRate;
        }

        /// <summary>
        /// 计算总费用
        /// </summary>
        /// <param name="amount">成交金额</param>
        /// <param name="isSell">是否为卖出</param>
        /// <param name="isShanghai">是否为上海交易所</param>
        /// <returns>总费用</returns>
        public decimal CalculateTotalFee(decimal amount, bool isSell, bool isShanghai)
        {
            var totalFee = 0m;

            // 佣金
            totalFee += CalculateCommission(amount);

            // 印花税（仅卖出）
            if (isSell && _includeStampDuty)
            {
                totalFee += CalculateStampDuty(amount);
            }

            // 过户费（仅上海交易所）
            if (isShanghai && _includeTransferFee)
            {
                totalFee += CalculateTransferFee(amount);
            }

            return totalFee;
        }

        /// <summary>
        /// 获取费用模型名称
        /// </summary>
        public override string ToString()
        {
            return $"AShareFeeModel(佣金率:{_commissionRate:P2}, 最低佣金:{_minCommission:CNY}, " +
                   $"印花税:{(_includeStampDuty ? StampDutyRate.ToString("P2") : "无")}, " +
                   $"过户费:{(_includeTransferFee ? TransferFeeRate.ToString("P4") : "无")})";
        }
    }
}
