"""Risk management system - THE MOST CRITICAL COMPONENT."""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import structlog

from src.core.models import Order, Position, Portfolio, TradingSignal, SignalType
from src.core.config import trading_config

logger = structlog.get_logger(__name__)


@dataclass
class RiskCheck:
    """Result of a risk check."""
    passed: bool
    reason: str = ""
    risk_level: str = "normal"  # normal, warning, critical


class RiskManager:
    """
    Central risk management system.
    
    HARD LIMITS - These are non-negotiable:
    - Max position size: X% of portfolio
    - Max daily loss: X% of portfolio
    - Max concurrent positions: X
    - Stop loss on every trade
    """
    
    def __init__(self):
        self.daily_pnl: Decimal = Decimal("0")
        self.weekly_pnl: Decimal = Decimal("0")
        self.daily_starting_balance: Optional[Decimal] = None
        self.weekly_starting_balance: Optional[Decimal] = None
        self.last_reset_day: Optional[datetime] = None
        self.last_reset_week: Optional[datetime] = None
        
        # Emergency stop flag
        self.emergency_stop = False
        self.emergency_reason: Optional[str] = None
        
        # Track rejected signals for analysis
        self.rejected_signals: List[Dict] = []
        
    async def initialize(self, portfolio: Portfolio):
        """Initialize risk manager with current portfolio state."""
        now = datetime.utcnow()
        self.daily_starting_balance = portfolio.total_balance
        self.weekly_starting_balance = portfolio.total_balance
        self.last_reset_day = now
        self.last_reset_week = now
        
        logger.info(
            "risk_manager.initialized",
            daily_start=str(self.daily_starting_balance),
            weekly_start=str(self.weekly_starting_balance),
            max_position_pct=trading_config.max_position_pct,
            max_daily_loss_pct=trading_config.max_daily_loss_pct
        )
    
    def reset_periods(self, portfolio: Portfolio):
        """Reset daily/weekly tracking periods."""
        now = datetime.utcnow()
        
        # Reset daily
        if self.last_reset_day and now.date() != self.last_reset_day.date():
            self.daily_pnl = Decimal("0")
            self.daily_starting_balance = portfolio.total_balance
            self.last_reset_day = now
            self.emergency_stop = False  # Reset emergency stop on new day
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
        Validate a trading signal against risk rules.
        Returns RiskCheck indicating if signal can be executed.
        """
        # Check emergency stop first
        if self.emergency_stop:
            return RiskCheck(
                passed=False,
                reason=f"Emergency stop active: {self.emergency_reason}",
                risk_level="critical"
            )
        
        # Reset periods if needed
        self.reset_periods(portfolio)
        
        # Rule 1: Check daily loss limit
        daily_loss_pct = self._calculate_daily_loss_pct(portfolio)
        if daily_loss_pct >= trading_config.max_daily_loss_pct:
            self._trigger_emergency_stop(f"Daily loss limit reached: {daily_loss_pct:.2f}%")
            return RiskCheck(
                passed=False,
                reason=f"Daily loss limit reached: {daily_loss_pct:.2f}%",
                risk_level="critical"
            )
        
        # Rule 2: Check weekly loss limit
        weekly_loss_pct = self._calculate_weekly_loss_pct(portfolio)
        if weekly_loss_pct >= trading_config.max_weekly_loss_pct:
            self._trigger_emergency_stop(f"Weekly loss limit reached: {weekly_loss_pct:.2f}%")
            return RiskCheck(
                passed=False,
                reason=f"Weekly loss limit reached: {weekly_loss_pct:.2f}%",
                risk_level="critical"
            )
        
        # Rule 3: Check max concurrent positions
        open_positions = len([p for p in current_positions.values() if p.side != PositionSide.NONE])
        if open_positions >= trading_config.max_concurrent_positions:
            return RiskCheck(
                passed=False,
                reason=f"Max concurrent positions reached: {open_positions}",
                risk_level="warning"
            )
        
        # Rule 4: Check if already have position in this symbol
        if signal.symbol in current_positions:
            existing = current_positions[signal.symbol]
            if signal.signal_type == SignalType.BUY and existing.side == PositionSide.LONG:
                return RiskCheck(
                    passed=False,
                    reason=f"Already have LONG position in {signal.symbol}",
                    risk_level="normal"
                )
        
        # Rule 5: Check portfolio exposure
        exposure_pct = portfolio.exposure_pct
        if exposure_pct >= 50:  # Warning at 50%
            return RiskCheck(
                passed=False,
                reason=f"High portfolio exposure: {exposure_pct:.2f}%",
                risk_level="warning"
            )
        
        # Rule 6: Check signal confidence
        if signal.confidence < 0.6:
            return RiskCheck(
                passed=False,
                reason=f"Signal confidence too low: {signal.confidence:.2f}",
                risk_level="normal"
            )
        
        logger.info(
            "risk_manager.signal_approved",
            symbol=signal.symbol,
            signal=signal.signal_type.value,
            strategy=signal.strategy_name,
            confidence=signal.confidence
        )
        
        return RiskCheck(passed=True, risk_level="normal")
    
    def calculate_position_size(
        self,
        portfolio: Portfolio,
        entry_price: Decimal,
        stop_loss_price: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate safe position size based on risk parameters.
        Uses fixed percentage risk per trade model.
        """
        if portfolio.total_balance <= 0:
            return Decimal("0")
        
        # Base position size on max_position_pct of portfolio
        max_position_value = portfolio.total_balance * (
            Decimal(str(trading_config.max_position_pct)) / 100
        )
        
        # Adjust based on available balance
        position_value = min(max_position_value, portfolio.available_balance * Decimal("0.95"))
        
        # Calculate quantity
        if entry_price > 0:
            quantity = position_value / entry_price
        else:
            quantity = Decimal("0")
        
        logger.debug(
            "risk_manager.position_size",
            max_position_value=str(max_position_value),
            entry_price=str(entry_price),
            quantity=str(quantity)
        )
        
        return quantity
    
    def calculate_stop_loss(
        self,
        entry_price: Decimal,
        side: str = "long"
    ) -> Decimal:
        """Calculate stop loss price based on configuration."""
        stop_pct = Decimal(str(trading_config.stop_loss_pct)) / 100
        
        if side == "long":
            return entry_price * (Decimal("1") - stop_pct)
        else:
            return entry_price * (Decimal("1") + stop_pct)
    
    def calculate_take_profit(
        self,
        entry_price: Decimal,
        side: str = "long"
    ) -> Decimal:
        """Calculate take profit price based on risk:reward ratio (1:2)."""
        tp_pct = Decimal(str(trading_config.take_profit_pct)) / 100
        
        if side == "long":
            return entry_price * (Decimal("1") + tp_pct)
        else:
            return entry_price * (Decimal("1") - tp_pct)
    
    def update_pnl(self, realized_pnl: Decimal):
        """Update PnL tracking."""
        self.daily_pnl += realized_pnl
        self.weekly_pnl += realized_pnl
        
        logger.info(
            "risk_manager.pnl_update",
            realized=str(realized_pnl),
            daily_pnl=str(self.daily_pnl),
            weekly_pnl=str(self.weekly_pnl)
        )
        
        # Check if we hit daily limit
        if self.daily_starting_balance:
            daily_loss_pct = abs(self.daily_pnl) / self.daily_starting_balance * 100
            if daily_loss_pct >= trading_config.max_daily_loss_pct:
                self._trigger_emergency_stop(f"Daily loss limit exceeded: {daily_loss_pct:.2f}%")
    
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
    
    def _trigger_emergency_stop(self, reason: str):
        """Trigger emergency stop - halts all trading."""
        self.emergency_stop = True
        self.emergency_reason = reason
        
        logger.critical(
            "risk_manager.emergency_stop_triggered",
            reason=reason,
            daily_pnl=str(self.daily_pnl),
            weekly_pnl=str(self.weekly_pnl)
        )
    
    def get_risk_report(self, portfolio: Portfolio) -> Dict:
        """Generate current risk status report."""
        return {
            'emergency_stop': self.emergency_stop,
            'emergency_reason': self.emergency_reason,
            'daily_pnl': str(self.daily_pnl),
            'daily_loss_pct': str(self._calculate_daily_loss_pct(portfolio)),
            'weekly_pnl': str(self.weekly_pnl),
            'weekly_loss_pct': str(self._calculate_weekly_loss_pct(portfolio)),
            'portfolio_exposure_pct': str(portfolio.exposure_pct),
            'max_position_pct': trading_config.max_position_pct,
            'max_daily_loss_pct': trading_config.max_daily_loss_pct,
            'rejected_signals_24h': len(self.rejected_signals)
        }
    
    def reset_emergency_stop(self):
        """Manually reset emergency stop (use with caution)."""
        was_stopped = self.emergency_stop
        self.emergency_stop = False
        self.emergency_reason = None
        
        if was_stopped:
            logger.warning("risk_manager.emergency_stop_reset")
