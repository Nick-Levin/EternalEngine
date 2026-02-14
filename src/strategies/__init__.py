"""
Trading Strategies for The Eternal Engine.

This module contains both legacy strategy implementations and the new
four-engine architecture. The engines in src/engines/ are the primary
trading logic components.

Legacy Strategies (for backward compatibility):
- DCAStrategy: Dollar-cost averaging implementation
- GridStrategy: Grid trading for sideways markets

New Engine Architecture (recommended):
- CoreHodlEngine: 60% allocation - long-term accumulation
- TrendEngine: 20% allocation - trend following
- FundingEngine: 15% allocation - funding arbitrage
- TacticalEngine: 5% allocation - crisis deployment

Migration Note:
The strategy classes are being migrated to the engine architecture.
New development should use the engines in src/engines/.
"""

# Legacy strategies
from src.strategies.base import BaseStrategy
from src.strategies.dca_strategy import DCAStrategy
from src.strategies.grid_strategy import GridStrategy

# New engine architecture - re-export from engines module
from src.engines import (
    BaseEngine,
    EngineConfig,
    CoreHodlEngine,
    TrendEngine,
    FundingEngine,
    TacticalEngine,
    CoreHodlConfig,
    TrendEngineConfig,
    FundingEngineConfig,
    TacticalEngineConfig,
)

__all__ = [
    # Legacy strategies
    "BaseStrategy",
    "DCAStrategy",
    "GridStrategy",
    # New engines
    "BaseEngine",
    "EngineConfig",
    "CoreHodlEngine",
    "TrendEngine",
    "FundingEngine",
    "TacticalEngine",
    # Engine configs
    "CoreHodlConfig",
    "TrendEngineConfig",
    "FundingEngineConfig",
    "TacticalEngineConfig",
]
