#!/usr/bin/env python3
"""
下载Tushare财务数据用于Barra CNE5 Growth和Leverage因子计算

使用方法:
    python download_financial_data.py --token YOUR_TUSHARE_TOKEN

注意: 需要Tushare积分权限才能下载财务数据
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import tushare as ts
from tqdm import tqdm

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
TUSHARE_DATA_DIR = DATA_ROOT / "tushare_data"

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="下载Tushare财务数据")
    parser.add_argument('--token', type=str, required=True, help='Tushare API token')
    parser.add_argument('--limit', type=int, help='限制下载数量（测试用）')
    args = parser.parse_args()

    # 初始化Tushare
    ts.set_token(args.token)
    pro = ts.pro_api()

    # 获取股票列表
    stock_basic_file = TUSHARE_DATA_DIR / "stock_basic/data.parquet"
    df_stocks = pd.read_parquet(stock_basic_file)
    stock_list = df_stocks['ts_code'].tolist()

    if args.limit:
        stock_list = stock_list[:args.limit]

    logger.info(f"Downloading financial data for {len(stock_list)} stocks...")

    # 创建目录
    for subdir in ['income', 'fina_indicator', 'balancesheet']:
        (TUSHARE_DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # 下载数据
    for ts_code in tqdm(stock_list):
        try:
            # 下载利润表
            df_income = pro.income(ts_code=ts_code)
            if len(df_income) > 0:
                output_dir = TUSHARE_DATA_DIR / "income" / f"date={ts_code}"
                output_dir.mkdir(parents=True, exist_ok=True)
                df_income.to_parquet(output_dir / "data.parquet", index=False)

            # 下载财务指标
            df_fina = pro.fina_indicator(ts_code=ts_code)
            if len(df_fina) > 0:
                output_dir = TUSHARE_DATA_DIR / "fina_indicator" / f"date={ts_code}"
                output_dir.mkdir(parents=True, exist_ok=True)
                df_fina.to_parquet(output_dir / "data.parquet", index=False)

            # API限流
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"Error downloading {ts_code}: {e}")

    logger.info("Download complete!")


if __name__ == "__main__":
    main()
