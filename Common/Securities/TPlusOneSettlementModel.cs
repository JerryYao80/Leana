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
using QuantConnect.Logging;
using QuantConnect.Securities;

namespace QuantConnect.Securities
{
    /// <summary>
    /// T+1结算模型 - A股特有的结算规则
    /// 当天买入的股票当天不能卖出，第二天才能卖（T+1）
    /// 当天卖出的股票资金当��不能使用，第二天才能用于买入
    /// </summary>
    public class TPlusOneSettlementModel : ImmediateSettlementModel
    {
        // 记录每只股票每日的可卖数量
        // 结构: Dictionary<Symbol, Dictionary<可卖日期, 数量>>
        private readonly Dictionary<Symbol, Dictionary<DateTime, decimal>> _sellableQuantities;

        // 记录未结算资金
        // 结构: Dictionary<结算日期, 金额>
        private readonly Dictionary<DateTime, decimal> _unsettledFunds;

        // 记录每只股票的买入历史（用于调试）
        private readonly List<SettlementRecord> _settlementHistory;

        /// <summary>
        /// 结算记录（用于调试和日志）
        /// </summary>
        private class SettlementRecord
        {
            public DateTime DateTime { get; set; }
            public Symbol Symbol { get; set; }
            public decimal Quantity { get; set; }
            public string Operation { get; set; } // "BUY" 或 "SELL"
            public DateTime SettlementDate { get; set; }
        }

        /// <summary>
        /// 构造T+1结算模型
        /// </summary>
        public TPlusOneSettlementModel()
        {
            _sellableQuantities = new Dictionary<Symbol, Dictionary<DateTime, decimal>>();
            _unsettledFunds = new Dictionary<DateTime, decimal>();
            _settlementHistory = new List<SettlementRecord>();
        }

        /// <summary>
        /// 处理资金结算（买入/卖出）
        /// </summary>
        public override void ApplyFunds(ApplyFundsSettlementModelParameters parameters)
        {
            var symbol = parameters.Security.Symbol;
            var utcTime = parameters.UtcTime;
            var portfolio = parameters.Portfolio;

            // 从CashAmount获取金额（正值表示资金流入，负值表示资金流出）
            // 买入: quantity < 0 （花费现金）
            // 卖出: quantity > 0 （获得现金）
            var cashAmount = parameters.CashAmount;

            if (cashAmount.Amount < 0)
            {
                // 买入操作：记录可卖时间（T+1）
                var quantity = Math.Abs(cashAmount.Amount);
                var settlementDate = utcTime.Date.AddDays(1); // T+1

                if (!_sellableQuantities.ContainsKey(symbol))
                {
                    _sellableQuantities[symbol] = new Dictionary<DateTime, decimal>();
                }

                if (!_sellableQuantities[symbol].ContainsKey(settlementDate))
                {
                    _sellableQuantities[symbol][settlementDate] = 0;
                }

                _sellableQuantities[symbol][settlementDate] += quantity;

                // 记录历史
                _settlementHistory.Add(new SettlementRecord
                {
                    DateTime = utcTime,
                    Symbol = symbol,
                    Quantity = quantity,
                    Operation = "BUY",
                    SettlementDate = settlementDate
                });

                Log.Trace($"TPlusOneSettlementModel.ApplyFunds: 买入 {symbol} {quantity}股, 可卖日期: {settlementDate:yyyy-MM-dd}");
            }
            else if (cashAmount.Amount > 0)
            {
                // 卖出操作：记录待结算资金（T+1）
                var amount = cashAmount.Amount;
                var settlementDate = utcTime.Date.AddDays(1); // T+1

                if (!_unsettledFunds.ContainsKey(settlementDate))
                {
                    _unsettledFunds[settlementDate] = 0;
                }

                _unsettledFunds[settlementDate] += amount;

                // 记录历史
                _settlementHistory.Add(new SettlementRecord
                {
                    DateTime = utcTime,
                    Symbol = symbol,
                    Quantity = amount,
                    Operation = "SELL",
                    SettlementDate = settlementDate
                });

                Log.Trace($"TPlusOneSettlementModel.ApplyFunds: 卖出 {symbol} 获得 {amount:CNY}, 资金可用日期: {settlementDate:yyyy-MM-dd}");
            }

            // 调用基类处理标准资金操作
            base.ApplyFunds(parameters);
        }

        /// <summary>
        /// 扫描并处理结算
        /// </summary>
        public override void Scan(ScanSettlementModelParameters parameters)
        {
            var utcTime = parameters.UtcTime;
            var currentDate = utcTime.Date;
            var portfolio = parameters.Portfolio;

            Log.Trace($"TPlusOneSettlementModel.Scan: 开始扫描结算 {currentDate:yyyy-MM-dd}");

            // 处理资金结算
            if (_unsettledFunds.ContainsKey(currentDate))
            {
                var unsettledAmount = _unsettledFunds[currentDate];

                if (unsettledAmount > 0)
                {
                    // 将未结算资金转入可用资金
                    portfolio.CashBook[Currencies.CNY].AddAmount(unsettledAmount);

                    Log.Trace($"TPlusOneSettlementModel.Scan: 结算资金 {unsettledAmount:CNY} 已转入可用资金");

                    // 清除已结算的资金记录
                    _unsettledFunds.Remove(currentDate);
                }
            }

            // 释放可卖股票（日志记录）
            foreach (var kvp in _sellableQuantities)
            {
                var symbol = kvp.Key;
                var dateQuantities = kvp.Value;

                if (dateQuantities.ContainsKey(currentDate))
                {
                    var quantity = dateQuantities[currentDate];
                    Log.Trace($"TPlusOneSettlementModel.Scan: {symbol} 的 {quantity}股 已可卖 (T+1到期)");
                }
            }

            // 调用基类扫描
            base.Scan(parameters);
        }

        /// <summary>
        /// 获取指定股票的可卖数量
        /// </summary>
        /// <param name="symbol">股票代码</param>
        /// <param name="currentDate">当前日期</param>
        /// <returns>可卖数量</returns>
        public decimal GetSellableQuantity(Symbol symbol, DateTime currentDate)
        {
            if (!_sellableQuantities.ContainsKey(symbol))
            {
                return 0;
            }

            var total = 0m;
            foreach (var kvp in _sellableQuantities[symbol])
            {
                // 如果可卖日期 <= 当前日期，说明已可卖
                if (kvp.Key <= currentDate)
                {
                    total += kvp.Value;
                }
            }

            return total;
        }

        /// <summary>
        /// 检查指定数量的股票是否可卖
        /// </summary>
        /// <param name="symbol">股票代码</param>
        /// <param name="quantity">要卖的数量</param>
        /// <param name="currentDate">当前日期</param>
        /// <returns>True if sellable, false otherwise</returns>
        public bool IsQuantitySellable(Symbol symbol, decimal quantity, DateTime currentDate)
        {
            var sellableQuantity = GetSellableQuantity(symbol, currentDate);
            return sellableQuantity >= quantity;
        }

        /// <summary>
        /// 扣减可卖数量（卖出成功后调用）
        /// </summary>
        /// <param name="symbol">股票代码</param>
        /// <param name="quantity">卖出的数量</param>
        /// <param name="currentDate">当前日期</param>
        public void ReduceSellableQuantity(Symbol symbol, decimal quantity, DateTime currentDate)
        {
            if (!_sellableQuantities.ContainsKey(symbol))
            {
                Log.Trace($"TPlusOneSettlementModel.ReduceSellableQuantity: {symbol} 没有可卖记录");
                return;
            }

            var remaining = quantity;
            var dateQuantities = _sellableQuantities[symbol];

            // 按日期顺序扣减（先进先出）
            var sortedDates = new List<DateTime>(dateQuantities.Keys);
            sortedDates.Sort();

            foreach (var date in sortedDates)
            {
                if (date <= currentDate && remaining > 0)
                {
                    var available = dateQuantities[date];
                    var deduction = Math.Min(available, remaining);

                    dateQuantities[date] = available - deduction;
                    remaining -= deduction;

                    if (dateQuantities[date] <= 0)
                    {
                        // 清除已用完的记录
                        dateQuantities.Remove(date);
                    }
                }
            }

            // 如果所有记录都已清空，移除该股票的记录
            if (dateQuantities.Count == 0)
            {
                _sellableQuantities.Remove(symbol);
            }

            Log.Trace($"TPlusOneSettlementModel.ReduceSellableQuantity: {symbol} 扣减 {quantity}股");
        }

        /// <summary>
        /// 获取未结算资金总额
        /// </summary>
        /// <returns>未结算资金总额</returns>
        public decimal GetTotalUnsettledFunds()
        {
            var total = 0m;
            foreach (var kvp in _unsettledFunds)
            {
                total += kvp.Value;
            }
            return total;
        }

        /// <summary>
        /// 获取指定日期的未结算资金
        /// </summary>
        /// <param name="date">结算日期</param>
        /// <returns>未结算资金</returns>
        public decimal GetUnsettledFunds(DateTime date)
        {
            return _unsettledFunds.ContainsKey(date) ? _unsettledFunds[date] : 0;
        }

        /// <summary>
        /// 打印结算历史记录（调试用）
        /// </summary>
        public void PrintSettlementHistory()
        {
            Log.Trace("=== T+1结算历史记录 ===");
            foreach (var record in _settlementHistory)
            {
                Log.Trace($"  {record.DateTime:yyyy-MM-dd HH:mm:ss} {record.Operation} {record.Symbol} {record.Quantity} -> 可用日期: {record.SettlementDate:yyyy-MM-dd}");
            }
            Log.Trace($"当前未结算资金: {GetTotalUnsettledFunds():CNY}");
            Log.Trace("====================");
        }

        /// <summary>
        /// 清理过期数据（可选，用于节省内存）
        /// </summary>
        /// <param name="currentDate">当前日期</param>
        /// <param name="daysToKeep">保留天数</param>
        public void CleanupOldData(DateTime currentDate, int daysToKeep = 30)
        {
            var cutoffDate = currentDate.AddDays(-daysToKeep);

            // 清理过期的可卖记录
            foreach (var kvp in _sellableQuantities)
            {
                var datesToRemove = new List<DateTime>();
                foreach (var dateKvp in kvp.Value)
                {
                    if (dateKvp.Key < cutoffDate && dateKvp.Value <= 0)
                    {
                        datesToRemove.Add(dateKvp.Key);
                    }
                }

                foreach (var date in datesToRemove)
                {
                    kvp.Value.Remove(date);
                }
            }

            // 清理过期的未结算资金记录
            var fundsDatesToRemove = new List<DateTime>();
            foreach (var kvp in _unsettledFunds)
            {
                if (kvp.Key < cutoffDate && kvp.Value <= 0)
                {
                    fundsDatesToRemove.Add(kvp.Key);
                }
            }

            foreach (var date in fundsDatesToRemove)
            {
                _unsettledFunds.Remove(date);
            }

            Log.Trace($"TPlusOneSettlementModel.CleanupOldData: 已清理 {cutoffDate:yyyy-MM-dd} 之前的数据");
        }
    }
}
