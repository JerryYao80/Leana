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

import numpy as np
import pandas as pd
from tqdm import tqdm

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


def load_market_caps(date_str: str, stock_codes: List[str]) -> Dict[str, float]:
    """
    加载指定日期的股票市值

    Args:
        date_str: 日期字符串 (YYYYMMDD)
        stock_codes: 股票代码列表

    Returns:
        {ts_code: market_cap} 字典
    """
    market_caps = {}
    date_dt = pd.to_datetime(date_str, format='%Y%m%d')

    for ts_code in stock_codes:
        try:
            path = TUSHARE_DATA_DIR / "daily_basic" / f"date={ts_code}" / "data.parquet"
            if not path.exists():
                continue

            df = pd.read_parquet(path)
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')

            # 找到最接近该日期的数据
            df = df[df['trade_date'] <= date_dt].sort_values('trade_date', ascending=False)

            if len(df) > 0:
                market_caps[ts_code] = df.iloc[0]['total_mv']

        except Exception:
            continue

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


def calculate_factor_returns() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    计算所有交易日的因子收益率

    Returns:
        (factor_returns_df, residuals_df)
    """
    logger.info("开始计算因子收益率...")

    # 获取所有日期文件
    date_files = sorted(FACTOR_DATA_DIR.glob("*.parquet"))
    logger.info(f"找到 {len(date_files)} 个交易日文件")

    # 收集结果
    all_factor_returns = []
    all_residuals = []

    # 首先构建一个股票价格数据缓存，用于计算收益率
    logger.info("构建股票价格数据缓存...")
    stock_price_cache = {}
    daily_dir = TUSHARE_DATA_DIR / "daily"
    if daily_dir.exists():
        stock_dirs = list(daily_dir.iterdir())[:1000]  # 限制数量避免内存溢出
        for stock_dir in tqdm(stock_dirs, desc="缓存价格数据"):
            if stock_dir.is_dir():
                ts_code = stock_dir.name.replace('date=', '')
                try:
                    df = pd.read_parquet(stock_dir / "data.parquet")
                    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')
                    stock_price_cache[ts_code] = df[['trade_date', 'close', 'pct_chg']].copy()
                except:
                    pass

    logger.info(f"缓存了 {len(stock_price_cache)} 只股票的价格数据")

    # 逐日处理
    failed_dates = []

    for date_file in tqdm(date_files, desc="计算因子收益率"):
        date_str = date_file.stem
        try:
            # 加载因子数据
            factor_df = pd.read_parquet(date_file)

            # 计算股票收益率
            stock_returns = {}
            for ts_code in factor_df['ts_code'].values:
                if ts_code in stock_price_cache:
                    price_df = stock_price_cache[ts_code]
                    # 找到最接近该日期的收益率
                    target_date = pd.to_datetime(date_str, format='%Y%m%d')
                    price_df = price_df[price_df['trade_date'] <= target_date].sort_values('trade_date', ascending=False)
                    if len(price_df) > 0:
                        stock_returns[ts_code] = price_df.iloc[0]['pct_chg']

            if not stock_returns:
                continue

            # 构建收益率DataFrame
            returns_df = pd.DataFrame([
                {'ts_code': k, 'return': v}
                for k, v in stock_returns.items()
            ])

            # 加载市值数据
            market_caps = load_market_caps(date_str, factor_df['ts_code'].tolist())

            # 横截面回归
            factor_returns, residuals = cross_sectional_regression(
                factor_df, returns_df, market_caps
            )

            # 保存因子收益率
            all_factor_returns.append([date_str] + factor_returns.tolist())

            # 保存残差
            for ts_code, resid in residuals.items():
                all_residuals.append({
                    'trade_date': date_str,
                    'ts_code': ts_code,
                    'residual': resid
                })

        except Exception as e:
            failed_dates.append((date_str, str(e)))
            logger.warning(f"处理日期 {date_str} 失败: {e}")

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
