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
FactorModel Framework - Barra CNE5 Factor Model Implementation

This module implements the Barra CNE5 (China) factor model, which includes:
- 10 style factors (Size, Beta, Momentum, Volatility, etc.)
- 30 industry factors (CITIC first-level industries)
"""

from AlgorithmImports import *
from .BaseFactorModel import BaseFactorModel
from datetime import date, datetime
from typing import Dict, List, Optional
import pandas as pd
import json
from pathlib import Path


class BarraCNE5Model(BaseFactorModel):
    """
    Barra CNE5 (China) Factor Model Implementation.

    This model uses pre-computed factor data stored in parquet files
    and risk parameters estimated from historical factor returns.

    Data files expected:
        - factor_data_dir/by_date/YYYYMMDD.parquet: Daily factor exposures
        - risk_params_file: JSON with covariance matrix and specific risks
    """

    # 10 Barra CNE5 style factors
    STYLE_FACTORS = [
        'size',                  # Market capitalization factor
        'beta',                  # Market beta
        'momentum',              # Price momentum
        'volatility',            # Return volatility
        'non_linear_size',       # Non-linear size (cube of size)
        'book_to_price',         # Book-to-market ratio
        'liquidity',             # Trading liquidity
        'earnings_yield',        # Earnings yield
        'growth',                # Growth factor
        'leverage'               # Financial leverage
    ]

    # 30 CITIC first-level industry factors
    INDUSTRY_FACTORS = [
        'ind_petrochemical',       # Oil & Petrochemical
        'ind_coal',                # Coal
        'ind_nonferrous',          # Non-ferrous metals
        'ind_utilities',           # Utilities
        'ind_steel',               # Steel
        'ind_chemicals',           # Chemicals
        'ind_building_materials',  # Building materials
        'ind_construction',        # Construction
        'ind_transportation',      # Transportation
        'ind_automobiles',         # Automobiles
        'ind_machinery',           # Machinery
        'ind_defense',             # Defense
        'ind_electrical_equipment', # Electrical equipment
        'ind_electronics',         # Electronics
        'ind_computers',           # Computers
        'ind_communications',      # Communications
        'ind_consumer_appliances', # Consumer appliances
        'ind_light_manufacturing', # Light manufacturing
        'ind_textiles_apparel',    # Textiles & apparel
        'ind_food_beverage',       # Food & beverage
        'ind_agriculture',         # Agriculture
        'ind_banking',             # Banking
        'ind_non_bank_finance',    # Non-banking finance
        'ind_real_estate',         # Real estate
        'ind_commerce_retail',     # Commerce & retail
        'ind_social_services',     # Social services
        'ind_media',               # Media
        'ind_pharmaceuticals',     # Pharmaceuticals
        'ind_environmental',       # Environmental protection
        'ind_comprehensive'        # Comprehensive
    ]

    # All factors combined
    ALL_FACTORS = STYLE_FACTORS + INDUSTRY_FACTORS

    def __init__(self, factor_data_dir: str, risk_params_file: str):
        """
        Initialize Barra CNE5 factor model.

        Args:
            factor_data_dir: Directory containing factor data (e.g., /data/barra_factors/by_date/)
            risk_params_file: Path to risk parameters JSON (e.g., /data/barra_risk/risk_params_latest.json)
        """
        super().__init__(factor_data_dir, risk_params_file)
        self._cache_size = 10  # Maximum number of cached days

    def get_factor_data(self, date: date) -> Optional[pd.DataFrame]:
        """
        Get factor exposure data for a specific date.

        Args:
            date: The date to get factor data for (can be date, datetime, or string)

        Returns:
            DataFrame with factor exposures, indexed by ts_code (e.g., '000001.SZ')
            Columns include all style and industry factors
            Returns None if data file doesn't exist
        """
        # Convert date to proper format
        if isinstance(date, datetime):
            date = date.date()
        elif isinstance(date, str):
            date = pd.to_datetime(date).date()

        # Check cache first
        if date in self._factor_cache:
            return self._factor_cache[date]

        # Build file path: by_date/YYYYMMDD.parquet
        date_str = date.strftime("%Y%m%d")
        file_path = self.factor_data_dir / f"{date_str}.parquet"

        if not file_path.exists():
            return None

        try:
            # Read parquet file
            df = pd.read_parquet(file_path)

            # Set index to ts_code if not already
            if 'ts_code' in df.columns and df.index.name != 'ts_code':
                df = df.set_index('ts_code')

            # Cache the result (with size limit)
            if len(self._factor_cache) >= self._cache_size:
                # Remove oldest entry
                oldest_key = min(self._factor_cache.keys())
                del self._factor_cache[oldest_key]
            self._factor_cache[date] = df

            return df

        except Exception as e:
            Log.error(f"BarraCNE5Model: Failed to read factor data for {date_str}: {e}")
            return None

    def get_risk_params(self) -> Dict:
        """
        Get current risk model parameters.

        Returns:
            Dictionary containing:
                - factor_covariance: Factor covariance matrix (nested dict)
                - factor_volatility: Factor volatilities (dict)
                - specific_risks: Idiosyncratic risks by security (dict)
                - estimation_date: Date of risk model estimation (string)
                - estimation_window: Window used for estimation (int)
                - half_life: Half-life used for exponential weighting (int)
                - num_factors: Number of factors (int)
                - num_stocks: Number of stocks (int)
        """
        if self._risk_params is None:
            # Reload if not loaded
            self._load_risk_params()

        return self._risk_params if self._risk_params else {}

    def get_factor_list(self) -> List[str]:
        """
        Get list of all factors in the model.

        Returns:
            List of all factor names (10 style + 30 industry)
        """
        return self.ALL_FACTORS.copy()

    def get_style_factors(self) -> List[str]:
        """Get list of style factors only."""
        return self.STYLE_FACTORS.copy()

    def get_industry_factors(self) -> List[str]:
        """Get list of industry factors only."""
        return self.INDUSTRY_FACTORS.copy()

    def get_factor_exposure(self, symbol: str, date: date, factor_name: str) -> Optional[float]:
        """
        Get exposure of a specific security to a specific factor on a given date.

        Args:
            symbol: Security symbol (e.g., '000001.SZ')
            date: Date to get exposure for
            factor_name: Name of the factor

        Returns:
            Factor exposure value, or None if not available
        """
        df = self.get_factor_data(date)
        if df is None:
            return None

        if symbol not in df.index:
            return None

        if factor_name not in df.columns:
            return None

        return float(df.loc[symbol, factor_name])

    def get_all_factor_exposures(self, symbol: str, date: date) -> Optional[Dict[str, float]]:
        """
        Get all factor exposures for a specific security on a given date.

        Args:
            symbol: Security symbol (e.g., '000001.SZ')
            date: Date to get exposures for

        Returns:
            Dictionary mapping factor names to exposure values
        """
        df = self.get_factor_data(date)
        if df is None:
            return None

        if symbol not in df.index:
            return None

        return df.loc[symbol].to_dict()

    def is_neutral_to_factor(self, factor_name: str) -> bool:
        """
        Check if portfolio should be neutral to a specific factor.
        For Barra CNE5, we typically neutralize to industry factors.

        Args:
            factor_name: Name of the factor

        Returns:
            True if portfolio should be neutral to this factor
        """
        # Neutral to all industry factors by default
        return factor_name.startswith('ind_')

    def get_estimation_date(self) -> Optional[date]:
        """Get the date when risk parameters were estimated."""
        risk_params = self.get_risk_params()
        est_date_str = risk_params.get('estimation_date')
        if est_date_str:
            return pd.to_datetime(est_date_str).date()
        return None
