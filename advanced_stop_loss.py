"""
Advanced Stop-Loss Module
Implements trailing stops, ATR-based stops, regime awareness, and intraday monitoring
"""

import talib
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import logging
import json
import time

from config_manager import get_config
from ib_insync import Stock, Order, IB

logger = logging.getLogger(__name__)

# Global IBKR connection (will be set by the main trading system)
ib = None

def ensure_ibkr_connection():
    """Ensure IBKR connection is available"""
    global ib
    if ib is None:
        try:
            from robotrading_improved import ib as main_ib
            ib = main_ib
        except ImportError:
            logger.error("IBKR connection not available")
            return False
    
    if ib is None or not ib.isConnected():
        logger.warning("IBKR not connected")
        return False
    
    return True

@dataclass
class PositionTracker:
    """Tracks position data for advanced stop-loss calculations"""
    symbol: str
    entry_price: float
    entry_time: datetime
    high_price: float
    quantity: int
    atr_value: float = 0.0
    last_check: datetime = None
    
    def update_high_price(self, current_price: float):
        """Update the high price since entry"""
        if current_price > self.high_price:
            self.high_price = current_price
    
    def get_trailing_stop(self, trailing_percent: float) -> float:
        """Calculate trailing stop price"""
        return self.high_price * (1 - trailing_percent / 100)
    
    def get_atr_stop(self, atr_multiplier: float) -> float:
        """Calculate ATR-based stop price"""
        return self.entry_price - (atr_multiplier * self.atr_value)
    
    def get_effective_stop(self, trailing_percent: float, atr_multiplier: float) -> float:
        """Get the more conservative stop (higher of the two)"""
        trailing_stop = self.get_trailing_stop(trailing_percent)
        atr_stop = self.get_atr_stop(atr_multiplier)
        return max(trailing_stop, atr_stop)

class AdvancedStopLossManager:
    """Manages advanced stop-loss functionality"""
    
    def __init__(self):
        self.config = get_config()
        self.position_trackers: Dict[str, PositionTracker] = {}
        self.last_intraday_check = None
        
    def calculate_atr(self, symbol: str, period: int = 14) -> float:
        """Calculate Average True Range for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            
            if hist.empty or len(hist) < period:
                logger.warning(f"Insufficient data for ATR calculation for {symbol}")
                return 0.0
            
            high = hist['High'].values
            low = hist['Low'].values
            close = hist['Close'].values
            
            atr = talib.ATR(high, low, close, timeperiod=period)
            return atr[-1] if not np.isnan(atr[-1]) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ATR for {symbol}: {e}")
            return 0.0
    
    def get_hmm_regime_probability(self, symbol: str) -> Optional[float]:
        """Get HMM high volatility regime probability for a symbol"""
        try:
            # This would integrate with your HMM model
            # For now, return None to indicate no regime data
            # In practice, you'd call your HMM model here
            return None
        except Exception as e:
            logger.error(f"Error getting HMM regime for {symbol}: {e}")
            return None
    
    def update_position_trackers(self):
        """Update position trackers with current positions"""
        if not ensure_ibkr_connection():
            return
        
        try:
            positions = ib.positions()
            current_time = datetime.now()
            
            for pos in positions:
                if pos.position <= 0:  # Skip short positions
                    continue
                
                symbol = pos.contract.symbol
                current_price = pos.marketValue / pos.position
                avg_cost = pos.averageCost
                
                if symbol not in self.position_trackers:
                    # New position - create tracker
                    atr_value = self.calculate_atr(symbol, self.config.stop_loss.atr_period)
                    self.position_trackers[symbol] = PositionTracker(
                        symbol=symbol,
                        entry_price=avg_cost,
                        entry_time=current_time,
                        high_price=max(avg_cost, current_price),
                        quantity=pos.position,
                        atr_value=atr_value,
                        last_check=current_time
                    )
                    logger.info(f"Created position tracker for {symbol}: Entry=${avg_cost:.2f}, ATR=${atr_value:.2f}")
                else:
                    # Update existing tracker
                    tracker = self.position_trackers[symbol]
                    tracker.update_high_price(current_price)
                    tracker.last_check = current_time
                    
                    # Update ATR periodically (every hour)
                    if (current_time - tracker.last_check).seconds > 3600:
                        tracker.atr_value = self.calculate_atr(symbol, self.config.stop_loss.atr_period)
                        tracker.last_check = current_time
            
            # Remove trackers for positions no longer held
            current_symbols = {pos.contract.symbol for pos in positions if pos.position > 0}
            symbols_to_remove = set(self.position_trackers.keys()) - current_symbols
            for symbol in symbols_to_remove:
                del self.position_trackers[symbol]
                logger.info(f"Removed position tracker for {symbol}")
                
        except Exception as e:
            logger.error(f"Error updating position trackers: {e}")
    
    def check_stop_loss_positions(self) -> List[Tuple[str, float, str]]:
        """
        Check all positions for stop-loss triggers
        Returns list of (symbol, loss_percentage, reason) tuples
        """
        if not self.config.stop_loss.enabled:
            return []
        
        if not ensure_ibkr_connection():
            return []
        
        self.update_position_trackers()
        stop_loss_triggered = []
        current_time = datetime.now()
        
        try:
            positions = ib.positions()
            
            for pos in positions:
                if pos.position <= 0:
                    continue
                
                symbol = pos.contract.symbol
                current_price = pos.marketValue / pos.position
                avg_cost = pos.averageCost
                
                if symbol not in self.position_trackers:
                    continue
                
                tracker = self.position_trackers[symbol]
                
                # Check minimum hold time
                hold_time_minutes = (current_time - tracker.entry_time).total_seconds() / 60
                if hold_time_minutes < self.config.stop_loss.min_hold_time:
                    continue
                
                # Get regime-aware threshold
                regime_prob = self.get_hmm_regime_probability(symbol)
                effective_threshold = self.config.stop_loss.stop_loss_threshold
                
                if (self.config.stop_loss.regime_aware and 
                    regime_prob is not None and 
                    regime_prob > self.config.stop_loss.high_vol_threshold):
                    effective_threshold = self.config.stop_loss.stop_loss_threshold * self.config.stop_loss.high_vol_tightening
                    logger.info(f"High volatility regime detected for {symbol} (prob={regime_prob:.2f}), tightening stop-loss threshold to {effective_threshold:.1f}%")
                
                # Calculate effective stop price
                effective_stop = tracker.get_effective_stop(
                    self.config.stop_loss.trailing_percent,
                    self.config.stop_loss.atr_multiplier
                )
                
                # Check if stop-loss is triggered
                loss_pct = ((current_price - avg_cost) / avg_cost) * 100
                
                if current_price < effective_stop:
                    reason = f"Stop-loss triggered: Price ${current_price:.2f} < Stop ${effective_stop:.2f} (Loss: {loss_pct:.1f}%)"
                    stop_loss_triggered.append((symbol, loss_pct, reason))
                    
                    # Log detailed stop-loss information
                    logger.warning(f"🛑 STOP LOSS TRIGGERED: {symbol}")
                    logger.warning(f"   Entry Price: ${avg_cost:.2f}")
                    logger.warning(f"   Current Price: ${current_price:.2f}")
                    logger.warning(f"   High Price: ${tracker.high_price:.2f}")
                    logger.warning(f"   ATR Value: ${tracker.atr_value:.2f}")
                    logger.warning(f"   Trailing Stop: ${tracker.get_trailing_stop(self.config.stop_loss.trailing_percent):.2f}")
                    logger.warning(f"   ATR Stop: ${tracker.get_atr_stop(self.config.stop_loss.atr_multiplier):.2f}")
                    logger.warning(f"   Effective Stop: ${effective_stop:.2f}")
                    logger.warning(f"   Regime Prob: {regime_prob:.2f}" if regime_prob else "   Regime Prob: N/A")
                    logger.warning(f"   Reason: {reason}")
        
        except Exception as e:
            logger.error(f"Error checking stop-loss positions: {e}")
        
        return stop_loss_triggered
    
    def execute_stop_loss_sell(self, symbol: str, quantity: int) -> bool:
        """Execute stop-loss sell order"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            order = Order(
                action='SELL',
                orderType='MKT',
                totalQuantity=abs(quantity),
                tif='DAY',
                outsideRth=True
            )
            
            trade = ib.placeOrder(contract, order)
            ib.sleep(1)  # Wait for order submission
            
            if trade.orderStatus.status in ["Filled", "Submitted"]:
                logger.info(f"Stop-loss sell executed for {symbol}. Order ID: {trade.order.orderId}")
                return True
            else:
                logger.error(f"Stop-loss sell failed for {symbol}. Status: {trade.orderStatus.status}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing stop-loss sell for {symbol}: {e}")
            return False
    
    def process_stop_losses(self) -> int:
        """Process all stop-loss triggers and execute sells"""
        stop_loss_positions = self.check_stop_loss_positions()
        executed_sells = 0
        
        for symbol, loss_pct, reason in stop_loss_positions:
            logger.warning(f"Processing stop-loss for {symbol}: {reason}")
            
            # Get current position quantity
            try:
                positions = ib.positions()
                position_qty = 0
                for pos in positions:
                    if pos.contract.symbol == symbol and pos.position > 0:
                        position_qty = pos.position
                        break
                
                if position_qty > 0:
                    if self.execute_stop_loss_sell(symbol, position_qty):
                        executed_sells += 1
                        # Log stop-loss execution (no email alerts as requested)
                        self.send_stop_loss_alert(symbol, loss_pct, reason)
                    else:
                        logger.error(f"Failed to execute stop-loss sell for {symbol}")
                else:
                    logger.warning(f"No position found for {symbol} during stop-loss execution")
                    
            except Exception as e:
                logger.error(f"Error processing stop-loss for {symbol}: {e}")
        
        return executed_sells
    
    def send_stop_loss_alert(self, symbol: str, loss_pct: float, reason: str):
        """Log stop-loss execution (no email alerts as requested)"""
        try:
            # Only log the stop-loss execution, no email alerts
            logger.warning(f"🛑 STOP-LOSS EXECUTED: {symbol} - {reason}")
            logger.warning(f"   Loss Percentage: {loss_pct:.2f}%")
            logger.warning(f"   Action: SELL executed without email alert")
            logger.info(f"Stop-loss execution logged for {symbol} (no email sent)")
        except Exception as e:
            logger.error(f"Error logging stop-loss execution for {symbol}: {e}")
    
    def should_run_intraday_check(self) -> bool:
        """Check if intraday stop-loss check should run"""
        if not self.config.stop_loss.enabled:
            return False
        
        current_time = datetime.now()
        
        # Check if it's market hours (9:30 AM - 4:00 PM EST)
        market_hours = 9.5 <= current_time.hour + current_time.minute / 60 <= 16
        
        if not market_hours:
            return False
        
        # Check if enough time has passed since last check
        if self.last_intraday_check is None:
            return True
        
        time_since_last = (current_time - self.last_intraday_check).total_seconds() / 60
        return time_since_last >= self.config.stop_loss.intraday_check_interval
    
    def run_intraday_check(self) -> int:
        """Run intraday stop-loss check if needed"""
        if not self.should_run_intraday_check():
            return 0
        
        logger.info("Running intraday stop-loss check...")
        executed_sells = self.process_stop_losses()
        self.last_intraday_check = datetime.now()
        
        if executed_sells > 0:
            logger.info(f"Intraday stop-loss check completed: {executed_sells} positions sold")
        else:
            logger.info("Intraday stop-loss check completed: No positions triggered")
        
        return executed_sells

# Global instance
advanced_stop_loss_manager = AdvancedStopLossManager()

def check_advanced_stop_loss_positions() -> List[Tuple[str, float, str]]:
    """Convenience function to check stop-loss positions"""
    return advanced_stop_loss_manager.check_stop_loss_positions()

def process_advanced_stop_losses() -> int:
    """Convenience function to process stop-losses"""
    return advanced_stop_loss_manager.process_stop_losses()

def run_intraday_stop_loss_check() -> int:
    """Convenience function to run intraday check"""
    return advanced_stop_loss_manager.run_intraday_check()