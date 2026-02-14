"""
The Eternal Engine - Four Strategy Engines

This module contains the four engines that power The Eternal Engine:
- CORE-HODL (60%): Long-term BTC/ETH accumulation with DCA and rebalancing
- TREND (20%): Perpetual futures trend following with risk management
- FUNDING (15%): Delta-neutral funding rate arbitrage
- TACTICAL (5%): Crisis deployment during extreme market conditions

Each engine operates independently in its own subaccount for isolation.
"""

from src.engines.base import BaseEngine, EngineConfig
from src.engines.core_hodl import CoreHodlEngine, CoreHodlConfig
from src.engines.trend import TrendEngine, TrendEngineConfig
from src.engines.funding import FundingEngine, FundingEngineConfig
from src.engines.tactical import TacticalEngine, TacticalEngineConfig

__all__ = [
    # Base classes
    "BaseEngine",
    "EngineConfig",
    # Engines
    "CoreHodlEngine",
    "TrendEngine",
    "FundingEngine",
    "TacticalEngine",
    # Configs
    "CoreHodlConfig",
    "TrendEngineConfig",
    "FundingEngineConfig",
    "TacticalEngineConfig",
]
