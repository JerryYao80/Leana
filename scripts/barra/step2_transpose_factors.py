#!/usr/bin/env python3
"""
Barra CNE5 因子计算脚本 - Step 2: 转置因子数据

功能:
    将按股票存���的因子数据转置为按日期存储

执行方式:
    python step2_transpose_factors.py

输入:
    /data/barra_factors/by_stock/{ts_code}.parquet

输出:
    /data/barra_factors/by_date/{date}.parquet
    /data/barra_reports/step2_transpose.log
"""

import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from tqdm import tqdm

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
INPUT_DIR = DATA_ROOT / "barra_factors/by_stock"
OUTPUT_DIR = DATA_ROOT / "barra_factors/by_date"
REPORTS_DIR = DATA_ROOT / "barra_reports"

# 创建目录
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_DIR / "step2_transpose.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 30个行业列
INDUSTRY_COLUMNS = [
    'ind_petrochemical', 'ind_coal', 'ind_nonferrous', 'ind_utilities', 'ind_steel',
    'ind_chemicals', 'ind_building_materials', 'ind_construction', 'ind_transportation',
    'ind_automobiles', 'ind_machinery', 'ind_defense', 'ind_electrical_equipment',
    'ind_electronics', 'ind_computers', 'ind_communications', 'ind_consumer_appliances',
    'ind_light_manufacturing', 'ind_textiles_apparel', 'ind_food_beverage',
    'ind_agriculture', 'ind_banking', 'ind_non_bank_finance', 'ind_real_estate',
    'ind_commerce_retail', 'ind_social_services', 'ind_media', 'ind_pharmaceuticals',
    'ind_environmental', 'ind_comprehensive'
]

# 所有因子列
FACTOR_COLUMNS = (
    ['size', 'beta', 'momentum', 'volatility', 'non_linear_size',
     'book_to_price', 'liquidity', 'earnings_yield', 'growth', 'leverage'] +
    INDUSTRY_COLUMNS
)


def load_all_factor_files() -> Dict[str, pd.DataFrame]:
    """
    加载所有股票的因子数据

    Returns:
        {ts_code: DataFrame} 字典
    """
    logger.info("加载因子数据文件...")

    factor_files = list(INPUT_DIR.glob("*.parquet"))
    logger.info(f"找到 {len(factor_files)} 个因子文件")

    stock_data = {}
    failed_files = []

    for file_path in tqdm(factor_files, desc="加载因子文件"):
        try:
            ts_code = file_path.stem
            df = pd.read_parquet(file_path)

            # 确保trade_date是正确的格式 (YYYYMMDD)
            if 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')
                df = df.dropna(subset=['trade_date'])
                stock_data[ts_code] = df

        except Exception as e:
            failed_files.append((file_path.name, str(e)))
            logger.warning(f"加载失败 {file_path.name}: {e}")

    logger.info(f"成功加载 {len(stock_data)} 只股票的因子数据")
    if failed_files:
        logger.warning(f"失败文件数: {len(failed_files)}")

    return stock_data


def transpose_by_date(stock_data: Dict[str, pd.DataFrame],
                     batch_size: int = 500) -> None:
    """
    将按股票存储的数据转置为按日期存储

    Args:
        stock_data: {ts_code: DataFrame} 字典
        batch_size: 每批处理的股票数量 (用于内存管理)
    """
    logger.info("开始转置数据...")

    # 收集所有交易日期
    all_dates = set()
    for df in stock_data.values():
        all_dates.update(df['trade_date'].dt.date.unique())

    all_dates = sorted(all_dates)
    logger.info(f"共 {len(all_dates)} 个交易日")

    # 按日期组织数据
    date_to_stocks = defaultdict(list)

    for ts_code, df in tqdm(stock_data.items(), desc="组织数据"):
        for date in df['trade_date'].dt.date.unique():
            date_to_stocks[date].append(ts_code)

    logger.info(f"每个日期平均股票数: {sum(len(v) for v in date_to_stocks.values()) / len(date_to_stocks):.0f}")

    # 逐日期处理
    processed_dates = 0
    failed_dates = []

    for date in tqdm(all_dates, desc="转置数据"):
        try:
            # 获取该日期有数据的所有股票
            stock_codes = date_to_stocks[date]

            # 收集该日期所有股票的数据
            date_data = []
            for ts_code in stock_codes:
                df = stock_data[ts_code]
                stock_df = df[df['trade_date'].dt.date == date].copy()

                if len(stock_df) > 0:
                    # 添加股票代码列
                    stock_df = stock_df.copy()
                    stock_df['ts_code'] = ts_code
                    date_data.append(stock_df)

            if not date_data:
                continue

            # 合并所有股票的数据
            combined_df = pd.concat(date_data, ignore_index=True)

            # 选择输出列
            output_cols = ['ts_code'] + FACTOR_COLUMNS
            output_df = combined_df[output_cols].copy()

            # 保存为Parquet文件
            date_str = date.strftime('%Y%m%d')
            output_path = OUTPUT_DIR / f"{date_str}.parquet"
            output_df.to_parquet(output_path, index=False)

            processed_dates += 1

        except Exception as e:
            failed_dates.append((date, str(e)))
            logger.warning(f"处理日期 {date} 失败: {e}")

    logger.info(f"成功处理 {processed_dates} 个交易日")
    if failed_dates:
        logger.warning(f"失败日期数: {len(failed_dates)}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Barra CNE5 因子计算 - Step 2: 转置因子数据")
    logger.info("=" * 60)
    logger.info(f"输入目录: {INPUT_DIR}")
    logger.info(f"输出目录: {OUTPUT_DIR}")

    # 加载所有因子数据
    stock_data = load_all_factor_files()

    if not stock_data:
        logger.error("没有找到任何因子数据，请先运行 step1_calculate_factors.py")
        return

    # 转置数据
    transpose_by_date(stock_data)

    # 统计结果
    output_files = list(OUTPUT_DIR.glob("*.parquet"))
    logger.info("=" * 60)
    logger.info(f"转置完成!")
    logger.info(f"输出文件数: {len(output_files)}")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 60)

    # 保存统计报告
    stats = {
        'timestamp': datetime.now().isoformat(),
        'input_files': len(stock_data),
        'output_files': len(output_files),
        'input_directory': str(INPUT_DIR),
        'output_directory': str(OUTPUT_DIR)
    }

    stats_path = REPORTS_DIR / "step2_results.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(f"统计报告已保存到: {stats_path}")


if __name__ == "__main__":
    main()
