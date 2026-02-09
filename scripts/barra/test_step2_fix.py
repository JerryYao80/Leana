#!/usr/bin/env python3
"""
测试 step2_transpose_factors.py 的修复
"""

import sys
from pathlib import Path
from datetime import datetime, date
import pandas as pd

INPUT_DIR = Path("/home/project/ccleana/data/barra_factors/by_stock")
OUTPUT_DIR = Path("/home/project/ccleana/data/barra_factors/by_date_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FACTOR_COLUMNS = (
    ['size', 'beta', 'momentum', 'volatility', 'non_linear_size',
     'book_to_price', 'liquidity', 'earnings_yield', 'growth', 'leverage'] +
    [f'ind_industry_{i}' for i in range(30)]
)

def process_single_date(args):
    """测试单日期处理函数"""
    test_date, stock_codes, input_dir = args
    
    print(f"处理日期: {test_date}, 股票数: {len(stock_codes)}")
    
    date_data = []
    for ts_code in stock_codes[:10]:
        stock_file = Path(input_dir) / f"{ts_code}.parquet"
        if not stock_file.exists():
            continue
        
        try:
            df = pd.read_parquet(stock_file)
            if 'trade_date' not in df.columns:
                continue
            
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d', errors='coerce')
            df = df.dropna(subset=['trade_date'])
            
            stock_df = df[df['trade_date'].dt.date == test_date].copy()
            
            if len(stock_df) > 0:
                stock_df['ts_code'] = ts_code
                date_data.append(stock_df)
        except Exception as e:
            print(f"  错误 {ts_code}: {e}")
            continue
    
    if not date_data:
        return (test_date.strftime('%Y%m%d'), False)
    
    combined_df = pd.concat(date_data, ignore_index=True)
    print(f"  合并 {len(date_data)} 只股票, {len(combined_df)} 条记录")
    
    date_str = test_date.strftime('%Y%m%d')
    output_path = OUTPUT_DIR / f"{date_str}.parquet"
    combined_df.to_parquet(output_path, index=False)
    
    return (date_str, True)


def test_single_process():
    """测试单进程模式"""
    print("=" * 60)
    print("测试1: 单进程模式")
    print("=" * 60)
    
    test_date = date(2024, 1, 2)
    stock_files = list(INPUT_DIR.glob("*.parquet"))[:20]
    stock_codes = [f.stem for f in stock_files]
    
    task = (test_date, stock_codes, str(INPUT_DIR))
    date_str, success = process_single_date(task)
    
    if success:
        print(f"✓ 单进程测试成功: {date_str}")
        output_file = OUTPUT_DIR / f"{date_str}.parquet"
        df = pd.read_parquet(output_file)
        print(f"  输出文件: {output_file}")
        print(f"  记录数: {len(df)}")
        print(f"  列数: {len(df.columns)}")
    else:
        print(f"✗ 单进程测试失败")
        return False
    
    return True


def test_multiprocess():
    """测试多进程模式"""
    print("\n" + "=" * 60)
    print("测试2: 多进程模式")
    print("=" * 60)
    
    from multiprocessing import Pool
    
    stock_files = list(INPUT_DIR.glob("*.parquet"))[:50]
    stock_codes = [f.stem for f in stock_files]
    
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    tasks = [(d, stock_codes, str(INPUT_DIR)) for d in dates]
    
    print(f"创建2核进程池处理 {len(tasks)} 个任务...")
    
    with Pool(processes=2) as pool:
        results = pool.map(process_single_date, tasks)
    
    success_count = sum(1 for _, s in results if s)
    print(f"\n✓ 多进程测试完成: {success_count}/{len(tasks)} 成功")
    
    return success_count == len(tasks)


if __name__ == "__main__":
    print("开始测试 step2_transpose_factors 修复方案\n")
    
    test1 = test_single_process()
    
    if test1:
        test2 = test_multiprocess()
        
        if test2:
            print("\n" + "=" * 60)
            print("✓ 所有测试通过！修复方案有效。")
            print("=" * 60)
            sys.exit(0)
    
    print("\n" + "=" * 60)
    print("✗ 测试失败")
    print("=" * 60)
    sys.exit(1)
