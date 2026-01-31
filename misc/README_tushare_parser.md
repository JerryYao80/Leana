# Tushare 文档解析器

此脚本用于解析 Tushare 数据接口文档,提取接口名称和输出参数。

## 功能

- 从 https://tushare.pro/document/2 抓取接口文档
- 解析每个接口的输出参数
- 生成 JSON 格式的数据字典

## 依赖

```bash
pip install requests beautifulsoup4
```

## 使用方法

### 测试模式（解析指定接口）

默认情况下,脚本会解析几个示例接口:

```bash
python3 parse_tushare_docs.py
```

### 解析所有接口

编辑 `parse_tushare_docs.py` 中的 `main()` 函数,替换为:

```python
def main():
    test_url = "https://tushare.pro/document/2"
    
    try:
        # 解析所有接口
        api_data = parse_tushare_api(test_url, limit=None)
        
        output_file = "tushare-net.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"✓ 成功解析 {len(api_data)} 个接口")
        print(f"✓ 数据已保存到: {output_file}")
```

## 输出格式

生成的 `tushare-net.json` 文件格式如下:

```json
{
  "基础信息": {
    "ts_code": "TS代码",
    "symbol": "股票代码",
    "name": "股票名称",
    ...
  },
  "交易日历": {
    "exchange": "交易所 SSE上交所 SZSE深交所",
    "cal_date": "日历日期",
    ...
  },
  ...
}
```

## 示例输出

```
测试模式: 解析指定的 5 个接口

开始解析接口详情:
[1/5]   获取: doc_id=25 ... ✓ 基础信息 (17 参数)
[2/5]   获取: doc_id=26 ... ✓ 交易日历 (4 参数)
[3/5]   获取: doc_id=27 ... ✓ A股日线行情 (11 参数)
[4/5]   获取: doc_id=32 ... ✓ 每日指标 (18 参数)
[5/5]   获取: doc_id=33 ... ✓ 利润表 (94 参数)

============================================================
✓ 成功解析 5 个接口
✓ 数据已保存到: tushare-net.json
```

## 注意事项

1. 脚本包含延迟(0.5秒/请求)以避免过于频繁的请求
2. 某些页面是分类页面,不包含具体的接口信息,会被跳过
3. 建议先在测试模式下运行,确认脚本正常工作后再解析所有接口

## 许可证

本脚本仅用于学习和研究目的。请遵守 Tushare 的使用条款。
