import pandas as pd

def execute_parquet_to_txt_export(input_path, output_path, delimiter='\t'):
    """
    执行 Parquet 到 TXT 的数据转换作业
    
    参数:
    input_path (str): 源 Parquet 文件路径
    output_path (str): 目标文本文件路径
    delimiter (str): 文本数据分隔符，默认为制表符
    """
    # 建立底层解析引擎并加载二进制数据
    # 要求环境已安装 pyarrow 或 fastparquet
    data_frame = pd.read_parquet(input_path)

    # 实施持久化转换
    # 排除行索引以维持数据块的纯净度
    data_frame.to_csv(
        output_path, 
        sep=delimiter, 
        index=False, 
        encoding='utf-8'
    )

if __name__ == "__main__":
    # 配置输入与输出参数
    SOURCE_FILE = "/home/project/tushare-downloader/tushare_data/index_basic/data.parquet"
    TARGET_FILE = 'output_data.txt'

    # 启动转换流程
    execute_parquet_to_txt_export(SOURCE_FILE, TARGET_FILE)

