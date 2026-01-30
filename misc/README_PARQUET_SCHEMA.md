# Parquet Schema Generator

扫描多层嵌套目录，提取所有parquet文件的表结构信息。

## 依赖

```bash
pip install pyarrow
```

## 使用方法

```bash
cd misc
python generate_parquet_schema.py
```

## 输出

生成 `tushare-dir.json` 文件，格式：

```json
{
  "Data/equity/china/daily/000001.parquet": [
    {"name": "date", "type": "timestamp[ns]"},
    {"name": "open", "type": "double"},
    {"name": "high", "type": "double"},
    {"name": "low", "type": "double"},
    {"name": "close", "type": "double"},
    {"name": "volume", "type": "int64"}
  ]
}
```

## 配置

编辑脚本中的 `scan_dirs` 列表来修改扫描目录：

```python
scan_dirs = [
    project_root / "Data",
    project_root / "另一个目录",
]
```
