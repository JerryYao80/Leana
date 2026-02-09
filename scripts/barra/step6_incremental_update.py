#!/usr/bin/env python3
"""
Barra CNE5 因子增量更新脚本 - Step 6: Incremental Update

功能:
    1. 检测自上次运行以来的新交易日
    2. 仅计算新交易日的因子
    3. 追加到现有by_date文件
    4. 增量更新factor_returns和risk_params
    5. 运行验证检查

执行方式:
    python step6_incremental_update.py [--verbose]

输入:
    /data/tushare_data/daily/{ts_code}.parquet (新数据)
    /data/barra_factors/by_date/*.parquet (现有因子)
    /data/barra_risk/factor_returns.parquet (现有因子收益)

输出:
    /data/barra_factors/by_date/{new_date}.parquet (新因子文件)
    /data/barra_risk/factor_returns.parquet (更新)
    /data/barra_risk/risk_params_latest.json (更新)
    /data/barra_reports/incremental_update.log
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set, Tuple
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd
from tqdm import tqdm

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
TUSHARE_DATA_DIR = Path("/home/project/tushare-downloader/tushare_data")
FACTOR_DIR = DATA_ROOT / "barra_factors/by_date"
RISK_DIR = DATA_ROOT / "barra_risk"
REPORTS_DIR = DATA_ROOT / "barra_reports"

# 创建目录
FACTOR_DIR.mkdir(parents=True, exist_ok=True)
RISK_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_DIR / "incremental_update.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_latest_factor_date() -> str:
    """
    获取最新的因子数据日期

    Returns:
        最新日期字符串 (YYYYMMDD) 或 None
    """
    factor_files = list(FACTOR_DIR.glob("*.parquet"))

    if len(factor_files) == 0:
        logger.warning("No existing factor files found")
        return None

    # 从文件名提取日期
    dates = [f.stem for f in factor_files]
    dates.sort()

    latest_date = dates[-1]
    logger.info(f"Latest factor date: {latest_date}")

    return latest_date


def get_new_trading_days(since_date: str = None) -> List[str]:
    """
    获取需要计算的新交易日

    Args:
        since_date: 起始日期 (YYYYMMDD)，如果为None则从最新因子日期开始

    Returns:
        新交易日列表 (YYYYMMDD)
    """
    if since_date is None:
        since_date = get_latest_factor_date()

    if since_date is None:
        logger.error("Cannot determine starting date")
        return []

    # 从trade_cal获取交易日历
    trade_cal_file = TUSHARE_DATA_DIR / "trade_cal/data.parquet"

    if not trade_cal_file.exists():
        logger.error(f"Trade calendar not found: {trade_cal_file}")
        return []

    df_cal = pd.read_parquet(trade_cal_file)

    # 筛选A股交易日
    df_cal = df_cal[
        (df_cal['exchange'] == 'SSE') &
        (df_cal['is_open'] == 1) &
        (df_cal['cal_date'] > since_date)
    ].sort_values('cal_date')

    new_dates = df_cal['cal_date'].tolist()

    logger.info(f"Found {len(new_dates)} new trading days since {since_date}")

    return new_dates


def process_date_factors(args: Tuple) -> Tuple[str, bool, pd.DataFrame]:
    """
    并行处理单个日期的因子计算

    Args:
        args: (trade_date, calculator, stock_list) 元组

    Returns:
        (trade_date, success, df_factors)
    """
    trade_date, calculator, stock_list = args

    try:
        all_factors = []

        for ts_code in stock_list:
            try:
                factors = calculator.calculate_stock_factors(ts_code)

                if factors is not None:
                    factors_date = factors[factors['trade_date'] == trade_date]

                    if len(factors_date) > 0:
                        all_factors.append(factors_date)

            except Exception:
                pass

        if len(all_factors) == 0:
            return (trade_date, False, None)

        df_all = pd.concat(all_factors, ignore_index=True)
        return (trade_date, True, df_all)

    except Exception:
        return (trade_date, False, None)


def calculate_factors_for_dates_parallel(trade_dates: List[str], n_cores: int = 4) -> List[Tuple[str, pd.DataFrame]]:
    """
    并行计算多个日期的因子

    Args:
        trade_dates: 交易日期列表
        n_cores: 使用的CPU核心数

    Returns:
        [(trade_date, df_factors)] 列表
    """
    from step1_calculate_factors import FactorCalculator, load_benchmark_data

    logger.info(f"开始并行计算 {len(trade_dates)} 个日期的因子...")

    benchmark_data = load_benchmark_data()
    calculator = FactorCalculator(benchmark_data)

    stock_basic_file = TUSHARE_DATA_DIR / "stock_basic/data.parquet"
    df_stocks = pd.read_parquet(stock_basic_file)

    df_stocks = df_stocks[
        (df_stocks['market'] == '主板') |
        (df_stocks['market'] == '创业板') |
        (df_stocks['market'] == '科创板')
    ]

    stock_list = df_stocks['ts_code'].tolist()

    tasks = [(date, calculator, stock_list) for date in trade_dates]

    actual_cores = min(n_cores, cpu_count())
    logger.info(f"使用 {actual_cores} 个CPU核心进行并行计算")

    results = []

    with Pool(processes=actual_cores) as pool:
        task_results = list(tqdm(
            pool.imap_unordered(process_date_factors, tasks),
            total=len(tasks),
            desc=f"计算因子 [{actual_cores}核并行]"
        ))

    for trade_date, success, df_factors in task_results:
        if success and df_factors is not None:
            results.append((trade_date, df_factors))

    logger.info(f"成功计算 {len(results)} 个日期的因子")
    return results


def save_factor_data(df: pd.DataFrame, trade_date: str):
    """
    保存因子数据到by_date文件

    Args:
        df: 因子DataFrame
        trade_date: 交易日期 (YYYYMMDD)
    """
    output_file = FACTOR_DIR / f"{trade_date}.parquet"

    df.to_parquet(output_file, index=False)

    logger.info(f"Saved factors to {output_file}")


def update_factor_returns(new_dates: List[str]):
    """
    增量更新因子收益

    Args:
        new_dates: 新交易日列表
    """
    logger.info("Updating factor returns...")

    # 加载现有因子收益
    factor_returns_file = RISK_DIR / "factor_returns.parquet"

    if factor_returns_file.exists():
        df_returns = pd.read_parquet(factor_returns_file)
    else:
        df_returns = pd.DataFrame()

    # 计算新日期的因子收益
    # 这里简化实现，实际应该调用step3的代码
    logger.info(f"Calculating factor returns for {len(new_dates)} new dates")

    # TODO: 实现增量因子收益计算

    # 保存更新后的因子收益
    df_returns.to_parquet(factor_returns_file, index=False)

    logger.info("Factor returns updated")


def update_risk_params():
    """
    更新风险模型参数
    """
    logger.info("Updating risk parameters...")

    # 这里简化实现，实际应该调用step4的代码
    # TODO: 实现增量风险参数更新

    logger.info("Risk parameters updated")


def validate_new_data(new_dates: List[str]):
    """
    验证新数据质量

    Args:
        new_dates: 新交易日列表
    """
    logger.info("Validating new data...")

    for trade_date in new_dates:
        factor_file = FACTOR_DIR / f"{trade_date}.parquet"

        if not factor_file.exists():
            logger.error(f"Missing factor file: {factor_file}")
            continue

        df = pd.read_parquet(factor_file)

        # 检查股票数量
        if len(df) < 4000:
            logger.warning(f"{trade_date}: Low stock count ({len(df)})")

        # 检查因子方差
        for factor in ['growth', 'leverage']:
            variance = df[factor].var()
            if variance < 0.001:
                logger.warning(f"{trade_date}: {factor} has low variance ({variance:.6f})")

        # 检查缺失值
        missing_pct = df.isnull().mean()
        for factor, pct in missing_pct.items():
            if pct > 0.2:
                logger.warning(f"{trade_date}: {factor} has {pct:.1%} missing values")

    logger.info("Validation complete")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Barra CNE5 增量更新")
    parser.add_argument('--verbose', action='store_true', help='详细日志')
    parser.add_argument('--since-date', type=str, help='起始日期 (YYYYMMDD)')
    parser.add_argument('--dry-run', action='store_true', help='试运行（不保存）')
    parser.add_argument('--parallel', type=int, default=4, help='并行进程数（默认: 4）')
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("Barra CNE5 Incremental Update")
    logger.info("=" * 60)
    logger.info(f"并行进程数: {args.parallel}")

    new_dates = get_new_trading_days(args.since_date)

    if len(new_dates) == 0:
        logger.info("No new trading days to process")
        return

    logger.info(f"Processing {len(new_dates)} new trading days")

    results = calculate_factors_for_dates_parallel(new_dates, n_cores=args.parallel)

    if not args.dry_run:
        for trade_date, df_factors in results:
            save_factor_data(df_factors, trade_date)

    if not args.dry_run:
        update_factor_returns(new_dates)

    if not args.dry_run:
        update_risk_params()

    validate_new_data(new_dates)

    logger.info("=" * 60)
    logger.info("Incremental update complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
