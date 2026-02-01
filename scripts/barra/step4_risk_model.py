#!/usr/bin/env python3
"""
Barra CNE5 因子计算脚本 - Step 4: 估计风险模型

功能:
    1. 估计因子协方差矩阵 F (指数加权，半衰期90天)
    2. 估计特质风险 Δ (个股残差风险)
    3. 输出风险参数JSON文件

执行方式:
    python step4_risk_model.py [--estimation-window N] [--half-life N]

输入:
    /data/barra_risk/factor_returns.parquet
    /data/barra_risk/residuals.parquet

输出:
    /data/barra_risk/risk_params_latest.json
    /data/barra_risk/specific_risks.parquet
    /data/barra_reports/step4_risk_model.log
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
INPUT_DIR = DATA_ROOT / "barra_risk"
OUTPUT_DIR = DATA_ROOT / "barra_risk"
REPORTS_DIR = DATA_ROOT / "barra_reports"

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_DIR / "step4_risk_model.log"),
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


def estimate_factor_covariance(factor_returns: pd.DataFrame,
                                 half_life: int = 90) -> pd.DataFrame:
    """
    估计因子协方差矩阵 (指数加权)

    Args:
        factor_returns: 因子收益率时间序列
        half_life: 半衰期 (天数)

    Returns:
        因子协方差矩阵 DataFrame
    """
    logger.info(f"估计因子协方差矩阵 (半衰期={half_life}天)...")

    # 只使用有效的因子列
    valid_factors = [f for f in ALL_FACTORS if f in factor_returns.columns]
    logger.info(f"有效因子数: {len(valid_factors)}")

    # 计算衰减系数
    decay = 0.5 ** (1 / half_life)

    # 准备数据: 去除NaN
    df = factor_returns[['trade_date'] + valid_factors].copy()
    df = df.dropna()

    if len(df) == 0:
        logger.error("没有有效的因子收益率数据")
        return pd.DataFrame(index=valid_factors, columns=valid_factors)

    # 提取因子收益率矩阵
    T = len(df)
    factor_matrix = df[valid_factors].values

    # 计算指数权重
    weights = np.array([decay ** (T - 1 - i) for i in range(T)])
    weights = weights / weights.sum()  # 归一化

    # 去均值
    factor_mean = factor_matrix.mean(axis=0)
    factor_centered = factor_matrix - factor_mean

    # 计算加权协方差
    weighted_factor = factor_centered * np.sqrt(weights.reshape(-1, 1))
    cov_matrix = np.dot(weighted_factor.T, weighted_factor)

    # 转换为DataFrame
    cov_df = pd.DataFrame(cov_matrix, index=valid_factors, columns=valid_factors)

    # 确保正定性: 特征值调整
    logger.info("检查协方差矩阵正定性...")
    eigenvalues = np.linalg.eigvals(cov_df.values)

    min_eigenvalue = eigenvalues.min()
    if min_eigenvalue <= 0:
        logger.warning(f"协方差矩阵非正定, 最小特征值={min_eigenvalue:.6f}")
        # 调整: 添加小的正数对角线元素
        adjustment = abs(min_eigenvalue) + 1e-6
        cov_adjusted = cov_df.values + np.eye(cov_df.shape[0]) * adjustment
        cov_df = pd.DataFrame(cov_adjusted, index=valid_factors, columns=valid_factors)
        logger.info(f"已调整协方差矩阵，添加对角线元素 {adjustment:.6f}")

    return cov_df


def estimate_specific_risks(residuals: pd.DataFrame,
                             window: int = 252,
                             half_life: int = 90) -> Dict[str, float]:
    """
    估计特质风险 (个股残差风险)

    Args:
        residuals: 残差数据
        window: 估计窗口
        half_life: 半衰期

    Returns:
        {ts_code: specific_risk} 字典
    """
    logger.info(f"估计特质风险 (窗口={window}天, 半衰期={half_life}天)...")

    # 检查残差数据是否为空
    if residuals is None or len(residuals) == 0:
        logger.warning("残差数据为空，无法估计特质风险")
        return {}

    if 'ts_code' not in residuals.columns or 'residual' not in residuals.columns:
        logger.warning(f"残差数据缺少必要列: {residuals.columns.tolist()}")
        return {}

    # 按股票分组
    stock_residuals = residuals.groupby('ts_code')['residual'].apply(list)

    specific_risks = {}

    for ts_code, resid_list in stock_residuals.items():
        resid_array = np.array(resid_list)

        if len(resid_array) < window:
            # 如果数据不足，使用全部数据计算标准差
            if len(resid_array) > 0:
                risk = np.std(resid_array)
                # 确保在合理范围内
                risk = np.clip(risk, 0.01, 0.10)
                specific_risks[ts_code] = risk
        else:
            # 使用指数加权标准差
            decay = 0.5 ** (1 / half_life)
            weights = np.array([decay ** (len(resid_array) - 1 - i) for i in range(len(resid_array))])
            weights = weights / weights.sum()

            # 计算加权均值
            weighted_mean = np.sum(weights * resid_array)

            # 计算加权方差
            weighted_var = np.sum(weights * (resid_array - weighted_mean) ** 2)

            risk = np.sqrt(weighted_var)
            risk = np.clip(risk, 0.01, 0.10)
            specific_risks[ts_code] = risk

    logger.info(f"估计了 {len(specific_risks)} 只股票的特质风险")
    logger.info(f"特质风险均值: {np.mean(list(specific_risks.values())):.4f}")
    logger.info(f"特质风险范围: [{np.min(list(specific_risks.values())):.4f}, {np.max(list(specific_risks.values())):.4f}]")

    return specific_risks


def calculate_factor_volatility(factor_returns: pd.DataFrame) -> Dict[str, float]:
    """计算因子波动率 (年化)"""
    logger.info("计算因子波动率...")

    factor_vols = {}

    for factor in ALL_FACTORS:
        if factor in factor_returns.columns:
            # 计算年化波动率 (假设252个交易日)
            vol = factor_returns[factor].std() * np.sqrt(252)
            factor_vols[factor] = float(vol)

    return factor_vols


def ensure_positive_definite(cov_matrix: pd.DataFrame) -> pd.DataFrame:
    """确保协方差矩阵正定"""
    eigenvalues = np.linalg.eigvals(cov_matrix.values)

    if eigenvalues.min() > 0:
        return cov_matrix

    # 添加正则化项
    lambda_reg = abs(eigenvalues.min()) + 1e-6
    cov_reg = cov_matrix.values + np.eye(cov_matrix.shape[0]) * lambda_reg

    return pd.DataFrame(cov_reg, index=cov_matrix.index, columns=cov_matrix.columns)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="估计Barra CNE5风险模型")
    parser.add_argument('--estimation-window', type=int, default=252, help='估计窗口 (天数)')
    parser.add_argument('--half-life', type=int, default=90, help='指数衰减半衰期 (天数)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Barra CNE5 因子计算 - Step 4: 估计风险模型")
    logger.info("=" * 60)
    logger.info(f"估计窗口: {args.estimation_window} 天")
    logger.info(f"半衰期: {args.half_life} 天")

    # 加载因子收益率
    factor_returns_path = INPUT_DIR / "factor_returns.parquet"
    if not factor_returns_path.exists():
        logger.error(f"找不到因子收益率文件: {factor_returns_path}")
        logger.error("请先运行 step3_factor_returns.py")
        return

    factor_returns = pd.read_parquet(factor_returns_path)
    factor_returns['trade_date'] = pd.to_datetime(factor_returns['trade_date'])
    logger.info(f"加载因子收益率: {len(factor_returns)} 条记录")

    # 加载残差
    residuals_path = INPUT_DIR / "residuals.parquet"
    if not residuals_path.exists():
        logger.error(f"找不到残差文件: {residuals_path}")
        return

    residuals = pd.read_parquet(residuals_path)
    logger.info(f"加载残差: {len(residuals)} 条记录")

    # 估计因子协方差矩阵
    factor_cov = estimate_factor_covariance(factor_returns, args.half_life)

    # 确保正定性
    factor_cov = ensure_positive_definite(factor_cov)

    # 估计特质风险
    specific_risks = estimate_specific_risks(residuals, args.estimation_window, args.half_life)

    # 计算因子波动率
    factor_vols = calculate_factor_volatility(factor_returns)

    # 构建风险参数嵌套格式 (JSON友好)
    factor_cov_nested = {}
    for i, factor1 in enumerate(factor_cov.index):
        factor_cov_nested[factor1] = {}
        for j, factor2 in enumerate(factor_cov.columns):
            factor_cov_nested[factor1][factor2] = float(factor_cov.iloc[i, j])

    # 获取最新日期
    latest_date = factor_returns['trade_date'].max()

    # 构建风险参数
    risk_params = {
        'estimation_date': latest_date.strftime('%Y-%m-%d'),
        'estimation_window': args.estimation_window,
        'half_life': args.half_life,
        'num_factors': len(factor_cov),
        'num_stocks': len(specific_risks),
        'factor_covariance': factor_cov_nested,
        'factor_volatility': factor_vols,
        'specific_risks': {k: float(v) for k, v in specific_risks.items()}
    }

    # 保存风险参数
    output_path = OUTPUT_DIR / "risk_params_latest.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(risk_params, f, ensure_ascii=False, indent=2)

    logger.info(f"风险参数已保存到: {output_path}")

    # 保存特质风险为Parquet
    specific_risks_df = pd.DataFrame([
        {'ts_code': k, 'specific_risk': v}
        for k, v in specific_risks.items()
    ])
    specific_risks_path = OUTPUT_DIR / "specific_risks.parquet"
    specific_risks_df.to_parquet(specific_risks_path, index=False)
    logger.info(f"特质风险已保存到: {specific_risks_path}")

    # 输出统计信息
    logger.info("=" * 60)
    logger.info("风险模型估计完成!")
    logger.info(f"因子数量: {len(factor_cov)}")
    logger.info(f"股票数量: {len(specific_risks)}")
    logger.info("")
    logger.info("风格因子波动率 (年化):")
    for factor in STYLE_FACTORS:
        if factor in factor_vols:
            logger.info(f"  {factor}: {factor_vols[factor]:.4f}")
    logger.info("")
    if len(specific_risks) > 0:
        logger.info(f"特质风险统计:")
        logger.info(f"  均值: {np.mean(list(specific_risks.values())):.4f}")
        logger.info(f"  中位数: {np.median(list(specific_risks.values())):.4f}")
        logger.info(f"  最小值: {np.min(list(specific_risks.values())):.4f}")
        logger.info(f"  最大值: {np.max(list(specific_risks.values())):.4f}")
    else:
        logger.warning("没有特质风险数据（残差数据为空）")
    logger.info("=" * 60)

    # 保存统计报告
    stats = {
        'timestamp': datetime.now().isoformat(),
        'estimation_date': latest_date.strftime('%Y-%m-%d'),
        'estimation_window': args.estimation_window,
        'half_life': args.half_life,
        'num_factors': len(factor_cov),
        'num_stocks': len(specific_risks),
        'factor_volatility': factor_vols,
        'specific_risk_stats': {
            'mean': float(np.mean(list(specific_risks.values()))) if len(specific_risks) > 0 else None,
            'median': float(np.median(list(specific_risks.values()))) if len(specific_risks) > 0 else None,
            'min': float(np.min(list(specific_risks.values()))) if len(specific_risks) > 0 else None,
            'max': float(np.max(list(specific_risks.values()))) if len(specific_risks) > 0 else None,
            'std': float(np.std(list(specific_risks.values()))) if len(specific_risks) > 0 else None
        },
        'output_file': str(output_path)
    }

    stats_path = REPORTS_DIR / "step4_results.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(f"统计报告已保存到: {stats_path}")


if __name__ == "__main__":
    main()
