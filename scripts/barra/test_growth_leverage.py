#!/usr/bin/env python3
"""
测试Growth和Leverage因子计算

验证修复后的因子计算是否正常工作
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

# 添加脚本路径
sys.path.insert(0, str(Path(__file__).parent))

from step1_calculate_factors import FactorCalculator, load_benchmark_data

DATA_ROOT = Path("/home/project/ccleana/data")
TUSHARE_DATA_DIR = DATA_ROOT / "tushare_data"


def test_growth_leverage():
    """测试Growth和Leverage因子计算"""
    print("=" * 60)
    print("Testing Growth and Leverage Factor Calculation")
    print("=" * 60)

    # 加载基准数据
    benchmark_data = load_benchmark_data()
    calculator = FactorCalculator(benchmark_data)

    # 测试股票列表（选择几只大盘股）
    test_stocks = ['000001.SZ', '600000.SH', '000002.SZ']

    for ts_code in test_stocks:
        print(f"\nTesting {ts_code}...")

        # 加载日行情数据
        daily_file = TUSHARE_DATA_DIR / "daily" / f"date={ts_code}" / "data.parquet"

        if not daily_file.exists():
            print(f"  ❌ Daily data not found")
            continue

        df_daily = pd.read_parquet(daily_file)
        print(f"  ✓ Loaded {len(df_daily)} days of daily data")

        # 测试Growth因子
        print(f"\n  Testing Growth factor...")
        income_file = TUSHARE_DATA_DIR / "income" / f"date={ts_code}" / "data.parquet"

        if income_file.exists():
            growth_series = calculator._calc_growth(ts_code, df_daily)
            growth_value = growth_series.iloc[0] if len(growth_series) > 0 else np.nan

            if pd.isna(growth_value):
                print(f"    ⚠️  Growth = NaN (insufficient data)")
            else:
                print(f"    ✓ Growth = {growth_value:.4f}")
        else:
            print(f"    ⚠️  Income data not found (will use NaN)")

        # 测试Leverage因子
        print(f"\n  Testing Leverage factor...")
        fina_file = TUSHARE_DATA_DIR / "fina_indicator" / f"date={ts_code}" / "data.parquet"

        if fina_file.exists():
            leverage_series = calculator._calc_leverage(ts_code, df_daily)
            leverage_value = leverage_series.iloc[0] if len(leverage_series) > 0 else np.nan

            if pd.isna(leverage_value):
                print(f"    ⚠️  Leverage = NaN (insufficient data)")
            else:
                print(f"    ✓ Leverage = {leverage_value:.4f}")
        else:
            print(f"    ⚠️  Financial indicator data not found (will use NaN)")

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("\nIf financial data is not available:")
    print("  - Growth and Leverage will be NaN (not 0.0 or 0.5)")
    print("  - This is correct behavior - factors will be excluded from calculations")
    print("\nTo download financial data:")
    print("  python scripts/tushare/download_financial_data.py --token YOUR_TOKEN")
    print("=" * 60)


if __name__ == "__main__":
    test_growth_leverage()
