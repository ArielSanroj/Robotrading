"""
Improved Trading Bot with Stability & Fault Tolerance
- Retry/backoff for external calls
- Isolated asset-class workflows
- Graceful degradation for email failures
- Structured logging and metrics
- Configuration management
- Health checks
"""

import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import numpy as np
import schedule
import time
from datetime import datetime
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import logging
from ib_insync import IB, Stock, Order
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
from statsmodels.tsa.stattools import adfuller
import signal
import sys
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json

# Import new modules
from portfolio_manager import PortfolioManager, AssetClass, AssetAllocation
from crypto_trader import CryptoTrader
from bond_trader import BondTrader
from retry_utils import retry_api_call, retry_ibkr_call, retry_smtp_call
from config_manager import get_config, get_broker_config, get_email_config, get_trading_config
from logging_config import setup_logging, get_trading_logger, get_metrics
from data_cache import cached_data_provider
from health_check import HealthChecker, run_health_check

# Suppress urllib3 warning
import warnings
warnings.filterwarnings("ignore", category=Warning)

# Global configuration
config = get_config()
trading_config = get_trading_config()
email_config = get_email_config()

# Set up structured logging
logger = setup_logging(
    level=config.logging.level,
    format_type=config.logging.format,
    log_file=config.logging.file_path,
    max_file_size=config.logging.max_file_size,
    backup_count=config.logging.backup_count
)

# Trading logger for structured events
trading_logger = get_trading_logger("trading_bot")

# Global state
trading_session = {
    'session_type': '',  # 'MORNING' or 'AFTERNOON'
    'stocks_purchased': [],
    'stocks_sold': [],
    'money_spent': 0.0,
    'money_earned': 0.0,
    'total_trades': 0,
    'session_start_time': None
}

# Global IBKR client
ib = None
ib_lock = threading.Lock()

# Graceful shutdown flag
shutdown_flag = threading.Event()

@dataclass
class TradingResult:
    """Result of a trading operation"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag.set()
    
    # Send final summary if possible
    try:
        send_trading_summary()
    except Exception as e:
        logger.error(f"Failed to send final summary: {e}")
    
    # Disconnect from IBKR
    try:
        if ib and ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected from IBKR")
    except Exception as e:
        logger.error(f"Error disconnecting from IBKR: {e}")
    
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_ibkr() -> bool:
    """Initialize IBKR connection with retry logic"""
    global ib
    
    broker_config = get_broker_config("IBKR")
    if not broker_config:
        logger.error("IBKR broker configuration not found")
        return False
    
    try:
        with ib_lock:
            if ib and ib.isConnected():
                return True
            
            ib = IB()
            ib.connect(
                broker_config.host, 
                broker_config.port, 
                clientId=broker_config.client_id,
                timeout=30
            )
            
            if ib.isConnected():
                trading_logger.logger.info(
                    f"Connected to IBKR",
                    extra={
                        "event_type": "ibkr_connected",
                        "host": broker_config.host,
                        "port": broker_config.port,
                        "client_id": broker_config.client_id,
                        "paper_trading": broker_config.paper_trading
                    }
                )
                return True
            else:
                logger.error("Failed to connect to IBKR")
                return False
                
    except Exception as e:
        logger.error(f"Failed to initialize IBKR: {e}")
        return False

def ensure_ibkr_connection() -> bool:
    """Ensure IBKR connection is active, reconnect if needed"""
    global ib
    
    with ib_lock:
        if ib and ib.isConnected():
            return True
        
        logger.warning("IBKR connection lost, attempting to reconnect...")
        return initialize_ibkr()

@retry_api_call(max_retries=3, base_delay=1.0)
def get_top_stocks_cached(num_stocks=15) -> pd.DataFrame:
    """
    Get top-performing stocks with caching
    """
    # Check cache first
    cached_data = cached_data_provider.get_slickcharts_data(num_stocks)
    if cached_data is not None:
        return cached_data
    
    # Fetch from Slickcharts
    url = "https://www.slickcharts.com/sp500/performance"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=config.api.slickcharts_timeout)
    if response.status_code != 200:
        raise requests.exceptions.RequestException(f"Slickcharts returned status {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not table:
        raise ValueError("No table found on Slickcharts")

    rows = table.find_all('tr')[1:num_stocks + 1]
    data = []
    
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 4:
            continue
        
        try:
            symbol = cols[2].text.strip() or cols[2].find('a').text.strip() if cols[2].find('a') else 'N/A'
            ytd_str = cols[3].text.strip().replace('%', '').replace(',', '')
            ytd = float(ytd_str)
            
            if symbol != 'N/A':
                # Quick validation with yfinance
                ticker = yf.Ticker(symbol)
                if not ticker.history(period='1d').empty:
                    data.append({'Symbol': symbol, 'YTD': ytd})
                    
        except (ValueError, IndexError) as e:
            logger.warning(f"Skipping invalid row: {e}")
            continue

    if not data:
        raise ValueError("No valid data extracted from Slickcharts")

    df = pd.DataFrame(data)
    
    # Cache the result
    cached_data_provider.cache_slickcharts_data(df, num_stocks, ttl=600)  # 10 minutes
    
    return df

@retry_api_call(max_retries=2, base_delay=1.0)
def cross_check_alpha_cached(symbol: str) -> Optional[float]:
    """
    Cross-check price using Alpha Vantage API with caching
    """
    if not config.api.alpha_vantage_key:
        return None
    
    # Check cache first
    cached_data = cached_data_provider.get_alpha_vantage_data(symbol)
    if cached_data is not None:
        return cached_data
    
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={config.api.alpha_vantage_key}"
    
    response = requests.get(url, timeout=config.api.yfinance_timeout)
    if response.status_code != 200:
        raise requests.exceptions.RequestException(f"Alpha Vantage returned status {response.status_code}")
    
    data = response.json()
    if "Global Quote" not in data:
        raise ValueError(f"No price data for {symbol} from Alpha Vantage")
    
    price = float(data['Global Quote']['05. price'])
    
    # Cache the result
    cached_data_provider.cache_alpha_vantage_data(price, symbol, ttl=300)  # 5 minutes
    
    return price

@retry_api_call(max_retries=2, base_delay=1.0)
def fetch_stock_data_cached(symbols: List[str], period='1y') -> pd.DataFrame:
    """
    Fetch historical stock data with caching
    """
    df = pd.DataFrame()
    
    for symbol in symbols:
        # Check cache first
        cached_data = cached_data_provider.get_yfinance_data(symbol, period)
        if cached_data is not None:
            df[symbol] = cached_data['Close']
            continue
        
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                logger.warning(f"No data for {symbol}")
                continue
            
            # Cross-check with Alpha Vantage
            alpha_price = cross_check_alpha_cached(symbol)
            if alpha_price and abs(data['Close'].iloc[-1] - alpha_price) / alpha_price > 0.05:
                logger.warning(f"Price mismatch for {symbol}: YFinance={data['Close'].iloc[-1]:.2f}, AlphaVantage={alpha_price:.2f}")
            
            df[symbol] = data['Close']
            
            # Cache the result
            cached_data_provider.cache_yfinance_data(data, symbol, period, ttl=300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            continue
    
    return df

def validate_hmm_inputs(prices: pd.Series) -> Tuple[bool, str]:
    """
    Validate inputs for HMM model
    Returns (is_valid, message)
    """
    if len(prices) < 252:
        return False, f"Insufficient data (need 252 days, have {len(prices)})"
    
    # Check for stationarity
    try:
        returns = np.log(prices / prices.shift(1)).dropna()
        adf_result = adfuller(returns)
        
        if adf_result[1] > 0.05:  # p-value > 0.05 means not stationary
            return False, f"Returns are not stationary (ADF p-value: {adf_result[1]:.4f})"
        
        # Check for sufficient variation
        if returns.std() < 0.001:  # Very low volatility
            return False, f"Returns have insufficient variation (std: {returns.std():.6f})"
        
        return True, "Inputs are valid for HMM"
        
    except Exception as e:
        return False, f"Error validating inputs: {e}"

def generate_signals_robust(df: pd.DataFrame, k_regimes=2) -> pd.DataFrame:
    """
    Generate signals with robust HMM fitting and fallback strategies
    """
    signals = pd.DataFrame(index=df.index)
    
    for col in df.columns:
        prices = df[col].dropna()
        
        # Validate inputs
        is_valid, message = validate_hmm_inputs(prices)
        if not is_valid:
            logger.warning(f"HMM inputs invalid for {col}: {message}")
            # Fallback to simple moving average strategy
            signals[col] = generate_simple_ma_signal(prices)
            continue
        
        # Try HMM fitting
        try:
            returns = np.log(prices / prices.shift(1)).dropna()
            model = MarkovRegression(returns, k_regimes=k_regimes, switching_variance=True)
            results = model.fit(disp=False)
            
            probs = results.smoothed_marginal_probabilities
            latest_prob_low = probs[0].iloc[-1]
            signal = 1 if latest_prob_low > 0.5 else -1 if latest_prob_low < 0.5 else 0
            
            signals[col] = pd.Series(signal, index=prices.index).fillna(0)
            
            trading_logger.log_trade_signal(
                symbol=col,
                action="BUY" if signal == 1 else "SELL" if signal == -1 else "HOLD",
                asset_class="equity",
                confidence=abs(latest_prob_low - 0.5) * 2  # Convert to 0-1 scale
            )
            
        except Exception as e:
            logger.warning(f"HMM fitting failed for {col}: {e}, using fallback")
            signals[col] = generate_simple_ma_signal(prices)
    
    return signals

def generate_simple_ma_signal(prices: pd.Series) -> pd.Series:
    """
    Simple moving average fallback strategy
    """
    try:
        short_ma = prices.rolling(window=10).mean()
        long_ma = prices.rolling(window=30).mean()
        
        signal = pd.Series(0, index=prices.index)
        signal[short_ma > long_ma] = 1
        signal[short_ma < long_ma] = -1
        
        return signal
    except Exception as e:
        logger.error(f"Fallback strategy failed for {prices.name}: {e}")
        return pd.Series(0, index=prices.index)

@retry_smtp_call(max_retries=2, base_delay=5.0)
def send_email_alert_robust(symbol: str, action: str, top_df=None, trade_value=0.0) -> bool:
    """
    Send email alert with graceful degradation
    """
    if not email_config.enabled:
        logger.info("Email alerts disabled, skipping email")
        return True
    
    try:
        msg = EmailMessage()
        ytd = top_df[top_df['Symbol'] == symbol]['YTD'].iloc[0] if top_df is not None and symbol in top_df['Symbol'].values else 'N/A'
        
        # Track trade in session
        if action == 'BUY':
            trading_session['stocks_purchased'].append({
                'symbol': symbol,
                'value': trade_value,
                'ytd': ytd
            })
            trading_session['money_spent'] += trade_value
        else:  # SELL
            trading_session['stocks_sold'].append({
                'symbol': symbol,
                'value': trade_value,
                'ytd': ytd
            })
            trading_session['money_earned'] += trade_value
        
        trading_session['total_trades'] += 1
        
        msg.set_content(
            f"ALERT: {action} {symbol} - {'Strong upward trend!' if action == 'BUY' else 'Potential reversal!'}\nYTD Return: {ytd}%\nTrade Value: ${trade_value:.2f}")
        msg['Subject'] = f"Trading Alert: {action} {symbol}"
        msg['From'] = email_config.username
        
        # Send to all recipients
        for recipient in email_config.recipients:
            msg['To'] = recipient
            
            with smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port) as smtp:
                smtp.login(email_config.username, email_config.password)
                smtp.send_message(msg)
        
        trading_logger.logger.info(
            f"Email sent for {action} {symbol}",
            extra={
                "event_type": "email_sent",
                "symbol": symbol,
                "action": action,
                "recipients": len(email_config.recipients)
            }
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email for {action} {symbol}: {e}")
        # Don't raise exception - graceful degradation
        return False

def send_trading_summary_robust() -> bool:
    """
    Send trading summary with division-by-zero protection
    """
    if not email_config.enabled:
        logger.info("Email alerts disabled, skipping summary")
        return True
    
    try:
        msg = EmailMessage()
        
        # Calculate net profit/loss with division-by-zero protection
        net_profit = trading_session['money_earned'] - trading_session['money_spent']
        
        if trading_session['money_spent'] > 0:
            profit_pct = (net_profit / trading_session['money_spent'] * 100)
        else:
            profit_pct = 0.0
            logger.info("No money spent in this session, profit percentage set to 0")
        
        # Build email content
        content = f"""
🤖 ROBOTRADING SESSION SUMMARY
{'='*50}

📅 Session: {trading_session['session_type']} TRADING
⏰ Time: {trading_session['session_start_time'].strftime('%Y-%m-%d %H:%M:%S') if trading_session['session_start_time'] else 'N/A'}

📊 TRADING ACTIVITY
{'-'*30}
Total Trades: {trading_session['total_trades']}
Stocks Purchased: {len(trading_session['stocks_purchased'])}
Stocks Sold: {len(trading_session['stocks_sold'])}

💰 FINANCIAL SUMMARY
{'-'*30}
Money Spent: ${trading_session['money_spent']:.2f}
Money Earned: ${trading_session['money_earned']:.2f}
Net Profit/Loss: ${net_profit:.2f} ({profit_pct:+.1f}%)

📈 STOCKS PURCHASED
{'-'*30}
"""
        
        if trading_session['stocks_purchased']:
            for stock in trading_session['stocks_purchased']:
                content += f"• {stock['symbol']}: ${stock['value']:.2f} (YTD: {stock['ytd']}%)\n"
        else:
            content += "• No stocks purchased\n"
        
        content += f"""
📉 STOCKS SOLD
{'-'*30}
"""
        
        if trading_session['stocks_sold']:
            for stock in trading_session['stocks_sold']:
                content += f"• {stock['symbol']}: ${stock['value']:.2f} (YTD: {stock['ytd']}%)\n"
        else:
            content += "• No stocks sold\n"
        
        content += f"""
🎯 NEXT SESSION
{'-'*30}
Next trading session will be at {'3:30 PM GMT-5' if trading_session['session_type'] == 'MORNING' else '9:00 AM GMT-5 tomorrow'}

---
🤖 Robotrading Bot - Automated Trading System
"""
        
        msg.set_content(content)
        msg['Subject'] = f"🤖 Trading Summary - {trading_session['session_type']} Session"
        msg['From'] = email_config.username
        
        # Send to all recipients
        for recipient in email_config.recipients:
            msg['To'] = recipient
            
            with smtplib.SMTP_SSL(email_config.smtp_server, email_config.smtp_port) as smtp:
                smtp.login(email_config.username, email_config.password)
                smtp.send_message(msg)
        
        trading_logger.logger.info(
            f"Trading summary email sent",
            extra={
                "event_type": "summary_sent",
                "session_type": trading_session['session_type'],
                "total_trades": trading_session['total_trades'],
                "profit_loss": net_profit
            }
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to send trading summary email: {e}")
        return False

def check_stop_loss_positions_robust() -> List[Tuple[str, float]]:
    """
    Check current positions for stop-loss triggers with robust error handling.
    Returns list of (symbol, loss_percentage) tuples that should be sold.
    Uses advanced stop-loss functionality if available.
    """
    try:
        # Try to use advanced stop-loss functionality
        from advanced_stop_loss import check_advanced_stop_loss_positions
        advanced_positions = check_advanced_stop_loss_positions()
        
        # Convert to simple format for backward compatibility
        simple_positions = [(symbol, loss_pct) for symbol, loss_pct, reason in advanced_positions]
        
        if simple_positions:
            logger.info(f"Advanced stop-loss check found {len(simple_positions)} positions to sell")
            for symbol, loss_pct in simple_positions:
                trading_logger.logger.warning(
                    f"Advanced stop loss triggered",
                    extra={
                        "event_type": "advanced_stop_loss_triggered",
                        "symbol": symbol,
                        "loss_percentage": loss_pct
                    }
                )
        
        return simple_positions
        
    except ImportError:
        # Fallback to basic stop-loss if advanced module not available
        logger.warning("Advanced stop-loss module not available, using basic stop-loss")
        return check_basic_stop_loss_positions()
    except Exception as e:
        logger.error(f"Error in advanced stop-loss check: {e}")
        return check_basic_stop_loss_positions()

def check_basic_stop_loss_positions() -> List[Tuple[str, float]]:
    """
    Basic stop-loss check as fallback
    """
    if not ensure_ibkr_connection():
        return []
    
    try:
        positions = ib.positions()
        stop_loss_triggered = []
        
        # Get stop-loss threshold from config
        try:
            stop_loss_threshold = trading_config.stop_loss_threshold
        except:
            stop_loss_threshold = -5.0  # Default fallback
        
        for p in positions:
            if p.position > 0:  # Long position
                symbol = p.contract.symbol
                current_price = p.marketValue / p.position
                avg_cost = p.averageCost
                
                if avg_cost > 0:
                    loss_pct = ((current_price - avg_cost) / avg_cost) * 100
                    if loss_pct <= stop_loss_threshold:  # Loss exceeds stop-loss threshold
                        stop_loss_triggered.append((symbol, loss_pct))
                        trading_logger.logger.warning(
                            f"Basic stop loss triggered",
                            extra={
                                "event_type": "basic_stop_loss_triggered",
                                "symbol": symbol,
                                "loss_percentage": loss_pct,
                                "current_price": current_price,
                                "avg_cost": avg_cost,
                                "stop_loss_threshold": stop_loss_threshold
                            }
                        )
                        logger.warning(f"🛑 BASIC STOP LOSS TRIGGERED: {symbol} {loss_pct:.1f}% loss (${current_price:.2f} vs ${avg_cost:.2f}) - SELLING")
        
        return stop_loss_triggered
    except Exception as e:
        logger.error(f"Error checking basic stop-loss positions: {e}")
        return []

@retry_ibkr_call(max_retries=3, base_delay=2.0)
def execute_trade_robust(symbol: str, action: str, asset_class=AssetClass.EQUITY) -> Optional[Dict[str, Any]]:
    """
    Execute trade with robust error handling and fill confirmation
    """
    if not ensure_ibkr_connection():
        logger.error("IBKR client not available. Skipping trade.")
        return None

    try:
        # Get current price with caching
        ticker = yf.Ticker(symbol)
        latest_price = ticker.info.get('regularMarketPrice', ticker.history(period='1d')['Close'].iloc[-1])
        
        if latest_price <= 0:
            logger.error(f"Invalid price for {symbol}: {latest_price}")
            return None

        # Update portfolio value from account
        account = ib.accountSummary()
        total_value = float([a.value for a in account if a.tag == 'NetLiquidation'][0])
        portfolio_manager.update_portfolio_value(total_value)
        
        # Get current positions
        positions = ib.positions()
        positions_data = []
        for p in positions:
            if p.position != 0:
                positions_data.append({
                    'symbol': p.contract.symbol,
                    'qty': p.position,
                    'market_value': p.marketValue
                })
        
        portfolio_manager.update_positions(positions_data)
        
        # Fixed position size with allocation limits
        trade_size = min(trading_config.shares_per_trade, 
                        portfolio_manager.get_available_allocation(asset_class) // latest_price)
        
        if trade_size <= 0:
            logger.warning(f"No available allocation for {symbol} in {asset_class}")
            return None
        
        # Create and place order
        contract = Stock(symbol, 'SMART', 'USD')
        order = Order()
        order.action = action
        order.totalQuantity = trade_size
        order.orderType = 'MKT'
        
        # Place order
        trade = ib.placeOrder(contract, order)
        
        # Wait for fill confirmation (non-blocking)
        start_time = time.time()
        timeout = 30  # 30 seconds timeout
        
        while time.time() - start_time < timeout:
            if trade.isDone():
                break
            time.sleep(0.1)  # Non-blocking sleep
        
        if trade.isDone() and trade.orderStatus.status == 'Filled':
            # Get execution details
            executions = ib.executions()
            fill_price = None
            fill_quantity = 0
            
            for exec in executions:
                if exec.contract.symbol == symbol and exec.time.date() == datetime.now().date():
                    fill_price = exec.price
                    fill_quantity = exec.shares
                    break
            
            if fill_price is None:
                # Fallback to order price
                fill_price = latest_price
                fill_quantity = trade_size
            
            trade_value = fill_price * fill_quantity
            
            trading_logger.log_trade_execution(
                symbol=symbol,
                action=action,
                quantity=fill_quantity,
                price=fill_price,
                order_id=str(trade.order.orderId)
            )
            
            return {
                'symbol': symbol,
                'action': action,
                'quantity': fill_quantity,
                'price': fill_price,
                'value': trade_value,
                'order_id': trade.order.orderId
            }
        else:
            logger.warning(f"Order not filled for {symbol}: {trade.orderStatus.status}")
            return None
            
    except Exception as e:
        logger.error(f"Error executing trade for {symbol}: {e}")
        return None

def run_equity_trading() -> TradingResult:
    """
    Run equity trading workflow in isolation
    """
    try:
        trading_logger.logger.info("Starting equity trading workflow")
        
        # Get top stocks with caching
        top_df = get_top_stocks_cached(15)
        if top_df.empty:
            logger.warning("No stocks retrieved, using fallback symbols")
            equity_symbols = ['STX', 'PLTR', 'WDC', 'GEV', 'NEM', 'VST', 'TPL', 'SMCI', 'ANET', 'KLAC', 'NVDA', 'LRCX', 'AXON', 'NTAP', 'PGR']
        else:
            equity_symbols = top_df['Symbol'].tolist()
            portfolio_manager.equity_symbols = set(equity_symbols)
        
        # Generate signals with robust HMM
        stock_data = fetch_stock_data_cached(equity_symbols)
        equity_signals = generate_signals_robust(stock_data)
        
        # Process signals
        buy_signals = [(s, equity_signals[s].iloc[-1]) for s in equity_symbols if s in equity_signals.columns and equity_signals[s].iloc[-1] == 1]
        buy_signals = sorted(buy_signals, key=lambda x: top_df[top_df['Symbol'] == x[0]]['YTD'].iloc[0], reverse=True)[:5]
        sell_signals = [(s, equity_signals[s].iloc[-1]) for s in equity_symbols if s in equity_signals.columns and equity_signals[s].iloc[-1] == -1]
        
        # ADVANCED STOP-LOSS CHECKING: Check for losing positions to sell (NO EMAIL ALERTS)
        try:
            from advanced_stop_loss import process_advanced_stop_losses
            executed_stop_losses = process_advanced_stop_losses()
            if executed_stop_losses > 0:
                logger.info(f"Advanced stop-loss processing completed: {executed_stop_losses} positions sold (no email alerts sent)")
        except ImportError:
            # Fallback to basic stop-loss checking
            stop_loss_positions = check_stop_loss_positions_robust()
            for symbol, loss_pct in stop_loss_positions:
                logger.warning(f"🛑 BASIC STOP LOSS: {symbol} {loss_pct:.1f}% loss - Selling to limit losses (no email alert)")
                sell_signals.append((symbol, -1))
        except Exception as e:
            logger.error(f"Error in stop-loss processing: {e}")
            # Fallback to basic stop-loss checking
            stop_loss_positions = check_stop_loss_positions_robust()
            for symbol, loss_pct in stop_loss_positions:
                logger.warning(f"🛑 FALLBACK STOP LOSS: {symbol} {loss_pct:.1f}% loss - Selling to limit losses (no email alert)")
                sell_signals.append((symbol, -1))
        
        # Execute trades
        trades_executed = 0
        for symbol, signal in buy_signals + sell_signals:
            action = "BUY" if signal == 1 else "SELL"
            order = execute_trade_robust(symbol, action, AssetClass.EQUITY)
            
            if order:
                trades_executed += 1
                # Send email alert
                send_email_alert_robust(symbol, action, top_df, order['value'])
        
        return TradingResult(
            success=True,
            message=f"Equity trading completed: {trades_executed} trades executed",
            data={'trades_executed': trades_executed, 'signals_generated': len(buy_signals + sell_signals)}
        )
        
    except Exception as e:
        logger.error(f"Equity trading failed: {e}")
        return TradingResult(
            success=False,
            message=f"Equity trading failed: {e}",
            error=e
        )

def run_bond_trading() -> TradingResult:
    """
    Run bond trading workflow in isolation
    """
    try:
        trading_logger.logger.info("Starting bond trading workflow")
        
        bond_trader = BondTrader()
        bond_symbols = list(bond_trader.bond_etfs.keys())
        bond_signals = bond_trader.generate_bond_signals(bond_symbols)
        
        # Process bond signals
        bond_buy_signals = [(s, bond_signals[s]) for s in bond_symbols if bond_signals[s] == 1]
        bond_sell_signals = [(s, bond_signals[s]) for s in bond_symbols if bond_signals[s] == -1]
        
        # Execute trades
        trades_executed = 0
        for symbol, signal in bond_buy_signals + bond_sell_signals:
            action = "BUY" if signal == 1 else "SELL"
            order = execute_trade_robust(symbol, action, AssetClass.FIXED_INCOME)
            
            if order:
                trades_executed += 1
                send_email_alert_robust(symbol, action, None, order['value'])
        
        return TradingResult(
            success=True,
            message=f"Bond trading completed: {trades_executed} trades executed",
            data={'trades_executed': trades_executed, 'signals_generated': len(bond_buy_signals + bond_sell_signals)}
        )
        
    except Exception as e:
        logger.error(f"Bond trading failed: {e}")
        return TradingResult(
            success=False,
            message=f"Bond trading failed: {e}",
            error=e
        )

def run_crypto_trading() -> TradingResult:
    """
    Run crypto trading workflow in isolation
    """
    try:
        trading_logger.logger.info("Starting crypto trading workflow")
        
        crypto_trader = CryptoTrader()
        crypto_symbols = list(crypto_trader.crypto_symbols.keys())
        crypto_signals = crypto_trader.generate_crypto_signals(crypto_symbols)
        
        # Process crypto signals
        crypto_buy_signals = [(s, crypto_signals[s]) for s in crypto_symbols if crypto_signals[s] == 1]
        crypto_sell_signals = [(s, crypto_signals[s]) for s in crypto_symbols if crypto_signals[s] == -1]
        
        # Execute trades
        trades_executed = 0
        for symbol, signal in crypto_buy_signals + crypto_sell_signals:
            action = "BUY" if signal == 1 else "SELL"
            order = execute_trade_robust(symbol, action, AssetClass.CRYPTO)
            
            if order:
                trades_executed += 1
                send_email_alert_robust(symbol, action, None, order['value'])
        
        return TradingResult(
            success=True,
            message=f"Crypto trading completed: {trades_executed} trades executed",
            data={'trades_executed': trades_executed, 'signals_generated': len(crypto_buy_signals + crypto_sell_signals)}
        )
        
    except Exception as e:
        logger.error(f"Crypto trading failed: {e}")
        return TradingResult(
            success=False,
            message=f"Crypto trading failed: {e}",
            error=e
        )

def run_bot_robust():
    """
    Main bot function with isolated workflows and graceful error handling
    """
    session_start = datetime.now()
    trading_session['session_start_time'] = session_start
    trading_session['session_type'] = 'MORNING' if session_start.hour < 12 else 'AFTERNOON'
    
    trading_logger.log_session_start(trading_session['session_type'])
    
    logger.info(f"--- Multi-Asset Trading Bot Run: {session_start.strftime('%Y-%m-%d %H:%M:%S')} ---")
    logger.info(f"Trading Mode: {'PAPER' if config.brokers[0].paper_trading else 'LIVE'}")
    
    # Initialize portfolio managers
    portfolio_manager = PortfolioManager()
    
    # Run each asset class workflow in isolation
    results = {}
    
    # 1. EQUITY TRADING (60% of portfolio)
    logger.info("=" * 50)
    logger.info("EQUITY TRADING (60% allocation)")
    logger.info("=" * 50)
    results['equity'] = run_equity_trading()
    
    # 2. FIXED INCOME TRADING (30% of portfolio)
    logger.info("=" * 50)
    logger.info("FIXED INCOME TRADING (30% allocation)")
    logger.info("=" * 50)
    results['bonds'] = run_bond_trading()
    
    # 3. CRYPTO TRADING (10% of portfolio)
    logger.info("=" * 50)
    logger.info("CRYPTO TRADING (10% allocation)")
    logger.info("=" * 50)
    results['crypto'] = run_crypto_trading()
    
    # 4. PORTFOLIO SUMMARY
    logger.info("=" * 50)
    logger.info("PORTFOLIO SUMMARY")
    logger.info("=" * 50)
    portfolio_manager.log_portfolio_status()
    
    # Log session results
    total_trades = sum(r.data.get('trades_executed', 0) for r in results.values() if r.success)
    net_profit = trading_session['money_earned'] - trading_session['money_spent']
    
    trading_logger.log_session_end(
        session_type=trading_session['session_type'],
        total_trades=total_trades,
        profit_loss=net_profit
    )
    
    # Send summary email
    send_trading_summary_robust()
    
    # Log results summary
    logger.info("Trading session completed:")
    for asset_class, result in results.items():
        status = "SUCCESS" if result.success else "FAILED"
        logger.info(f"  {asset_class.upper()}: {status} - {result.message}")
    
    return results

def main():
    """Main entry point with health checks and graceful shutdown"""
    try:
        # Run health check before starting
        logger.info("Running health check...")
        health_results = run_health_check({
            "alpha_vantage_key": config.api.alpha_vantage_key,
            "email": {
                "enabled": email_config.enabled,
                "smtp_server": email_config.smtp_server,
                "smtp_port": email_config.smtp_port,
                "username": email_config.username,
                "password": email_config.password
            },
            "brokers": [
                {
                    "name": broker.name,
                    "enabled": broker.enabled,
                    "host": broker.host,
                    "port": broker.port,
                    "client_id": broker.client_id
                }
                for broker in config.brokers
            ]
        }, detailed=True)
        
        logger.info(f"Health check completed: {health_results['overall_status']}")
        
        # Initialize IBKR
        if not initialize_ibkr():
            logger.error("Failed to initialize IBKR, exiting")
            return
        
        # Run the bot
        results = run_bot_robust()
        
        # Log final metrics
        metrics = get_metrics()
        logger.info(f"Final metrics: {json.dumps(metrics, indent=2)}")
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
    finally:
        # Cleanup
        try:
            if ib and ib.isConnected():
                ib.disconnect()
                logger.info("Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    main()