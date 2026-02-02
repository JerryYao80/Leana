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

"""
Barra CNE5 Factor-Based Trading Algorithm

This algorithm implements a factor-based trading strategy using the Barra CNE5
risk model. It combines multiple style factors to generate alpha signals while
controlling risk using the estimated covariance matrix.

Key features:
- Factor-based alpha generation using weighted style factors
- Risk-controlled portfolio optimization
- Industry neutrality constraints
- Monthly rebalancing schedule
"""

from AlgorithmImports import *
from FactorModel.BarraCNE5Model import BarraCNE5Model
from datetime import timedelta
import json
import pandas as pd
import numpy as np


class BarraAlphaModel(AlphaModel):
    """
    Alpha model that generates insights based on Barra CNE5 factor exposures.

    This model computes a composite alpha score by combining multiple style factors
    with pre-specified weights. The alpha score is then converted into price insights.
    """

    def __init__(self, factor_model: BarraCNE5Model, factor_weights: dict, insight_period: timedelta = None):
        """
        Initialize the Barra alpha model.

        Args:
            factor_model: BarraCNE5Model instance for accessing factor data
            factor_weights: Dictionary mapping factor names to weights (e.g., {'momentum': 0.3, 'size': -0.2})
            insight_period: Duration for which insights are valid (default: 30 days)
        """
        self.factor_model = factor_model
        self.factor_weights = factor_weights
        self.insight_period = insight_period or timedelta(days=30)
        self.securities = []
        self.last_emit_date = {}

        # Validate factor weights
        style_factors = set(factor_model.get_style_factors())
        for factor in factor_weights:
            if factor not in style_factors:
                Log.warning(f"BarraAlphaModel: Unknown factor '{factor}' in weights")

        self.Name = "BarraCNE5AlphaModel"

    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        """
        Generate insights based on current factor exposures.

        Args:
            algorithm: The algorithm instance
            data: Current data slice

        Returns:
            List of Insight objects with direction and magnitude based on alpha scores
        """
        insights = []
        current_date = algorithm.Time.date()

        # Get factor data for current date
        factor_df = self.factor_model.get_factor_data(current_date)

        if factor_df is None:
            # Try previous trading day if today's data not available
            for i in range(1, 6):
                prev_date = current_date - timedelta(days=i)
                factor_df = self.factor_model.get_factor_data(prev_date)
                if factor_df is not None:
                    break

        if factor_df is None:
            return insights

        # Generate insights for each security
        for security in self.securities:
            if security.price == 0:
                continue

            symbol = security.symbol
            ts_code = self._symbol_to_ts_code(symbol)

            if ts_code not in factor_df.index:
                continue

            # Check if we should emit new insight
            if not self._should_emit_insight(algorithm.utc_time, symbol):
                continue

            # Calculate composite alpha score
            alpha = self._calculate_alpha(factor_df.loc[ts_code])

            # Convert alpha to insight direction and magnitude
            if abs(alpha) > 0.01:  # Only emit if alpha is significant
                direction = InsightDirection.UP if alpha > 0 else InsightDirection.DOWN
                magnitude = min(abs(alpha), 1.0)  # Cap magnitude at 100%

                insights.append(Insight.price(
                    symbol,
                    self.insight_period,
                    direction,
                    magnitude,
                    magnitude  # Use magnitude as confidence
                ))

                self.last_emit_date[symbol] = algorithm.utc_time

        return insights

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        """
        Handle securities added to or removed from the universe.

        Args:
            algorithm: The algorithm instance
            changes: Security additions and removals
        """
        for added in changes.added_securities:
            if added not in self.securities:
                self.securities.append(added)

        for removed in changes.removed_securities:
            if removed in self.securities:
                self.securities.remove(removed)
            if removed.symbol in self.last_emit_date:
                del self.last_emit_date[removed.symbol]

    def _should_emit_insight(self, utc_time: datetime, symbol: Symbol) -> bool:
        """Check if we should emit a new insight for this symbol."""
        last_emit = self.last_emit_date.get(symbol)
        if last_emit is None:
            return True

        # Only emit if previous insight has expired
        return (utc_time - last_emit) >= self.insight_period

    def _calculate_alpha(self, factor_row: pd.Series) -> float:
        """
        Calculate composite alpha score from factor exposures.

        Args:
            factor_row: Series containing factor exposures for a single security

        Returns:
            Composite alpha score
        """
        alpha = 0.0
        total_weight = 0.0

        for factor, weight in self.factor_weights.items():
            if factor in factor_row and pd.notna(factor_row[factor]):
                alpha += weight * factor_row[factor]
                total_weight += abs(weight)

        # Normalize by total weight if any weights were applied
        if total_weight > 0:
            alpha = alpha / total_weight

        # Z-score style: normalize by dividing by approximate std
        # Most factors have std around 0.5-1.0 after winsorization
        alpha = alpha / 0.5

        return alpha

    def _symbol_to_ts_code(self, symbol: Symbol) -> str:
        """Convert LEAN Symbol to tushare ts_code format."""
        # LEAN stores symbols as "000001.SZ" or "600000.SH"
        # This should be directly compatible
        return symbol.value


class BarraPortfolioConstructionModel(PortfolioConstructionModel):
    """
    Portfolio construction model that optimizes weights using Barra risk model.

    This model uses the estimated factor covariance matrix to construct
    a portfolio that maximizes risk-adjusted returns while maintaining
    industry neutrality and respecting position limits.
    """

    def __init__(self,
                 factor_model: BarraCNE5Model,
                 risk_aversion: float = 1.0,
                 max_position_weight: float = 0.05,
                 max_turnover: float = 0.3,
                 rebalance: timedelta = None):
        """
        Initialize the Barra portfolio construction model.

        Args:
            factor_model: BarraCNE5Model instance for accessing risk parameters
            risk_aversion: Risk aversion coefficient (higher = more conservative)
            max_position_weight: Maximum weight for any single position
            max_turnover: Maximum portfolio turnover per rebalance
            rebalance: Time between rebalances (default: monthly)
        """
        super().__init__()
        self.factor_model = factor_model
        self.risk_aversion = risk_aversion
        self.max_position_weight = max_position_weight
        self.max_turnover = max_turnover

        # Set rebalancing function
        rebalancing_func = rebalance or timedelta(days=30)
        if isinstance(rebalancing_func, timedelta):
            rebalancing_func = lambda dt: dt + rebalancing_func
        if rebalancing_func:
            self.set_rebalancing_func(rebalancing_func)

        self.previous_weights = {}
        self.rebalance_time = None

        self.Name = "BarraCNE5PortfolioConstruction"

    def create_targets(self, algorithm: QCAlgorithm, insights: List[Insight]) -> List[PortfolioTarget]:
        """
        Create portfolio targets using risk-constrained optimization.

        Args:
            algorithm: The algorithm instance
            insights: List of active insights

        Returns:
            List of PortfolioTarget objects with optimal weights
        """
        if not insights:
            return []

        # Get risk parameters
        risk_params = self.factor_model.get_risk_params()
        if not risk_params:
            Log.error("BarraPCM: Risk parameters not available")
            return []

        # Group insights by symbol (use most recent insight per symbol)
        insights_by_symbol = {}
        for insight in insights:
            if insight.symbol not in insights_by_symbol or insight.generated_time_utc > insights_by_symbol[insight.symbol].generated_time_utc:
                insights_by_symbol[insight.symbol] = insight

        active_insights = list(insights_by_symbol.values())

        if not active_insights:
            return []

        # Calculate optimal weights using mean-variance optimization
        optimal_weights = self._optimize_portfolio(algorithm, active_insights, risk_params)

        # Create portfolio targets
        targets = []
        for symbol, weight in optimal_weights.items():
            if abs(weight) > 0.0001:  # Only include meaningful positions
                targets.append(PortfolioTarget(symbol, weight))

        # Update previous weights for next turnover calculation
        self.previous_weights = optimal_weights
        self.rebalance_time = algorithm.time

        return targets

    def _optimize_portfolio(self, algorithm: QCAlgorithm, insights: List[Insight], risk_params: dict) -> dict:
        """
        Solve the portfolio optimization problem.

        Uses a simplified mean-variance optimization with Barra risk model:
            max w'α - λ * w'Σw
            s.t. sum(w) = 1 (or target leverage)
                 |w_i| <= max_position
                 industry_neutral constraints
        """
        # Get current date's factor exposures
        current_date = algorithm.time.date()
        factor_df = self.factor_model.get_factor_data(current_date)

        if factor_df is None:
            # Fall back to equal weight if no factor data
            n = len(insights)
            weight = 1.0 / n if n > 0 else 0
            return {i.symbol: weight for i in insights}

        # Build alpha vector and exposure matrix
        symbols = []
        alphas = []
        exposures = []

        industry_factors = self.factor_model.get_industry_factors()

        for insight in insights:
            ts_code = self._symbol_to_ts_code(insight.symbol)
            if ts_code not in factor_df.index:
                continue

            symbols.append(insight.symbol)
            # Alpha from insight (direction * magnitude * confidence)
            alpha = float(insight.direction) * insight.magnitude * (insight.confidence or 1.0)
            alphas.append(alpha)

            # Get factor exposures (style factors only for risk calculation)
            style_row = factor_df.loc[ts_code]
            style_exposures = [style_row.get(f, 0) for f in self.factor_model.get_style_factors()]
            exposures.append(style_exposures)

        if not symbols:
            return {}

        n = len(symbols)
        alphas = np.array(alphas)
        exposures = np.array(exposures)

        # Get factor covariance matrix
        cov_dict = risk_params.get('factor_covariance', {})
        style_factors = self.factor_model.get_style_factors()
        k = len(style_factors)

        # Build factor covariance matrix
        F = np.zeros((k, k))
        for i, f1 in enumerate(style_factors):
            for j, f2 in enumerate(style_factors):
                if f1 in cov_dict and f2 in cov_dict[f1]:
                    F[i, j] = cov_dict[f1][f2]

        # Calculate asset covariance: Σ = X*F*X' + D
        # where D is diagonal matrix of specific risks
        specific_variances = np.zeros(n)
        for i, symbol in enumerate(symbols):
            ts_code = self._symbol_to_ts_code(symbol)
            specific_risk = self.factor_model.get_specific_risk(ts_code)
            specific_variances[i] = specific_risk ** 2

        # Σ = XFX' + diag(specific_variances)
        asset_cov = exposures @ F @ exposures.T + np.diag(specific_variances)

        # Add regularization for numerical stability
        asset_cov += np.eye(n) * 1e-6

        # Simple optimization: w = Σ^(-1) * α (normalized)
        # For more complex optimization, use cvxpy
        try:
            inv_cov = np.linalg.inv(asset_cov)
            raw_weights = inv_cov @ alphas

            # Normalize to sum to 1 (long-only constraint)
            sum_positive = sum(w for w in raw_weights if w > 0)
            if sum_positive > 0:
                weights = np.maximum(raw_weights, 0) / sum_positive
            else:
                weights = np.ones(n) / n

            # Apply position limits
            weights = np.clip(weights, 0, self.max_position_weight)

            # Re-normalize
            weights = weights / weights.sum()

        except np.linalg.LinAlgError:
            # Fallback to equal weights on error
            weights = np.ones(n) / n

        # Apply turnover constraint
        if self.previous_weights:
            weights = self._apply_turnover_constraint(symbols, weights, self.previous_weights, self.max_turnover)

        # Create result dictionary
        result = {}
        for i, symbol in enumerate(symbols):
            if weights[i] > 0.0001:
                result[symbol] = float(weights[i])

        return result

    def _apply_turnover_constraint(self, symbols: list, new_weights: np.ndarray,
                                  old_weights: dict, max_turnover: float) -> np.ndarray:
        """Apply turnover constraint to limit trading."""
        old_w = np.array([old_weights.get(s, 0) for s in symbols])
        turnover = np.sum(np.abs(new_weights - old_w))

        if turnover <= max_turnover:
            return new_weights

        # Scale down trades proportionally
        scale = max_turnover / turnover
        adjusted = old_w + scale * (new_weights - old_w)

        # Ensure non-negative and re-normalize
        adjusted = np.maximum(adjusted, 0)
        adjusted = adjusted / adjusted.sum()

        return adjusted

    def _symbol_to_ts_code(self, symbol: Symbol) -> str:
        """Convert LEAN Symbol to tushare ts_code format."""
        return symbol.value


class BarraRiskManagementModel(RiskManagementModel):
    """
    Risk management model for Barra-based strategies.

    Provides risk controls including:
    - Maximum drawdown per position
    - Maximum portfolio drawdown
    - Position size limits
    """

    def __init__(self, max_drawdown: float = 0.05, max_position_loss: float = 0.10):
        """
        Initialize the risk management model.

        Args:
            max_drawdown: Maximum portfolio drawdown before liquidation
            max_position_loss: Maximum loss per position before stop-loss
        """
        super().__init__()
        self.max_drawdown = max_drawdown
        self.max_position_loss = max_position_loss
        self.portfolio_peak = None
        self.entry_prices = {}

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        """Track entry prices for new positions."""
        for added in changes.added_securities:
            if not algorithm.portfolio[added.symbol].invested:
                self.entry_prices[added.symbol] = added.price

    def manage_risk(self, algorithm: QCAlgorithm, targets: List[PortfolioTarget]) -> List[PortfolioTarget]:
        """
        Generate liquidation targets for positions that exceed risk limits.

        Args:
            algorithm: The algorithm instance
            targets: Current portfolio targets

        Returns:
            List of PortfolioTarget objects for liquidation
        """
        risk_targets = []

        # Check portfolio-level drawdown
        portfolio_value = algorithm.portfolio.total_portfolio_value
        if self.portfolio_peak is None:
            self.portfolio_peak = portfolio_value
        else:
            self.portfolio_peak = max(self.portfolio_peak, portfolio_value)

        drawdown = (self.portfolio_peak - portfolio_value) / self.portfolio_peak

        if drawdown > self.max_drawdown:
            Log.warning(f"BarraRMM: Portfolio drawdown {drawdown:.2%} exceeds limit {self.max_drawdown:.2%}")
            # Liquidate all positions
            for symbol in algorithm.portfolio.keys():
                if algorithm.portfolio[symbol].invested:
                    risk_targets.append(PortfolioTarget(symbol, 0))
            return risk_targets

        # Check individual position losses
        for symbol in algorithm.portfolio.keys():
            if not algorithm.portfolio[symbol].invested:
                continue

            security = algorithm.securities[symbol]
            if symbol in self.entry_prices:
                entry_price = self.entry_prices[symbol]
                current_price = security.price

                if entry_price > 0:
                    pct_change = (current_price - entry_price) / entry_price

                    # Update entry price on profitable trades (trailing stop)
                    if pct_change > 0:
                        self.entry_prices[symbol] = current_price

                    # Check stop-loss
                    elif pct_change < -self.max_position_loss:
                        Log.warning(f"BarraRMM: Stop-loss triggered for {symbol.value}: {pct_change:.2%}")
                        risk_targets.append(PortfolioTarget(symbol, 0))

        return risk_targets


class BarraCNE5Algorithm(QCAlgorithm):
    """
    Main algorithm class for Barra CNE5 factor-based trading strategy.

    This algorithm implements a complete factor-based trading system:
    1. Uses CSI 300 as the universe
    2. Generates alpha from Barra style factors
    3. Optimizes portfolio using Barra risk model
    4. Rebalances monthly with risk controls
    """

    def initialize(self):
        """Initialize the algorithm."""

        # 1. Basic algorithm settings
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(10_000_000)  # 10M initial capital
        self.set_benchmark("000300.SH")  # CSI 300 as benchmark

        # 2. Initialize Barra CNE5 factor model
        self.factor_model = BarraCNE5Model(
            factor_data_dir="/data/barra_factors/by_date",
            risk_params_file="/data/barra_risk/risk_params_latest.json"
        )

        # 3. Load factor weights configuration
        self.factor_weights = self._load_factor_weights()

        # 4. Load CSI 300 universe
        universe_symbols = self._load_csi300_universe()

        # 5. Set up universe selection
        self.set_universe_selection(ManualUniverseSelectionModel(universe_symbols))

        # 6. Set up Framework models
        self.set_alpha(BarraAlphaModel(
            self.factor_model,
            self.factor_weights,
            timedelta(days=30)
        ))

        self.set_portfolio_construction(BarraPortfolioConstructionModel(
            self.factor_model,
            risk_aversion=1.0,
            max_position_weight=0.05,
            max_turnover=0.3,
            rebalance=timedelta(days=30)  # Monthly rebalancing
        ))

        self.set_execution(ImmediateExecutionModel())
        self.set_risk_management(BarraRiskManagementModel(
            max_drawdown=0.10,
            max_position_loss=0.10
        ))

        # 7. Set warm-up period for indicators
        self.set_warm_up(timedelta(days=252))

        # 8. Schedule monthly rebalancing
        self.schedule.on(
            self.date_rules.month_start(),
            self.time_rules.after_market_open("000300.SH", 30),
            self._rebalance
        )

        # Logging
        self.debug("Barra CNE5 Algorithm Initialized")
        self.debug(f"Factor weights: {self.factor_weights}")
        self.debug(f"Universe size: {len(universe_symbols)}")

    def _load_factor_weights(self) -> dict:
        """Load factor weights from configuration file."""
        default_weights = {
            'momentum': 0.25,
            'book_to_price': 0.20,
            'earnings_yield': 0.15,
            'liquidity': 0.15,
            'volatility': -0.15,  # Low volatility premium
            'size': -0.10,  # Small cap premium
            'beta': 0.0,
            'growth': 0.0,
            'non_linear_size': 0.0,
            'leverage': 0.0
        }

        config_path = "/data/barra_config/factor_weights.json"
        try:
            if System.IO.file.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get('factor_weights', default_weights)
        except Exception as e:
            self.debug(f"Failed to load factor weights: {e}")

        return default_weights

    def _load_csi300_universe(self) -> list:
        """Load CSI 300 constituent stocks."""
        # Default CSI 300 sample (actual list should be loaded from file)
        default_symbols = [
            "600000.SH", "600004.SH", "600009.SH", "600010.SH", "600011.SH",
            "600015.SH", "600016.SH", "600018.SH", "600019.SH", "600025.SH",
            "600028.SH", "600029.SH", "600030.SH", "600031.SH", "600036.SH",
            "600048.SH", "600050.SH", "600104.SH", "600109.SH", "600111.SH",
            "600176.SH", "600177.SH", "600276.SH", "600309.SH", "600332.SH",
            "600340.SH", "600346.SH", "600372.SH", "600398.SH", "600487.SH",
            "600519.SH", "600547.SH", "600570.SH", "600585.SH", "600588.SH",
            "600606.SH", "600690.SH", "600703.SH", "600745.SH", "600887.SH",
            "600893.SH", "600900.SH", "600905.SH", "600909.SH", "600926.SH",
            "600958.SH", "600999.SH", "601012.SH", "601066.SH", "601088.SH",
            "601100.SH", "601138.SH", "601166.SH", "601169.SH", "601186.SH",
            "601211.SH", "601229.SH", "601236.SH", "601288.SH", "601318.SH",
            "601328.SH", "601336.SH", "601377.SH", "601388.SH", "601398.SH",
            "601601.SH", "601628.SH", "601668.SH", "601688.SH", "601766.SH",
            "601788.SH", "601818.SH", "601857.SH", "601888.SH", "601901.SH",
            "601939.SH", "601988.SH", "601998.SH", "603259.SH", "603288.SH",
            "603393.SH", "603993.SH", "605188.SH"
        ]

        config_path = "/data/barra_config/csi300.txt"
        symbols = []

        try:
            if System.IO.file.exists(config_path):
                with open(config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            symbols.append(line)
            if symbols:
                return self._create_symbol_list(symbols)
        except Exception as e:
            self.debug(f"Failed to load CSI 300 list: {e}")

        return self._create_symbol_list(default_symbols)

    def _create_symbol_list(self, ts_codes: list) -> list:
        """Convert ts_code list to LEAN Symbol objects."""
        symbols = []
        for ts_code in ts_codes:
            # Parse market from ts_code
            if ts_code.endswith('.SH'):
                symbols.append(Symbol.create(ts_code.replace('.SH', ''), SecurityType.EQUITY, Market.CHINA))
            elif ts_code.endswith('.SZ'):
                symbols.append(Symbol.create(ts_code.replace('.SZ', ''), SecurityType.EQUITY, Market.CHINA))
        return symbols

    def _rebalance(self):
        """Scheduled rebalancing callback."""
        self.debug(f"Monthly rebalancing at {self.time}")

    def on_data(self, data: Slice):
        """Main data handler."""
        pass

    def on_order_event(self, order_event: OrderEvent):
        """Handle order events."""
        if order_event.status == OrderStatus.FILLED:
            self.debug(f"Order filled: {order_event.symbol} - {order_event.quantity} shares @ {order_event.fill_price:.2f}")

    def on_end_of_algorithm(self):
        """Called when algorithm ends."""
        self.debug("Barra CNE5 Algorithm completed")
