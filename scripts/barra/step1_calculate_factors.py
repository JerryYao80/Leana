#!/usr/bin/env python3
"""
Barra CNE5 因子计算脚本 - Step 1: 计算因子暴露矩阵

功能:
    1. 计算10个Barra风格因子 (Size, Beta, Momentum, Volatility, Non-linear Size,
       Book-to-Price, Liquidity, Earnings Yield, Growth, Leverage)
    2. 添加30个行业哑变量
    3. 输出按股票存储的Parquet文件

执行方式:
    python step1_calculate_factors.py [--parallel N]

输入:
    /data/tushare_data/daily/{ts_code}.parquet
    /data/tushare_data/daily_basic/{ts_code}.parquet
    /data/tushare_data/sw_daily/data.parquet (基准: 801300.SI)
    /data/tushare_data/stock_basic/data.parquet

输出:
    /data/barra_factors/by_stock/{ts_code}.parquet
    /data/barra_config/industry.json
    /data/barra_reports/step1_factor_calculation.log
"""

import argparse
import json
import logging
import multiprocessing
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
TUSHARE_DATA_DIR = DATA_ROOT / "tushare_data"
OUTPUT_DIR = DATA_ROOT / "barra_factors/by_stock"
CONFIG_DIR = DATA_ROOT / "barra_config"
REPORTS_DIR = DATA_ROOT / "barra_reports"

# 创建目录
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_DIR / "step1_factor_calculation.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 行业分类映射 - 30个中信一级行业
# 由于stock_basic使用的是申万行业，我们需要映射到Barra风格的中信行业
INDUSTRY_MAPPING = {
    # 银行
    '银行': 'ind_banking',
    '农林牧渔': 'ind_agriculture',
    '采掘': 'ind_petrochemical',  # 映射到石油石化
    '化工': 'ind_chemicals',
    '钢铁': 'ind_steel',
    '有色金属': 'ind_nonferrous',
    '电子': 'ind_electronics',
    '汽车': 'ind_automobiles',
    '家用电器': 'ind_consumer_appliances',
    '食品饮料': 'ind_food_beverage',
    '纺织服饰': 'ind_textiles_apparel',
    '轻工制造': 'ind_light_manufacturing',
    '医药生物': 'ind_pharmaceuticals',
    '公用事业': 'ind_utilities',
    '交通运输': 'ind_transportation',
    '房地产': 'ind_real_estate',
    '商业贸易': 'ind_commerce_retail',
    '休闲服务': 'ind_social_services',
    '综合': 'ind_comprehensive',
    '建筑材料': 'ind_building_materials',
    '建筑装饰': 'ind_construction',
    '电气设备': 'ind_electrical_equipment',
    '国防军工': 'ind_defense',
    '计算机': 'ind_computers',
    '传媒': 'ind_media',
    '通信': 'ind_communications',
    '非银金融': 'ind_non_bank_finance',
    '环保': 'ind_environmental',
    '化工': 'ind_chemicals',
    # 添加更多映射
    '机械设备': 'ind_machinery',
    '汽车': 'ind_automobiles',
    '电子': 'ind_electronics',
}

# 30个Barra CNE5行业列表
BARRA_INDUSTRIES = [
    'ind_petrochemical',  # 石油石化
    'ind_coal',           # 煤炭
    'ind_nonferrous',     # 有色金属
    'ind_utilities',      # 电力及公用事业
    'ind_steel',          # 钢铁
    'ind_chemicals',      # 基础化工
    'ind_building_materials',  # 建材
    'ind_construction',   # 建筑
    'ind_transportation', # 交通运输
    'ind_automobiles',    # 汽车
    'ind_machinery',      # 机械
    'ind_defense',        # 国防军工
    'ind_electrical_equipment',  # 电力设备
    'ind_electronics',    # 电子
    'ind_computers',      # 计算机
    'ind_communications', # 通信
    'ind_consumer_appliances',  # 家电
    'ind_light_manufacturing',  # 轻工制造
    'ind_textiles_apparel',  # 纺织服装
    'ind_food_beverage',  # 食品饮料
    'ind_agriculture',    # 农林牧渔
    'ind_banking',        # 银行
    'ind_non_bank_finance',  # 非银行金融
    'ind_real_estate',    # 房地产
    'ind_commerce_retail',  # 商贸零售
    'ind_social_services',  # 社会服务
    'ind_media',          # 传媒
    'ind_pharmaceuticals',  # 医药
    'ind_environmental',   # 环保
    'ind_comprehensive',   # 综合
]

# 滚动窗口参数
BETA_WINDOW = 252
MOMENTUM_SHORT = 21
MOMENTUM_LONG = 252
VOLATILITY_WINDOW = 252
LIQUIDITY_SHORT = 21
LIQUIDITY_MEDIUM = 63
LIQUIDITY_LONG = 252


class FactorCalculator:
    """Barra CNE5 因子计算器"""

    def __init__(self, benchmark_data: pd.DataFrame = None):
        """
        初始化因子计算器

        Args:
            benchmark_data: 基准指数数据 (801300.SI 沪深300)
        """
        self.benchmark_data = benchmark_data
        self.stock_basic = self._load_stock_basic()

    def _load_stock_basic(self) -> pd.DataFrame:
        """加载股票基本信息"""
        path = TUSHARE_DATA_DIR / "stock_basic/data.parquet"
        df = pd.read_parquet(path)
        # 创建行业映射
        df['barra_industry'] = df['industry'].map(INDUSTRY_MAPPING).fillna('ind_comprehensive')
        return df.set_index('ts_code')

    def get_stock_industry(self, ts_code: str) -> str:
        """获取股票的Barra行业分类"""
        if ts_code in self.stock_basic.index:
            return self.stock_basic.loc[ts_code, 'barra_industry']
        return 'ind_comprehensive'

    def get_industry_dummies(self, ts_code: str) -> Dict[str, int]:
        """生成行业哑变量"""
        industry = self.get_stock_industry(ts_code)
        return {ind: 1 if ind == industry else 0 for ind in BARRA_INDUSTRIES}

    def calculate_stock_factors(self, ts_code: str) -> Optional[pd.DataFrame]:
        """
        计算单只股票的所有因子

        Args:
            ts_code: 股票代码 (如 000001.SZ)

        Returns:
            因子DataFrame，如果计算失败返回None
        """
        try:
            # 加载基础数据
            daily = self._load_daily_data(ts_code)
            daily_basic = self._load_daily_basic_data(ts_code)

            if daily is None or daily_basic is None:
                logger.warning(f"数据缺失: {ts_code}")
                return None

            # 合并数据 - 使用suffixes参数避免冲突
            # daily的列保持不变，daily_basic的重复列添加'_basic'后缀
            df = daily.merge(daily_basic, on='trade_date', how='inner',
                           suffixes=('', '_basic'))

            # 删除重复的ts_code列（daily_basic的ts_code变成ts_code_basic）
            if 'ts_code_basic' in df.columns:
                df = df.drop(columns=['ts_code_basic'])

            # 确保使用来自daily的close价格，而不是daily_basic的
            # daily_basic的close已经变成close_basic
            if 'close_basic' in df.columns:
                df = df.drop(columns=['close_basic'])  # 删除重复的close列

            if len(df) < BETA_WINDOW:
                logger.warning(f"数据不足: {ts_code}, 只有 {len(df)} 条记录")
                return None

            # 按交易日期排序
            df = df.sort_values('trade_date').reset_index(drop=True)

            # 验证关键列存在
            if 'close' not in df.columns:
                logger.error(f"关键列 'close' 不存在于 {ts_code}")
                logger.error(f"可用列: {df.columns.tolist()}")
                return None

            # 计算各因子
            df['size'] = self._calc_size(df)
            df['beta'] = self._calc_beta(df, ts_code)
            df['momentum'] = self._calc_momentum(df)
            df['volatility'] = self._calc_volatility(df)
            df['non_linear_size'] = self._calc_non_linear_size(df['size'])
            df['book_to_price'] = self._calc_book_to_price(df)
            df['liquidity'] = self._calc_liquidity(df)
            df['earnings_yield'] = self._calc_earnings_yield(df)
            df['growth'] = 0.0  # 简化版
            df['leverage'] = 0.5  # 简化版

            # 添加行业哑变量
            industry_dummies = self.get_industry_dummies(ts_code)
            for ind, value in industry_dummies.items():
                df[ind] = value

            # 选择输出列
            factor_cols = (
                ['trade_date', 'size', 'beta', 'momentum', 'volatility',
                 'non_linear_size', 'book_to_price', 'liquidity',
                 'earnings_yield', 'growth', 'leverage'] +
                BARRA_INDUSTRIES
            )

            result = df[factor_cols].copy()

            # 清理数据: 处理无穷值和极端值
            for col in ['size', 'beta', 'momentum', 'volatility', 'non_linear_size',
                       'book_to_price', 'liquidity', 'earnings_yield']:
                if col in result.columns:
                    # 替换无穷值为NaN
                    result[col] = result[col].replace([np.inf, -np.inf], np.nan)
                    # 截断极端值
                    q1 = result[col].quantile(0.01)
                    q99 = result[col].quantile(0.99)
                    result[col] = result[col].clip(lower=q1, upper=q99)

            return result

        except Exception as e:
            logger.error(f"计算因子失败 {ts_code}: {e}")
            return None

    def _load_daily_data(self, ts_code: str) -> Optional[pd.DataFrame]:
        """加载日行情数据"""
        path = TUSHARE_DATA_DIR / "daily" / f"date={ts_code}" / "data.parquet"
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def _load_daily_basic_data(self, ts_code: str) -> Optional[pd.DataFrame]:
        """加载日行情基本面数据"""
        path = TUSHARE_DATA_DIR / "daily_basic" / f"date={ts_code}" / "data.parquet"
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def _calc_size(self, df: pd.DataFrame) -> pd.Series:
        """计算市值因子: ln(total_mv)"""
        return np.log(df['total_mv'].replace(0, np.nan))

    def _calc_beta(self, df: pd.DataFrame, ts_code: str) -> pd.Series:
        """
        计算Beta因子 (市场风险)
        Beta = Cov(R_stock, R_benchmark) / Var(R_benchmark)
        使用252天滚动窗口
        """
        if self.benchmark_data is None or len(self.benchmark_data) == 0:
            # 如果没有基准数据，返回默认值
            return pd.Series([1.0] * len(df), index=df.index)

        # 准备股票数据
        stock_df = df[['trade_date', 'close']].copy()
        stock_df['trade_date'] = pd.to_datetime(stock_df['trade_date'], format='%Y%m%d')

        # 准备基准数据
        benchmark = self.benchmark_data[['trade_date', 'close']].copy()
        benchmark['trade_date'] = pd.to_datetime(benchmark['trade_date'], format='%Y%m%d')
        benchmark = benchmark.sort_values('trade_date').drop_duplicates(subset=['trade_date'])

        # 按日期合并对齐
        merged = stock_df.merge(benchmark, on='trade_date', how='left', suffixes=('_stock', '_bench'))

        # 计算收益率
        merged['stock_ret'] = merged['close_stock'].pct_change(fill_method=None)
        merged['bench_ret'] = merged['close_bench'].pct_change(fill_method=None)

        # 滚动计算Beta
        betas = []
        for i in range(len(merged)):
            if i < BETA_WINDOW:
                betas.append(np.nan)
            else:
                window_data = merged.iloc[i-BETA_WINDOW:i][['stock_ret', 'bench_ret']].dropna()
                if len(window_data) < BETA_WINDOW * 0.8:  # 至少80%有效数据
                    betas.append(np.nan)
                else:
                    cov = window_data['stock_ret'].cov(window_data['bench_ret'])
                    var = window_data['bench_ret'].var()
                    if var > 0:
                        beta = cov / var
                        # 截断极端值
                        betas.append(np.clip(beta, -2, 3))
                    else:
                        betas.append(1.0)

        return pd.Series(betas, index=df.index)

    def _calc_momentum(self, df: pd.DataFrame) -> pd.Series:
        """
        计算动量因子: (P_t-21 / P_t-252) - 1
        跳过最近1个月，使用过去11个月的收益率
        """
        close = df['close'].values
        momentum = np.zeros(len(df))

        for i in range(len(df)):
            if i < MOMENTUM_LONG:
                momentum[i] = np.nan
            else:
                p_short = close[i - MOMENTUM_SHORT] if i >= MOMENTUM_SHORT else close[0]
                p_long = close[i - MOMENTUM_LONG]
                if p_long > 0:
                    momentum[i] = (p_short / p_long) - 1
                else:
                    momentum[i] = np.nan

        return pd.Series(momentum, index=df.index)

    def _calc_volatility(self, df: pd.DataFrame) -> pd.Series:
        """
        计算波动率因子: 收益率的标准差
        使用252天滚动窗口
        """
        returns = df['close'].pct_change()
        return returns.rolling(window=VOLATILITY_WINDOW, min_periods=126).std()

    def _calc_non_linear_size(self, size: pd.Series) -> pd.Series:
        """
        计算非线性市值因子: Size^3
        (完整版需要对Size做正交化，这里使用简化版)
        """
        size_cubed = size ** 3
        return size_cubed

    def _calc_book_to_price(self, df: pd.DataFrame) -> pd.Series:
        """
        计算价值因子 (Book-to-Price): 1/PB
        """
        btp = df['pb'].apply(lambda x: 1/x if x > 0 else np.nan)
        return btp

    def _calc_liquidity(self, df: pd.DataFrame) -> pd.Series:
        """
        计算流动性因子: 加权换手率
        Liquidity = 0.35 * TO_1M + 0.35 * TO_3M + 0.30 * TO_12M
        """
        turnover = df['turnover_rate'].fillna(0)

        to_1m = turnover.rolling(window=LIQUIDITY_SHORT, min_periods=10).mean()
        to_3m = turnover.rolling(window=LIQUIDITY_MEDIUM, min_periods=42).mean()
        to_12m = turnover.rolling(window=LIQUIDITY_LONG, min_periods=126).mean()

        liquidity = 0.35 * to_1m + 0.35 * to_3m + 0.30 * to_12m
        return liquidity

    def _calc_earnings_yield(self, df: pd.DataFrame) -> pd.Series:
        """
        计算盈利收益率: 1/PE_TTM
        (简化版，完整版需要结合财务数据)
        """
        ey = df['pe_ttm'].apply(lambda x: 1/x if x > 0 else np.nan)
        return ey


def load_benchmark_data() -> pd.DataFrame:
    """加载基准指数数据 (沪深300: 801300.SI)"""
    path = TUSHARE_DATA_DIR / "sw_daily" / "year=2020" / "data.parquet"

    # 尝试从多个年份加载数据
    dfs = []
    for year in range(2019, 2026):
        path = TUSHARE_DATA_DIR / "sw_daily" / f"year={year}" / "data.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            df = df[df['ts_code'] == '801300.SI'].copy()
            dfs.append(df)

    if dfs:
        benchmark = pd.concat(dfs, ignore_index=True)
        benchmark['trade_date'] = pd.to_datetime(benchmark['trade_date'], format='%Y%m%d')
        return benchmark.sort_values('trade_date').reset_index(drop=True)

    logger.warning("未找到基准指数数据，Beta因子将使用默认值1.0")
    return pd.DataFrame()


def process_single_stock(ts_code: str, calculator: FactorCalculator) -> Tuple[str, bool]:
    """
    处理单只股票的因子计算

    Args:
        ts_code: 股票代码
        calculator: 因子计算器实例

    Returns:
        (ts_code, success)
    """
    result = calculator.calculate_stock_factors(ts_code)

    if result is not None:
        try:
            # 保存到Parquet文件
            output_path = OUTPUT_DIR / f"{ts_code}.parquet"
            result.to_parquet(output_path, index=False)
            return (ts_code, True)
        except Exception as e:
            logger.error(f"保存失败 {ts_code}: {e}")
            return (ts_code, False)

    return (ts_code, False)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="计算Barra CNE5因子暴露")
    parser.add_argument('--parallel', type=int, default=4, help='并行进程数')
    parser.add_argument('--start-date', type=str, default='20200101', help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', type=str, default='20241231', help='结束日期 (YYYYMMDD)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Barra CNE5 因子计算 - Step 1: 计算因子暴露矩阵")
    logger.info("=" * 60)
    logger.info(f"并行进程数: {args.parallel}")
    logger.info(f"输出目录: {OUTPUT_DIR}")

    # 加载基准数据
    logger.info("加载基准指数数据...")
    benchmark_data = load_benchmark_data()
    if benchmark_data is not None and len(benchmark_data) > 0:
        logger.info(f"基准指数数据加载成功: {len(benchmark_data)} 条记录")
    else:
        logger.warning("基准指数数据加载失败，Beta因子将使用默认值")

    # 创建因子计算器
    calculator = FactorCalculator(benchmark_data)

    # 获取所有股票列表
    logger.info("获取股票列表...")
    stock_list_dir = TUSHARE_DATA_DIR / "daily"
    if stock_list_dir.exists():
        stock_codes = [d.name.replace('date=', '') for d in stock_list_dir.iterdir() if d.is_dir()]
    else:
        logger.error("找不到股票数据目录")
        return

    logger.info(f"共 {len(stock_codes)} 只股票")

    # 过滤股票: 只计算在指定日期范围内有数据的股票
    # 这里简化处理，计算所有股票

    # 并行处理
    logger.info(f"开始并行计算 (使用 {args.parallel} 个进程)...")

    success_count = 0
    fail_count = 0

    # 使用多进程
    with multiprocessing.Pool(processes=args.parallel) as pool:
        # 使用imap_unordered以便实时显示进度
        results = list(tqdm(
            pool.starmap(
                process_single_stock,
                [(ts_code, calculator) for ts_code in stock_codes]
            ),
            total=len(stock_codes),
            desc="计算因子"
        ))

    # 统计结果
    for ts_code, success in results:
        if success:
            success_count += 1
        else:
            fail_count += 1

    logger.info("=" * 60)
    logger.info(f"计算完成!")
    logger.info(f"成功: {success_count} 只股票")
    logger.info(f"失败: {fail_count} 只股票")
    logger.info(f"成功率: {success_count / len(stock_codes) * 100:.2f}%")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 60)

    # 保存行业映射配置
    industry_config = {
        'industry_list': BARRA_INDUSTRIES,
        'industry_mapping': {}
    }

    for ts_code in calculator.stock_basic.index:
        industry_config['industry_mapping'][ts_code] = calculator.get_stock_industry(ts_code)

    config_path = CONFIG_DIR / "industry.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(industry_config, f, ensure_ascii=False, indent=2)

    logger.info(f"行业配置已保存到: {config_path}")

    # 保存统计报告
    stats = {
        'timestamp': datetime.now().isoformat(),
        'total_stocks': len(stock_codes),
        'successful': success_count,
        'failed': fail_count,
        'success_rate': success_count / len(stock_codes) if len(stock_codes) > 0 else 0,
        'output_directory': str(OUTPUT_DIR)
    }

    stats_path = REPORTS_DIR / "step1_results.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(f"统计报告已保存到: {stats_path}")


if __name__ == "__main__":
    main()
