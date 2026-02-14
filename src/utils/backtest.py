"""Simple backtesting engine for strategy validation."""
from typing import List, Dict
from datetime import datetime
from decimal import Decimal
import pandas as pd
import structlog

from src.core.models import MarketData, Order, Trade, SignalType
from src.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class BacktestEngine:
    """
    Simple backtesting engine for strategy validation.
    
    Features:
    - Simulates order execution at market price
    - Tracks portfolio value over time
    - Calculates key metrics (Sharpe, drawdown, win rate)
    """
    
    def __init__(
        self,
        initial_balance: Decimal = Decimal("10000"),
        fee_rate: Decimal = Decimal("0.001")  # 0.1%
    ):
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        
        # State
        self.balance = initial_balance
        self.positions: Dict[str, Decimal] = {}  # symbol -> quantity
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        
    def run(
        self,
        strategy: BaseStrategy,
        market_data: Dict[str, List[MarketData]]
    ) -> Dict:
        """
        Run backtest with given strategy and data.
        
        Returns backtest results including:
        - Total return
        - Max drawdown
        - Sharpe ratio
        - Win rate
        - Trade statistics
        """
        logger.info("backtest.starting", strategy=strategy.name)
        
        # Sort data by timestamp
        timestamps = self._get_sorted_timestamps(market_data)
        
        for timestamp in timestamps:
            # Get data up to this point
            current_data = self._get_data_at_time(market_data, timestamp)
            
            # Get strategy signals
            signals = strategy.analyze(current_data)
            
            # Process signals
            for signal in signals:
                self._process_signal(signal, current_data)
            
            # Record equity
            equity = self._calculate_equity(current_data, timestamp)
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': equity,
                'balance': self.balance
            })
        
        # Calculate metrics
        results = self._calculate_metrics()
        
        logger.info("backtest.complete", **results)
        
        return results
    
    def _process_signal(self, signal, market_data):
        """Process a trading signal."""
        symbol = signal.symbol
        
        if signal.signal_type == SignalType.BUY:
            self._execute_buy(symbol, market_data)
        elif signal.signal_type == SignalType.SELL:
            self._execute_sell(symbol, market_data)
    
    def _execute_buy(self, symbol: str, market_data: Dict):
        """Execute a buy order."""
        if symbol not in market_data or not market_data[symbol]:
            return
        
        price = market_data[symbol][-1].close
        
        # Use 10% of balance per trade
        trade_value = self.balance * Decimal("0.1")
        if trade_value <= 0:
            return
        
        quantity = (trade_value * (Decimal("1") - self.fee_rate)) / price
        
        # Update state
        fee = trade_value * self.fee_rate
        self.balance -= trade_value
        
        if symbol in self.positions:
            self.positions[symbol] += quantity
        else:
            self.positions[symbol] = quantity
        
        logger.debug(
            "backtest.buy",
            symbol=symbol,
            price=str(price),
            quantity=str(quantity),
            fee=str(fee)
        )
    
    def _execute_sell(self, symbol: str, market_data: Dict):
        """Execute a sell order."""
        if symbol not in self.positions or self.positions[symbol] <= 0:
            return
        
        if symbol not in market_data or not market_data[symbol]:
            return
        
        price = market_data[symbol][-1].close
        quantity = self.positions[symbol]
        
        # Calculate proceeds
        gross_value = quantity * price
        fee = gross_value * self.fee_rate
        net_value = gross_value - fee
        
        # Update state
        self.balance += net_value
        del self.positions[symbol]
        
        logger.debug(
            "backtest.sell",
            symbol=symbol,
            price=str(price),
            quantity=str(quantity),
            fee=str(fee)
        )
    
    def _calculate_equity(
        self, 
        market_data: Dict, 
        timestamp: datetime
    ) -> Decimal:
        """Calculate total equity at given time."""
        equity = self.balance
        
        for symbol, quantity in self.positions.items():
            if symbol in market_data and market_data[symbol]:
                price = market_data[symbol][-1].close
                equity += quantity * price
        
        return equity
    
    def _get_sorted_timestamps(
        self, 
        market_data: Dict[str, List[MarketData]]
    ) -> List[datetime]:
        """Get sorted list of all timestamps."""
        timestamps = set()
        
        for symbol_data in market_data.values():
            for data in symbol_data:
                timestamps.add(data.timestamp)
        
        return sorted(timestamps)
    
    def _get_data_at_time(
        self, 
        market_data: Dict, 
        timestamp: datetime
    ) -> Dict:
        """Get market data up to given timestamp."""
        result = {}
        
        for symbol, data_list in market_data.items():
            result[symbol] = [
                d for d in data_list 
                if d.timestamp <= timestamp
            ]
        
        return result
    
    def _calculate_metrics(self) -> Dict:
        """Calculate backtest performance metrics."""
        if not self.equity_curve:
            return {}
        
        df = pd.DataFrame(self.equity_curve)
        
        # Calculate returns
        df['returns'] = df['equity'].pct_change()
        
        # Total return
        total_return = (
            (df['equity'].iloc[-1] - self.initial_balance) 
            / self.initial_balance * 100
        )
        
        # Max drawdown
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
        max_drawdown = df['drawdown'].min() * 100
        
        # Sharpe ratio (annualized, assuming 252 trading days)
        if len(df) > 1:
            returns_mean = df['returns'].mean()
            returns_std = df['returns'].std()
            if returns_std > 0:
                sharpe_ratio = (returns_mean / returns_std) * (252 ** 0.5)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # Win rate
        win_count = sum(1 for t in self.trades if t.realized_pnl > 0)
        total_trades = len(self.trades)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_return_pct': round(float(total_return), 2),
            'max_drawdown_pct': round(float(max_drawdown), 2),
            'sharpe_ratio': round(float(sharpe_ratio), 2),
            'total_trades': total_trades,
            'win_rate_pct': round(float(win_rate), 2),
            'final_equity': round(float(df['equity'].iloc[-1]), 2),
            'initial_balance': float(self.initial_balance)
        }
