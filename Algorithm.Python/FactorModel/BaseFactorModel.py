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
FactorModel Framework - Base Factor Model Abstract Class

This module provides the abstract base class for factor models,
supporting various risk models like Barra CNE5, CNE6, and custom implementations.
"""

from AlgorithmImports import *
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path


class BaseFactorModel(ABC):
    """
    Abstract base class for factor models.

    This class defines the interface that all factor models must implement.
    It provides methods for accessing factor data, risk parameters, and factor lists.

    Derived classes must implement:
        - get_factor_data(date): Get factor exposures for a specific date
        - get_risk_params(): Get current risk model parameters
        - get_factor_list(): Get list of all factors in the model
    """

    def __init__(self, factor_data_dir: str, risk_params_file: str):
        """
        Initialize the factor model.

        Args:
            factor_data_dir: Directory containing factor data files (by_date/*.parquet)
            risk_params_file: Path to risk parameters JSON file
        """
        self.factor_data_dir = Path(factor_data_dir)
        self.risk_params_file = Path(risk_params_file)
        self._risk_params = None
        self._factor_cache = {}
        self._load_risk_params()

    @abstractmethod
    def get_factor_data(self, date: date) -> Optional[pd.DataFrame]:
        """
        Get factor exposure data for a specific date.

        Args:
            date: The date to get factor data for

        Returns:
            DataFrame with factor exposures, indexed by security symbol,
            or None if data is not available
        """
        pass

    @abstractmethod
    def get_risk_params(self) -> Dict:
        """
        Get current risk model parameters.

        Returns:
            Dictionary containing:
                - factor_covariance: Factor covariance matrix (nested dict)
                - factor_volatility: Factor volatilities (dict)
                - specific_risks: Idiosyncratic risks by security (dict)
                - estimation_date: Date of risk model estimation
                - estimation_window: Window used for estimation
        """
        pass

    @abstractmethod
    def get_factor_list(self) -> List[str]:
        """
        Get list of all factors in the model.

        Returns:
            List of factor names (e.g., ['size', 'beta', 'momentum', ...])
        """
        pass

    def _load_risk_params(self) -> None:
        """Load risk parameters from JSON file."""
        if self.risk_params_file.exists():
            with open(self.risk_params_file, 'r') as f:
                self._risk_params = json.load(f)
        else:
            self._risk_params = {}

    def get_style_factors(self) -> List[str]:
        """
        Get list of style factors only.

        Returns:
            List of style factor names
        """
        return self.get_factor_list()

    def get_industry_factors(self) -> List[str]:
        """
        Get list of industry factors only.

        Returns:
            List of industry factor names
        """
        all_factors = self.get_factor_list()
        return [f for f in all_factors if f.startswith('ind_')]

    def get_specific_risk(self, symbol: str) -> float:
        """
        Get specific (idiosyncratic) risk for a security.

        Args:
            symbol: Security symbol (e.g., '000001.SZ')

        Returns:
            Specific risk value
        """
        risk_params = self.get_risk_params()
        specific_risks = risk_params.get('specific_risks', {})
        return specific_risks.get(symbol, 0.03)  # Default 3% if not found

    def get_factor_covariance(self) -> pd.DataFrame:
        """
        Get factor covariance matrix as DataFrame.

        Returns:
            DataFrame with factor covariance matrix
        """
        risk_params = self.get_risk_params()
        cov_dict = risk_params.get('factor_covariance', {})

        if not cov_dict:
            return pd.DataFrame()

        # Convert nested dict to DataFrame
        factors = list(cov_dict.keys())
        cov_matrix = pd.DataFrame(index=factors, columns=factors)

        for i, factor1 in enumerate(factors):
            for j, factor2 in enumerate(factors):
                cov_matrix.iloc[i, j] = cov_dict[factor1].get(factor2, 0.0)

        return cov_matrix

    def clear_cache(self) -> None:
        """Clear the internal factor data cache."""
        self._factor_cache.clear()

    def is_neutral_to_factor(self, factor_name: str) -> bool:
        """
        Check if portfolio should be neutral to a specific factor.

        Args:
            factor_name: Name of the factor

        Returns:
            True if portfolio should be neutral to this factor
        """
        # By default, neutral to all industry factors
        return factor_name.startswith('ind_')
