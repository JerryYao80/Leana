using System;
using QuantConnect;

class ChinaMarketValidator
{
    static void Main(string[] args)
    {
        Console.WriteLine("=== 验证A股市场定义和CNY货币支持 ===\n");

        int passedTests = 0;
        int totalTests = 0;

        // 测试1: 验证Market.China常量
        totalTests++;
        Console.WriteLine("测试1: 验证Market.China常量");
        try
        {
            string chinaMarket = Market.China;
            if (chinaMarket == "china")
            {
                Console.WriteLine($"✅ PASS: Market.China = '{chinaMarket}'");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"❌ FAIL: Market.China = '{chinaMarket}' (期望: 'china')");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 测试2: 验证Market.ChinaA常量
        totalTests++;
        Console.WriteLine("\n测试2: 验证Market.ChinaA常量");
        try
        {
            string chinaAMarket = Market.ChinaA;
            if (chinaAMarket == "china-a")
            {
                Console.WriteLine($"✅ PASS: Market.ChinaA = '{chinaAMarket}'");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"❌ FAIL: Market.ChinaA = '{chinaAMarket}' (期望: 'china-a')");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 测试3: 验证Market编码/解码
        totalTests++;
        Console.WriteLine("\n测试3: 验证Market.China编码/解码");
        try
        {
            int? chinaCode = Market.Encode("china");
            string decodedMarket = Market.Decode(chinaCode ?? 0);

            if (chinaCode.HasValue && decodedMarket == "china")
            {
                Console.WriteLine($"✅ PASS: Market.China 编码={chinaCode}, 解码='{decodedMarket}'");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"❌ FAIL: 编码={chinaCode}, 解码='{decodedMarket}'");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 测试4: 验证Currencies.CNY常量
        totalTests++;
        Console.WriteLine("\n测试4: 验证Currencies.CNY常量");
        try
        {
            string cnyCurrency = Currencies.CNY;
            if (cnyCurrency == "CNY")
            {
                Console.WriteLine($"✅ PASS: Currencies.CNY = '{cnyCurrency}'");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"❌ FAIL: Currencies.CNY = '{cnyCurrency}' (期望: 'CNY')");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 测试5: 验证CNY货币符号
        totalTests++;
        Console.WriteLine("\n测试5: 验证CNY货币符号");
        try
        {
            string cnySymbol = Currencies.GetCurrencySymbol("CNY");
            if (cnySymbol == "¥")
            {
                Console.WriteLine($"✅ PASS: CNY货币符号 = '{cnySymbol}'");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"❌ FAIL: CNY货币符号 = '{cnySymbol}' (期望: '¥')");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 测试6: 验证Market.China在支持的市场列表中
        totalTests++;
        Console.WriteLine("\n测试6: 验证Market.China在支持的市场列表中");
        try
        {
            var supportedMarkets = Market.SupportedMarkets();
            if (supportedMarkets.Contains("china"))
            {
                Console.WriteLine($"✅ PASS: 'china' 在支持的市场列表中");
                passedTests++;
            }
            else
            {
                Console.WriteLine($"❌ FAIL: 'china' 不在支持的市场列表中");
                Console.WriteLine($"   支持的市场: {string.Join(", ", supportedMarkets)}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 测试7: 验证市场时间配置文件存在
        totalTests++;
        Console.WriteLine("\n测试7: 验证市场时间配置文件");
        try
        {
            string configPath = "/home/project/ccleana/Leana/Data/market-hours/market-hours-database.json";
            if (System.IO.File.Exists(configPath))
            {
                Console.WriteLine($"✅ PASS: 配置文件存在");
                passedTests++;

                // 读取文件并检查是否包含china配置
                string content = System.IO.File.ReadAllText(configPath);
                if (content.Contains("\"Equity-china-[*]\""))
                {
                    Console.WriteLine($"   ✅ 包含 'Equity-china-[*]' 配置");
                }
                else
                {
                    Console.WriteLine($"   ❌ 未找到 'Equity-china-[*]' 配置");
                }

                // 检查时区配置
                if (content.Contains("\"Asia/Shanghai\""))
                {
                    Console.WriteLine($"   ✅ 包含 'Asia/Shanghai' 时区");
                }
                else
                {
                    Console.WriteLine($"   ❌ 未找到 'Asia/Shanghai' 时区");
                }

                // 检查交易时间
                if (content.Contains("\"09:30:00\"") && content.Contains("\"11:30:00\""))
                {
                    Console.WriteLine($"   ✅ 包含A股上午交易时间 09:30-11:30");
                }
                else
                {
                    Console.WriteLine($"   ❌ 未找到完整的上午交易时间");
                }
            }
            else
            {
                Console.WriteLine($"❌ FAIL: 配置文件不存在: {configPath}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ FAIL: 异常 - {ex.Message}");
        }

        // 总结
        Console.WriteLine($"\n{'='*50}");
        Console.WriteLine($"测试结果: {passedTests}/{totalTests} 通过");
        if (passedTests == totalTests)
        {
            Console.WriteLine("✅ 所有测试通过！");
            Environment.Exit(0);
        }
        else
        {
            Console.WriteLine($"❌ {totalTests - passedTests} 个测试失败");
            Environment.Exit(1);
        }
    }
}
