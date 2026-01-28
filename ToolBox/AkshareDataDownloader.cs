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

            Console.WriteLine($"[下载] {symbol} ({startDate:yyyy-MM-dd} 至 {endDate:yyyy-MM-dd})");

            const int maxRetries = 3;
            for (int retry = 0; retry <= maxRetries; retry++)
            {
                try
                {
                    using (Py.GIL())
                    {
                        Console.Write("  正在获取数据");
                        ShowProgress(0);

                        var df = _akshare.stock_zh_a_hist(
                            symbol: symbol,
                            period: "daily",
                            start_date: startDate.ToString("yyyyMMdd"),
                            end_date: endDate.ToString("yyyyMMdd"),
                            adjust: adjust
                        );

                        ShowProgress(50);

                        long rowCount = _pd.DataFrame.len(df);
                        if (rowCount == 0)
                        {
                            Console.WriteLine();
                            Log.Trace($"AkshareDataDownloader.Download: {symbol} 没有数据");
                            Console.WriteLine($"  ⚠️  警告: {symbol} 在指定日期范围内没有数据");
                            return;
                        }

                        Console.WriteLine();
                        Console.WriteLine($"  ✓ 获取到 {rowCount} 条数据");

                        var symbolDir = Path.Combine(outputDirectory, "daily", symbol);
                        if (!Directory.Exists(symbolDir))
                        {
                            Directory.CreateDirectory(symbolDir);
                        }

                        var outputFile = Path.Combine(symbolDir, $"{startDate:yyyyMMdd}_{endDate:yyyyMMdd}_tradebar.csv");

                        Console.Write("  正在转换格式");
                        ConvertToLeanFormat(df, outputFile, symbol, rowCount);
                        Console.WriteLine();

                        Console.WriteLine($"  ✅ 成功保存到: {outputFile}");
                        Log.Trace($"AkshareDataDownloader.Download: {symbol} 数据已保存到 {outputFile}");
                        return;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine();
                    var errorType = GetErrorType(ex);
                    var suggestion = GetErrorSuggestion(errorType);

                    if (retry < maxRetries)
                    {
                        Console.WriteLine($"  ⚠️  {errorType}: {ex.Message}");
                        if (!string.IsNullOrEmpty(suggestion))
                        {
                            Console.WriteLine($"      建议: {suggestion}");
                        }
                        Console.WriteLine($"      正在重试 ({retry + 1}/{maxRetries})...");
                        System.Threading.Thread.Sleep(2000);
                    }
                    else
                    {
                        Console.WriteLine($"  ❌ 下载失败: {errorType}");
                        Console.WriteLine($"      错误详情: {ex.Message}");
                        if (!string.IsNullOrEmpty(suggestion))
                        {
                            Console.WriteLine($"      建议: {suggestion}");
                        }
                        Log.Error($"AkshareDataDownloader.Download: 下载失败 - {ex.Message}");
                        throw;
                    }
                }
            }
        }

        private void ShowProgress(int percent)
        {
            const int barLength = 30;
            int filled = (int)(barLength * percent / 100.0);
            var bar = new string('█', filled) + new string('░', barLength - filled);
            Console.Write($" [{bar}] {percent}%\r");
        }

        private string GetErrorType(Exception ex)
        {
            var message = ex.Message.ToLower();
            if (message.Contains("connection") && message.Contains("aborted"))
                return "网络连接中断";
            if (message.Contains("timeout"))
                return "请求超时";
            if (message.Contains("remote end closed"))
                return "服务器关闭连接";
            if (message.Contains("403") || message.Contains("forbidden"))
                return "访问被拒绝(403)";
            if (message.Contains("429") || message.Contains("too many"))
                return "请求过于频繁(429)";
            if (message.Contains("500") || message.Contains("internal server"))
                return "服务器内部错误(500)";
            if (message.Contains("no module") || message.Contains("import"))
                return "Python模块缺失";
            return "未知错误";
        }

        private string GetErrorSuggestion(string errorType)
        {
            return errorType switch
            {
                "网络连接中断" => "检查网络连接是否稳定",
                "请求超时" => "检查网络速度，考虑使用代理或稍后重试",
                "服务器关闭连接" => "akshare服务可能暂时不可用，请稍后重试",
                "访问被拒绝(403)" => "可能IP被封禁，请稍后重试或更换网络",
                "请求过于频繁(429)" => "降低请求频率，等待一段时间后再试",
                "服务器内部错误(500)" => "数据源服务器异常，请稍后重试",
                "Python模块缺失" => "运行 'pip install akshare pandas numpy' 安装依赖",
                _ => null
            };
        }

        /// <summary>
        /// 转换akshare数据为LEAN CSV格式
        /// </summary>
        /// <param name="df">pandas DataFrame</param>
        /// <param name="outputFile">输出文件路径</param>
        /// <param name="symbol">股票代码</param>
        /// <param name="totalRows">总行数（用于进度显示）</param>
        private void ConvertToLeanFormat(dynamic df, string outputFile, string symbol, long totalRows)
        {
            using (var writer = new StreamWriter(outputFile))
            {
                writer.WriteLine("date,time,open,high,low,close,volume");

                using (Py.GIL())
                {
                    long rowCount = _pd.DataFrame.len(df);
                    int lastPercent = 0;

                    for (long i = 0; i < rowCount; i++)
                    {
                        var row = _pd.DataFrame.iloc(df, new PyTuple(new PyObject[] { i.ToPython() }));

                        var dateStr = row.GetAttr("日期").ToString();
                        var open = row.GetAttr("开盘").ToString();
                        var high = row.GetAttr("最高").ToString();
                        var low = row.GetAttr("最低").ToString();
                        var close = row.GetAttr("收盘").ToString();
                        var volume = row.GetAttr("成交量").ToString();

                        if (DateTime.TryParseExact(dateStr, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime date))
                        {
                            var line = $"{date:yyyyMMdd},235900,{open},{high},{low},{close},{volume}";
                            writer.WriteLine(line);

                            int currentPercent = (int)((i + 1) * 100 / rowCount);
                            if (currentPercent > lastPercent && currentPercent % 10 == 0)
                            {
                                ShowProgress(currentPercent);
                                lastPercent = currentPercent;
                            }
                        }
                        else
                        {
                            Log.Trace($"AkshareDataDownloader.ConvertToLeanFormat: 无法解析日期 {dateStr}");
                        }
                    }

                    ShowProgress(100);
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
            Console.WriteLine($"\n[批量下载] 共 {symbols.Length} 只股票");
            Console.WriteLine($"日期范围: {startDate:yyyy-MM-dd} 至 {endDate:yyyy-MM-dd}");
            Console.WriteLine(new string('-', 60));

            int successCount = 0;
            int failCount = 0;

            for (int i = 0; i < symbols.Length; i++)
            {
                var symbol = symbols[i];
                Console.WriteLine($"\n[{i + 1}/{symbols.Length}] {symbol}");

                try
                {
                    Download(symbol, startDate, endDate, outputDirectory);
                    successCount++;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"  ❌ 失败: {ex.Message}");
                    Log.Error($"AkshareDataDownloader.DownloadBatch: {symbol} 下载失败 - {ex.Message}");
                    failCount++;
                }

                if (i < symbols.Length - 1)
                {
                    Console.Write("  等待1秒避免请求过快...");
                    System.Threading.Thread.Sleep(1000);
                    Console.WriteLine(" 完成");
                }
            }

            Console.WriteLine();
            Console.WriteLine(new string('=', 60));
            Console.WriteLine($"批量下载完成:");
            Console.WriteLine($"  ✅ 成功: {successCount}/{symbols.Length}");
            if (failCount > 0)
            {
                Console.WriteLine($"  ❌ 失败: {failCount}/{symbols.Length}");
            }
            Console.WriteLine(new string('=', 60));

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
