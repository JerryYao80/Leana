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
using System.IO;
using System.Globalization;
using Python.Runtime;
using QuantConnect.Logging;
using QuantConnect.Util;

namespace QuantConnect.ToolBox
{
    /// <summary>
    /// Akshare数据下载器 - 用于下载A股历史数据并转换为LEAN格式
    /// </summary>
    public class AkshareDataDownloader
    {
        private dynamic _akshare;
        private dynamic _pd;
        private bool _initialized = false;

        /// <summary>
        /// 初始化Python环境和akshare库
        /// </summary>
        public void Initialize()
        {
            if (_initialized) return;

            try
            {
                // 初始化Python引擎
                PythonEngine.Initialize();

                // 导入必要的库
                using (Py.GIL())
                {
                    _akshare = Py.Import("akshare");
                    _pd = Py.Import("pandas");
                }

                _initialized = true;
                Log.Trace("AkshareDataDownloader: Python环境和akshare库初始化成功");
            }
            catch (Exception ex)
            {
                Log.Error($"AkshareDataDownloader.Initialize: 初始化失败 - {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// 下载A股历史数据
        /// </summary>
        /// <param name="symbol">股票代码（如 "000001"）</param>
        /// <param name="startDate">开始日期</param>
        /// <param name="endDate">结束日期</param>
        /// <param name="outputDirectory">输出目录</param>
        /// <param name="adjust">复权类型：""-不复权, "qfq"-前复权, "hfq"-后复权</param>
        public void Download(string symbol, DateTime startDate, DateTime endDate, string outputDirectory, string adjust = "qfq")
        {
            if (!_initialized)
            {
                Initialize();
            }

            Log.Trace($"AkshareDataDownloader.Download: 开始下载 {symbol} 数据 ({startDate:yyyy-MM-dd} 至 {endDate:yyyy-MM-dd})");

            try
            {
                using (Py.GIL())
                {
                    // 调用akshare接口获取股票数据
                    // akshare.stock_zh_a_hist(symbol="000001", period="daily", start_date="20100101", end_date="20100131", adjust="qfq")
                    var df = _akshare.stock_zh_a_hist(
                        symbol: symbol,
                        period: "daily",
                        start_date: startDate.ToString("yyyyMMdd"),
                        end_date: endDate.ToString("yyyyMMdd"),
                        adjust: adjust
                    );

                    // 检查数据是否为空
                    long rowCount = _pd.DataFrame.len(df);
                    if (rowCount == 0)
                    {
                        Log.Trace($"AkshareDataDownloader.Download: {symbol} 没有数据");
                        return;
                    }

                    Log.Trace($"AkshareDataDownloader.Download: {symbol} 获取到 {rowCount} 条数据");

                    // 创建输出目录
                    var symbolDir = Path.Combine(outputDirectory, "daily", symbol);
                    if (!Directory.Exists(symbolDir))
                    {
                        Directory.CreateDirectory(symbolDir);
                    }

                    // 生成输出文件名
                    var outputFile = Path.Combine(symbolDir, $"{startDate:yyyyMMdd}_{endDate:yyyyMMdd}_tradebar.csv");

                    // 转换并保存为LEAN CSV格式
                    ConvertToLeanFormat(df, outputFile, symbol);

                    Log.Trace($"AkshareDataDownloader.Download: {symbol} 数据已保存到 {outputFile}");
                }
            }
            catch (Exception ex)
            {
                Log.Error($"AkshareDataDownloader.Download: 下载失败 - {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// 转换akshare数据为LEAN CSV格式
        /// </summary>
        /// <param name="df">pandas DataFrame</param>
        /// <param name="outputFile">输出文件路径</param>
        /// <param name="symbol">股票代码</param>
        private void ConvertToLeanFormat(dynamic df, string outputFile, string symbol)
        {
            // LEAN CSV格式: date,time,open,high,low,close,volume
            // akshare返回的列: 日期, 开盘, 最高, 最低, 收盘, 成交量, ...

            using (var writer = new StreamWriter(outputFile))
            {
                // 写入CSV头
                writer.WriteLine("date,time,open,high,low,close,volume");

                // 遍历DataFrame的每一行
                using (Py.GIL())
                {
                    // 获取行数
                    long rowCount = _pd.DataFrame.len(df);

                    for (long i = 0; i < rowCount; i++)
                    {
                        // 获取第i行
                        var row = _pd.DataFrame.iloc(df, new PyTuple(new PyObject[] { i.ToPython() }));

                        // 提取数据
                        var dateStr = row.GetAttr("日期").ToString();
                        var open = row.GetAttr("开盘").ToString();
                        var high = row.GetAttr("最高").ToString();
                        var low = row.GetAttr("最低").ToString();
                        var close = row.GetAttr("收盘").ToString();
                        var volume = row.GetAttr("成交量").ToString();

                        // 解析日期
                        if (DateTime.TryParseExact(dateStr, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime date))
                        {
                            // LEAN格式: date,time,open,high,low,close,volume
                            // time使用235959表示日终
                            var line = $"{date:yyyyMMdd},235900,{open},{high},{low},{close},{volume}";
                            writer.WriteLine(line);
                        }
                        else
                        {
                            Log.Trace($"AkshareDataDownloader.ConvertToLeanFormat: 无法解析日期 {dateStr}");
                        }
                    }
                }
            }

            Log.Trace($"AkshareDataDownloader.ConvertToLeanFormat: 已转换并保存到 {outputFile}");
        }

        /// <summary>
        /// 批量下载多只股票的数据
        /// </summary>
        /// <param name="symbols">股票代码列表</param>
        /// <param name="startDate">开始日期</param>
        /// <param name="endDate">结束日期</param>
        /// <param name="outputDirectory">输出目录</param>
        public void DownloadBatch(string[] symbols, DateTime startDate, DateTime endDate, string outputDirectory)
        {
            Log.Trace($"AkshareDataDownloader.DownloadBatch: 开始批量下载 {symbols.Length} 只股票");

            int successCount = 0;
            int failCount = 0;

            foreach (var symbol in symbols)
            {
                try
                {
                    Download(symbol, startDate, endDate, outputDirectory);
                    successCount++;
                }
                catch (Exception ex)
                {
                    Log.Error($"AkshareDataDownloader.DownloadBatch: {symbol} 下载失败 - {ex.Message}");
                    failCount++;
                }
            }

            Log.Trace($"AkshareDataDownloader.DownloadBatch: 批量下载完成 - 成功: {successCount}, 失败: {failCount}");
        }

        /// <summary>
        /// 获取A股股票列表
        /// </summary>
        /// <returns>股票代码列表</returns>
        public string[] GetStockList()
        {
            if (!_initialized)
            {
                Initialize();
            }

            Log.Trace("AkshareDataDownloader.GetStockList: 开始获取股票列表");

            try
            {
                using (Py.GIL())
                {
                    // 获取A股股票列表
                    var df = _akshare.stock_zh_a_spot_em();

                    // 提取股票代码列 - 直接获取整个列
                    var codes = df.GetAttr("代码");

                    // 转换为C#字符串数组
                    long rowCount = _pd.DataFrame.len(df);
                    var symbolList = new string[rowCount];

                    for (long i = 0; i < rowCount; i++)
                    {
                        var code = _pd.Series.iloc(codes, new PyTuple(new PyObject[] { i.ToPython() })).ToString();
                        symbolList[i] = code;
                    }

                    Log.Trace($"AkshareDataDownloader.GetStockList: 获取�� {symbolList.Length} 只股票");
                    return symbolList;
                }
            }
            catch (Exception ex)
            {
                Log.Error($"AkshareDataDownloader.GetStockList: 获取失败 - {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// 释放资源
        /// </summary>
        public void Dispose()
        {
            if (_initialized)
            {
                // Python环境由PythonEngine管理，无需手动释放
                _initialized = false;
                Log.Trace("AkshareDataDownloader.Dispose: 已释放资源");
            }
        }
    }

    /// <summary>
    /// Akshare数据下载器命令行工具
    /// </summary>
    public class AkshareDataDownloaderProgram
    {
        public static void Main(string[] args)
        {
            if (args.Length < 4)
            {
                Console.WriteLine("用法: AkshareDataDownloader <symbol> <startDate> <endDate> <outputDirectory> [adjust]");
                Console.WriteLine("  symbol: 股票代码（如 000001）");
                Console.WriteLine("  startDate: 开始日期（格式: yyyyMMdd）");
                Console.WriteLine("  endDate: 结束日期（格式: yyyyMMdd）");
                Console.WriteLine("  outputDirectory: 输出目录");
                Console.WriteLine("  adjust: 复权类型（可选）: \"\"-不复权, \"qfq\"-前复权（默认）, \"hfq\"-后复权");
                Console.WriteLine();
                Console.WriteLine("示例:");
                Console.WriteLine("  AkshareDataDownloader 000001 20240101 20241231 /home/project/ccleana/data");
                return;
            }

            var symbol = args[0];
            var startDate = DateTime.ParseExact(args[1], "yyyyMMdd", CultureInfo.InvariantCulture);
            var endDate = DateTime.ParseExact(args[2], "yyyyMMdd", CultureInfo.InvariantCulture);
            var outputDirectory = args[3];
            var adjust = args.Length > 4 ? args[4] : "qfq";

            var downloader = new AkshareDataDownloader();
            try
            {
                downloader.Download(symbol, startDate, endDate, outputDirectory, adjust);
                Console.WriteLine($"✅ 下载完成: {symbol}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ 下载失败: {ex.Message}");
                Environment.Exit(1);
            }
            finally
            {
                downloader.Dispose();
            }
        }
    }
}
