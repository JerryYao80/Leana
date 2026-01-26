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
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Orders.Slippage;
using QuantConnect.Securities;

namespace QuantConnect.Securities.Equity
{
    /// <summary>
    /// A股证券类扩展方法 - 实现T+1交易规则和涨跌停限制
    /// </summary>
    public static class AShareEquityExtensions
    {
        /// <summary>
        /// 检查证券是否为ST股票（Special Treatment）
        /// ST股票涨跌停限制为5%
        /// </summary>
        public static bool IsSpecialTreatment(this Security security)
        {
            var symbol = security.Symbol.Value;
            return symbol.Contains("ST") || symbol.Contains("st");
        }

        /// <summary>
        /// 检查证券是否为创业板/科创板
        /// 创业板/科创板涨跌停限制为20%
        /// </summary>
        public static bool IsGrowthEnterpriseMarket(this Security security)
        {
            var symbol = security.Symbol.Value;
            // 创业板：300xxx, 301xxx
            // 科创板：688xxx
            return symbol.StartsWith("300") || symbol.StartsWith("301") || symbol.StartsWith("688");
        }

        /// <summary>
        /// 检查是否为新股上市（前5日无涨跌停限制）
        /// </summary>
        public static bool IsNewListing(this Security security, DateTime listingDate, DateTime currentDate)
        {
            var daysSinceListing = (currentDate - listingDate).Days;
            return daysSinceListing < 5;
        }

        /// <summary>
        /// 获取涨跌停限制比例
        /// </summary>
        /// <param name="security">证券</param>
        /// <returns>涨跌停限制比例</returns>
        public static decimal GetPriceLimit(this Security security)
        {
            // 创业板/科创板：20%
            if (security.IsGrowthEnterpriseMarket())
            {
                return 0.20m;
            }

            // ST股票：5%
            if (security.IsSpecialTreatment())
            {
                return 0.05m;
            }

            // 普通股票：10%
            return 0.10m;
        }

        /// <summary>
        /// 检查价格是否在涨跌停范围内
        /// </summary>
        /// <param name="security">证券</param>
        /// <param name="price">待检查的价格</param>
        /// <param name="referencePrice">参考价格（通常是昨收价）</param>
        /// <returns>True if price is within limit, false otherwise</returns>
        public static bool IsPriceWithinLimit(this Security security, decimal price, decimal referencePrice)
        {
            var limit = security.GetPriceLimit();
            var lowerLimit = referencePrice * (1 - limit);
            var upperLimit = referencePrice * (1 + limit);

            return price >= lowerLimit && price <= upperLimit;
        }

        /// <summary>
        /// 获取涨停价
        /// </summary>
        /// <param name="security">证券</param>
        /// <param name="referencePrice">参考价格（昨收价）</param>
        /// <returns>涨停价格</returns>
        public static decimal GetUpperLimitPrice(this Security security, decimal referencePrice)
        {
            var limit = security.GetPriceLimit();
            return referencePrice * (1 + limit);
        }

        /// <summary>
        /// 获取跌停价
        /// </summary>
        /// <param name="security">证券</param>
        /// <param name="referencePrice">参考价格（昨收价）</param>
        /// <returns>跌停价格</returns>
        public static decimal GetLowerLimitPrice(this Security security, decimal referencePrice)
        {
            var limit = security.GetPriceLimit();
            return referencePrice * (1 - limit);
        }

        /// <summary>
        /// 获取股票类型描述
        /// </summary>
        /// <param name="security">证券</param>
        /// <returns>股票类型描述</returns>
        public static string GetStockTypeDescription(this Security security)
        {
            if (security.IsGrowthEnterpriseMarket())
                return "创业板/科创板（20%涨跌停）";
            if (security.IsSpecialTreatment())
                return "ST股票（5%涨跌停）";
            return "普通股票（10%涨跌停）";
        }
    }
}
