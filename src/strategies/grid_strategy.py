"""
Grid Trading Strategy

Places buy and sell orders at predefined price intervals (grid).
Profits from price oscillations in sideways markets.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import structlog

from src.core.models import MarketData, TradingSignal, SignalType, Position
from src.core.config import strategy_config
from src.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class GridStrategy(BaseStrategy):
    """
    Grid Trading Strategy.
    
    Strategy Logic:
    - Create grid levels around current price
    - Buy when price drops to lower grid level
    - Sell when price rises to upper grid level
    - Profits from range-bound market oscillations
    
    Risk Level: LOW-MEDIUM
    Best For: Sideways/ranging markets
    
    Risk Controls:
    - Stop loss outside grid range
    - Maximum grid levels
    - Position size limits per grid
    """
    
    def __init__(self, symbols: List[str], **kwargs):
        super().__init__("Grid", symbols, **kwargs)
        
        # Grid configuration
        self.grid_levels = kwargs.get('grid_levels', strategy_config.grid_levels)
        self.grid_spacing_pct = kwargs.get(
            'grid_spacing_pct', 
            strategy_config.grid_spacing_pct
        )
        self.investment_per_grid_pct = kwargs.get('investment_per_grid_pct', 2.0)
        
        # Track active grids per symbol
        self.active_grids: Dict[str, Dict] = {}
        
        # Track filled grid orders
        self.filled_orders: Dict[str, List[Decimal]] = {s: [] for s in symbols}
        
        self.logger.info(
            "grid_strategy.initialized",
            grid_levels=self.grid_levels,
            grid_spacing_pct=self.grid_spacing_pct,
            symbols=symbols
        )
    
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """Analyze price and generate grid signals."""
        signals = []
        
        for symbol in self.symbols:
            if symbol not in data or not data[symbol]:
                continue
            
            current_price = data[symbol][-1].close
            
            # Initialize grid if not active
            if symbol not in self.active_grids:
                grid = self._create_grid(current_price)
                self.active_grids[symbol] = grid
                
                # Create initial buy signals for lower levels
                for level_price in grid['buy_levels']:
                    if level_price < current_price:
                        signals.append(self._create_grid_signal(
                            symbol, SignalType.BUY, level_price, grid
                        ))
            else:
                # Check for grid level triggers
                grid = self.active_grids[symbol]
                
                # Check buy levels
                for level_price in grid['buy_levels']:
                    if self._should_trigger_buy(current_price, level_price, symbol):
                        signals.append(self._create_grid_signal(
                            symbol, SignalType.BUY, level_price, grid
                        ))
                
                # Check sell levels
                for level_price in grid['sell_levels']:
                    if self._should_trigger_sell(current_price, level_price, symbol):
                        signals.append(self._create_grid_signal(
                            symbol, SignalType.SELL, level_price, grid
                        ))
                
                # Check if price moved outside grid - reset needed
                if current_price < grid['lower_stop'] or current_price > grid['upper_stop']:
                    self.logger.warning(
                        "grid_strategy.price_outside_range",
                        symbol=symbol,
                        current_price=str(current_price),
                        grid_range=f"{grid['lower_stop']}-{grid['upper_stop']}"
                    )
                    # Remove grid to force reinitialization
                    del self.active_grids[symbol]
        
        return signals
    
    def _create_grid(self, center_price: Decimal) -> Dict:
        """Create grid levels around center price."""
        spacing = Decimal(str(self.grid_spacing_pct)) / 100
        
        # Calculate grid levels
        buy_levels = []
        sell_levels = []
        
        for i in range(1, self.grid_levels + 1):
            factor = Decimal("1") - (spacing * i)
            buy_levels.append(center_price * factor)
        
        for i in range(1, self.grid_levels + 1):
            factor = Decimal("1") + (spacing * i)
            sell_levels.append(center_price * factor)
        
        # Stop loss levels outside grid
        stop_factor = spacing * (self.grid_levels + 1)
        lower_stop = center_price * (Decimal("1") - stop_factor)
        upper_stop = center_price * (Decimal("1") + stop_factor)
        
        return {
            'center_price': center_price,
            'buy_levels': buy_levels,
            'sell_levels': sell_levels,
            'lower_stop': lower_stop,
            'upper_stop': upper_stop,
            'created_at': datetime.utcnow()
        }
    
    def _should_trigger_buy(
        self, 
        current_price: Decimal, 
        level_price: Decimal,
        symbol: str
    ) -> bool:
        """Check if price reached buy level and not already filled."""
        # Price at or below level
        if current_price > level_price:
            return False
        
        # Check not already filled at this level recently
        filled = self.filled_orders.get(symbol, [])
        for fp in filled:
            if abs(fp - level_price) / level_price < Decimal("0.001"):  # 0.1% tolerance
                return False
        
        return True
    
    def _should_trigger_sell(
        self, 
        current_price: Decimal, 
        level_price: Decimal,
        symbol: str
    ) -> bool:
        """Check if price reached sell level and have position."""
        # Price at or above level
        if current_price < level_price:
            return False
        
        # Need to have bought at lower price first
        filled = self.filled_orders.get(symbol, [])
        has_lower_buy = any(fp < level_price for fp in filled)
        
        return has_lower_buy
    
    def _create_grid_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        price: Decimal,
        grid: Dict
    ) -> TradingSignal:
        """Create a grid trading signal."""
        metadata = {
            'strategy': 'Grid',
            'grid_level': str(price),
            'center_price': str(grid['center_price']),
            'grid_spacing_pct': self.grid_spacing_pct,
            'grid_levels': self.grid_levels
        }
        
        self.logger.info(
            "grid_strategy.signal",
            symbol=symbol,
            signal=signal_type.value,
            price=str(price)
        )
        
        return self._create_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=0.8,
            metadata=metadata
        )
    
    async def on_order_filled(
        self, 
        symbol: str, 
        side: str, 
        amount: Decimal, 
        price: Decimal
    ):
        """Track filled grid orders."""
        if symbol not in self.filled_orders:
            self.filled_orders[symbol] = []
        
        self.filled_orders[symbol].append(price)
        
        # Keep only recent fills (last 20)
        self.filled_orders[symbol] = self.filled_orders[symbol][-20:]
        
        self.logger.info(
            "grid_strategy.order_filled",
            symbol=symbol,
            side=side,
            price=str(price),
            amount=str(amount)
        )
    
    async def on_position_closed(
        self, 
        symbol: str, 
        pnl: Decimal, 
        pnl_pct: Decimal
    ):
        """Track grid position close."""
        self.total_pnl += pnl
        
        # Reset filled orders for this symbol
        self.filled_orders[symbol] = []
        
        self.logger.info(
            "grid_strategy.position_closed",
            symbol=symbol,
            pnl=str(pnl),
            pnl_pct=str(pnl_pct)
        )
    
    def get_grid_info(self, symbol: str) -> Optional[Dict]:
        """Get current grid information for a symbol."""
        if symbol not in self.active_grids:
            return None
        
        grid = self.active_grids[symbol]
        return {
            'center_price': str(grid['center_price']),
            'buy_levels': [str(p) for p in grid['buy_levels']],
            'sell_levels': [str(p) for p in grid['sell_levels']],
            'lower_stop': str(grid['lower_stop']),
            'upper_stop': str(grid['upper_stop']),
            'created_at': grid['created_at'].isoformat()
        }
    
    def reset_grid(self, symbol: str):
        """Manually reset grid for a symbol."""
        if symbol in self.active_grids:
            del self.active_grids[symbol]
        self.filled_orders[symbol] = []
        self.logger.info("grid_strategy.reset", symbol=symbol)
