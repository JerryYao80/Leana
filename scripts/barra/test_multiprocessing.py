#!/usr/bin/env python3
"""
测试多进程是否正常工作
"""

import os
import time
from multiprocessing import Pool, cpu_count


def heavy_computation(n):
    """模拟CPU密集型计算"""
    result = 0
    for i in range(n):
        result += i ** 2
    return result


def test_sequential():
    """单进程测试"""
    print("\n=== 单进程测试 ===")
    start = time.time()
    results = [heavy_computation(100000) for _ in range(8)]
    elapsed = time.time() - start
    print(f"单进程耗时: {elapsed:.2f}秒")
    return elapsed


def test_multiprocessing():
    """多进程测试"""
    n_cores = min(cpu_count(), 4)
    print(f"\n=== 多进程测试 ({n_cores}核) ===")

    start = time.time()
    with Pool(processes=n_cores) as pool:
        results = pool.map(heavy_computation, [100000] * 8)
    elapsed = time.time() - start
    print(f"多进程耗时: {elapsed:.2f}秒")
    return elapsed


def main():
    print("=" * 50)
    print("多进程功能测试")
    print("=" * 50)
    print(f"系统CPU核心数: {cpu_count()}")

    # 单进程测试
    seq_time = test_sequential()

    # 多进程测试
    para_time = test_multiprocessing()

    # 计算加速比
    speedup = seq_time / para_time
    print("\n" + "=" * 50)
    print(f"加速比: {speedup:.2f}x")
    if speedup > 1.5:
        print("✓ 多进程工作正常!")
    else:
        print("✗ 多进程可能未生效，请检查:")
        print("  1. 是否在支持多进程的环境中运行")
        print("  2. Windows用户需要使用 if __name__ == '__main__': 保护")
        print("  3. 某些IDE的调试器可能禁用多进程")
    print("=" * 50)


if __name__ == '__main__':
    main()
