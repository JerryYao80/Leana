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
using NUnit.Framework;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Securities;

namespace QuantConnect.Tests.Common.Orders.Fees
{
    /// <summary>
    /// A股费用模型单元测试
    /// </summary>
    [TestFixture]
    public class AShareFeeModelTests
    {
        /// <summary>
        /// 测试买入佣金计算 - 低于最低佣金时使用最低佣金
        /// </summary>
        [Test]
        public void GetOrderFee_BuySmallAmount_ReturnsMinCommission()
        {
            // Arrange
            var feeModel = new AShareFeeModel();
            var symbol = Symbol.Create("000001", SecurityType.Equity, Market.China);
            var security = new Security(
                SecurityExchangeHours.AlwaysOpen(DateTimeZone.Utc),
                new CashBook(),
                new SymbolProperties(SymbolProperties.GetDefault("USD")),
                ErrorCurrencyConverter.Instance
            );
            var order = new MarketOrder(symbol, 100, DateTime.UtcNow);
            order.Price = 10m; // 100股 @ 10元 = 1000元

            var parameters = new OrderFeeParameters(security, order);

            // Act
            var fee = feeModel.GetOrderFee(parameters);

            // Assert
            // 佣金 = 1000 * 0.0003 = 0.3元，低于最低5元，所以使用5元
            Assert.AreEqual(5m, fee.Value.Amount);
            Assert.AreEqual(Currencies.CNY, fee.Value.Currency);
        }

        /// <summary>
        /// 测试买入佣金计算 - 高于最低佣金时按实际计算
        /// </summary>
        [Test]
        public void GetOrderFee_BuyLargeAmount_ReturnsActualCommission()
        {
            // Arrange
            var feeModel = new AShareFeeModel();
            var symbol = Symbol.Create("000001", SecurityType.Equity, Market.China);
            var security = new Security(
                SecurityExchangeHours.AlwaysOpen(DateTimeZone.Utc),
                new CashBook(),
                new SymbolProperties(SymbolProperties.GetDefault("USD")),
                ErrorCurrencyConverter.Instance
            );
            var order = new MarketOrder(symbol, 10000, DateTime.UtcNow);
            order.Price = 10m; // 10000股 @ 10元 = 100000元

            var parameters = new OrderFeeParameters(security, order);

            // Act
            var fee = feeModel.GetOrderFee(parameters);

            // Assert
            // 佣金 = 100000 * 0.0003 = 30元
            Assert.AreEqual(30m, fee.Value.Amount);
        }

        /// <summary>
        /// 测试卖出费用 - 包含印花税
        /// </summary>
        [Test]
        public void GetOrderFee_SellLargeAmount_IncludesStampDuty()
        {
            // Arrange
            var feeModel = new AShareFeeModel();
            var symbol = Symbol.Create("000001", SecurityType.Equity, Market.China);
            var security = new Security(
                SecurityExchangeHours.AlwaysOpen(DateTimeZone.Utc),
                new CashBook(),
                new SymbolProperties(SymbolProperties.GetDefault("USD")),
                ErrorCurrencyConverter.Instance
            );
            var order = new MarketOrder(symbol, -10000, DateTime.UtcNow); // 卖出
            order.Price = 10m; // 10000股 @ 10元 = 100000元

            var parameters = new OrderFeeParameters(security, order);

            // Act
            var fee = feeModel.GetOrderFee(parameters);

            // Assert
            // 佣金 = 100000 * 0.0003 = 30元
            // 印花税 = 100000 * 0.001 = 100元
            // 总计 = 130元
            Assert.AreEqual(130m, fee.Value.Amount);
        }

        /// <summary>
        /// 测试上海交易所过户费
        /// </summary>
        [Test]
        public void GetOrderFee_ShanghaiExchange_IncludesTransferFee()
        {
            // Arrange
            var feeModel = new AShareFeeModel();
            var symbol = Symbol.Create("600000", SecurityType.Equity, Market.China); // 上海交易所股票
            var security = new Security(
                SecurityExchangeHours.AlwaysOpen(DateTimeZone.Utc),
                new CashBook(),
                new SymbolProperties(SymbolProperties.GetDefault("USD")),
                ErrorCurrencyConverter.Instance
            );
            var order = new MarketOrder(symbol, 10000, DateTime.UtcNow);
            order.Price = 10m;

            var parameters = new OrderFeeParameters(security, order);

            // Act
            var fee = feeModel.GetOrderFee(parameters);

            // Assert
            // 佣金 = 100000 * 0.0003 = 30元
            // 过户费 = 100000 * 0.00002 = 2元
            // 总计 = 32元
            Assert.AreEqual(32m, fee.Value.Amount);
        }

        /// <summary>
        /// 测试深圳交易所不收取过户费
        /// </summary>
        [Test]
        public void GetOrderFee_ShenzhenExchange_NoTransferFee()
        {
            // Arrange
            var feeModel = new AShareFeeModel();
            var symbol = Symbol.Create("000001", SecurityType.Equity, Market.China); // 深圳交易所股票
            var security = new Security(
                SecurityExchangeHours.AlwaysOpen(DateTimeZone.Utc),
                new CashBook(),
                new SymbolProperties(SymbolProperties.GetDefault("USD")),
                ErrorCurrencyConverter.Instance
            );
            var order = new MarketOrder(symbol, 10000, DateTime.UtcNow);
            order.Price = 10m;

            var parameters = new OrderFeeParameters(security, order);

            // Act
            var fee = feeModel.GetOrderFee(parameters);

            // Assert
            // 佣金 = 100000 * 0.0003 = 30元
            // 无过户费（深圳交易所）
            // 总计 = 30元
            Assert.AreEqual(30m, fee.Value.Amount);
        }
    }
}
