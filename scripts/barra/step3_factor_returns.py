#!/usr/bin/env python3
"""
Barra CNE5 因子计算脚本 - Step 3: 计算因子收益率

功能:
    通过横截面回归计算因子收益率 f
    每个交易日: R_t = X_t @ f_t + u_t
    使用加权��小二乘法 (WLS)，权重 = sqrt(market_cap)

执行方式:
    python step3_factor_returns.py

输入:
    /data/barra_factors/by_date/{date}.parquet (因子暴露)
    /data/tushare_data/daily_basic/{ts_code}.parquet (市值数据用于权重)

输出:
    /data/barra_risk/factor_returns.parquet (因子收益率时间序列)
    /data/barra_risk/residuals.parquet (股票残差)
    /data/barra_reports/step3_factor_returns.log
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from functools import partial

import numpy as np
import pandas as pd
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import os

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
FACTOR_DATA_DIR = DATA_ROOT / "barra_factors/by_date"
TUSHARE_DATA_DIR = DATA_ROOT / "tushare_data"
OUTPUT_DIR = DATA_ROOT / "barra_risk"
REPORTS_DIR = DATA_ROOT / "barra_reports"

# 创建目录
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_DIR / "step3_factor_returns.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 因子列表
STYLE_FACTORS = [
    'size', 'beta', 'momentum', 'volatility', 'non_linear_size',
    'book_to_price', 'liquidity', 'earnings_yield', 'growth', 'leverage'
]

INDUSTRY_FACTORS = [
    'ind_petrochemical', 'ind_coal', 'ind_nonferrous', 'ind_utilities', 'ind_steel',
    'ind_chemicals', 'ind_building_materials', 'ind_construction', 'ind_transportation',
    'ind_automobiles', 'ind_machinery', 'ind_defense', 'ind_electrical_equipment',
    'ind_electronics', 'ind_computers', 'ind_communications', 'ind_consumer_appliances',
    'ind_light_manufacturing', 'ind_textiles_apparel', 'ind_food_beverage',
    'ind_agriculture', 'ind_banking', 'ind_non_bank_finance', 'ind_real_estate',
    'ind_commerce_retail', 'ind_social_services', 'ind_media', 'ind_pharmaceuticals',
    'ind_environmental', 'ind_comprehensive'
]

ALL_FACTORS = STYLE_FACTORS + INDUSTRY_FACTORS

# 全局缓存（用于多进程子进程）
_GLOBAL_STOCK_PRICE_CACHE = None
_GLOBAL_MARKET_CAP_CACHE = None


def init_worker(stock_price_cache: Dict, market_cap_cache: Dict):
    """
    子进程初始���函数：接收缓存数据

    Args:
        stock_price_cache: 价格数据缓存
        market_cap_cache: 市值数据缓存
    """
    global _GLOBAL_STOCK_PRICE_CACHE, _GLOBAL_MARKET_CAP_CACHE
    _GLOBAL_STOCK_PRICE_CACHE = stock_price_cache
    _GLOBAL_MARKET_CAP_CACHE = market_cap_cache


def load_stock_returns(date_str: str) -> Dict[str, float]:
    """
    加载指定日期的股票收益率

    Args:
        date_str: 日期字符串 (YYYYMMDD)

    Returns:
        {ts_code: return} 字典
    """
    returns = {}

    # 从daily目录加载所有股票的收益率
    # 由于文件很多，这里简化处理 - 从daily_basic的pct_chg获取
    # 或者可以预加载一个映射表

    # 更高效的方式是：一次性加载所有股票的收益率数据
    # 这里使用一个简化的方法：从daily_basic目录按需加载
    return returns


def build_market_cap_cache() -> Dict[str, pd.DataFrame]:
    """
    构建市值数据缓存 (一次性加载所有股票市值数据)

    Returns:
        {ts_code: DataFrame} 字典
    """
    cache = {}
    basic_dir = TUSHARE_DATA_DIR / "daily_basic"
    if not basic_dir.exists():
        return cache

    stock_dirs = list(basic_dir.iterdir())
    logger.info(f"开始构建市值缓存，共 {len(stock_dirs)} 只股票...")

    for stock_dir in tqdm(stock_dirs, desc="加载市值数据"):
        if stock_dir.is_dir():
            ts_code = stock_dir.name.replace('date=', '')
            try:
                path = stock_dir / "data.parquet"
                if path.exists():
                    df = pd.read_parquet(path)
                    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')
                    cache[ts_code] = df
            except:
                pass

    logger.info(f"市值缓存构建完成，共 {len(cache)} 只股票")
    return cache


def get_market_caps_for_date(date_str: str, market_cap_cache: Dict[str, pd.DataFrame],
                              stock_codes: List[str]) -> Dict[str, float]:
    """
    从缓存中获取指定日期的股票市值

    Args:
        date_str: 日期字符串 (YYYYMMDD)
        market_cap_cache: 市值缓存字典
        stock_codes: 股票代码列表

    Returns:
        {ts_code: market_cap} 字典
    """
    market_caps = {}
    date_dt = pd.to_datetime(date_str, format='%Y%m%d')

    for ts_code in stock_codes:
        if ts_code not in market_cap_cache:
            continue

        df = market_cap_cache[ts_code]
        df_filtered = df[df['trade_date'] <= date_dt].sort_values('trade_date', ascending=False)

        if len(df_filtered) > 0:
            market_caps[ts_code] = df_filtered.iloc[0]['total_mv']

    return market_caps


def cross_sectional_regression(factor_df: pd.DataFrame,
                                 returns_df: pd.DataFrame,
                                 market_caps: Dict[str, float]) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    横截面回归计算因子收益率

    R_t = X_t @ f_t + u_t

    Args:
        factor_df: 因子暴露 DataFrame (ts_code x factors)
        returns_df: 收益率 DataFrame (ts_code x return)
        market_caps: 市值字典 {ts_code: mv}

    Returns:
        (factor_returns, residuals)
    """
    # 合并数据
    merged = factor_df.merge(returns_df, on='ts_code', how='inner')

    if len(merged) < 50:  # 至少50只股票才进行回归
        return np.zeros(len(ALL_FACTORS)), {}

    # 准备回归数据
    stock_codes = merged['ts_code'].values
    y = merged['return'].values

    # 构建因子暴露矩阵 X
    factor_cols = [col for col in ALL_FACTORS if col in merged.columns]
    X = merged[factor_cols].values

    # 处理NaN值
    valid_mask = ~(np.isnan(y) | np.isnan(X).any(axis=1))
    if valid_mask.sum() < 50:
        return np.zeros(len(ALL_FACTORS)), {}

    y = y[valid_mask]
    X = X[valid_mask]
    stock_codes_valid = stock_codes[valid_mask]

    # 构建权重矩阵 W (按市值加权)
    weights = np.ones(len(y))
    for i, code in enumerate(stock_codes_valid):
        mv = market_caps.get(code, 1e8)  # 默认市值
        weights[i] = np.sqrt(max(mv, 1e8))  # sqrt(mv)

    # WLS回归
    W = np.diag(weights)
    XTW = X.T @ W
    XTWX = XTW @ X

    # 检查矩阵是否可逆
    if np.linalg.det(XTWX) == 0 or np.isnan(np.linalg.det(XTWX)):
        # 使用岭回归
        lambda_ridge = 0.01
        XTWX = XTWX + lambda_ridge * np.eye(XTWX.shape[0])

    try:
        XTWX_inv = np.linalg.inv(XTWX)
        XTWy = XTW @ y
        factor_returns = XTWX_inv @ XTWy
    except np.linalg.LinAlgError:
        return np.zeros(len(ALL_FACTORS)), {}

    # 计算残差
    predicted = X @ factor_returns
    residuals = y - predicted

    # 保存残差
    residual_dict = {code: float(res) for code, res in zip(stock_codes_valid, residuals)}

    return factor_returns, residual_dict


def process_single_date(args: Tuple) -> Tuple:
    """
    处理单个交易日的因子收益率计算（用于多进程）

    Args:
        args: (date_str, date_file_path) 元组

    Returns:
        (date_str, factor_returns_list, residuals_list, status)
        status: 0=成功, 1=数据不足, 2=失败
    """
    date_str, date_file_path = args

    try:
        # 加载因子数据
        factor_df = pd.read_parquet(date_file_path)

        # 从全局缓存获取数据
        global _GLOBAL_STOCK_PRICE_CACHE, _GLOBAL_MARKET_CAP_CACHE
        stock_price_cache = _GLOBAL_STOCK_PRICE_CACHE
        market_cap_cache = _GLOBAL_MARKET_CAP_CACHE

        if stock_price_cache is None or market_cap_cache is None:
            return (date_str, None, None, 2)  # 缓存未初始化

        # 计算股票收益率
        stock_returns = {}
        for ts_code in factor_df['ts_code'].values:
            if ts_code in stock_price_cache:
                price_df = stock_price_cache[ts_code]
                target_date = pd.to_datetime(date_str, format='%Y%m%d')
                price_df_filtered = price_df[price_df['trade_date'] <= target_date].sort_values('trade_date', ascending=False)
                if len(price_df_filtered) > 0:
                    stock_returns[ts_code] = price_df_filtered.iloc[0]['pct_chg']

        if len(stock_returns) < 50:
            return (date_str, None, None, 1)  # 数据不足

        # 构建收益率DataFrame
        returns_df = pd.DataFrame([
            {'ts_code': k, 'return': v}
            for k, v in stock_returns.items()
        ])

        # 从缓存获取市值数据
        market_caps = get_market_caps_for_date(date_str, market_cap_cache, factor_df['ts_code'].tolist())

        # 横截面回归
        factor_returns, residuals = cross_sectional_regression(
            factor_df, returns_df, market_caps
        )

        # 构建残差列表（使用基本类型，确保可以pickle序列化）
        residual_list = [
            {'trade_date': date_str, 'ts_code': ts_code, 'residual': float(resid)}
            for ts_code, resid in residuals.items()
        ]

        # 将numpy数组转换为列表
        factor_returns_list = [float(x) for x in factor_returns]

        return (date_str, factor_returns_list, residual_list, 0)

    except Exception:
        return (date_str, None, None, 2)  # 失败


def calculate_factor_returns() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    计算所有交易日的因子收益率（使用多进程并行）

    Returns:
        (factor_returns_df, residuals_df)
    """
    logger.info("开始计算因子收益率...")

    # 获取所有日期文件
    date_files = sorted(FACTOR_DATA_DIR.glob("*.parquet"))
    logger.info(f"找到 {len(date_files)} 个交易日文件")

    # 确定使用的CPU核心数
    n_cores = min(cpu_count(), 4)  # 最多使用4核
    logger.info(f"检测到系统有 {cpu_count()} 个CPU核心，将使用 {n_cores} 个核心进行并行计算")

    # 1. 构建股票价格数据缓存（加载所有股票）
    logger.info("构建股票价格数据缓存...")
    stock_price_cache = {}
    daily_dir = TUSHARE_DATA_DIR / "daily"
    if daily_dir.exists():
        stock_dirs = [d for d in daily_dir.iterdir() if d.is_dir()]
        logger.info(f"发现 {len(stock_dirs)} 只股票目录")
        for stock_dir in tqdm(stock_dirs, desc="缓存价格数据"):
            ts_code = stock_dir.name.replace('date=', '')
            try:
                df = pd.read_parquet(stock_dir / "data.parquet")
                df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')
                stock_price_cache[ts_code] = df[['trade_date', 'close', 'pct_chg']].copy()
            except:
                pass

    logger.info(f"成功缓存 {len(stock_price_cache)} 只股票的价格数据")

    # 2. 构建市值数据缓存（一次性加载所有股票市值）
    market_cap_cache = build_market_cap_cache()

    # 3. 准备任务参数
    tasks = [(f.stem, f) for f in date_files]

    # 4. 使用多进程池并行处理
    all_factor_returns = []
    all_residuals = []
    insufficient_data_count = 0
    failed_dates = []

    logger.info(f"开始并行处理 {len(tasks)} 个交易日...")

    with Pool(
        processes=n_cores,
        initializer=init_worker,
        initargs=(stock_price_cache, market_cap_cache)
    ) as pool:
        # 使用 imap_unordered 以便实时显示进度
        results = list(tqdm(
            pool.imap_unordered(process_single_date, tasks),
            total=len(tasks),
            desc=f"计算因子收益率 [{n_cores}核并行]"
        ))

    # 5. 收集结果
    for date_str, factor_returns, residuals, status in results:
        if status == 0:  # 成功
            all_factor_returns.append([date_str] + factor_returns)
            all_residuals.extend(residuals)
        elif status == 1:  # 数据不足
            insufficient_data_count += 1
        else:  # 失败
            failed_dates.append(date_str)

    # 构建因子收益率DataFrame
    factor_returns_df = pd.DataFrame(
        all_factor_returns,
        columns=['trade_date'] + ALL_FACTORS
    )
    factor_returns_df['trade_date'] = pd.to_datetime(
        factor_returns_df['trade_date'], format='%Y%m%d'
    )

    # 构建残差DataFrame
    residuals_df = pd.DataFrame(all_residuals)

    logger.info(f"成功计算 {len(factor_returns_df)} 个交易日的因子收益率")
    logger.info(f"共 {len(residuals_df)} 条残差记录")
    if insufficient_data_count > 0:
        logger.warning(f"因数据不足跳过的日期数: {insufficient_data_count}")
    if failed_dates:
        logger.warning(f"失败日期数: {len(failed_dates)}")

    return factor_returns_df, residuals_df


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Barra CNE5 因子计算 - Step 3: 计算因子收益率")
    logger.info("=" * 60)
    logger.info(f"输入目录: {FACTOR_DATA_DIR}")
    logger.info(f"输出目录: {OUTPUT_DIR}")

    # 计算因子收益率
    factor_returns_df, residuals_df = calculate_factor_returns()

    if len(factor_returns_df) == 0:
        logger.error("没有计算出任何因子收益率，请检查输入数据")
        return

    # 保存因子收益率
    factor_returns_path = OUTPUT_DIR / "factor_returns.parquet"
    factor_returns_df.to_parquet(factor_returns_path, index=False)
    logger.info(f"因子收益率已保存到: {factor_returns_path}")

    # 保存残差
    residuals_path = OUTPUT_DIR / "residuals.parquet"
    residuals_df.to_parquet(residuals_path, index=False)
    logger.info(f"残差已保存到: {residuals_path}")

    # 输出统计信息
    logger.info("=" * 60)
    logger.info("因子收益率统计:")
    for factor in STYLE_FACTORS:
        if factor in factor_returns_df.columns:
            mean = factor_returns_df[factor].mean()
            std = factor_returns_df[factor].std()
            logger.info(f"  {factor}: mean={mean:.6f}, std={std:.6f}")

    logger.info("=" * 60)
    logger.info(f"完成! 因子收益率记录数: {len(factor_returns_df)}")
    logger.info(f"      残差记录数: {len(residuals_df)}")
    logger.info("=" * 60)

    # 保存统计报告
    stats = {
        'timestamp': datetime.now().isoformat(),
        'trading_days': len(factor_returns_df),
        'factor_returns_file': str(factor_returns_path),
        'residuals_file': str(residuals_path),
        'factor_statistics': {}
    }

    for factor in STYLE_FACTORS:
        if factor in factor_returns_df.columns:
            stats['factor_statistics'][factor] = {
                'mean': float(factor_returns_df[factor].mean()),
                'std': float(factor_returns_df[factor].std()),
                'min': float(factor_returns_df[factor].min()),
                'max': float(factor_returns_df[factor].max())
            }

    stats_path = REPORTS_DIR / "step3_results.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(f"统计报告已保存到: {stats_path}")


if __name__ == "__main__":
    main()
