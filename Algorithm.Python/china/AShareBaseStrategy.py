# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from AlgorithmImports import *
import sqlite3
import os

### <summary>
### A股策略基类
### 提供A股市场通用的交易信号记录和SQLite持久化功能
### </summary>
class AShareBaseStrategy(QCAlgorithm):
    """
    A股策略基类，封装以下功能：
    1. 交易信号记录和标准化输出
    2. SQLite数据库持���化
    3. A股交易时段检查
    4. 股数100股整数倍约束
    """

    def _init_signal_recorder(self, db_name="trading_signals.db"):
        """
        初始化交易信号记录器

        Args:
            db_name: 数据库文件名，默认为 trading_signals.db
        """
        # 交易信号列表（当日）
        self._trading_signals = []

        # SQLite数据库路径 - 使用LEAN的Object Store路径
        try:
            # 尝试获取Object Store根目录
            storage_root = self.ObjectStore.RootPath
            self._db_path = os.path.join(storage_root, db_name)
        except:
            # 降级：使用当前工作目录
            self._db_path = os.path.join(os.getcwd(), db_name)

        # 初始化数据库表
        self._init_database()

    def _init_database(self):
        """初始化SQLite数据库，创建必要的表"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # 交易信号表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trading_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL
                )
            ''')

            # 持仓记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    profit_loss_percent REAL NOT NULL
                )
            ''')

            # 账户总览表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_assets REAL NOT NULL,
                    available_cash REAL NOT NULL
                )
            ''')

            conn.commit()
            conn.close()
        except Exception as e:
            self.Log(f"[AShareBase] 数据库初始化失败: {str(e)}")

    def _is_a_share_trading_time(self):
        """
        检查当前时间是否在A股交易时段内

        A股交易时间：
        - 上午：9:30-11:30
        - 下午：13:00-15:00

        Returns:
            bool: True表示在交易时段内
        """
        hour = self.Time.hour
        minute = self.Time.minute

        # 上午交易时段：9:30-11:30
        morning = (9 < hour or (hour == 9 and minute >= 30)) and (hour < 11 or (hour == 11 and minute <= 30))

        # 下午交易时段：13:00-15:00（包含15:00整）
        afternoon = (hour == 13 and minute >= 0) or (13 < hour < 15) or (hour == 15 and minute == 0)

        return morning or afternoon

    def _record_trading_signal(self, symbol, action, quantity, price):
        """
        记录交易信号

        Args:
            symbol: 股票代码（如"000001"）
            action: 交易动作（"买入" 或 "卖出"）
            quantity: 数量（会自动转为100的整数倍）
            price: 价格

        Note:
            数量会自动调整为100的整数倍（A股最小交易单位）
        """
        # 确保数量是100的整数倍
        quantity = (int(quantity) // 100) * 100
        if quantity < 100:
            quantity = 100

        # 记录信号
        self._trading_signals.append({
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'amount': price * quantity
        })

    def _get_cash_amount(self):
        """获取可用资金金额，支持多货币场景"""
        try:
            # 尝试获取CNY货币
            if hasattr(self.Portfolio.CashBook, '__getitem__'):
                if Currencies.CNY in self.Portfolio.CashBook:
                    return self.Portfolio.CashBook[Currencies.CNY].Amount
            # 降级到总现金
            return self.Portfolio.Cash
        except:
            return self.Portfolio.Cash

    def _format_currency(self, value):
        """格式化货币输出，支持多货币场景"""
        try:
            # 如果有CNY货币，使用CNY格式
            if hasattr(self.Portfolio.CashBook, '__getitem__'):
                if Currencies.CNY in self.Portfolio.CashBook:
                    return f"{value:CNY}"
            # 降级到普通格式
            return f"{value:.2f}"
        except:
            return f"{value:.2f}"

    def _save_signals_to_db(self, timestamp):
        """保存交易信号到数据库"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            for signal in self._trading_signals:
                cursor.execute(
                    "INSERT INTO trading_signals (timestamp, symbol, action, quantity, price, amount) VALUES (?, ?, ?, ?, ?, ?)",
                    (timestamp, signal['symbol'], signal['action'],
                     int(signal['quantity']), signal['price'], signal['amount'])
                )

            conn.commit()
            conn.close()
        except Exception as e:
            self.Log(f"[AShareBase] 保存交易信号失败: {str(e)}")

    def _save_holdings_to_db(self, timestamp):
        """保存持仓信息到数据库"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # 保存所有持仓
            for symbol, holdings in self.Portfolio.items():
                if holdings.Invested:
                    cursor.execute(
                        "INSERT INTO holdings (timestamp, symbol, quantity, cost_price, current_price, profit_loss_percent) VALUES (?, ?, ?, ?, ?, ?)",
                        (timestamp, str(symbol), int(holdings.Quantity),
                         holdings.AveragePrice, holdings.Price,
                         holdings.UnrealizedProfitPercent * 100)
                    )

            # 保存账户总览
            cursor.execute(
                "INSERT INTO account_summary (timestamp, total_assets, available_cash) VALUES (?, ?, ?)",
                (timestamp, self.Portfolio.TotalPortfolioValue, self._get_cash_amount())
            )

            conn.commit()
            conn.close()
        except Exception as e:
            self.Log(f"[AShareBase] 保存持仓信息失败: {str(e)}")

    def _log_trading_signals(self):
        """
        输出格式化的交易信号到日志

        输出格式：
        === YYYY-MM-DD HH:MM:SS 信号 ===
        000001 买入： 300股，成本: 8.00，耗资: 2400.00
        600000 卖出： 500股，成本: 6.00，耗资: 3000.00
        === 合计 ===
        000001 持仓: 400股, 成本: 8.32, 现价: 8.16, 盈亏: -2.52%
        600000 持仓: 100股, 成本: 6.21, 现价: 6.18, 盈亏: -1.29%
        总资产: 999971.00
        可用资金: 998537.00
        """
        if not self._trading_signals:
            return

        timestamp = self.Time.strftime("%Y-%m-%d %H:%M:%S")

        # 输出交易信号
        self.Log(f"=== {timestamp} 信号 ===")
        for signal in self._trading_signals:
            self.Log(f"{signal['symbol']} {signal['action']}： {int(signal['quantity'])}股，成本: {signal['price']:.2f}，耗资: {signal['amount']:.2f}")

        # 输出持仓汇总
        self.Log(f"=== 合计 ===")
        for symbol, holdings in self.Portfolio.items():
            if holdings.Invested:
                self.Log(f"{symbol} 持仓: {int(holdings.Quantity)}股, "
                        f"成本: {holdings.AveragePrice:.2f}, "
                        f"现价: {holdings.Price:.2f}, "
                        f"盈亏: {holdings.UnrealizedProfitPercent:.2%}")

        # 输出账户总览
        self.Log(f"总资产: {self.Portfolio.TotalPortfolioValue:.2f}")
        self.Log(f"可用资金: {self._get_cash_amount():.2f}")

    def _flush_signals(self, save_to_db=True):
        """
        刷新并输出交易信号

        Args:
            save_to_db: 是否保存到数据库，默认True

        Note:
            此方法会清空当日交易信号列表
        """
        if not self._trading_signals:
            return

        timestamp = self.Time.strftime("%Y-%m-%d %H:%M:%S")

        # 输出信号到日志
        self._log_trading_signals()

        # 保存到数据库
        if save_to_db:
            self._save_signals_to_db(timestamp)
            self._save_holdings_to_db(timestamp)

        # 清空信号列表
        self._trading_signals = []

    def OnEndOfDay(self):
        """
        每日收盘时调用（子类可覆盖此方法）

        基类实现：自动输出交易信号
        """
        # 输出当日交易信号（如果有）
        if self._trading_signals:
            self._flush_signals()
        else:
            # 即使没有交易信号，也确保列表为空以备下一天使用
            self._trading_signals = []
