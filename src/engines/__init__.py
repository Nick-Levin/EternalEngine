"""
The Eternal Engine - Four Strategy Engines

This module contains the four engines that power The Eternal Engine:
- CORE-HODL (60%): Long-term BTC/ETH accumulation with DCA and rebalancing
- TREND (20%): Perpetual futures trend following with risk management
- FUNDING (15%): Delta-neutral funding rate arbitrage
- TACTICAL (5%): Crisis deployment during extreme market conditions

Each engine operates independently in its own subaccount for isolation.
"""

from src.core.models import EngineType
from src.engines.base import BaseEngine, EngineConfig
from src.engines.core_hodl import CoreHodlConfig, CoreHodlEngine
from src.engines.funding import FundingEngine, FundingEngineConfig
from src.engines.tactical import TacticalEngine, TacticalEngineConfig
from src.engines.trend import TrendEngine, TrendEngineConfig


def create_engine(engine_type: EngineType, **kwargs) -> BaseEngine:
    """Factory function to create engines by type."""
    engine_map = {
        EngineType.CORE_HODL: CoreHodlEngine,
        EngineType.TREND: TrendEngine,
        EngineType.FUNDING: FundingEngine,
        EngineType.TACTICAL: TacticalEngine,
    }
    engine_class = engine_map.get(engine_type)
    if not engine_class:
        raise ValueError(f"Unknown engine type: {engine_type}")
    return engine_class(**kwargs)


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
    # Factory
    "create_engine",
]
