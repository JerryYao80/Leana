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
using System.Globalization;
using System.Linq;
using NodaTime;
using Python.Runtime;
using QuantConnect.Data;
using QuantConnect.Data.Market;
using QuantConnect.Interfaces;
using QuantConnect.Logging;
using QuantConnect.Util;

namespace QuantConnect.Lean.Engine.HistoricalData
{
    /// <summary>
    /// Akshare历史数据提供者
    /// 通过Python的akshare库获取A股历史数据
    /// </summary>
    public class AkshareHistoryProvider : HistoryProviderBase
    {
        // Python对象
        private dynamic _akshare;
        private dynamic _pd;

        // 初始化状态
        private bool _initialized = false;

        // 数据点计数
        private int _dataPointCount = 0;

        /// <summary>
        /// 获取数据点总数
        /// </summary>
        public override int DataPointCount => _dataPointCount;

        /// <summary>
        /// 初始化历史数据提供者
        /// </summary>
        public override void Initialize(HistoryProviderInitializeParameters parameters)
        {
            if (_initialized) return;

            try
            {
                Log.Trace("AkshareHistoryProvider.Initialize: 开始初始化");

                // 初始化Python引擎
                PythonEngine.Initialize();

                // 导入必要的库
                using (Py.GIL())
                {
                    _akshare = Py.Import("akshare");
                    _pd = Py.Import("pandas");
                }

                _initialized = true;
                _dataPointCount = 0;

                Log.Trace("AkshareHistoryProvider.Initialize: 初始化成功");
            }
            catch (Exception ex)
            {
                Log.Error($"AkshareHistoryProvider.Initialize: 初始化失败 - {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// 获取历史数据
        /// </summary>
        public override IEnumerable<Slice> GetHistory(IEnumerable<HistoryRequest> requests, DateTimeZone sliceTimeZone)
        {
            if (!_initialized)
            {
                throw new InvalidOperationException("AkshareHistoryProvider未初始化。请先调用Initialize()方法。");
            }

            Log.Trace($"AkshareHistoryProvider.GetHistory: 开始处理 {requests.Count()} 个数据请求");

            var results = new List<Slice>();

            foreach (var request in requests)
            {
                try
                {
                    // 只处理A股股票数据
                    if (request.Symbol.ID.SecurityType != SecurityType.Equity)
                    {
                        Log.Trace($"AkshareHistoryProvider.GetHistory: 跳过非股票数据 {request.Symbol}");
                        continue;
                    }

                    // 检查市场是否为中国
                    if (request.Symbol.ID.Market != Market.China && request.Symbol.ID.Market != Market.ChinaA)
                    {
                        Log.Trace($"AkshareHistoryProvider.GetHistory: 跳过非中国市场数据 {request.Symbol}");
                        continue;
                    }

                    // 获取数据
                    var dataPoints = GetHistoryData(request);

                    if (dataPoints != null && dataPoints.Count() > 0)
                    {
                        // 按时间分组创建Slice
                        var groupedByTime = dataPoints.GroupBy(d => d.Time);

                        foreach (var group in groupedByTime)
                        {
                            var dataCollection = new List<BaseData>();
                            foreach (var data in group)
                            {
                                dataCollection.Add(data);
                                _dataPointCount++;
                            }

                            // 创建Slice
                            var slice = new Slice(group.Key, dataCollection, group.Key);
                            results.Add(slice);
                        }

                        Log.Trace($"AkshareHistoryProvider.GetHistory: {request.Symbol} 获取到 {dataPoints.Count()} 条数据");
                    }
                    else
                    {
                        Log.Trace($"AkshareHistoryProvider.GetHistory: {request.Symbol} 没有获取到数据");
                    }
                }
                catch (Exception ex)
                {
                    Log.Error($"AkshareHistoryProvider.GetHistory: 处理 {request.Symbol} 时出错 - {ex.Message}");
                }
            }

            Log.Trace($"AkshareHistoryProvider.GetHistory: 完成，共返回 {results.Count} 个Slice");

            return results;
        }

        /// <summary>
        /// 获取单个请求的历史数据
        /// </summary>
        private IEnumerable<BaseData> GetHistoryData(HistoryRequest request)
        {
            var symbol = request.Symbol.Value;
            var startDate = request.StartTimeUtc;
            var endDate = request.EndTimeUtc;
            var resolution = request.Resolution;

            // 只支持日线和分钟线数据
            if (resolution != Resolution.Daily && resolution != Resolution.Hour &&
                resolution != Resolution.Minute && resolution != Resolution.Second)
            {
                Log.Trace($"AkshareHistoryProvider.GetHistoryData: 不支持的分辨率 {resolution}");
                return Enumerable.Empty<BaseData>();
            }

            Log.Trace($"AkshareHistoryProvider.GetHistoryData: 获取 {symbol} 数据 ({startDate:yyyy-MM-dd} 至 {endDate:yyyy-MM-dd}), 分辨率: {resolution}");

            var tradeBars = new List<BaseData>();

            using (Py.GIL())
            {
                try
                {
                    // 确定数据周期
                    string period = GetPeriodString(resolution);

                    // 调用akshare获取数据
                    // stock_zh_a_hist(symbol="000001", period="daily", start_date="20100101", end_date="20100131", adjust="qfq")
                    var df = _akshare.stock_zh_a_hist(
                        symbol: symbol,
                        period: period,
                        start_date: startDate.ToString("yyyyMMdd"),
                        end_date: endDate.ToString("yyyyMMdd"),
                        adjust: "qfq"  // 前复权
                    );

                    // 检查数据是否为空
                    long rowCount = _pd.DataFrame.len(df);
                    if (rowCount == 0)
                    {
                        Log.Trace($"AkshareHistoryProvider.GetHistoryData: {symbol} 没有数据");
                        return Enumerable.Empty<BaseData>();
                    }

                    Log.Trace($"AkshareHistoryProvider.GetHistoryData: {symbol} 获取到 {rowCount} 条原始数据");

                    // 转换为TradeBar
                    for (long i = 0; i < rowCount; i++)
                    {
                        var row = _pd.DataFrame.iloc(df, new PyTuple(new PyObject[] { i.ToPython() }));

                        // 提取数据
                        var dateStr = row.GetAttr("日期").ToString();
                        var open = decimal.Parse(row.GetAttr("开盘").ToString(), CultureInfo.InvariantCulture);
                        var high = decimal.Parse(row.GetAttr("最高").ToString(), CultureInfo.InvariantCulture);
                        var low = decimal.Parse(row.GetAttr("最低").ToString(), CultureInfo.InvariantCulture);
                        var close = decimal.Parse(row.GetAttr("收盘").ToString(), CultureInfo.InvariantCulture);
                        var volume = decimal.Parse(row.GetAttr("成交量").ToString(), CultureInfo.InvariantCulture);

                        // 解析日期
                        if (DateTime.TryParseExact(dateStr, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime date))
                        {
                            // 转换为UTC时间
                            var utcDateTime = date.ConvertToUtc(request.DataTimeZone);

                            // 创建TradeBar
                            var tradeBar = new TradeBar
                            {
                                Symbol = request.Symbol,
                                Time = utcDateTime,
                                EndTime = utcDateTime.AddDays(1), // 日线数据结束时间为次日
                                Open = open,
                                High = high,
                                Low = low,
                                Close = close,
                                Volume = volume,
                                Period = resolution.ToTimeSpan(),
                                DataType = MarketDataType.TradeBar
                            };

                            tradeBars.Add(tradeBar);
                        }
                        else
                        {
                            Log.Trace($"AkshareHistoryProvider.GetHistoryData: 无法解析日期 {dateStr}");
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log.Error($"AkshareHistoryProvider.GetHistoryData: 获取数据时出错 - {ex.Message}");
                }
            }

            return tradeBars;
        }

        /// <summary>
        /// 将分辨率转换为akshare的period字符串
        /// </summary>
        private string GetPeriodString(Resolution resolution)
        {
            switch (resolution)
            {
                case Resolution.Daily:
                    return "daily";
                case Resolution.Hour:
                    return "60"; // 60分钟
                case Resolution.Minute:
                    return "1"; // 1分钟
                case Resolution.Second:
                    return ""; // 不支持，会使用默认
                default:
                    return "daily";
            }
        }

        /// <summary>
        /// 释放资源
        /// </summary>
        public void Dispose()
        {
            if (_initialized)
            {
                _akshare = null;
                _pd = null;
                _initialized = false;
                Log.Trace("AkshareHistoryProvider.Dispose: 已释放资源");
            }
        }
    }
}
