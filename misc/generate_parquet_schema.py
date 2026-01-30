#!/usr/bin/env python3
"""
扫描多层嵌套目录结构，提取所有parquet文件的表结构信息
生成 tushare-dir.json 文件，包含每个parquet文件的路径和列结构
"""

import os
import json
from pathlib import Path
import pyarrow.parquet as pq


def find_parquet_files(root_dir):
    """
    递归查找所有parquet文件
    
    Args:
        root_dir: 根目录路径
        
    Returns:
        list: 所有parquet文件的绝对路径列表
    """
    parquet_files = []
    root_path = Path(root_dir)
    
    if not root_path.exists():
        print(f"警告: 目录不存在 - {root_dir}")
        return parquet_files
    
    # 递归查找所有.parquet文件
    for parquet_file in root_path.rglob("*.parquet"):
        if parquet_file.is_file():
            parquet_files.append(str(parquet_file))
    
    return parquet_files


def get_parquet_schema(file_path):
    """
    读取parquet文件的表结构信息
    
    Args:
        file_path: parquet文件路径
        
    Returns:
        list: 列名列表，如果读取失败返回None
    """
    try:
        # 读取parquet文件的schema - 使用 to_arrow_schema() 转换为Arrow schema
        parquet_file = pq.ParquetFile(file_path)
        schema = parquet_file.schema.to_arrow_schema()
        
        # 提取列名和类型信息
        columns = []
        for field in schema:
            columns.append({
                "name": field.name,
                "type": str(field.type)
            })
        
        return columns
    except Exception as e:
        print(f"读取文件失败 {file_path}: {str(e)}")
        return None


def generate_schema_json(root_dirs, output_file):
    """
    生成包含所有parquet文件schema信息的JSON文件
    
    Args:
        root_dirs: 要扫描的根目录列表
        output_file: 输出JSON文件路径
    """
    schema_dict = {}
    
    # 如果传入的是字符串，转为列表
    if isinstance(root_dirs, str):
        root_dirs = [root_dirs]
    
    # 扫描所有指定的根目录
    for root_dir in root_dirs:
        print(f"扫描目录: {root_dir}")
        parquet_files = find_parquet_files(root_dir)
        print(f"找到 {len(parquet_files)} 个parquet文件")
        
        # 提取每个文件的schema
        for file_path in parquet_files:
            print(f"处理: {file_path}")
            schema = get_parquet_schema(file_path)
            
            if schema is not None:
                # 使用相对路径作为key（相对于项目根目录）
                try:
                    # 尝试获取相对路径
                    project_root = Path(__file__).parent.parent
                    rel_path = str(Path(file_path).relative_to(project_root))
                except ValueError:
                    # 如果无法获取相对路径，使用绝对路径
                    rel_path = file_path
                
                schema_dict[rel_path] = schema
    
    # 写入JSON文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schema_dict, f, ensure_ascii=False, indent=2)
    
    print(f"\n生成完成! 输出文件: {output_file}")
    print(f"共处理 {len(schema_dict)} 个parquet文件")


def main():
    """主函数"""
    # 设置要扫描的目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # 可以配置多个扫描目录
    scan_dirs = [
        #"/home/project/ccleana/data/tmp_data",
        "/home/project/ccleana/data/tushare_data",  # LEAN项目的Data目录
        # 可以添加更多目录
        # project_root / "另一个目录",
    ]
    
    # 只扫描存在的目录
    existing_dirs = [str(d) for d in scan_dirs if Path(d).exists()]
    
    if not existing_dirs:
        print("警告: 没有找到任何要扫描的目录")
        print("请检查以下目录是否存在:")
        for d in scan_dirs:
            print(f"  - {d}")
        return
    
    # 输出文件路径
    output_file = script_dir / "tushare-dir.json"
    
    # 生成schema JSON文件
    generate_schema_json(existing_dirs, str(output_file))


if __name__ == "__main__":
    main()
