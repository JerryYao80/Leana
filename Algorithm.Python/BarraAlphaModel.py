"""
Barra CNE5 Alpha Model

Generates insights based on Barra CNE5 factor exposures.
Uses linear combination of factor scores to generate alpha signals.

Author: Implementation Team
Date: 2026-02-06
"""

from AlgorithmImports import *
import json
from pathlib import Path


class BarraAlphaModel(AlphaModel):
    """
    Alpha model that generates insights based on Barra CNE5 factor exposures.

    Uses a linear combination of factor scores:
        alpha_score = Σ(weight_k * factor_k)

    Where:
        - weight_k is the configured weight for factor k
        - factor_k is the standardized exposure to factor k
    """

    def __init__(self, factor_data, factor_weights=None, insight_period=1):
        """
        Initialize the Barra Alpha Model.

        Args:
            factor_data: Dictionary of {date: {ts_code: {factor: value}}}
            factor_weights: Dictionary of factor weights (default: equal weight)
            insight_period: Number of days for insight period (default: 1)
        """
        self.factor_data = factor_data
        self.insight_period = timedelta(days=insight_period)

        # Default factor weights (can be customized)
        if factor_weights is None:
            self.factor_weights = {
                'momentum': 0.25,
                'book_to_price': 0.20,  # Value factor
                'earnings_yield': 0.15,
                'growth': 0.15,
                'volatility': -0.10,  # Negative weight (prefer low volatility)
                'size': 0.05,
                'leverage': -0.05,  # Negative weight (prefer low leverage)
                'liquidity': 0.05,
            }
        else:
            self.factor_weights = factor_weights

        # Track last update time
        self.last_update = None

    def Update(self, algorithm, data):
        """
        Generate insights based on current factor exposures.

        Args:
            algorithm: The algorithm instance
            data: The current data slice

        Returns:
            List of Insight objects
        """
        insights = []
        current_date = algorithm.Time.date()

        # Only update once per day
        if self.last_update == current_date:
            return insights

        self.last_update = current_date

        # Get factor exposures for current date
        if current_date not in self.factor_data:
            algorithm.Debug(f"No factor data available for {current_date}")
            return insights

        factors_today = self.factor_data[current_date]

        # Calculate alpha scores for all active securities
        alpha_scores = {}

        for symbol in algorithm.ActiveSecurities.Keys:
            ts_code = symbol.Value

            if ts_code not in factors_today:
                continue

            stock_factors = factors_today[ts_code]

            # Calculate weighted alpha score
            score = self._calculate_alpha_score(stock_factors)

            if score is not None and not math.isnan(score):
                alpha_scores[symbol] = score

        # Generate insights for top/bottom stocks
        if len(alpha_scores) > 0:
            insights = self._generate_insights(algorithm, alpha_scores)

        return insights

    def _calculate_alpha_score(self, stock_factors):
        """
        Calculate alpha score for a stock based on factor exposures.

        Args:
            stock_factors: Dictionary of factor values for the stock

        Returns:
            Alpha score (float) or None if insufficient data
        """
        score = 0.0
        total_weight = 0.0

        for factor_name, weight in self.factor_weights.items():
            if factor_name in stock_factors:
                factor_value = stock_factors[factor_name]

                # Skip NaN values
                if factor_value is None or math.isnan(factor_value):
                    continue

                score += weight * factor_value
                total_weight += abs(weight)

        # Normalize by total weight
        if total_weight > 0:
            return score / total_weight
        else:
            return None

    def _generate_insights(self, algorithm, alpha_scores):
        """
        Generate insights based on alpha scores.

        Args:
            algorithm: The algorithm instance
            alpha_scores: Dictionary of {symbol: score}

        Returns:
            List of Insight objects
        """
        insights = []

        # Sort stocks by alpha score
        sorted_stocks = sorted(alpha_scores.items(), key=lambda x: x[1], reverse=True)

        # Generate insights for top and bottom stocks
        num_stocks = len(sorted_stocks)
        num_long = max(1, num_stocks // 10)  # Top 10%
        num_short = max(1, num_stocks // 10)  # Bottom 10%

        # Long positions (high alpha scores)
        for symbol, score in sorted_stocks[:num_long]:
            insights.append(Insight.Price(
                symbol,
                self.insight_period,
                InsightDirection.Up,
                magnitude=abs(score),
                confidence=0.5,
                source_model="BarraAlphaModel"
            ))

        # Short positions (low alpha scores) - only if shorting is enabled
        # For A-shares, typically long-only, so we skip short positions
        # Uncomment below if shorting is allowed:
        # for symbol, score in sorted_stocks[-num_short:]:
        #     insights.append(Insight.Price(
        #         symbol,
        #         self.insight_period,
        #         InsightDirection.Down,
        #         magnitude=abs(score),
        #         confidence=0.5,
        #         source_model="BarraAlphaModel"
        #     ))

        return insights

    def OnSecuritiesChanged(self, algorithm, changes):
        """
        Handle universe changes.

        Args:
            algorithm: The algorithm instance
            changes: SecurityChanges object
        """
        # Log additions and removals
        for security in changes.AddedSecurities:
            algorithm.Debug(f"Added to universe: {security.Symbol}")

        for security in changes.RemovedSecurities:
            algorithm.Debug(f"Removed from universe: {security.Symbol}")


class BarraAlphaModelWithConfig(BarraAlphaModel):
    """
    Extended Barra Alpha Model that loads factor weights from configuration file.
    """

    def __init__(self, factor_data, config_path=None, insight_period=1):
        """
        Initialize with configuration file.

        Args:
            factor_data: Dictionary of factor data
            config_path: Path to factor weights JSON file
            insight_period: Number of days for insight period
        """
        # Load factor weights from config
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                factor_weights = config.get('weights', None)
        else:
            factor_weights = None

        super().__init__(factor_data, factor_weights, insight_period)


class BarraLongOnlyAlphaModel(BarraAlphaModel):
    """
    Long-only version of Barra Alpha Model (suitable for A-shares).
    Only generates long positions, no short positions.
    """

    def _generate_insights(self, algorithm, alpha_scores):
        """
        Generate long-only insights.

        Args:
            algorithm: The algorithm instance
            alpha_scores: Dictionary of {symbol: score}

        Returns:
            List of Insight objects (long positions only)
        """
        insights = []

        # Sort stocks by alpha score (descending)
        sorted_stocks = sorted(alpha_scores.items(), key=lambda x: x[1], reverse=True)

        # Generate insights for top stocks only
        num_stocks = len(sorted_stocks)
        num_long = max(1, min(50, num_stocks // 5))  # Top 20%, max 50 stocks

        for symbol, score in sorted_stocks[:num_long]:
            # Only generate insights for positive scores
            if score > 0:
                insights.append(Insight.Price(
                    symbol,
                    self.insight_period,
                    InsightDirection.Up,
                    magnitude=abs(score),
                    confidence=min(0.8, 0.3 + abs(score)),  # Higher confidence for higher scores
                    source_model="BarraLongOnlyAlphaModel"
                ))

        return insights


class BarraRankAlphaModel(BarraAlphaModel):
    """
    Rank-based Barra Alpha Model.
    Uses percentile ranks instead of raw factor values.
    """

    def Update(self, algorithm, data):
        """
        Generate insights based on factor ranks.

        Args:
            algorithm: The algorithm instance
            data: The current data slice

        Returns:
            List of Insight objects
        """
        insights = []
        current_date = algorithm.Time.date()

        # Only update once per day
        if self.last_update == current_date:
            return insights

        self.last_update = current_date

        # Get factor exposures for current date
        if current_date not in self.factor_data:
            return insights

        factors_today = self.factor_data[current_date]

        # Calculate ranks for each factor
        factor_ranks = self._calculate_factor_ranks(factors_today)

        # Calculate alpha scores based on ranks
        alpha_scores = {}

        for symbol in algorithm.ActiveSecurities.Keys:
            ts_code = symbol.Value

            if ts_code not in factor_ranks:
                continue

            stock_ranks = factor_ranks[ts_code]

            # Calculate weighted rank score
            score = self._calculate_rank_score(stock_ranks)

            if score is not None:
                alpha_scores[symbol] = score

        # Generate insights
        if len(alpha_scores) > 0:
            insights = self._generate_insights(algorithm, alpha_scores)

        return insights

    def _calculate_factor_ranks(self, factors_today):
        """
        Calculate percentile ranks for each factor.

        Args:
            factors_today: Dictionary of {ts_code: {factor: value}}

        Returns:
            Dictionary of {ts_code: {factor: rank}}
        """
        import numpy as np

        # Collect factor values for all stocks
        factor_values = {}
        for factor_name in self.factor_weights.keys():
            values = []
            ts_codes = []

            for ts_code, factors in factors_today.items():
                if factor_name in factors:
                    value = factors[factor_name]
                    if value is not None and not math.isnan(value):
                        values.append(value)
                        ts_codes.append(ts_code)

            if len(values) > 0:
                # Calculate percentile ranks (0 to 1)
                ranks = np.argsort(np.argsort(values)) / (len(values) - 1) if len(values) > 1 else [0.5] * len(values)
                factor_values[factor_name] = dict(zip(ts_codes, ranks))

        # Reorganize by ts_code
        factor_ranks = {}
        for ts_code in factors_today.keys():
            factor_ranks[ts_code] = {}
            for factor_name in self.factor_weights.keys():
                if factor_name in factor_values and ts_code in factor_values[factor_name]:
                    factor_ranks[ts_code][factor_name] = factor_values[factor_name][ts_code]

        return factor_ranks

    def _calculate_rank_score(self, stock_ranks):
        """
        Calculate alpha score based on factor ranks.

        Args:
            stock_ranks: Dictionary of {factor: rank}

        Returns:
            Rank-based alpha score
        """
        score = 0.0
        total_weight = 0.0

        for factor_name, weight in self.factor_weights.items():
            if factor_name in stock_ranks:
                rank = stock_ranks[factor_name]

                # Convert rank to score (-1 to 1)
                # For negative weights, invert the rank
                if weight < 0:
                    rank_score = -(rank - 0.5) * 2
                else:
                    rank_score = (rank - 0.5) * 2

                score += abs(weight) * rank_score
                total_weight += abs(weight)

        if total_weight > 0:
            return score / total_weight
        else:
            return None
