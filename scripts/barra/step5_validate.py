#!/usr/bin/env python3
"""
Barra CNE5 因子计算脚本 - Step 5: 验证数据质量

功能:
    1. 检查数据完整性
    2. 分析数据质量
    3. 验证数学性质
    4. 生成HTML验证报告

执行方式:
    python step5_validate.py

输入:
    /data/barra_factors/by_stock/*.parquet
    /data/barra_factors/by_date/*.parquet
    /data/barra_risk/factor_returns.parquet
    /data/barra_risk/risk_params_latest.json
    /data/barra_risk/specific_risks.parquet

输出:
    /data/barra_reports/validation_report.html
    /data/barra_reports/step5_validation.log
"""

import base64
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 非GUI后端
import matplotlib.pyplot as plt
import seaborn as sns

# 配置路径
DATA_ROOT = Path("/home/project/ccleana/data")
FACTOR_BY_STOCK_DIR = DATA_ROOT / "barra_factors/by_stock"
FACTOR_BY_DATE_DIR = DATA_ROOT / "barra_factors/by_date"
RISK_DIR = DATA_ROOT / "barra_risk"
REPORTS_DIR = DATA_ROOT / "barra_reports"

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(REPORTS_DIR / "step5_validation.log"),
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


class DataValidator:
    """数据验证器"""

    def __init__(self):
        self.validation_results = {
            'completeness': {},
            'quality': {},
            'math_properties': {},
            'issues': []
        }

    def check_completeness(self) -> Dict:
        """检查数据完整性"""
        logger.info("检查数据完整性...")

        results = {
            'by_stock_files': 0,
            'by_date_files': 0,
            'factor_returns_rows': 0,
            'residuals_rows': 0,
            'risk_params_exists': False,
            'specific_risks_rows': 0
        }

        # 检查by_stock文件
        by_stock_files = list(FACTOR_BY_STOCK_DIR.glob("*.parquet"))
        results['by_stock_files'] = len(by_stock_files)
        logger.info(f"  by_stock文件数: {len(by_stock_files)}")

        # 检查by_date文件
        by_date_files = list(FACTOR_BY_DATE_DIR.glob("*.parquet"))
        results['by_date_files'] = len(by_date_files)
        logger.info(f"  by_date文件数: {len(by_date_files)}")

        # 检查factor_returns
        factor_returns_path = RISK_DIR / "factor_returns.parquet"
        if factor_returns_path.exists():
            df = pd.read_parquet(factor_returns_path)
            results['factor_returns_rows'] = len(df)
            logger.info(f"  factor_returns行数: {len(df)}")
        else:
            self.validation_results['issues'].append("缺少factor_returns.parquet")

        # 检查residuals
        residuals_path = RISK_DIR / "residuals.parquet"
        if residuals_path.exists():
            df = pd.read_parquet(residuals_path)
            results['residuals_rows'] = len(df)
            logger.info(f"  residuals行数: {len(df)}")
        else:
            self.validation_results['issues'].append("缺少residuals.parquet")

        # 检查risk_params
        risk_params_path = RISK_DIR / "risk_params_latest.json"
        results['risk_params_exists'] = risk_params_path.exists()
        if not risk_params_path.exists():
            self.validation_results['issues'].append("缺少risk_params_latest.json")

        # 检查specific_risks
        specific_risks_path = RISK_DIR / "specific_risks.parquet"
        if specific_risks_path.exists():
            df = pd.read_parquet(specific_risks_path)
            results['specific_risks_rows'] = len(df)
            logger.info(f"  specific_risks行数: {len(df)}")
        else:
            self.validation_results['issues'].append("缺少specific_risks.parquet")

        self.validation_results['completeness'] = results
        return results

    def check_data_quality(self, sample_stocks: int = 100) -> Dict:
        """检查数据质量"""
        logger.info("检查数据质量...")

        results = {
            'missing_ratio': {},
            'outlier_ratio': {},
            'factor_stats': {}
        }

        # 采样检查
        by_stock_files = list(FACTOR_BY_STOCK_DIR.glob("*.parquet"))[:sample_stocks]

        missing_ratios = []
        outlier_ratios = []

        for file_path in by_stock_files:
            try:
                df = pd.read_parquet(file_path)

                for factor in STYLE_FACTORS:
                    if factor in df.columns:
                        # 缺失值比例
                        missing_ratio = df[factor].isna().sum() / len(df)
                        missing_ratios.append(missing_ratio)

                        # 异常值比例 (超过3倍标准差)
                        if df[factor].notna().sum() > 0:
                            mean = df[factor].mean()
                            std = df[factor].std()
                            if std > 0:
                                outlier_count = ((df[factor] - mean).abs() > 3 * std).sum()
                                outlier_ratio = outlier_count / len(df)
                                outlier_ratios.append(outlier_ratio)

                        # 因子统计
                        if factor not in results['factor_stats']:
                            results['factor_stats'][factor] = {
                                'samples': 0,
                                'means': [],
                                'stds': []
                            }

                        if df[factor].notna().sum() > 0:
                            results['factor_stats'][factor]['samples'] += 1
                            results['factor_stats'][factor]['means'].append(df[factor].mean())
                            results['factor_stats'][factor]['stds'].append(df[factor].std())

            except Exception as e:
                logger.warning(f"检查文件失败 {file_path.name}: {e}")

        # 汇总统计
        if missing_ratios:
            results['missing_ratio'] = {
                'mean': float(np.mean(missing_ratios)),
                'max': float(np.max(missing_ratios))
            }
            logger.info(f"  缺失值比例 - 均值: {results['missing_ratio']['mean']:.4f}, 最大: {results['missing_ratio']['max']:.4f}")

            if results['missing_ratio']['mean'] > 0.05:
                self.validation_results['issues'].append(f"缺失值比例过高: {results['missing_ratio']['mean']:.2%}")

        if outlier_ratios:
            results['outlier_ratio'] = {
                'mean': float(np.mean(outlier_ratios)),
                'max': float(np.max(outlier_ratios))
            }
            logger.info(f"  异常值比例 - 均值: {results['outlier_ratio']['mean']:.4f}, 最大: {results['outlier_ratio']['max']:.4f}")

        # 计算各因子汇总统计
        for factor, stats in results['factor_stats'].items():
            if stats['means']:
                results['factor_stats'][factor]['mean'] = float(np.mean(stats['means']))
                results['factor_stats'][factor]['std'] = float(np.mean(stats['stds']))
                logger.info(f"  {factor}: 均值={results['factor_stats'][factor]['mean']:.4f}, 标准差={results['factor_stats'][factor]['std']:.4f}")

        self.validation_results['quality'] = results
        return results

    def check_math_properties(self) -> Dict:
        """检查数学性质"""
        logger.info("检查数学性质...")

        results = {
            'covariance_positive_definite': False,
            'covariance_eigenvalues': [],
            'factor_returns_near_zero': False,
            'specific_risks_reasonable': False
        }

        # 加载风险参数
        risk_params_path = RISK_DIR / "risk_params_latest.json"
        if risk_params_path.exists():
            with open(risk_params_path, 'r') as f:
                risk_params = json.load(f)

            # 检查协方差矩阵
            cov_nested = risk_params.get('factor_covariance', {})
            if cov_nested:
                factors = list(cov_nested.keys())
                n = len(factors)
                cov_matrix = np.zeros((n, n))

                for i, f1 in enumerate(factors):
                    for j, f2 in enumerate(factors):
                        cov_matrix[i, j] = cov_nested[f1].get(f2, 0)

                eigenvalues = np.linalg.eigvals(cov_matrix)
                results['covariance_eigenvalues'] = [float(e) for e in eigenvalues]

                if np.all(eigenvalues > 0):
                    results['covariance_positive_definite'] = True
                    logger.info(f"  协方差矩阵正定: 是 (最小特征值: {eigenvalues.min():.6f})")
                else:
                    logger.warning(f"  协方差矩阵非正定 (最小特征值: {eigenvalues.min():.6f})")
                    self.validation_results['issues'].append("协方差矩阵非正定")

            # 检查因子收益率均值
            factor_returns_path = RISK_DIR / "factor_returns.parquet"
            if factor_returns_path.exists():
                df = pd.read_parquet(factor_returns_path)
                for factor in STYLE_FACTORS:
                    if factor in df.columns:
                        mean_return = df[factor].mean()
                        logger.info(f"  {factor} 收益率均值: {mean_return:.6f}")

                        if abs(mean_return) < 0.01:
                            results['factor_returns_near_zero'] = True

            # 检查特质风险
            specific_risks = risk_params.get('specific_risks', {})
            if specific_risks:
                risks = list(specific_risks.values())
                results['specific_risks_reasonable'] = all(0.01 <= r <= 0.10 for r in risks)

                logger.info(f"  特质风险范围: [{min(risks):.4f}, {max(risks):.4f}]")

                if not results['specific_risks_reasonable']:
                    self.validation_results['issues'].append("特质风险超出合理范围")

        self.validation_results['math_properties'] = results
        return results

    def generate_factor_distribution_plot(self) -> str:
        """生成因子分布图"""
        logger.info("生成因子分布图...")

        by_stock_files = list(FACTOR_BY_STOCK_DIR.glob("*.parquet"))[:50]

        fig, axes = plt.subplots(2, 5, figsize=(15, 8))
        fig.suptitle('Barra CNE5 风格因子分布', fontsize=14)

        for i, factor in enumerate(STYLE_FACTORS):
            ax = axes[i // 5, i % 5]

            factor_values = []
            for file_path in by_stock_files:
                try:
                    df = pd.read_parquet(file_path)
                    if factor in df.columns:
                        factor_values.extend(df[factor].dropna().tolist())
                except:
                    pass

            if factor_values:
                ax.hist(factor_values, bins=50, alpha=0.7, edgecolor='black')
                ax.set_title(f'{factor}')
                ax.set_xlabel('Value')
                ax.set_ylabel('Frequency')
                ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存为base64
        import io
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return img_base64

    def generate_correlation_heatmap(self) -> str:
        """生成因子相关性热力图"""
        logger.info("生成因子相关性热力图...")

        # 收集因子数据
        factor_data = []
        by_stock_files = list(FACTOR_BY_STOCK_DIR.glob("*.parquet"))[:100]

        for file_path in by_stock_files:
            try:
                df = pd.read_parquet(file_path)
                # 取最后一行
                if len(df) > 0:
                    last_row = df.iloc[-1].to_dict()
                    factor_data.append(last_row)
            except:
                pass

        if not factor_data:
            return ""

        df = pd.DataFrame(factor_data)
        corr = df[STYLE_FACTORS].corr()

        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                   square=True, linewidths=0.5, cbar_kws={"shrink": 0.8},
                   ax=ax)
        ax.set_title('Barra CNE5 风格因子相关性矩阵', fontsize=14)

        plt.tight_layout()

        # 保存为base64
        import io
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return img_base64

    def generate_factor_returns_plot(self) -> str:
        """生成因子收益率时间序列图"""
        logger.info("生成因子收益率时间序列图...")

        factor_returns_path = RISK_DIR / "factor_returns.parquet"
        if not factor_returns_path.exists():
            return ""

        df = pd.read_parquet(factor_returns_path)
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        fig, axes = plt.subplots(2, 5, figsize=(15, 8))
        fig.suptitle('Barra CNE5 风格因子收益率时间序列', fontsize=14)

        for i, factor in enumerate(STYLE_FACTORS):
            ax = axes[i // 5, i % 5]

            if factor in df.columns:
                ax.plot(df['trade_date'], df[factor].cumsum(), linewidth=1)
                ax.set_title(f'{factor}')
                ax.set_xlabel('Date')
                ax.set_ylabel('Cumulative Return')
                ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存为base64
        import io
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return img_base64

    def generate_specific_risk_plot(self) -> str:
        """生成特质风险分布图"""
        logger.info("生成特质风险分布图...")

        specific_risks_path = RISK_DIR / "specific_risks.parquet"
        if not specific_risks_path.exists():
            return ""

        df = pd.read_parquet(specific_risks_path)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(df['specific_risk'], bins=50, alpha=0.7, edgecolor='black')
        ax.set_title('特质风险分布', fontsize=14)
        ax.set_xlabel('Specific Risk')
        ax.set_ylabel('Frequency')
        ax.axvline(df['specific_risk'].mean(), color='red', linestyle='--',
                  label=f'Mean: {df["specific_risk"].mean():.4f}')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存为base64
        import io
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return img_base64

    def generate_html_report(self) -> str:
        """生成HTML验证报告"""
        logger.info("生成HTML验证报告...")

        completeness = self.validation_results.get('completeness', {})
        quality = self.validation_results.get('quality', {})
        math_props = self.validation_results.get('math_properties', {})
        issues = self.validation_results.get('issues', [])

        # 生成图表
        dist_plot = self.generate_factor_distribution_plot()
        corr_plot = self.generate_correlation_heatmap()
        returns_plot = self.generate_factor_returns_plot()
        risk_plot = self.generate_specific_risk_plot()

        # 构建HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barra CNE5 数据验证报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #666;
            margin-top: 30px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .status-pass {{ color: #4CAF50; font-weight: bold; }}
        .status-fail {{ color: #f44336; font-weight: bold; }}
        .status-warn {{ color: #ff9800; font-weight: bold; }}
        .chart {{
            margin: 30px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .summary {{
            background-color: #e8f5e8;
            padding: 20px;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .issue {{
            background-color: #ffebee;
            padding: 10px;
            margin: 5px 0;
            border-left: 3px solid #f44336;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Barra CNE5 数据验证报告</h1>
        <p style="color: #666;">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <h2>验证总结</h2>
            <p><strong>总状态:</strong> {'<span class="status-pass">通过</span>' if not issues else '<span class="status-warn">警告</span>'}</p>
            <p><strong>问题数量:</strong> {len(issues)}</p>
        </div>

        <h2>1. 数据完整性</h2>
        <table>
            <tr><th>检查项</th><th>结果</th></tr>
            <tr><td>按股票存储文件数</td><td>{completeness.get('by_stock_files', 0)}</td></tr>
            <tr><td>按日期存储文件数</td><td>{completeness.get('by_date_files', 0)}</td></tr>
            <tr><td>因子收益率记录数</td><td>{completeness.get('factor_returns_rows', 0)}</td></tr>
            <tr><td>残差记录数</td><td>{completeness.get('residuals_rows', 0)}</td></tr>
            <tr><td>特质风险记录数</td><td>{completeness.get('specific_risks_rows', 0)}</td></tr>
            <tr><td>风险参数文件</td><td>{'存在' if completeness.get('risk_params_exists') else '<span class="status-fail">缺失</span>'}</td></tr>
        </table>

        <h2>2. 数据质量</h2>
        <table>
            <tr><th>检查项</th><th>结果</th></tr>
            <tr><td>缺失值比例 (均值)</td><td>{quality.get('missing_ratio', {}).get('mean', 0):.2%}</td></tr>
            <tr><td>缺失值比例 (最大)</td><td>{quality.get('missing_ratio', {}).get('max', 0):.2%}</td></tr>
            <tr><td>异常值比例 (均值)</td><td>{quality.get('outlier_ratio', {}).get('mean', 0):.2%}</td></tr>
            <tr><td>异常值比例 (最大)</td><td>{quality.get('outlier_ratio', {}).get('max', 0):.2%}</td></tr>
        </table>

        <h2>3. 数学性质</h2>
        <table>
            <tr><th>检查项</th><th>结果</th></tr>
            <tr><td>协方差矩阵正定</td><td>{'<span class="status-pass">是</span>' if math_props.get('covariance_positive_definite') else '<span class="status-fail">否</span>'}</td></tr>
            <tr><td>最小特征值</td><td>{min(math_props.get('covariance_eigenvalues', [0])):.6f}</td></tr>
            <tr><td>因子收益率接近零</td><td>{'<span class="status-pass">是</span>' if math_props.get('factor_returns_near_zero') else '<span class="status-warn">否</span>'}</td></tr>
            <tr><td>特质风险合理范围</td><td>{'<span class="status-pass">是</span>' if math_props.get('specific_risks_reasonable') else '<span class="status-fail">否</span>'}</td></tr>
        </table>

        <h2>4. 数据可视化</h2>

        <div class="chart">
            <h3>4.1 因子分布</h3>
            <img src="data:image/png;base64,{dist_plot}" alt="因子分布">
        </div>

        <div class="chart">
            <h3>4.2 因子相关性矩阵</h3>
            <img src="data:image/png;base64,{corr_plot}" alt="相关性矩阵">
        </div>

        <div class="chart">
            <h3>4.3 因子收益率时间序列 (累计)</h3>
            <img src="data:image/png;base64,{returns_plot}" alt="因子收益率">
        </div>

        <div class="chart">
            <h3>4.4 特质风险分布</h3>
            <img src="data:image/png;base64,{risk_plot}" alt="特质风险分布">
        </div>

        <h2>5. 问题列表</h2>
        """

        if issues:
            for issue in issues:
                html += f'<div class="issue">⚠ {issue}</div>'
        else:
            html += '<p style="color: #4CAF50;">✓ 未发现数据质量问题</p>'

        html += """
    </div>
</body>
</html>"""

        return html


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Barra CNE5 因子计算 - Step 5: 数据验证")
    logger.info("=" * 60)

    # 检查目录是否存在
    if not FACTOR_BY_STOCK_DIR.exists():
        logger.error(f"找不到因子数据目录: {FACTOR_BY_STOCK_DIR}")
        logger.error("请先运行 step1_calculate_factors.py")
        return

    # 创建验证器
    validator = DataValidator()

    # 执行各项检查
    validator.check_completeness()
    validator.check_data_quality(sample_stocks=100)
    validator.check_math_properties()

    # 生成HTML报告
    logger.info("生成验证报告...")
    html_report = validator.generate_html_report()

    # 保存报告
    report_path = REPORTS_DIR / "validation_report.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_report)

    logger.info(f"验证报告已保存到: {report_path}")

    # 输出总结
    issues = validator.validation_results.get('issues', [])
    logger.info("=" * 60)
    if not issues:
        logger.info("✓ 数据验证通过!")
    else:
        logger.warning(f"⚠ 发现 {len(issues)} 个问题:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
