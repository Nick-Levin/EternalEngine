"""Risk management system - THE MOST CRITICAL COMPONENT.

This module implements the comprehensive risk management framework for The Eternal Engine,
including the Four-Level Circuit Breaker System, risk-based position sizing, and
multi-layer risk validation.

CRITICAL: Any changes to this file must be reviewed and tested thoroughly.
Incorrect risk controls can lead to catastrophic losses.
"""
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import structlog

from src.core.models import (
    Order, Position, Portfolio, TradingSignal, SignalType,
    PositionSide, OrderSide, CircuitBreakerLevel
)
from src.core.config import trading_config

logger = structlog.get_logger(__name__)


class RiskLevel(Enum):
    """Risk severity levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class RiskCheck:
    """Result of a risk validation check.
    
    Attributes:
        passed: Whether the signal/order passed all risk checks
        reason: Human-readable explanation if check failed
        risk_level: Severity level of the risk assessment
        rule_triggered: Name of the risk rule that triggered (if any)
        metadata: Additional diagnostic information
    """
    passed: bool
    reason: str = ""
    risk_level: str = "normal"
    rule_triggered: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskRule:
    """Individual risk rule definition.
    
    Attributes:
        name: Unique identifier for the rule
        check_fn: Function that performs the validation
        priority: Lower numbers = higher priority (checked first)
        is_blocking: If True, failure stops all further checks
    """
    name: str
    check_fn: Callable[..., RiskCheck]
    priority: int = 100
    is_blocking: bool = True


@dataclass
class CircuitBreaker:
    """Circuit breaker state and configuration.
    
    Tracks the current circuit breaker level, when it was triggered,
    and any automatic recovery conditions.
    """
    level: CircuitBreakerLevel = CircuitBreakerLevel.NONE
    triggered_at: Optional[datetime] = None
    triggered_by: Optional[str] = None
    recovery_conditions: Dict[str, Any] = field(default_factory=dict)
    pause_until: Optional[datetime] = None
    
    # Action flags for current level
    reduce_positions_pct: Decimal = Decimal("0")  # 0.25 = 25% reduction
    pause_new_entries: bool = False
    close_directional: bool = False
    full_liquidation: bool = False
    widen_stops_pct: Decimal = Decimal("0")  # Additional stop buffer


class PositionSizingMethod(Enum):
    """Position sizing calculation methods."""
    KELLY = "kelly"           # Kelly Criterion based
    RISK_BASED = "risk_based" # Fixed risk per trade
    FIXED_PCT = "fixed_pct"   # Fixed percentage of portfolio


class RiskManager:
    """
    Central risk management system for The Eternal Engine.
    
    Implements comprehensive risk controls including:
    - Four-Level Circuit Breaker System (10%, 15%, 20%, 25% drawdown)
    - Risk-based position sizing (1/8 Kelly, 1% risk per trade)
    - Multi-layer risk validation with priority ordering
    - Correlation crisis detection
    - Emergency stop capabilities
    
    HARD LIMITS - These are non-negotiable:
    - Max position size: 5% of portfolio per position
    - Max daily loss: 2% of portfolio
    - Max weekly loss: 5% of portfolio
    - Max concurrent positions: 3
    - Max leverage: 2x (TREND/FUNDING), 1x (others)
    - Kelly fraction: 0.125 (1/8 Kelly)
    """
    
    # Circuit breaker thresholds (drawdown percentages)
    CIRCUIT_BREAKER_LEVELS = {
        CircuitBreakerLevel.LEVEL_1: Decimal("0.10"),  # 10% drawdown
        CircuitBreakerLevel.LEVEL_2: Decimal("0.15"),  # 15% drawdown
        CircuitBreakerLevel.LEVEL_3: Decimal("0.20"),  # 20% drawdown
        CircuitBreakerLevel.LEVEL_4: Decimal("0.25"),  # 25% drawdown
    }
    
    # Circuit breaker actions
    CIRCUIT_BREAKER_ACTIONS = {
        CircuitBreakerLevel.LEVEL_1: {
            'reduce_positions_pct': Decimal("0.25"),
            'pause_new_entries': False,
            'close_directional': False,
            'full_liquidation': False,
            'widen_stops_pct': Decimal("0.005"),  # 0.5% additional buffer
            'auto_recovery_drawdown': Decimal("0.05"),  # Recover at 5% from ATH
        },
        CircuitBreakerLevel.LEVEL_2: {
            'reduce_positions_pct': Decimal("0.50"),
            'pause_new_entries': True,
            'pause_duration_hours': 72,
            'close_directional': False,
            'full_liquidation': False,
            'widen_stops_pct': Decimal("0.01"),
            'manual_recovery_required': True,
        },
        CircuitBreakerLevel.LEVEL_3: {
            'reduce_positions_pct': Decimal("1.00"),
            'pause_new_entries': True,
            'close_directional': True,
            'full_liquidation': False,
            'move_to_stables_pct': Decimal("0.50"),
            'audit_required': True,
        },
        CircuitBreakerLevel.LEVEL_4: {
            'reduce_positions_pct': Decimal("1.00"),
            'pause_new_entries': True,
            'close_directional': True,
            'full_liquidation': True,
            'dual_auth_required': True,
        },
    }
    
    # Risk configuration constants
    KELLY_FRACTION = Decimal("0.125")  # 1/8 Kelly for safety
    MAX_LEVERAGE_TREND = Decimal("2.0")
    MAX_LEVERAGE_FUNDING = Decimal("2.0")
    MAX_LEVERAGE_CORE = Decimal("1.0")
    MAX_LEVERAGE_TACTICAL = Decimal("1.0")
    DEFAULT_RISK_PER_TRADE = Decimal("0.01")  # 1% risk per trade
    CORRELATION_CRISIS_THRESHOLD = Decimal("0.90")
    MIN_SIGNAL_CONFIDENCE = Decimal("0.60")
    
    def __init__(self):
        # PnL tracking
        self.daily_pnl: Decimal = Decimal("0")
        self.weekly_pnl: Decimal = Decimal("0")
        self.daily_starting_balance: Optional[Decimal] = None
        self.weekly_starting_balance: Optional[Decimal] = None
        self.all_time_high_balance: Optional[Decimal] = None
        self.last_reset_day: Optional[datetime] = None
        self.last_reset_week: Optional[datetime] = None
        
        # Emergency stop
        self.emergency_stop = False
        self.emergency_reason: Optional[str] = None
        self.emergency_triggered_at: Optional[datetime] = None
        
        # Circuit breaker state
        self.circuit_breaker = CircuitBreaker()
        self.circuit_breaker_history: List[Dict] = []
        
        # Risk rules registry
        self._risk_rules: List[RiskRule] = []
        self._register_default_rules()
        
        # Tracking
        self.rejected_signals: List[Dict] = []
        self.position_correlations: Dict[str, Decimal] = {}
        
        # Position sizing settings
        self.sizing_method = PositionSizingMethod.RISK_BASED
        
    def _register_default_rules(self):
        """Register the default set of risk rules in priority order."""
        self._risk_rules = [
            # Priority 1: Emergency stop check (highest priority, blocking)
            RiskRule(
                name="emergency_stop",
                check_fn=self._check_emergency_stop,
                priority=1,
                is_blocking=True
            ),
            # Priority 2: Circuit breaker check
            RiskRule(
                name="circuit_breaker",
                check_fn=self._check_circuit_breaker_rule,
                priority=2,
                is_blocking=True
            ),
            # Priority 3: Daily loss limit
            RiskRule(
                name="daily_loss_limit",
                check_fn=self._check_daily_loss_limit,
                priority=3,
                is_blocking=True
            ),
            # Priority 4: Weekly loss limit
            RiskRule(
                name="weekly_loss_limit",
                check_fn=self._check_weekly_loss_limit,
                priority=4,
                is_blocking=True
            ),
            # Priority 5: Maximum position size
            RiskRule(
                name="max_position_size",
                check_fn=self._check_max_position_size,
                priority=5,
                is_blocking=True
            ),
            # Priority 6: Maximum concurrent positions
            RiskRule(
                name="max_concurrent_positions",
                check_fn=self._check_max_concurrent_positions,
                priority=6,
                is_blocking=True
            ),
            # Priority 7: Correlation crisis check
            RiskRule(
                name="correlation_crisis",
                check_fn=self._check_correlation_crisis,
                priority=7,
                is_blocking=False  # Warning only, doesn't block
            ),
            # Priority 8: Signal confidence check
            RiskRule(
                name="signal_confidence",
                check_fn=self._check_signal_confidence,
                priority=8,
                is_blocking=True
            ),
            # Priority 9: Duplicate position check
            RiskRule(
                name="duplicate_position",
                check_fn=self._check_duplicate_position,
                priority=9,
                is_blocking=True
            ),
        ]
        # Sort by priority
        self._risk_rules.sort(key=lambda r: r.priority)
    
    async def initialize(self, portfolio: Portfolio):
        """Initialize risk manager with current portfolio state."""
        now = datetime.utcnow()
        self.daily_starting_balance = portfolio.total_balance
        self.weekly_starting_balance = portfolio.total_balance
        self.all_time_high_balance = portfolio.total_balance
        self.last_reset_day = now
        self.last_reset_week = now
        
        logger.info(
            "risk_manager.initialized",
            daily_start=str(self.daily_starting_balance),
            weekly_start=str(self.weekly_starting_balance),
            max_position_pct=trading_config.max_position_pct,
            max_daily_loss_pct=trading_config.max_daily_loss_pct,
            max_weekly_loss_pct=trading_config.max_weekly_loss_pct,
            kelly_fraction=float(self.KELLY_FRACTION),
        )
    
    def reset_periods(self, portfolio: Portfolio):
        """Reset daily/weekly tracking periods."""
        now = datetime.utcnow()
        
        # Reset daily
        if self.last_reset_day and now.date() != self.last_reset_day.date():
            self.daily_pnl = Decimal("0")
            self.daily_starting_balance = portfolio.total_balance
            self.last_reset_day = now
            # Don't auto-reset emergency stop - requires manual intervention
            logger.info("risk_manager.daily_reset", new_balance=str(portfolio.total_balance))
        
        # Reset weekly
        if self.last_reset_week:
            days_since_reset = (now - self.last_reset_week).days
            if days_since_reset >= 7:
                self.weekly_pnl = Decimal("0")
                self.weekly_starting_balance = portfolio.total_balance
                self.last_reset_week = now
                logger.info("risk_manager.weekly_reset", new_balance=str(portfolio.total_balance))
    
    def check_signal(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """
        Validate a trading signal against all risk rules.
        
        Rules are evaluated in priority order. If a blocking rule fails,
        subsequent rules are skipped.
        
        Args:
            signal: The trading signal to validate
            portfolio: Current portfolio state
            current_positions: Dictionary of open positions
            
        Returns:
            RiskCheck indicating if signal can be executed
        """
        # Reset periods if needed
        self.reset_periods(portfolio)
        
        # Update all-time high
        if self.all_time_high_balance and portfolio.total_balance > self.all_time_high_balance:
            self.all_time_high_balance = portfolio.total_balance
            logger.info("risk_manager.new_ath", balance=str(self.all_time_high_balance))
        
        # Check circuit breakers first
        self._check_circuit_breakers(portfolio)
        
        # Evaluate all risk rules in priority order
        warnings = []
        for rule in self._risk_rules:
            try:
                result = rule.check_fn(signal, portfolio, current_positions)
                
                if not result.passed:
                    # Log rejection
                    self._log_signal_rejected(signal, rule.name, result.reason)
                    
                    if rule.is_blocking:
                        logger.warning(
                            "risk_manager.signal_rejected_blocking",
                            symbol=signal.symbol,
                            rule=rule.name,
                            reason=result.reason,
                            priority=rule.priority
                        )
                        return RiskCheck(
                            passed=False,
                            reason=result.reason,
                            risk_level=result.risk_level,
                            rule_triggered=rule.name,
                            metadata=result.metadata
                        )
                    else:
                        # Non-blocking failure = warning
                        warnings.append({
                            'rule': rule.name,
                            'reason': result.reason,
                            'level': result.risk_level
                        })
                        
            except Exception as e:
                logger.error(
                    "risk_manager.rule_error",
                    rule=rule.name,
                    error=str(e),
                    symbol=signal.symbol
                )
                # On rule error, be conservative and block
                return RiskCheck(
                    passed=False,
                    reason=f"Risk rule '{rule.name}' encountered an error",
                    risk_level="critical",
                    rule_triggered=rule.name
                )
        
        # Signal passed all blocking rules
        logger.info(
            "risk_manager.signal_approved",
            symbol=signal.symbol,
            signal=signal.signal_type.value,
            strategy=signal.strategy_name,
            confidence=signal.confidence,
            warnings=warnings if warnings else None
        )
        
        return RiskCheck(
            passed=True,
            risk_level="warning" if warnings else "normal",
            reason=f"Passed with {len(warnings)} warning(s)" if warnings else "",
            metadata={'warnings': warnings} if warnings else {}
        )
    
    # === Risk Rule Implementations ===
    
    def _check_emergency_stop(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if emergency stop is active."""
        if self.emergency_stop:
            return RiskCheck(
                passed=False,
                reason=f"Emergency stop active: {self.emergency_reason}",
                risk_level="critical",
                metadata={
                    'triggered_at': self.emergency_triggered_at.isoformat() if self.emergency_triggered_at else None
                }
            )
        return RiskCheck(passed=True)
    
    def _check_circuit_breaker_rule(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if circuit breaker prevents new entries."""
        cb = self.circuit_breaker
        
        if cb.level == CircuitBreakerLevel.LEVEL_4:
            return RiskCheck(
                passed=False,
                reason=f"Circuit breaker LEVEL_4 active: Full liquidation required",
                risk_level="critical",
                metadata={'level': cb.level.value, 'triggered_at': cb.triggered_at.isoformat() if cb.triggered_at else None}
            )
        
        if cb.pause_new_entries and cb.pause_until and datetime.utcnow() < cb.pause_until:
            return RiskCheck(
                passed=False,
                reason=f"New entries paused until {cb.pause_until.isoformat()}",
                risk_level="critical",
                metadata={'pause_until': cb.pause_until.isoformat()}
            )
        
        if cb.close_directional and signal.signal_type in (SignalType.BUY, SignalType.SELL):
            return RiskCheck(
                passed=False,
                reason="Directional trading disabled due to circuit breaker",
                risk_level="critical",
                metadata={'level': cb.level.value}
            )
        
        return RiskCheck(passed=True)
    
    def _check_daily_loss_limit(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if daily loss limit has been reached."""
        daily_loss_pct = self._calculate_daily_loss_pct(portfolio)
        max_daily_loss = Decimal(str(trading_config.max_daily_loss_pct))
        
        if daily_loss_pct >= max_daily_loss:
            self.trigger_emergency_stop(f"Daily loss limit reached: {daily_loss_pct:.2f}%")
            return RiskCheck(
                passed=False,
                reason=f"Daily loss limit reached: {daily_loss_pct:.2f}% (max: {max_daily_loss}%)",
                risk_level="critical",
                metadata={'daily_loss_pct': float(daily_loss_pct), 'limit': float(max_daily_loss)}
            )
        
        # Warning at 80% of limit
        if daily_loss_pct >= max_daily_loss * Decimal("0.8"):
            return RiskCheck(
                passed=True,
                reason=f"Daily loss at {daily_loss_pct:.2f}% - approaching limit",
                risk_level="warning",
                metadata={'daily_loss_pct': float(daily_loss_pct)}
            )
        
        return RiskCheck(passed=True)
    
    def _check_weekly_loss_limit(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if weekly loss limit has been reached."""
        weekly_loss_pct = self._calculate_weekly_loss_pct(portfolio)
        max_weekly_loss = Decimal(str(trading_config.max_weekly_loss_pct))
        
        if weekly_loss_pct >= max_weekly_loss:
            self.trigger_emergency_stop(f"Weekly loss limit reached: {weekly_loss_pct:.2f}%")
            return RiskCheck(
                passed=False,
                reason=f"Weekly loss limit reached: {weekly_loss_pct:.2f}% (max: {max_weekly_loss}%)",
                risk_level="critical",
                metadata={'weekly_loss_pct': float(weekly_loss_pct), 'limit': float(max_weekly_loss)}
            )
        
        # Warning at 80% of limit
        if weekly_loss_pct >= max_weekly_loss * Decimal("0.8"):
            return RiskCheck(
                passed=True,
                reason=f"Weekly loss at {weekly_loss_pct:.2f}% - approaching limit",
                risk_level="warning",
                metadata={'weekly_loss_pct': float(weekly_loss_pct)}
            )
        
        return RiskCheck(passed=True)
    
    def _check_max_position_size(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if signal would exceed maximum position size."""
        if signal.symbol in current_positions:
            existing_position = current_positions[signal.symbol]
            position_value = existing_position.entry_price * existing_position.amount
            portfolio_pct = position_value / portfolio.total_balance * 100 if portfolio.total_balance > 0 else Decimal("0")
            max_pct = Decimal(str(trading_config.max_position_pct))
            
            if portfolio_pct >= max_pct:
                return RiskCheck(
                    passed=False,
                    reason=f"Position size {portfolio_pct:.2f}% exceeds maximum {max_pct}%",
                    risk_level="critical",
                    metadata={'current_pct': float(portfolio_pct), 'max_pct': float(max_pct)}
                )
        
        return RiskCheck(passed=True)
    
    def _check_max_concurrent_positions(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if maximum concurrent positions would be exceeded."""
        open_positions = len([
            p for p in current_positions.values() 
            if p.side != PositionSide.NONE
        ])
        max_positions = trading_config.max_concurrent_positions
        
        if open_positions >= max_positions:
            return RiskCheck(
                passed=False,
                reason=f"Max concurrent positions reached: {open_positions}/{max_positions}",
                risk_level="warning",
                metadata={'current': open_positions, 'max': max_positions}
            )
        
        return RiskCheck(passed=True)
    
    def _check_correlation_crisis(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if we're in a correlation crisis (all assets moving together)."""
        if len(current_positions) < 2:
            return RiskCheck(passed=True)
        
        # Calculate average correlation between positions
        # In a real implementation, this would use historical price data
        # For now, use a simplified check based on position P&L correlation
        avg_correlation = self._estimate_position_correlation(current_positions)
        
        if avg_correlation >= self.CORRELATION_CRISIS_THRESHOLD:
            return RiskCheck(
                passed=True,  # Warning only, doesn't block
                reason=f"Correlation crisis detected: {avg_correlation:.2f} - high systemic risk",
                risk_level="warning",
                metadata={'correlation': float(avg_correlation), 'threshold': float(self.CORRELATION_CRISIS_THRESHOLD)}
            )
        
        return RiskCheck(passed=True)
    
    def _check_signal_confidence(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if signal confidence meets minimum threshold."""
        confidence = Decimal(str(signal.confidence))
        
        if confidence < self.MIN_SIGNAL_CONFIDENCE:
            return RiskCheck(
                passed=False,
                reason=f"Signal confidence {confidence:.2f} below minimum {self.MIN_SIGNAL_CONFIDENCE}",
                risk_level="normal",
                metadata={'confidence': float(confidence), 'minimum': float(self.MIN_SIGNAL_CONFIDENCE)}
            )
        
        return RiskCheck(passed=True)
    
    def _check_duplicate_position(
        self,
        signal: TradingSignal,
        portfolio: Portfolio,
        current_positions: Dict[str, Position]
    ) -> RiskCheck:
        """Check if we already have a position in this symbol."""
        if signal.symbol in current_positions:
            existing = current_positions[signal.symbol]
            
            # Check for same-side position
            if signal.signal_type == SignalType.BUY and existing.side == PositionSide.LONG:
                return RiskCheck(
                    passed=False,
                    reason=f"Already have LONG position in {signal.symbol}",
                    risk_level="normal",
                    metadata={'symbol': signal.symbol, 'existing_side': existing.side.value}
                )
            
            if signal.signal_type == SignalType.SELL and existing.side == PositionSide.SHORT:
                return RiskCheck(
                    passed=False,
                    reason=f"Already have SHORT position in {signal.symbol}",
                    risk_level="normal",
                    metadata={'symbol': signal.symbol, 'existing_side': existing.side.value}
                )
        
        return RiskCheck(passed=True)
    
    # === Circuit Breaker Methods ===
    
    def check_circuit_breakers(self, portfolio: Portfolio) -> CircuitBreakerLevel:
        """
        Check and update circuit breaker state based on current drawdown.
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Current circuit breaker level
        """
        if not self.all_time_high_balance or self.all_time_high_balance == 0:
            return CircuitBreakerLevel.NONE
        
        current_drawdown = self._calculate_drawdown(portfolio)
        previous_level = self.circuit_breaker.level
        
        # Determine appropriate level
        new_level = CircuitBreakerLevel.NONE
        for level, threshold in sorted(self.CIRCUIT_BREAKER_LEVELS.items(), key=lambda x: x[1], reverse=True):
            if current_drawdown >= threshold:
                new_level = level
                break
        
        # If level changed, trigger actions
        if new_level != previous_level and new_level != CircuitBreakerLevel.NONE:
            self._activate_circuit_breaker(new_level, current_drawdown, portfolio)
        
        # Check for auto-recovery (Level 1 only)
        if self.circuit_breaker.level == CircuitBreakerLevel.LEVEL_1:
            recovery_threshold = self.CIRCUIT_BREAKER_ACTIONS[CircuitBreakerLevel.LEVEL_1]['auto_recovery_drawdown']
            if current_drawdown <= recovery_threshold:
                self.reset_circuit_breaker()
                logger.info(
                    "risk_manager.circuit_breaker_auto_recovered",
                    drawdown=float(current_drawdown),
                    recovery_threshold=float(recovery_threshold)
                )
        
        return self.circuit_breaker.level
    
    def _check_circuit_breakers(self, portfolio: Portfolio) -> CircuitBreakerLevel:
        """Alias for check_circuit_breakers for internal use."""
        return self.check_circuit_breakers(portfolio)
    
    def _activate_circuit_breaker(
        self, 
        level: CircuitBreakerLevel, 
        drawdown: Decimal,
        portfolio: Portfolio
    ):
        """Activate a circuit breaker level with appropriate actions."""
        now = datetime.utcnow()
        actions = self.CIRCUIT_BREAKER_ACTIONS.get(level, {})
        
        # Record previous state
        self.circuit_breaker_history.append({
            'timestamp': now.isoformat(),
            'previous_level': self.circuit_breaker.level.value,
            'new_level': level.value,
            'drawdown': float(drawdown),
            'portfolio_value': str(portfolio.total_balance)
        })
        
        # Update circuit breaker state
        self.circuit_breaker.level = level
        self.circuit_breaker.triggered_at = now
        self.circuit_breaker.triggered_by = f"Drawdown: {drawdown:.2%}"
        
        # Apply actions
        self.circuit_breaker.reduce_positions_pct = actions.get('reduce_positions_pct', Decimal("0"))
        self.circuit_breaker.pause_new_entries = actions.get('pause_new_entries', False)
        self.circuit_breaker.close_directional = actions.get('close_directional', False)
        self.circuit_breaker.full_liquidation = actions.get('full_liquidation', False)
        self.circuit_breaker.widen_stops_pct = actions.get('widen_stops_pct', Decimal("0"))
        
        # Set pause duration if applicable
        if 'pause_duration_hours' in actions:
            self.circuit_breaker.pause_until = now + timedelta(hours=actions['pause_duration_hours'])
        
        # Log critical event
        logger.critical(
            "risk_manager.circuit_breaker_activated",
            level=level.value,
            drawdown=float(drawdown),
            actions={k: str(v) if isinstance(v, Decimal) else v for k, v in actions.items()},
            portfolio_value=str(portfolio.total_balance)
        )
        
        # Level 3 and 4 trigger emergency stop
        if level in (CircuitBreakerLevel.LEVEL_3, CircuitBreakerLevel.LEVEL_4):
            self.trigger_emergency_stop(f"Circuit breaker {level.value} triggered")
    
    def reset_circuit_breaker(self) -> bool:
        """
        Reset circuit breaker to normal state.
        
        Returns:
            True if reset was successful, False if manual authorization required
        """
        level = self.circuit_breaker.level
        actions = self.CIRCUIT_BREAKER_ACTIONS.get(level, {})
        
        # Check if manual recovery is required
        if actions.get('manual_recovery_required', False) or actions.get('dual_auth_required', False):
            logger.warning(
                "risk_manager.circuit_breaker_reset_blocked",
                level=level.value,
                reason="Manual authorization required"
            )
            return False
        
        # Record reset
        self.circuit_breaker_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'reset',
            'previous_level': level.value,
            'new_level': 'NONE'
        })
        
        # Reset state
        self.circuit_breaker = CircuitBreaker()
        
        logger.info("risk_manager.circuit_breaker_reset", previous_level=level.value)
        return True
    
    # === Position Sizing Methods ===
    
    def calculate_position_size(
        self,
        portfolio: Portfolio,
        entry_price: Decimal,
        stop_loss_price: Optional[Decimal] = None,
        risk_pct: Optional[Decimal] = None,
        strategy_type: str = "core",
        win_rate: Optional[Decimal] = None,
        avg_win_loss_ratio: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate safe position size using risk-based sizing and Kelly Criterion.
        
        Uses 1/8 Kelly (0.125) for conservative position sizing to provide
        90% drawdown reduction vs full Kelly while maintaining growth.
        
        Args:
            portfolio: Current portfolio state
            entry_price: Entry price per unit
            stop_loss_price: Stop loss price (for risk-based sizing)
            risk_pct: Risk percentage per trade (default 1%)
            strategy_type: Type of strategy (core, trend, funding, tactical)
            win_rate: Historical win rate for Kelly calculation (optional)
            avg_win_loss_ratio: Average win/loss ratio for Kelly (optional)
            
        Returns:
            Quantity to purchase (in base asset units)
        """
        if portfolio.total_balance <= 0 or entry_price <= 0:
            return Decimal("0")
        
        # Base calculations
        max_position_value = portfolio.total_balance * (
            Decimal(str(trading_config.max_position_pct)) / 100
        )
        
        # Calculate risk-based size
        risk_per_trade = risk_pct if risk_pct is not None else self.DEFAULT_RISK_PER_TRADE
        risk_amount = portfolio.total_balance * risk_per_trade
        
        position_value = max_position_value
        
        # If stop loss provided, calculate size based on risk
        if stop_loss_price and stop_loss_price > 0:
            stop_distance = abs(entry_price - stop_loss_price)
            if stop_distance > 0:
                risk_based_size = risk_amount / stop_distance * entry_price
                position_value = min(position_value, risk_based_size)
        
        # Apply Kelly Criterion if we have sufficient data
        if win_rate is not None and avg_win_loss_ratio is not None:
            kelly_size = self._calculate_kelly_position_size(
                portfolio, win_rate, avg_win_loss_ratio
            )
            position_value = min(position_value, kelly_size)
        
        # Adjust for available balance (leave 5% buffer)
        position_value = min(position_value, portfolio.available_balance * Decimal("0.95"))
        
        # Apply leverage limits based on strategy type
        max_leverage = self._get_max_leverage(strategy_type)
        position_value = position_value * max_leverage
        
        # Apply circuit breaker reductions
        if self.circuit_breaker.reduce_positions_pct > 0:
            reduction = Decimal("1") - self.circuit_breaker.reduce_positions_pct
            position_value = position_value * reduction
            logger.warning(
                "risk_manager.position_size_circuit_breaker_reduction",
                reduction_pct=float(self.circuit_breaker.reduce_positions_pct * 100),
                adjusted_value=str(position_value)
            )
        
        # Calculate quantity
        quantity = position_value / entry_price
        
        # Round down to avoid over-sizing
        quantity = quantity.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        
        logger.debug(
            "risk_manager.position_size_calculated",
            max_position_value=str(max_position_value),
            entry_price=str(entry_price),
            stop_loss=str(stop_loss_price) if stop_loss_price else None,
            risk_pct=float(risk_per_trade),
            strategy_type=strategy_type,
            leverage=float(max_leverage),
            quantity=str(quantity)
        )
        
        return quantity
    
    def _calculate_kelly_position_size(
        self,
        portfolio: Portfolio,
        win_rate: Decimal,
        avg_win_loss_ratio: Decimal
    ) -> Decimal:
        """
        Calculate position size using 1/8 Kelly Criterion.
        
        Full Kelly: K% = W - [(1 - W) / R]
        Where W = win rate, R = win/loss ratio
        
        We use 1/8 Kelly for safety: f* = K% / 8
        """
        if win_rate <= 0 or avg_win_loss_ratio <= 0:
            return portfolio.total_balance * Decimal(str(trading_config.max_position_pct)) / 100
        
        # Full Kelly fraction
        full_kelly = win_rate - ((Decimal("1") - win_rate) / avg_win_loss_ratio)
        
        # Use 1/8 Kelly for safety
        kelly_fraction = full_kelly * self.KELLY_FRACTION
        
        # Kelly cannot be negative (would mean don't trade)
        kelly_fraction = max(kelly_fraction, Decimal("0"))
        
        # Cap at max position percentage
        max_pct = Decimal(str(trading_config.max_position_pct)) / 100
        kelly_fraction = min(kelly_fraction, max_pct)
        
        return portfolio.total_balance * kelly_fraction
    
    def _get_max_leverage(self, strategy_type: str) -> Decimal:
        """Get maximum leverage for a strategy type."""
        leverage_map = {
            'core': self.MAX_LEVERAGE_CORE,
            'trend': self.MAX_LEVERAGE_TREND,
            'funding': self.MAX_LEVERAGE_FUNDING,
            'tactical': self.MAX_LEVERAGE_TACTICAL,
        }
        return leverage_map.get(strategy_type.lower(), Decimal("1.0"))
    
    def calculate_stop_loss(
        self,
        entry_price: Decimal,
        side: str = "long",
        atr: Optional[Decimal] = None,
        multiplier: Decimal = Decimal("2")
    ) -> Decimal:
        """
        Calculate stop loss price based on configuration.
        
        Args:
            entry_price: Entry price
            side: Position side (long/short)
            atr: Average True Range for volatility-based stops (optional)
            multiplier: ATR multiplier for stop distance
            
        Returns:
            Stop loss price
        """
        # Base stop percentage
        stop_pct = Decimal(str(trading_config.stop_loss_pct)) / 100
        
        # Add circuit breaker widening if active
        if self.circuit_breaker.widen_stops_pct > 0:
            stop_pct = stop_pct + self.circuit_breaker.widen_stops_pct
            logger.debug(
                "risk_manager.stop_loss_widened",
                base_pct=float(Decimal(str(trading_config.stop_loss_pct)) / 100),
                additional_pct=float(self.circuit_breaker.widen_stops_pct),
                total_pct=float(stop_pct)
            )
        
        # If ATR provided, use volatility-based stop
        if atr is not None and atr > 0:
            stop_distance = atr * multiplier
            if side == "long":
                return max(entry_price - stop_distance, entry_price * Decimal("0.5"))
            else:
                return min(entry_price + stop_distance, entry_price * Decimal("1.5"))
        
        # Percentage-based stop
        if side == "long":
            return entry_price * (Decimal("1") - stop_pct)
        else:
            return entry_price * (Decimal("1") + stop_pct)
    
    def calculate_take_profit(
        self,
        entry_price: Decimal,
        side: str = "long",
        risk_reward_ratio: Decimal = Decimal("2")
    ) -> Decimal:
        """
        Calculate take profit price based on risk:reward ratio.
        
        Args:
            entry_price: Entry price
            side: Position side (long/short)
            risk_reward_ratio: Desired risk:reward ratio (default 1:2)
            
        Returns:
            Take profit price
        """
        stop_pct = Decimal(str(trading_config.stop_loss_pct)) / 100
        tp_pct = stop_pct * risk_reward_ratio
        
        if side == "long":
            return entry_price * (Decimal("1") + tp_pct)
        else:
            return entry_price * (Decimal("1") - tp_pct)
    
    # === Utility Methods ===
    
    def trigger_emergency_stop(self, reason: str):
        """
        Trigger emergency stop - halts all trading immediately.
        
        This is a critical safety mechanism that stops all trading activity.
        Manual intervention is required to reset.
        
        Args:
            reason: Explanation for why emergency stop was triggered
        """
        if not self.emergency_stop:
            self.emergency_stop = True
            self.emergency_reason = reason
            self.emergency_triggered_at = datetime.utcnow()
            
            logger.critical(
                "risk_manager.emergency_stop_triggered",
                reason=reason,
                triggered_at=self.emergency_triggered_at.isoformat(),
                daily_pnl=str(self.daily_pnl),
                weekly_pnl=str(self.weekly_pnl),
                circuit_breaker_level=self.circuit_breaker.level.value
            )
    
    def reset_emergency_stop(self, authorized_by: Optional[str] = None) -> bool:
        """
        Manually reset emergency stop.
        
        WARNING: Use with extreme caution. Verify the issue is resolved
        before resetting.
        
        Args:
            authorized_by: Identifier of person authorizing the reset
            
        Returns:
            True if reset was successful
        """
        was_stopped = self.emergency_stop
        
        if was_stopped:
            self.emergency_stop = False
            self.emergency_reason = None
            
            logger.warning(
                "risk_manager.emergency_stop_reset",
                was_triggered_at=self.emergency_triggered_at.isoformat() if self.emergency_triggered_at else None,
                authorized_by=authorized_by,
                manual_reset=True
            )
            
            self.emergency_triggered_at = None
            return True
        
        return False
    
    def update_pnl(self, realized_pnl: Decimal):
        """Update PnL tracking and check limits."""
        self.daily_pnl += realized_pnl
        self.weekly_pnl += realized_pnl
        
        logger.info(
            "risk_manager.pnl_update",
            realized=str(realized_pnl),
            daily_pnl=str(self.daily_pnl),
            weekly_pnl=str(self.weekly_pnl)
        )
    
    def get_circuit_breaker_actions(self) -> Dict[str, Any]:
        """Get current circuit breaker actions and restrictions."""
        cb = self.circuit_breaker
        return {
            'level': cb.level.value,
            'triggered_at': cb.triggered_at.isoformat() if cb.triggered_at else None,
            'triggered_by': cb.triggered_by,
            'reduce_positions_pct': float(cb.reduce_positions_pct),
            'pause_new_entries': cb.pause_new_entries,
            'pause_until': cb.pause_until.isoformat() if cb.pause_until else None,
            'close_directional': cb.close_directional,
            'full_liquidation': cb.full_liquidation,
            'widen_stops_pct': float(cb.widen_stops_pct),
        }
    
    def get_risk_report(self, portfolio: Portfolio) -> Dict[str, Any]:
        """Generate comprehensive risk status report."""
        drawdown = self._calculate_drawdown(portfolio)
        
        return {
            # Emergency status
            'emergency_stop': {
                'active': self.emergency_stop,
                'reason': self.emergency_reason,
                'triggered_at': self.emergency_triggered_at.isoformat() if self.emergency_triggered_at else None,
            },
            # Circuit breaker
            'circuit_breaker': self.get_circuit_breaker_actions(),
            # PnL tracking
            'pnl': {
                'daily_pnl': str(self.daily_pnl),
                'daily_loss_pct': float(self._calculate_daily_loss_pct(portfolio)),
                'weekly_pnl': str(self.weekly_pnl),
                'weekly_loss_pct': float(self._calculate_weekly_loss_pct(portfolio)),
                'current_drawdown_pct': float(drawdown * 100) if drawdown else 0,
            },
            # Limits
            'limits': {
                'max_position_pct': trading_config.max_position_pct,
                'max_daily_loss_pct': trading_config.max_daily_loss_pct,
                'max_weekly_loss_pct': trading_config.max_weekly_loss_pct,
                'max_concurrent_positions': trading_config.max_concurrent_positions,
            },
            # Portfolio
            'portfolio': {
                'total_balance': str(portfolio.total_balance),
                'available_balance': str(portfolio.available_balance),
                'exposure_pct': float(portfolio.exposure_pct),
            },
            # Statistics
            'statistics': {
                'rejected_signals_24h': len(self.rejected_signals),
                'circuit_breaker_activations': len(self.circuit_breaker_history),
            }
        }
    
    # === Private Helper Methods ===
    
    def _calculate_daily_loss_pct(self, portfolio: Portfolio) -> Decimal:
        """Calculate current daily loss percentage."""
        if not self.daily_starting_balance or self.daily_starting_balance == 0:
            return Decimal("0")
        current_pnl = portfolio.total_balance - self.daily_starting_balance
        if current_pnl < 0:
            return abs(current_pnl) / self.daily_starting_balance * 100
        return Decimal("0")
    
    def _calculate_weekly_loss_pct(self, portfolio: Portfolio) -> Decimal:
        """Calculate current weekly loss percentage."""
        if not self.weekly_starting_balance or self.weekly_starting_balance == 0:
            return Decimal("0")
        current_pnl = portfolio.total_balance - self.weekly_starting_balance
        if current_pnl < 0:
            return abs(current_pnl) / self.weekly_starting_balance * 100
        return Decimal("0")
    
    def _calculate_drawdown(self, portfolio: Portfolio) -> Optional[Decimal]:
        """Calculate current drawdown from all-time high."""
        if not self.all_time_high_balance or self.all_time_high_balance == 0:
            return None
        if portfolio.total_balance >= self.all_time_high_balance:
            return Decimal("0")
        return (self.all_time_high_balance - portfolio.total_balance) / self.all_time_high_balance
    
    def _estimate_position_correlation(
        self, 
        current_positions: Dict[str, Position]
    ) -> Decimal:
        """Estimate average correlation between positions (simplified)."""
        if len(current_positions) < 2:
            return Decimal("0")
        
        # Simplified correlation estimation based on P&L direction
        # In production, this would use actual price correlation matrices
        pnls = [p.unrealized_pnl for p in current_positions.values()]
        
        if len(pnls) < 2:
            return Decimal("0")
        
        # Check if all P&Ls are in same direction (high correlation indicator)
        positive_pnls = sum(1 for pnl in pnls if pnl > 0)
        negative_pnls = sum(1 for pnl in pnls if pnl < 0)
        
        total = len(pnls)
        max_same_direction = max(positive_pnls, negative_pnls)
        
        # Correlation estimate: ratio of positions moving same direction
        correlation = Decimal(str(max_same_direction / total))
        
        return correlation
    
    def _log_signal_rejected(self, signal: TradingSignal, rule: str, reason: str):
        """Log a rejected signal for analysis."""
        rejection = {
            'timestamp': datetime.utcnow().isoformat(),
            'symbol': signal.symbol,
            'signal_type': signal.signal_type.value,
            'strategy': signal.strategy_name,
            'confidence': signal.confidence,
            'rule_triggered': rule,
            'reason': reason,
        }
        self.rejected_signals.append(rejection)
        
        # Keep only last 1000 rejections
        if len(self.rejected_signals) > 1000:
            self.rejected_signals = self.rejected_signals[-1000:]


# === Convenience Functions ===

def create_risk_manager() -> RiskManager:
    """Factory function to create a configured RiskManager instance."""
    return RiskManager()
