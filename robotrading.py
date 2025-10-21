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

# Importar nuevos módulos de gestión de cartera
from portfolio_manager import PortfolioManager, AssetClass, AssetAllocation
from crypto_trader import CryptoTrader
from bond_trader import BondTrader

# Suppress urllib3 warning
import warnings
warnings.filterwarnings("ignore", category=Warning)

# Set up logging to file
logging.basicConfig(filename='alerts.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
IBKR_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.getenv("IBKR_PORT", 7497))  # 7497 for paper, 7496 for live
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", 1))

# Configuración de trading en vivo
USE_PAPER = os.getenv("USE_PAPER", "True").lower() == "true"
SHARES_PER_TRADE = int(os.getenv("SHARES_PER_TRADE", 10))

# Inicializar gestores de cartera
portfolio_manager = PortfolioManager()
crypto_trader = CryptoTrader()
bond_trader = BondTrader()

# Trading session tracking
trading_session = {
    'session_type': '',  # 'MORNING' or 'AFTERNOON'
    'stocks_purchased': [],
    'stocks_sold': [],
    'money_spent': 0.0,
    'money_earned': 0.0,
    'total_trades': 0,
    'session_start_time': None
}

if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECIPIENT_EMAIL]):
    logger.error("Missing email environment variables. Please set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and RECIPIENT_EMAIL.")
    exit(1)

# Initialize IBKR Client
try:
    ib = IB()
    ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
    logger.info(f"Connected to IBKR in {'Paper' if IBKR_PORT == 7497 else 'Live'} mode")
except Exception as e:
    logger.error(f"Failed to connect to IBKR: {e}")
    ib = None

# Email alert function
def send_email_alert(symbol, action, top_df=None, trade_value=0.0):
    """
    Sends an email alert for BUY or SELL signals using Gmail SMTP.
    Includes YTD return if top_df is provided.
    """
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
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
            logger.info(f"Email sent for {action} {symbol}")
    except Exception as e:
        logger.error(f"Failed to send email for {action} {symbol}: {e}")

# Trading session summary email
def send_trading_summary():
    """
    Sends a comprehensive trading session summary email.
    """
    try:
        msg = EmailMessage()
        
        # Calculate net profit/loss
        net_profit = trading_session['money_earned'] - trading_session['money_spent']
        profit_pct = (net_profit / trading_session['money_spent'] * 100) if trading_session['money_spent'] > 0 else 0
        
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
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
            logger.info(f"Trading summary email sent for {trading_session['session_type']} session")
            
    except Exception as e:
        logger.error(f"Failed to send trading summary email: {e}")

# Reset trading session
def reset_trading_session(session_type):
    """Reset trading session tracking for new session"""
    global trading_session
    trading_session = {
        'session_type': session_type,
        'stocks_purchased': [],
        'stocks_sold': [],
        'money_spent': 0.0,
        'money_earned': 0.0,
        'total_trades': 0,
        'session_start_time': datetime.now()
    }

# Execute trade via IBKR with portfolio allocation validation
def execute_trade(symbol, action, asset_class=AssetClass.EQUITY):
    """
    Executes a market order via IBKR based on the signal with portfolio allocation validation.
    - Checks portfolio allocation limits before trading
    - Determines appropriate trade size based on available allocation
    - Validates asset class limits
    """
    if not ib:
        logger.error("IBKR client not available. Skipping trade.")
        return None

    try:
        # Get current price
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
        
        # Determine trade size based on allocation limits
        if action == "BUY":
            # Check if we can trade this asset class
            can_trade, reason = portfolio_manager.can_trade_asset_class(asset_class, latest_price * SHARES_PER_TRADE)
            if not can_trade:
                logger.warning(f"Cannot buy {symbol} ({asset_class.value}): {reason}")
                return None
            
            # Get recommended trade size
            recommended_shares = portfolio_manager.get_recommended_trade_size(symbol, asset_class, latest_price)
            if recommended_shares <= 0:
                logger.warning(f"No buying power available for {symbol} in {asset_class.value}")
                return None
            
            # Use recommended size or default, whichever is smaller
            trade_shares = min(recommended_shares, SHARES_PER_TRADE)
            
            # Check buying power
            buying_power = float([a.value for a in account if a.tag == 'AvailableFunds'][0])
            trade_value = latest_price * trade_shares
            if buying_power < trade_value:
                logger.warning(f"Insufficient buying power for {symbol} (${buying_power:.2f} < ${trade_value:.2f})")
                return None
            
            # Check if already holding
            position_qty = sum(p.position for p in positions if p.contract.symbol == symbol)
            if position_qty > 0:
                logger.info(f"Already holding {symbol}. Skipping BUY.")
                return None
                
        else:  # SELL
            # Check current position
            position_qty = sum(p.position for p in positions if p.contract.symbol == symbol)
            if position_qty < SHARES_PER_TRADE:
                logger.warning(f"Insufficient shares to sell for {symbol}. Have {position_qty}, need {SHARES_PER_TRADE}")
                return None
            trade_shares = SHARES_PER_TRADE

        # Define contract based on asset class
        if asset_class == AssetClass.CRYPTO:
            # For crypto, we'll use stock contracts with crypto symbols
            contract = Stock(symbol, 'SMART', 'USD')
        else:
            contract = Stock(symbol, 'SMART', 'USD')
        
        ib.qualifyContracts(contract)

        # Prepare order
        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = trade_shares
        order.tif = "DAY"
        order.outsideRth = True  # Allow after-hours trading

        # Submit order
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)
        
        if trade.orderStatus.status in ["Filled", "Submitted"]:
            trade_value = latest_price * trade_shares
            logger.info(f"Trade executed: {action} {trade_shares} shares of {symbol} ({asset_class.value}). Order ID: {trade.order.orderId}. Value: ${trade_value:.2f}")
            
            # Log portfolio status after trade
            portfolio_manager.log_portfolio_status()
            
            return trade
        else:
            logger.error(f"Trade failed for {symbol}: Status {trade.orderStatus.status}")
            return None
            
    except Exception as e:
        logger.error(f"Error executing {action} for {symbol}: {e}")
        return None

# Step 1: Fetch top-performing stocks (YTD)
def get_top_stocks(num_stocks=15):
    """
    Scrapes Slickcharts for top S&P 500 YTD performers.
    Returns DataFrame with 'Symbol' and 'YTD' columns.
    """
    url = "https://www.slickcharts.com/sp500/performance"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to fetch Slickcharts: Status code {response.status_code}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        if not table:
            logger.error("No table found on Slickcharts. Check website structure.")
            return pd.DataFrame()

        rows = table.find_all('tr')[1:num_stocks + 1]
        data = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 4:
                logger.warning(f"Skipping invalid row: {row.text[:50]}...")
                continue
            try:
                symbol = cols[2].text.strip() or cols[2].find('a').text.strip() if cols[2].find('a') else 'N/A'
                ytd_str = cols[3].text.strip().replace('%', '').replace(',', '')
                ytd = float(ytd_str)
                if symbol != 'N/A':
                    ticker = yf.Ticker(symbol)
                    if ticker.history(period='1d').empty:
                        logger.warning(f"Invalid ticker {symbol} detected. Skipping.")
                        continue
                data.append({'Symbol': symbol, 'YTD': ytd})
            except (ValueError, IndexError) as e:
                logger.warning(f"Skipping row due to error: {e}")
                continue

        if not data:
            logger.error("No valid data extracted from Slickcharts.")
            return pd.DataFrame()

        df = pd.DataFrame(data).sort_values('YTD', ascending=False)
        logger.info(f"Top {num_stocks} stocks YTD:\n{df.to_string(index=False)}")
        return df
    except Exception as e:
        logger.error(f"Error in get_top_stocks: {e}")
        return pd.DataFrame()

# Step 2: Cross-check stock price with Alpha Vantage and Yahoo
def cross_check_alpha(symbol):
    """
    Cross-checks price using Alpha Vantage API.
    Returns price (float) or None if failed.
    """
    api_key = ALPHA_VANTAGE_KEY
    if not api_key:
        logger.warning("No Alpha Vantage API key. Skipping cross-check.")
        return None
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Alpha Vantage fetch failed for {symbol}: Status code {response.status_code}")
            return None
        data = response.json()
        if "Global Quote" not in data:
            logger.warning(f"No price data for {symbol} from Alpha Vantage: {data.get('Note', 'No data')}")
            return None
        price = float(data['Global Quote']['05. price'])
        logger.info(f"Alpha Vantage price for {symbol}: {price}")
        return price
    except Exception as e:
        logger.error(f"Alpha Vantage error for {symbol}: {e}")
        return None

# Step 3: Fetch historical stock data with cross-checking
def fetch_stock_data(symbols, period='1y'):
    """
    Fetches closing prices for the given symbols using yfinance, cross-checked with Alpha Vantage and Yahoo.
    Returns DataFrame with dates as index and symbols as columns.
    """
    data = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            if hist.empty:
                logger.warning(f"No historical data for {symbol} from yfinance")
                continue
            # Cross-check latest price
            latest_yf_price = hist['Close'].iloc[-1] if not hist['Close'].empty else None
            alpha_price = cross_check_alpha(symbol)
            yahoo_price = ticker.info.get('regularMarketPrice', None)
            if all([latest_yf_price, alpha_price, yahoo_price]):
                prices = [latest_yf_price, alpha_price, yahoo_price]
                median_price = np.median(prices)
                max_variance = max([abs(p - median_price) / median_price * 100 for p in prices])
                if max_variance > 2:
                    logger.warning(f"Skipping {symbol} due to high price variance: yfinance={latest_yf_price:.2f}, Alpha Vantage={alpha_price:.2f}, Yahoo={yahoo_price:.2f} ({max_variance:.2f}%)")
                    continue
            data[symbol] = hist['Close']
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            continue
    df = pd.DataFrame(data)
    if df.empty:
        logger.error("No data fetched for any symbols")
        raise ValueError("No data fetched for any symbols")
    logger.info(f"Fetched data for {len(data)} symbols up to {df.index[-1].date()}")
    return df

# Step 4: Generate buy/sell signals using HMM
def generate_signals(df, k_regimes=2):
    """
    Fits HMM (MarkovRegression) to detect regimes (low/high vol).
    - BUY (1) if low-vol regime (prob[0] > 0.5)
    - SELL (-1) if high-vol regime
    - HOLD (0) otherwise
    For long-only: set signal = 1 if prob[0] > 0.5 else 0
    Logs latest regime probabilities.
    """
    signals = pd.DataFrame(index=df.index)
    for col in df.columns:
        prices = df[col].dropna()
        if len(prices) < 252:  # Need ~1 year data
            logger.warning(f"Insufficient data for {col} (need 252 days, have {len(prices)})")
            continue

        # Daily log returns
        returns = np.log(prices / prices.shift(1)).dropna()

        # Fit MarkovRegression (2 regimes, switching variance)
        try:
            model = MarkovRegression(returns, k_regimes=k_regimes, switching_variance=True)
            results = model.fit(disp=False)
        except Exception as e:
            logger.warning(f"HMM fitting failed for {col}: {e}")
            continue

        # Smoothed probabilities (prob[0]: low-vol regime)
        probs = results.smoothed_marginal_probabilities
        latest_prob_low = probs[0].iloc[-1]
        signal = 1 if latest_prob_low > 0.5 else -1 if latest_prob_low < 0.5 else 0
        # For long-only: signal = 1 if latest_prob_low > 0.5 else 0

        signals[col] = pd.Series(signal, index=prices.index).fillna(0)

        # Log latest
        logger.info(f"{col} - Latest Signal: {'BUY' if signal == 1 else 'SELL' if signal == -1 else 'HOLD'}")
        logger.info(f"{col} - Latest Low-Vol Prob: {latest_prob_low:.2f}")

    return signals

# Step 4.5: Check for profitable positions for intraday profit-taking
def check_profitable_positions():
    """
    Check current positions for profit-taking opportunities.
    Returns list of (symbol, profit_percentage) tuples.
    """
    if not ib:
        return []
    
    try:
        positions = ib.positions()
        profitable = []
        
        for p in positions:
            if p.position > 0:  # Long position
                symbol = p.contract.symbol
                current_price = p.marketValue / p.position
                avg_cost = p.averageCost
                
                if avg_cost > 0:
                    profit_pct = ((current_price - avg_cost) / avg_cost) * 100
                    if profit_pct > 1.0:  # More than 1% profit
                        profitable.append((symbol, profit_pct))
                        logger.info(f"📈 {symbol}: {profit_pct:.1f}% profit (${current_price:.2f} vs ${avg_cost:.2f})")
        
        return profitable
    except Exception as e:
        logger.error(f"Error checking profitable positions: {e}")
        return []

def check_stop_loss_positions():
    """
    Check current positions for stop-loss triggers.
    Returns list of (symbol, loss_percentage) tuples that should be sold.
    """
    if not ib:
        return []
    
    try:
        positions = ib.positions()
        stop_loss_triggered = []
        
        # Get stop-loss threshold from config
        try:
            from config_manager import get_config
            config = get_config()
            stop_loss_threshold = config.trading.stop_loss_threshold
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
                        logger.warning(f"🛑 STOP LOSS TRIGGERED: {symbol} {loss_pct:.1f}% loss (${current_price:.2f} vs ${avg_cost:.2f}) - SELLING")
        
        return stop_loss_triggered
    except Exception as e:
        logger.error(f"Error checking stop-loss positions: {e}")
        return []

# Step 5: Run the bot (core logic) with multi-asset portfolio management
def run_bot():
    """
    Main bot function: Manages 60% equity, 30% fixed income, 10% crypto portfolio.
    Gets signals for all asset classes and executes trades within allocation limits.
    """
    logger.info(f"--- Multi-Asset Trading Bot Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    logger.info(f"Trading Mode: {'PAPER' if USE_PAPER else 'LIVE'}")
    
    try:
        # 1. EQUITY TRADING (60% of portfolio)
        logger.info("=" * 50)
        logger.info("EQUITY TRADING (60% allocation)")
        logger.info("=" * 50)
        
        top_df = get_top_stocks(15)
        if top_df.empty:
            logger.error("No stocks retrieved. Using fallback symbols.")
            equity_symbols = ['STX', 'PLTR', 'WDC', 'GEV', 'NEM', 'VST', 'TPL', 'SMCI', 'ANET', 'KLAC', 'NVDA', 'LRCX', 'AXON', 'NTAP', 'PGR']
        else:
            equity_symbols = top_df['Symbol'].tolist()
            # Update portfolio manager with equity symbols
            portfolio_manager.equity_symbols = set(equity_symbols)
        
        # Generate equity signals
        stock_data = fetch_stock_data(equity_symbols)
        equity_signals = generate_signals(stock_data)
        
        # Process equity signals with profit-taking logic
        buy_signals = [(s, equity_signals[s].iloc[-1]) for s in equity_symbols if s in equity_signals.columns and equity_signals[s].iloc[-1] == 1]
        buy_signals = sorted(buy_signals, key=lambda x: top_df[top_df['Symbol'] == x[0]]['YTD'].iloc[0], reverse=True)[:5]
        sell_signals = [(s, equity_signals[s].iloc[-1]) for s in equity_symbols if s in equity_signals.columns and equity_signals[s].iloc[-1] == -1]
        
        # INTRADAY PROFIT-TAKING: Check for profitable positions to sell
        current_time = datetime.now()
        if current_time.hour >= 15:  # After 3 PM, look for profit-taking opportunities
            profitable_positions = check_profitable_positions()
            for symbol, profit_pct in profitable_positions:
                if profit_pct > 2.0:  # Take profit if > 2% gain
                    logger.info(f"🎯 PROFIT TAKING: {symbol} +{profit_pct:.1f}% - Selling for profit")
                    sell_signals.append((symbol, -1))
        
        # STOP-LOSS CHECKING: Check for losing positions to sell
        stop_loss_positions = check_stop_loss_positions()
        for symbol, loss_pct in stop_loss_positions:
            logger.warning(f"🛑 STOP LOSS: {symbol} {loss_pct:.1f}% loss - Selling to limit losses")
            sell_signals.append((symbol, -1))
        
        all_equity_signals = buy_signals + sell_signals
        for symbol, signal in all_equity_signals:
            action = "BUY" if signal == 1 else "SELL"
            order = execute_trade(symbol, action, AssetClass.EQUITY)
            if order:
                # Get trade value for tracking
                try:
                    ticker = yf.Ticker(symbol)
                    latest_price = ticker.info.get('regularMarketPrice', ticker.history(period='1d')['Close'].iloc[-1])
                    trade_value = latest_price * 1  # 1 share per trade
                except:
                    trade_value = 0.0
                send_email_alert(symbol, action, top_df, trade_value)
            else:
                logger.info(f"Skipped email for {action} {symbol} due to failed trade")
        
        # 2. FIXED INCOME TRADING (30% of portfolio)
        logger.info("=" * 50)
        logger.info("FIXED INCOME TRADING (30% allocation)")
        logger.info("=" * 50)
        
        bond_symbols = list(bond_trader.bond_etfs.keys())
        bond_signals = bond_trader.generate_bond_signals(bond_symbols)
        
        # Process bond signals
        bond_buy_signals = [(s, bond_signals[s]) for s in bond_symbols if bond_signals[s] == 1]
        bond_sell_signals = [(s, bond_signals[s]) for s in bond_symbols if bond_signals[s] == -1]
        
        all_bond_signals = bond_buy_signals + bond_sell_signals
        for symbol, signal in all_bond_signals:
            action = "BUY" if signal == 1 else "SELL"
            order = execute_trade(symbol, action, AssetClass.FIXED_INCOME)
            if order:
                # Get trade value for tracking
                try:
                    ticker = yf.Ticker(symbol)
                    latest_price = ticker.info.get('regularMarketPrice', ticker.history(period='1d')['Close'].iloc[-1])
                    trade_value = latest_price * 1  # 1 share per trade
                except:
                    trade_value = 0.0
                send_email_alert(symbol, action, None, trade_value)
            else:
                logger.info(f"Skipped email for {action} {symbol} due to failed trade")
        
        # 3. CRYPTO TRADING (10% of portfolio)
        logger.info("=" * 50)
        logger.info("CRYPTO TRADING (10% allocation)")
        logger.info("=" * 50)
        
        crypto_symbols = list(crypto_trader.supported_cryptos.keys())
        crypto_signals = crypto_trader.generate_crypto_signals(crypto_symbols)
        
        # Process crypto signals
        crypto_buy_signals = [(s, crypto_signals[s]) for s in crypto_symbols if crypto_signals[s] == 1]
        crypto_sell_signals = [(s, crypto_signals[s]) for s in crypto_symbols if crypto_signals[s] == -1]
        
        all_crypto_signals = crypto_buy_signals + crypto_sell_signals
        for symbol, signal in all_crypto_signals:
            action = "BUY" if signal == 1 else "SELL"
            order = execute_trade(symbol, action, AssetClass.CRYPTO)
            if order:
                # Get trade value for tracking
                try:
                    ticker = yf.Ticker(symbol)
                    latest_price = ticker.info.get('regularMarketPrice', ticker.history(period='1d')['Close'].iloc[-1])
                    trade_value = latest_price * 1  # 1 share per trade
                except:
                    trade_value = 0.0
                send_email_alert(symbol, action, None, trade_value)
            else:
                logger.info(f"Skipped email for {action} {symbol} due to failed trade")
        
        # 4. PORTFOLIO SUMMARY
        logger.info("=" * 50)
        logger.info("PORTFOLIO SUMMARY")
        logger.info("=" * 50)
        portfolio_manager.log_portfolio_status()
        
    except Exception as e:
        logger.error(f"Error in multi-asset bot run: {e}")
    finally:
        if ib and ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected from IBKR")

# Step 6: Schedule the bot for day trading (9 AM and 3:30 PM GMT-5, weekdays only)
def run_bot_if_weekday():
    """
    Wrapper function to run the bot only on weekdays.
    """
    if datetime.now().weekday() >= 5:
        logger.info(f"Skipping scheduled run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} is a weekend.")
        return
    run_bot()

def run_morning_session():
    """Morning trading session at 9:00 AM GMT-5"""
    logger.info("🌅 MORNING TRADING SESSION (9:00 AM GMT-5)")
    reset_trading_session("MORNING")
    run_bot_if_weekday()
    send_trading_summary()

def run_afternoon_session():
    """Afternoon trading session at 3:30 PM GMT-5"""
    logger.info("🌆 AFTERNOON TRADING SESSION (3:30 PM GMT-5)")
    reset_trading_session("AFTERNOON")
    run_bot_if_weekday()
    send_trading_summary()

if __name__ == "__main__":
    logger.info("Starting Day Trading Bot with IBKR Integration...")
    logger.info("Scheduling daily runs at 9:00 AM and 3:30 PM GMT-5 (weekdays only).")
    
    # Schedule morning session (9:00 AM GMT-5)
    schedule.every().day.at("09:00").do(run_morning_session)
    
    # Schedule afternoon session (3:30 PM GMT-5) 
    schedule.every().day.at("15:30").do(run_afternoon_session)
    
    # Run initial session
    run_bot()
    
    # Keep scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)