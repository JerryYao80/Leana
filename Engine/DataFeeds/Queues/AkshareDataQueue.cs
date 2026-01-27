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
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Timers;
using Python.Runtime;
using QuantConnect.Data;
using QuantConnect.Data.Market;
using QuantConnect.Interfaces;
using QuantConnect.Logging;
using QuantConnect.Packets;
using QuantConnect.Util;

namespace QuantConnect.Lean.Engine.DataFeeds.Queues
{
    /// <summary>
    /// Akshare实时数据队列处理器
    /// 支持A股实时行情数据推送（分钟级更新）
    /// </summary>
    public class AkshareDataQueue : IDataQueueHandler
    {
        // Python对象
        private dynamic _akshare;
        private dynamic _pd;

        // 订阅管理
        private readonly Dictionary<Symbol, SubscriptionDataConfig> _subscriptions;
        private readonly Dictionary<Symbol, List<BaseData>> _latestData;
        private readonly object _lock = new object();

        // 定时器（用于定时获取数据）
        private readonly Timer _dataFetchTimer;

        // 初始化状态
        private bool _initialized = false;
        private bool _disposed = false;

        /// <summary>
        /// 数据获取间隔（毫秒）
        /// 默认300秒（5分钟），防止被封锁IP
        /// </summary>
        public int DataFetchInterval { get; set; } = 300000;

        /// <summary>
        /// 是否已连接
        /// </summary>
        public bool IsConnected => _initialized && !_disposed;

        /// <summary>
        /// 构造AkshareDataQueue
        /// </summary>
        public AkshareDataQueue()
        {
            _subscriptions = new Dictionary<Symbol, SubscriptionDataConfig>();
            _latestData = new Dictionary<Symbol, List<BaseData>>();

            // 创建定时器
            _dataFetchTimer = new Timer(DataFetchInterval);
            _dataFetchTimer.Elapsed += OnDataFetchTimer;
            _dataFetchTimer.AutoReset = true;

            Log.Trace("AkshareDataQueue: 已创建");
        }

        /// <summary>
        /// 初始化Python环境和akshare库
        /// </summary>
        private void Initialize()
        {
            if (_initialized) return;

            try
            {
                Log.Trace("AkshareDataQueue.Initialize: 开始初始化");

                // 初始化Python引擎
                PythonEngine.Initialize();

                // 导入必要的库
                using (Py.GIL())
                {
                    _akshare = Py.Import("akshare");
                    _pd = Py.Import("pandas");
                }

                _initialized = true;
                Log.Trace("AkshareDataQueue.Initialize: 初始化成功");
            }
            catch (Exception ex)
            {
                Log.Error($"AkshareDataQueue.Initialize: 初始化失败 - {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// 订阅数据
        /// </summary>
        public IEnumerator<BaseData> Subscribe(SubscriptionDataConfig dataConfig, EventHandler newDataAvailableHandler)
        {
            if (!_initialized)
            {
                Initialize();
            }

            var symbol = dataConfig.Symbol;

            Log.Trace($"AkshareDataQueue.Subscribe: 订阅 {symbol}");

            lock (_lock)
            {
                _subscriptions[symbol] = dataConfig;
                _latestData[symbol] = new List<BaseData>();
            }

            // 如果是第一个订阅，启动定时器
            if (_subscriptions.Count == 1)
            {
                _dataFetchTimer.Start();
                Log.Trace("AkshareDataQueue.Subscribe: 数据获取定时器已启动");
            }

            // 返回一个枚举器
            return new AkshareDataEnumerator(symbol, this, newDataAvailableHandler);
        }

        /// <summary>
        /// 取消订阅
        /// </summary>
        public void Unsubscribe(SubscriptionDataConfig dataConfig)
        {
            var symbol = dataConfig.Symbol;

            Log.Trace($"AkshareDataQueue.Unsubscribe: 取消订阅 {symbol}");

            lock (_lock)
            {
                _subscriptions.Remove(symbol);
                _latestData.Remove(symbol);
            }

            // 如果没有订阅了，停止定时器
            if (_subscriptions.Count == 0)
            {
                _dataFetchTimer.Stop();
                Log.Trace("AkshareDataQueue.Unsubscribe: 数据获取定时器已停止");
            }
        }

        /// <summary>
        /// 设置任务
        /// </summary>
        public void SetJob(LiveNodePacket job)
        {
            Log.Trace($"AkshareDataQueue.SetJob: 设置任务");
            // Akshare不需要特殊任务设置
        }

        /// <summary>
        /// 定时器事件处理
        /// </summary>
        private void OnDataFetchTimer(object sender, ElapsedEventArgs e)
        {
            try
            {
                FetchLatestData();
            }
            catch (Exception ex)
            {
                Log.Error($"AkshareDataQueue.OnDataFetchTimer: 获取数据时出错 - {ex.Message}");
            }
        }

        /// <summary>
        /// 获取最新数据
        /// </summary>
        private void FetchLatestData()
        {
            if (!_initialized || _disposed)
            {
                return;
            }

            Log.Trace("AkshareDataQueue.FetchLatestData: 开始获取实时数据");

            using (Py.GIL())
            {
                try
                {
                    // 调用akshare获取实时行情
                    // stock_zh_a_spot_em(): 获取A股实时行情数据
                    var df = _akshare.stock_zh_a_spot_em();

                    // 检查数据是否为空 - 使用 Python 内置的 len() 函数
                    PyObject lenFunc = _pd.Builtins.len();
                    long rowCount = lenFunc.Invoke(df).As<long>();
                    if (rowCount == 0)
                    {
                        Log.Trace("AkshareDataQueue.FetchLatestData: 没有获取到实时数据");
                        return;
                    }

                    // 遍历数据，更新订阅的股票
                    for (long i = 0; i < rowCount; i++)
                    {
                        var row = _pd.DataFrame.iloc(df, new PyTuple(new PyObject[] { i.ToPython() }));

                        // 提取股票代码
                        var code = row.GetAttr("代码").ToString();
                        var symbol = GetSymbol(code);

                        // 检查是否订阅了该股票
                        if (symbol == null)
                        {
                            continue;
                        }

                        lock (_lock)
                        {
                            if (!_subscriptions.ContainsKey(symbol))
                            {
                                continue;
                            }

                            // 提取行情数据
                            var price = decimal.Parse(row.GetAttr("最新价").ToString(), System.Globalization.CultureInfo.InvariantCulture);
                            var volume = decimal.Parse(row.GetAttr("成交量").ToString(), System.Globalization.CultureInfo.InvariantCulture);
                            var bidPrice = decimal.Parse(row.GetAttr("买一价").ToString(), System.Globalization.CultureInfo.InvariantCulture);
                            var askPrice = decimal.Parse(row.GetAttr("卖一价").ToString(), System.Globalization.CultureInfo.InvariantCulture);

                            // 创建Tick对象
                            var tick = new Tick
                            {
                                Symbol = symbol,
                                Time = DateTime.UtcNow,
                                Value = price,
                                Quantity = volume,
                                BidPrice = bidPrice,
                                AskPrice = askPrice,
                                TickType = TickType.Trade,
                                DataType = MarketDataType.Tick
                            };

                            // 更新最新数据
                            _latestData[symbol].Clear();
                            _latestData[symbol].Add(tick);

                            Log.Trace($"AkshareDataQueue.FetchLatestData: {symbol} 价格={price}, 成交量={volume}");
                        }
                    }

                    Log.Trace($"AkshareDataQueue.FetchLatestData: 已更新 {_latestData.Count} 只股票的实时数据");
                }
                catch (Exception ex)
                {
                    Log.Error($"AkshareDataQueue.FetchLatestData: 获取数据时出错 - {ex.Message}");
                }
            }
        }

        /// <summary>
        /// 根据股票代码获取Symbol对象
        /// </summary>
        private Symbol GetSymbol(string code)
        {
            lock (_lock)
            {
                foreach (var kvp in _subscriptions)
                {
                    if (kvp.Key.Value == code)
                    {
                        return kvp.Key;
                    }
                }
            }
            return null;
        }

        /// <summary>
        /// 获取指定Symbol的最新数据
        /// </summary>
        public IEnumerable<BaseData> GetData(Symbol symbol)
        {
            lock (_lock)
            {
                if (_latestData.ContainsKey(symbol))
                {
                    return _latestData[symbol].ToList();
                }
            }
            return Enumerable.Empty<BaseData>();
        }

        /// <summary>
        /// 释放资源
        /// </summary>
        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            Log.Trace("AkshareDataQueue.Dispose: 开始释放资源");

            _disposed = true;
            _dataFetchTimer.Stop();
            _dataFetchTimer.Dispose();

            lock (_lock)
            {
                _subscriptions.Clear();
                _latestData.Clear();
            }

            _akshare = null;
            _pd = null;
            _initialized = false;

            Log.Trace("AkshareDataQueue.Dispose: 已释放资源");
        }

        /// <summary>
        /// Akshare数据枚举器
        /// </summary>
        private class AkshareDataEnumerator : IEnumerator<BaseData>
        {
            private readonly Symbol _symbol;
            private readonly AkshareDataQueue _parent;
            private readonly EventHandler _newDataAvailableHandler;
            private BaseData _current;

            public AkshareDataEnumerator(Symbol symbol, AkshareDataQueue parent, EventHandler newDataAvailableHandler)
            {
                _symbol = symbol;
                _parent = parent;
                _newDataAvailableHandler = newDataAvailableHandler;
            }

            public BaseData Current => _current;

            object IEnumerator.Current => Current;

            public bool MoveNext()
            {
                // 从父对象获取最新数据
                var dataList = _parent.GetData(_symbol).ToList();

                if (dataList.Count > 0)
                {
                    _current = dataList[0];
                    return true;
                }

                return false;
            }

            public void Reset()
            {
                _current = null;
            }

            public void Dispose()
            {
                // 不需要释放资源
            }
        }
    }
}
