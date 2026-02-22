"""
Adaptive CORE-HODL Strategy (DCA with 3-phase deployment and rebalancing)

This is the CORE-HODL engine implementation - a sophisticated accumulation strategy
that dynamically adjusts to portfolio size and target allocation ratios.

Strategy Phases:
1. DEPLOYING: Initial capital deployment to reach 60% target allocation
2. REBALANCING: Adjusting BTC/ETH ratio without selling (buy more of underallocated)
3. MAINTAINING: Normal DCA operation to maintain target ratios

Key Features:
- Dynamic DCA amount based on gap to target (1, 4, or 12 week deployment)
- Rebalancing without selling (gradual buy adjustments over 4 weeks)
- 67% BTC / 33% ETH target ratio within crypto allocation
- Handles accounts from $100 to $164K+
- Never generates SELL signals (accumulation only)

Risk Level: MINIMAL
Timeframe: Weekly purchases
Assets: BTC, ETH (spot only)
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import structlog

from src.core.models import MarketData, TradingSignal, SignalType, Position
from src.core.config import engine_config
from src.strategies.base import BaseStrategy

logger = structlog.get_logger(__name__)


class CoreHodlState(Enum):
    """Core HODL strategy operational states."""
    DEPLOYING = "deploying"       # Initial capital deployment to reach target
    REBALANCING = "rebalancing"   # Adjusting BTC/ETH ratio
    MAINTAINING = "maintaining"   # Normal operation - maintaining ratios


class DCAStrategy(BaseStrategy):
    """
    Adaptive CORE-HODL Strategy.
    
    This strategy implements a 3-phase capital deployment system:
    
    Phase 1: DEPLOYING
    - Calculate gap between current and target (60% of portfolio)
    - Deploy schedule:
      * Gap < $500: 1 week
      * Gap < $50,000: 4 weeks
      * Gap >= $50,000: 12 weeks
    - Respect min order size ($5) and max (5% portfolio, $10K cap)
    
    Phase 2: REBALANCING
    - Target ratio: 67% BTC / 33% ETH of crypto allocation
    - Trigger: Ratio deviates >10% from target
    - Method: Adjust buy amounts over 4 weeks without selling:
      Week 1: 75% overallocated / 125% underallocated
      Week 2: 50% overallocated / 150% underallocated
      Week 3: 25% overallocated / 175% underallocated
      Week 4: 0% overallocated / 200% underallocated
    
    Phase 3: MAINTAINING
    - Standard equal-amount DCA buys
    - Monitor for rebalancing needs
    
    Configuration:
        symbols: Must include BTC and ETH pairs (e.g., ["BTCUSDT", "ETHUSDT"])
        portfolio_value: Current total portfolio value (updated externally)
        current_positions: Current position values by symbol
        interval_hours: Hours between purchases (default: 168 = weekly)
    
    Risk Level: MINIMAL
    Best For: Long-term crypto wealth accumulation
    """
    
    # Target allocation constants
    TARGET_PORTFOLIO_PCT = Decimal("0.60")  # 60% of total portfolio
    BTC_RATIO = Decimal("0.67")             # 67% of crypto allocation
    ETH_RATIO = Decimal("0.33")             # 33% of crypto allocation
    
    # Thresholds
    REBALANCE_THRESHOLD_PCT = Decimal("0.10")  # 10% deviation triggers rebalance
    MIN_ORDER_USD = Decimal("5")               # Minimum $5 order
    MAX_POSITION_PCT = Decimal("0.05")         # Max 5% per position
    MAX_ORDER_USD = Decimal("10000")           # Hard cap at $10K
    
    # Deployment schedule thresholds
    DEPLOY_SMALL_GAP = Decimal("500")          # < $500: 1 week
    DEPLOY_MEDIUM_GAP = Decimal("50000")       # < $50K: 4 weeks
    # >= $50K: 12 weeks
    
    # Deployment durations (in weeks)
    DEPLOY_WEEKS_SMALL = 1
    DEPLOY_WEEKS_MEDIUM = 4
    DEPLOY_WEEKS_LARGE = 12
    
    # Rebalancing schedule (weeks 1-4 multipliers)
    REBALANCE_MULTIPLIERS_OVER = [
        Decimal("0.75"),  # Week 1: 75%
        Decimal("0.50"),  # Week 2: 50%
        Decimal("0.25"),  # Week 3: 25%
        Decimal("0.00"),  # Week 4: 0%
    ]
    REBALANCE_MULTIPLIERS_UNDER = [
        Decimal("1.25"),  # Week 1: 125%
        Decimal("1.50"),  # Week 2: 150%
        Decimal("1.75"),  # Week 3: 175%
        Decimal("2.00"),  # Week 4: 200%
    ]
    
    def __init__(self, symbols: List[str], name: str = "CORE-HODL", **kwargs):
        super().__init__(name, symbols, **kwargs)
        
        # Strategy configuration
        self.interval_hours = kwargs.get(
            'interval_hours',
            engine_config.core_hodl.dca_interval_hours if hasattr(engine_config, 'core_hodl') else 168
        )
        self.base_amount_usdt = kwargs.get(
            'amount_usdt',
            engine_config.core_hodl.dca_amount_usdt if hasattr(engine_config, 'core_hodl') else 100
        )
        
        # State management
        self._state = CoreHodlState.DEPLOYING
        self._rebalance_week = 0  # Current week in rebalancing (0-3)
        self._rebalance_start_time: Optional[datetime] = None
        
        # Portfolio tracking (updated by external caller)
        self.portfolio_value: Decimal = kwargs.get('portfolio_value', Decimal("0"))
        self.current_positions: Dict[str, Decimal] = kwargs.get('current_positions', {})
        
        # Deployment tracking - freeze the capital amount to deploy
        self._deployment_start_value: Optional[Decimal] = None  # Set on first update
        self._deployment_weeks_remaining: Optional[int] = None  # Calculated based on gap
        self._deployment_new_deposits: Decimal = Decimal("0")  # Track new deposits separately
        self._DEPLOYMENT_THRESHOLD_PCT = Decimal("0.20")  # 20% increase = new deposit
        
        # Track last purchase time per symbol
        self.last_purchase: Dict[str, datetime] = {}
        
        # Database callback for persistence (set by engine)
        self._db_save_callback: Optional[callable] = None
        
        # Statistics
        self.total_invested: Dict[str, Decimal] = {s: Decimal("0") for s in symbols}
        self.purchase_count: Dict[str, int] = {s: 0 for s in symbols}
        
        # Identify BTC and ETH symbols
        self.btc_symbol = self._find_symbol(symbols, ["BTC", "bitcoin"])
        self.eth_symbol = self._find_symbol(symbols, ["ETH", "ethereum"])
        
        self.logger.info(
            "core_hodl_strategy.initialized",
            interval_hours=self.interval_hours,
            base_amount_usdt=float(self.base_amount_usdt),
            symbols=symbols,
            btc_symbol=self.btc_symbol,
            eth_symbol=self.eth_symbol,
            state=self._state.value
        )
    
    def _find_symbol(self, symbols: List[str], keywords: List[str]) -> Optional[str]:
        """Find a symbol matching any of the keywords."""
        for symbol in symbols:
            upper = symbol.upper()
            for keyword in keywords:
                if keyword.upper() in upper:
                    return symbol
        return None
    
    def set_db_save_callback(self, callback: callable):
        """
        Set callback for saving last_purchase to database.
        
        Args:
            callback: Async function callback(strategy_name, symbol, last_purchase)
        """
        self._db_save_callback = callback
    
    async def load_last_purchase_times(self, load_func: callable) -> Dict[str, datetime]:
        """
        Load last purchase times from database.
        
        Args:
            load_func: Async function that returns Dict[str, datetime] of symbol->timestamp
            
        Returns:
            Dictionary of loaded last_purchase times
        """
        try:
            loaded = await load_func()
            if loaded:
                self.last_purchase.update(loaded)
                self.logger.info(
                    "core_hodl.last_purchase_loaded",
                    symbols=list(loaded.keys()),
                    count=len(loaded)
                )
            return loaded
        except Exception as e:
            self.logger.warning("core_hodl.last_purchase_load_failed", error=str(e))
            return {}
    
    async def _save_last_purchase(self, symbol: str, timestamp: datetime):
        """
        Save last purchase time to database if callback is set.
        
        Args:
            symbol: Trading pair symbol
            timestamp: Purchase timestamp
        """
        if self._db_save_callback:
            try:
                await self._db_save_callback(self.name, symbol, timestamp)
            except Exception as e:
                self.logger.warning(
                    "core_hodl.last_purchase_save_failed",
                    symbol=symbol,
                    error=str(e)
                )
    
    def get_state(self) -> CoreHodlState:
        """Get current strategy state."""
        return self._state
    
    def get_target_allocation(self) -> Dict[str, Decimal]:
        """
        Calculate target allocation values based on current portfolio.
        
        Returns:
            Dictionary with 'total', 'btc', 'eth' target amounts in USD
        """
        total_target = self.portfolio_value * self.TARGET_PORTFOLIO_PCT
        btc_target = total_target * self.BTC_RATIO
        eth_target = total_target * self.ETH_RATIO
        
        return {
            'total': total_target,
            'btc': btc_target,
            'eth': eth_target
        }
    
    def calculate_deployment_amount(self, symbol: str) -> Decimal:
        """
        Calculate how much to buy this week for deployment phase.
        
        Uses the deployment_start_value (frozen at first update) to ensure
        consistent deployment schedule even if new deposits are made.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Amount in USD to deploy this week (may be 0 if no gap)
        """
        # Use deployment start value, not current portfolio value
        # This ensures consistent deployment even with new deposits
        base_value = self._deployment_start_value or self.portfolio_value
        
        if not base_value or base_value <= 0:
            return Decimal("0")
        
        # Calculate targets based on frozen deployment value
        total_target = base_value * self.TARGET_PORTFOLIO_PCT
        
        # Determine symbol-specific target
        if symbol == self.btc_symbol:
            target_value = total_target * self.BTC_RATIO
        elif symbol == self.eth_symbol:
            target_value = total_target * self.ETH_RATIO
        else:
            # Unknown symbol - use proportional allocation
            target_value = total_target / Decimal(len(self.symbols))
        
        # Calculate current value for this symbol
        current_value = self.current_positions.get(symbol, Decimal("0"))
        
        # Calculate gap to target
        gap = target_value - current_value
        
        if gap <= 0:
            # Already at or above target
            return Decimal("0")
        
        # Determine deployment weeks based on gap size (only on first calculation)
        if self._deployment_weeks_remaining is None:
            if gap < self.DEPLOY_SMALL_GAP:
                self._deployment_weeks_remaining = self.DEPLOY_WEEKS_SMALL
            elif gap < self.DEPLOY_MEDIUM_GAP:
                self._deployment_weeks_remaining = self.DEPLOY_WEEKS_MEDIUM
            else:
                self._deployment_weeks_remaining = self.DEPLOY_WEEKS_LARGE
            
            self.logger.info(
                "core_hodl.deployment_schedule_set",
                gap=float(gap),
                weeks=self._deployment_weeks_remaining,
                weekly_target=float(gap / self._deployment_weeks_remaining)
            )
        
        # Calculate weekly deployment amount
        weekly_amount = gap / Decimal(self._deployment_weeks_remaining)
        
        # Apply constraints (use current portfolio for max constraints)
        max_allowed = min(
            self.portfolio_value * self.MAX_POSITION_PCT,
            self.MAX_ORDER_USD
        )
        
        weekly_amount = min(weekly_amount, max_allowed)
        
        # Ensure minimum order size
        if weekly_amount < self.MIN_ORDER_USD:
            return Decimal("0")
        
        return weekly_amount
    
    def calculate_rebalance_adjustment(self, symbol: str, base_amount: Decimal) -> Decimal:
        """
        Adjust buy amount for rebalancing based on current ratio deviation.
        
        Args:
            symbol: Trading pair symbol
            base_amount: Base DCA amount
            
        Returns:
            Adjusted amount (may be 0 for overallocated asset in week 4)
        """
        if self._state != CoreHodlState.REBALANCING:
            return base_amount
        
        if not self.portfolio_value or self.portfolio_value <= 0:
            return base_amount
        
        # Get current values
        btc_value = self.current_positions.get(self.btc_symbol, Decimal("0"))
        eth_value = self.current_positions.get(self.eth_symbol, Decimal("0"))
        total_crypto = btc_value + eth_value
        
        if total_crypto <= 0:
            # No positions yet - use base amounts
            return base_amount
        
        # Calculate current ratios
        current_btc_ratio = btc_value / total_crypto
        current_eth_ratio = eth_value / total_crypto
        
        # Determine if symbol is over or under allocated
        if symbol == self.btc_symbol:
            deviation = current_btc_ratio - self.BTC_RATIO
            is_overallocated = deviation > 0
        elif symbol == self.eth_symbol:
            deviation = current_eth_ratio - self.ETH_RATIO
            is_overallocated = deviation > 0
        else:
            return base_amount
        
        # Apply rebalancing multiplier based on week and allocation status
        week_index = min(self._rebalance_week, 3)  # Clamp to valid index
        
        if is_overallocated:
            multiplier = self.REBALANCE_MULTIPLIERS_OVER[week_index]
        else:
            multiplier = self.REBALANCE_MULTIPLIERS_UNDER[week_index]
        
        adjusted = base_amount * multiplier
        
        # Apply constraints
        max_allowed = min(
            self.portfolio_value * self.MAX_POSITION_PCT,
            self.MAX_ORDER_USD
        )
        adjusted = min(adjusted, max_allowed)
        
        # Ensure minimum (unless multiplier is 0)
        if multiplier > 0 and adjusted < self.MIN_ORDER_USD:
            adjusted = Decimal("0")
        
        return adjusted
    
    def _update_state(self) -> None:
        """
        Update strategy state based on current portfolio conditions.
        
        State transitions:
        - DEPLOYING -> REBALANCING: When deployment target reached but ratio off
        - DEPLOYING -> MAINTAINING: When at target and ratio good
        - REBALANCING -> MAINTAINING: After 4 weeks of rebalancing
        - MAINTAINING -> REBALANCING: When ratio deviates >10%
        """
        if not self.portfolio_value or self.portfolio_value <= 0:
            return
        
        targets = self.get_target_allocation()
        
        # Calculate current total crypto value
        total_crypto = sum(self.current_positions.get(s, Decimal("0")) for s in self.symbols)
        
        # Check deployment gap
        deployment_gap = targets['total'] - total_crypto
        
        # Check ratio deviation
        btc_value = self.current_positions.get(self.btc_symbol, Decimal("0"))
        eth_value = self.current_positions.get(self.eth_symbol, Decimal("0"))
        
        if total_crypto > 0:
            current_btc_ratio = btc_value / total_crypto
            btc_deviation = abs(current_btc_ratio - self.BTC_RATIO)
            needs_rebalance = btc_deviation > self.REBALANCE_THRESHOLD_PCT
        else:
            needs_rebalance = False
        
        # State machine
        if self._state == CoreHodlState.DEPLOYING:
            if deployment_gap < self.MIN_ORDER_USD:
                # Deployment complete - check if rebalancing needed
                if needs_rebalance:
                    self._state = CoreHodlState.REBALANCING
                    self._rebalance_week = 0
                    self._rebalance_start_time = datetime.now(timezone.utc)
                    self.logger.info(
                        "core_hodl.state_change",
                        from_state="deploying",
                        to_state="rebalancing",
                        reason="deployment_complete_ratio_off"
                    )
                else:
                    self._state = CoreHodlState.MAINTAINING
                    self.logger.info(
                        "core_hodl.state_change",
                        from_state="deploying",
                        to_state="maintaining",
                        reason="deployment_complete_ratio_good"
                    )
        
        elif self._state == CoreHodlState.REBALANCING:
            # Check if rebalancing period is complete
            if self._rebalance_start_time:
                weeks_elapsed = (datetime.now(timezone.utc) - self._rebalance_start_time).days / 7
                if weeks_elapsed >= 4:
                    self._state = CoreHodlState.MAINTAINING
                    self._rebalance_week = 0
                    self.logger.info(
                        "core_hodl.state_change",
                        from_state="rebalancing",
                        to_state="maintaining",
                        reason="rebalance_complete"
                    )
                else:
                    # Update current week (0-3)
                    self._rebalance_week = int(weeks_elapsed)
        
        elif self._state == CoreHodlState.MAINTAINING:
            if needs_rebalance:
                self._state = CoreHodlState.REBALANCING
                self._rebalance_week = 0
                self._rebalance_start_time = datetime.now(timezone.utc)
                self.logger.info(
                    "core_hodl.state_change",
                    from_state="maintaining",
                    to_state="rebalancing",
                    reason="ratio_deviation",
                    deviation=float(btc_deviation)
                )
    
    def _calculate_buy_amount(self, symbol: str) -> Decimal:
        """
        Calculate the final buy amount for a symbol based on current state.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Final USD amount to buy (0 if no buy needed)
        """
        # Update state first
        self._update_state()
        
        # Get base amount based on state
        if self._state == CoreHodlState.DEPLOYING:
            amount = self.calculate_deployment_amount(symbol)
        else:
            # For REBALANCING and MAINTAINING, use base DCA amount
            amount = Decimal(str(self.base_amount_usdt))
        
        # Apply rebalancing adjustments if in rebalancing phase
        if self._state == CoreHodlState.REBALANCING:
            amount = self.calculate_rebalance_adjustment(symbol, amount)
        
        # Final constraints
        max_allowed = min(
            self.portfolio_value * self.MAX_POSITION_PCT,
            self.MAX_ORDER_USD
        )
        amount = min(amount, max_allowed)
        
        # Ensure minimum
        if amount < self.MIN_ORDER_USD:
            return Decimal("0")
        
        return amount
    
    async def analyze(self, data: Dict[str, List[MarketData]]) -> List[TradingSignal]:
        """
        Generate buy signals based on current state and allocation needs.
        
        Args:
            data: Dictionary of symbol -> list of MarketData
            
        Returns:
            List of TradingSignal objects (BUY signals only, no SELL)
        """
        signals = []
        now = datetime.now(timezone.utc)
        
        for symbol in self.symbols:
            if symbol not in data or not data[symbol]:
                continue
            
            last_price = data[symbol][-1].close
            
            # Check if it's time for next purchase
            last_purchase = self.last_purchase.get(symbol)
            
            if last_purchase is not None:
                time_since_last = now - last_purchase
                if time_since_last < timedelta(hours=self.interval_hours):
                    # Not time yet
                    continue
            
            # Calculate buy amount for this symbol
            buy_amount = self._calculate_buy_amount(symbol)
            
            if buy_amount > 0:
                # Determine reason for signal
                if self._state == CoreHodlState.DEPLOYING:
                    reason = "deployment"
                elif self._state == CoreHodlState.REBALANCING:
                    reason = f"rebalance_week_{self._rebalance_week + 1}"
                else:
                    reason = "maintenance"
                
                # Update last_purchase in memory to prevent duplicate signals
                # during the same analysis cycle. Database save happens in 
                # on_order_filled() only when orders actually execute.
                self.last_purchase[symbol] = now
                
                signals.append(self._create_buy_signal(symbol, last_price, buy_amount, reason))
        
        return signals
    
    def _create_buy_signal(
        self,
        symbol: str,
        price: Decimal,
        amount: Decimal,
        reason: str
    ) -> TradingSignal:
        """Create a CORE-HODL buy signal."""
        targets = self.get_target_allocation()
        current_value = self.current_positions.get(symbol, Decimal("0"))
        
        metadata = {
            'strategy': 'CORE-HODL',
            'state': self._state.value,
            'amount_usdt': float(amount),
            'current_price': float(price),
            'reason': reason,
            'interval_hours': self.interval_hours,
            'target_allocation': {
                'total': float(targets['total']),
                'btc': float(targets['btc']),
                'eth': float(targets['eth'])
            },
            'current_value': float(current_value),
            'portfolio_value': float(self.portfolio_value)
        }
        
        if self._state == CoreHodlState.REBALANCING:
            metadata['rebalance_week'] = self._rebalance_week + 1
        
        self.logger.info(
            "core_hodl.signal",
            symbol=symbol,
            price=str(price),
            amount=float(amount),
            state=self._state.value,
            reason=reason
        )
        
        return self._create_signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            confidence=1.0,  # DCA is deterministic
            metadata=metadata
        )
    
    async def on_order_filled(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal
    ):
        """Track CORE-HODL purchases."""
        if side == "buy":
            order_value = amount * price
            self.total_invested[symbol] += order_value
            self.purchase_count[symbol] += 1
            
            # Update internal position tracking
            if symbol not in self.current_positions:
                self.current_positions[symbol] = Decimal("0")
            self.current_positions[symbol] += order_value
            
            # Save last_purchase to database only when order actually fills
            # This ensures persistence across restarts without saving rejected signals
            now = datetime.now(timezone.utc)
            self.last_purchase[symbol] = now
            await self._save_last_purchase(symbol, now)
            
            # Decrement deployment weeks if in deploying phase
            # Only decrement once per weekly cycle, not per coin
            # Track that this symbol bought this week
            if self._state == CoreHodlState.DEPLOYING and self._deployment_weeks_remaining > 0:
                # Initialize weekly tracking if needed
                if not hasattr(self, '_weekly_purchase_count'):
                    self._weekly_purchase_count = 0
                
                # Count unique symbols purchased this week
                # We only decrement weeks_remaining once per weekly cycle
                # when the first symbol is purchased (after 168h interval)
                if symbol == self.btc_symbol and self.purchase_count.get(symbol, 0) == 1:
                    # First BTC purchase of this week cycle - decrement week counter
                    self._deployment_weeks_remaining -= 1
                    self.logger.info(
                        "core_hodl.deployment_week_completed",
                        weeks_remaining=self._deployment_weeks_remaining,
                        week_number=12 - self._deployment_weeks_remaining
                    )
            
            self.logger.info(
                "core_hodl.purchase_recorded",
                symbol=symbol,
                amount=str(amount),
                price=str(price),
                value=float(order_value),
                total_invested=float(self.total_invested[symbol]),
                purchase_count=self.purchase_count[symbol],
                state=self._state.value,
                weeks_remaining=self._deployment_weeks_remaining
            )
    
    async def on_position_closed(
        self,
        symbol: str,
        pnl: Decimal,
        pnl_pct: Decimal
    ):
        """Track position close (rarely used in CORE-HODL)."""
        self.total_pnl += pnl
        self.logger.info(
            "core_hodl.position_closed",
            symbol=symbol,
            pnl=str(pnl),
            pnl_pct=str(pnl_pct),
            state=self._state.value
        )
    
    def update_portfolio_state(
        self,
        portfolio_value: Decimal,
        positions: Dict[str, Decimal]
    ) -> None:
        """
        Update portfolio state from external source.
        
        Handles new deposits by tracking them separately from deployment capital.
        
        Args:
            portfolio_value: Total portfolio value in USD
            positions: Dictionary of symbol -> position value in USD
        """
        # Check for new deposits (significant increase in portfolio value)
        if self._deployment_start_value is not None and portfolio_value > self._deployment_start_value:
            increase_pct = (portfolio_value - self._deployment_start_value) / self._deployment_start_value
            if increase_pct > self._DEPLOYMENT_THRESHOLD_PCT:
                # New deposit detected (>20% increase)
                new_capital = portfolio_value - self._deployment_start_value
                self._deployment_new_deposits += new_capital
                self.logger.info(
                    "core_hodl.new_deposit_detected",
                    previous_value=float(self._deployment_start_value),
                    new_value=float(portfolio_value),
                    deposit_amount=float(new_capital),
                    increase_pct=float(increase_pct * 100)
                )
                # Note: New deposits will be handled via maintenance DCA after initial deployment
        
        # Initialize deployment start value on first update
        if self._deployment_start_value is None and portfolio_value > 0:
            self._deployment_start_value = portfolio_value
            self.logger.info(
                "core_hodl.deployment_started",
                start_value=float(portfolio_value),
                target_60pct=float(portfolio_value * self.TARGET_PORTFOLIO_PCT)
            )
        
        self.portfolio_value = portfolio_value
        self.current_positions = positions.copy()
        
        self.logger.debug(
            "core_hodl.portfolio_updated",
            portfolio_value=float(portfolio_value),
            deployment_start=float(self._deployment_start_value) if self._deployment_start_value else None,
            new_deposits=float(self._deployment_new_deposits),
            positions={k: float(v) for k, v in positions.items()}
        )
    
    def get_time_to_next_purchase(self, symbol: str) -> Optional[timedelta]:
        """Get time remaining until next scheduled purchase."""
        if symbol not in self.last_purchase:
            return timedelta(0)
        
        next_purchase = self.last_purchase[symbol] + timedelta(hours=self.interval_hours)
        remaining = next_purchase - datetime.now(timezone.utc)
        
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def get_allocation_status(self) -> Dict[str, Any]:
        """
        Get detailed allocation status for monitoring.
        
        Returns:
            Dictionary with current vs target allocation details
        """
        targets = self.get_target_allocation()
        total_crypto = sum(self.current_positions.get(s, Decimal("0")) for s in self.symbols)
        
        btc_value = self.current_positions.get(self.btc_symbol, Decimal("0"))
        eth_value = self.current_positions.get(self.eth_symbol, Decimal("0"))
        
        btc_pct = (btc_value / total_crypto * 100) if total_crypto > 0 else Decimal("0")
        eth_pct = (eth_value / total_crypto * 100) if total_crypto > 0 else Decimal("0")
        
        return {
            'state': self._state.value,
            'rebalance_week': self._rebalance_week + 1 if self._state == CoreHodlState.REBALANCING else None,
            'portfolio_value': float(self.portfolio_value),
            'target_total': float(targets['total']),
            'current_total': float(total_crypto),
            'deployment_gap': float(targets['total'] - total_crypto),
            'btc': {
                'target': float(targets['btc']),
                'current': float(btc_value),
                'target_pct': float(self.BTC_RATIO * 100),
                'current_pct': float(btc_pct),
                'gap': float(targets['btc'] - btc_value)
            },
            'eth': {
                'target': float(targets['eth']),
                'current': float(eth_value),
                'target_pct': float(self.ETH_RATIO * 100),
                'current_pct': float(eth_pct),
                'gap': float(targets['eth'] - eth_value)
            }
        }
    
    def get_stats(self) -> Dict:
        """Get CORE-HODL strategy statistics."""
        base_stats = super().get_stats()
        
        allocation_status = self.get_allocation_status()
        
        base_stats.update({
            'state': self._state.value,
            'interval_hours': self.interval_hours,
            'base_amount_usdt': float(self.base_amount_usdt),
            'total_invested': {k: str(v) for k, v in self.total_invested.items()},
            'purchase_count': self.purchase_count,
            'avg_investment_per_symbol': {
                k: str(v / self.purchase_count[k]) if self.purchase_count[k] > 0 else "0"
                for k, v in self.total_invested.items()
            },
            'allocation_status': allocation_status,
            'next_purchase_in_hours': {
                s: self.get_time_to_next_purchase(s).total_seconds() / 3600 if self.get_time_to_next_purchase(s) else 0
                for s in self.symbols
            }
        })
        return base_stats
