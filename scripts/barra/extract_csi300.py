#!/usr/bin/env python3
"""
生成CSI300成分股列表

功能:
    从index_weight数据提取沪深300成分股列表

输出:
    /data/barra_config/csi300.txt
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_ROOT = Path("/home/project/ccleana/data")
TUSHARE_DATA_DIR = DATA_ROOT / "tushare_data"
OUTPUT_DIR = DATA_ROOT / "barra_config"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("提取CSI300成分股...")

# 获取最新日期的index_weight数据
index_weight_dir = TUSHARE_DATA_DIR / "index_weight"
date_dirs = sorted(index_weight_dir.glob("date=*"), reverse=True)

csi300_stocks = set()

for date_dir in date_dirs[:5]:  # 检查最近5个交易日
    try:
        df = pd.read_parquet(date_dir / "data.parquet")

        # 提取000300.SH (沪市) 和 399300.SZ (深市)
        df_sh = df[df['index_code'] == '000300.SH'][['con_code']].dropna()
        df_sz = df[df['index_code'] == '399300.SZ'][['con_code']].dropna()

        csi300_stocks.update(df_sh.tolist())
        csi300_stocks.update(df_sz.tolist())

        if len(csi300_stocks) >= 300:
            break
    except:
        continue

print(f"找到 {len(csi300_stocks)} 只CSI300成分股")

# 保存到文件
output_file = OUTPUT_DIR / "csi300.txt"
with open(output_file, 'w') as f:
    for stock in sorted(csi300_stocks):
        f.write(stock + '\n')

print(f"已保存到: {output_file}")

# 显示前20只股票
print("\n前20只股票:")
for i, stock in enumerate(sorted(csi300_stocks)[:20], 1):
    print(f"  {i}. {stock}")
