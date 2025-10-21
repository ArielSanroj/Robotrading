# Interactive Brokers (IBKR) Integration

This trading bot now supports both **Alpaca** and **Interactive Brokers (IBKR)** with identical functionality. You can seamlessly switch between brokers by changing a single environment variable.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install ib_insync
```

### 2. Configure Environment
Copy `.env.example` to `.env` and update the broker settings:
```bash
cp .env.example .env
```

Edit `.env`:
```env
# Select your broker
BROKER=IBKR  # Options: ALPACA or IBKR
USE_PAPER=True  # Set to False for live trading

# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # 7497 for paper, 7496 for live
IBKR_CLIENT_ID=1
```

### 3. Test IBKR Connection
```bash
python test_ibkr.py
```

### 4. Run the Trading Bot
```bash
python robotrading.py
```

## 📋 IBKR Setup Requirements

### Prerequisites
1. **IBKR Account**: Sign up at [interactivebrokers.com](https://www.interactivebrokers.com)
   - Start with **Paper Trading** (free, $1M simulated funds)
   - Live trading requires account verification and funding

2. **TWS or IB Gateway**: Download from [IBKR API page](https://www.interactivebrokers.com/en/trading/ib-api.php)
   - **TWS**: Full desktop application
   - **IB Gateway**: Lightweight headless version (recommended for servers)

### API Configuration
1. **Enable API Access**:
   - Open TWS/Gateway
   - Go to **File > Global Configuration > API > Settings**
   - Check **"Enable ActiveX and Socket Clients"**
   - Set **Socket Port**: `7497` (paper) or `7496` (live)
   - Uncheck **"Read-Only API"** (for trading)
   - Add **Trusted IP**: `127.0.0.1`

2. **Start TWS/Gateway**:
   - Must be running **before** starting the bot
   - Log in with your IBKR credentials
   - Keep it running during bot operation

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `BROKER` | Trading broker | `ALPACA` | `ALPACA`, `IBKR` |
| `USE_PAPER` | Paper trading mode | `True` | `True`, `False` |
| `SHARES_PER_TRADE` | Shares per trade | `10` | Any integer |
| `IBKR_HOST` | IBKR Gateway host | `127.0.0.1` | IP address |
| `IBKR_PORT` | IBKR Gateway port | `7497` | `7497` (paper), `7496` (live) |
| `IBKR_CLIENT_ID` | Unique client ID | `1` | `1-100` |

### Broker Comparison

| Feature | Alpaca | IBKR |
|---------|--------|------|
| **Setup** | API keys only | TWS/Gateway required |
| **Paper Trading** | ✅ Built-in | ✅ Built-in |
| **Live Trading** | ✅ API-based | ✅ API-based |
| **Market Data** | ✅ Real-time | ✅ Real-time |
| **Position Checking** | ✅ | ✅ |
| **Order Types** | Market orders | Market orders |
| **Rate Limits** | Generous | 50 msg/sec |
| **Cost** | Free API | Free API |

## 🎯 Features

### Identical Functionality
Both brokers support the same features:
- ✅ **Top Stock Selection**: S&P 500 YTD performance
- ✅ **Cross-Price Verification**: Alpha Vantage integration
- ✅ **Technical Analysis**: SMA crossover signals
- ✅ **Position Management**: Automatic position checking
- ✅ **Market Hours**: Trading only during market hours
- ✅ **Email Alerts**: Gmail notifications
- ✅ **Scheduled Trading**: Daily 9:30 AM runs

### IBKR-Specific Features
- ✅ **Real-time Market Data**: Live price feeds
- ✅ **Account Summary**: Balance and equity tracking
- ✅ **Position Tracking**: Detailed position information
- ✅ **Order Status**: Real-time order monitoring
- ✅ **Connection Management**: Automatic reconnection

## 🧪 Testing

### Test Script
Run the included test script to verify your setup:
```bash
python test_ibkr.py
```

This will test:
- ✅ Connection to IBKR
- ✅ Account summary retrieval
- ✅ Position listing
- ✅ Market data access
- ✅ Market hours detection

### Manual Testing
1. **Paper Trading**: Start with paper mode (`USE_PAPER=True`)
2. **Monitor Logs**: Check `alerts.log` for detailed information
3. **Verify Orders**: Check TWS/Gateway for order execution
4. **Test Signals**: Run bot during market hours

## 🚨 Troubleshooting

### Common Issues

#### Connection Refused
```
Error: Connection refused
```
**Solution**: Ensure TWS/Gateway is running with API enabled

#### Permission Denied
```
Error: Permission denied
```
**Solution**: Add `127.0.0.1` to trusted IPs in TWS settings

#### No Market Data
```
Warning: No market data available
```
**Solution**: Check market hours and connection status

#### Order Failures
```
Error: Order failed
```
**Solution**: Verify account has sufficient buying power

### Debug Mode
Enable detailed logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Connection Status
Check if IBKR is connected:
```python
from ibkr_client import IBKRTradingClientSync
client = IBKRTradingClientSync(paper=True)
print(f"Connected: {client.is_connected()}")
```

## 📊 Usage Examples

### Switch Between Brokers
```bash
# Use Alpaca
export BROKER=ALPACA
python robotrading.py

# Use IBKR
export BROKER=IBKR
python robotrading.py
```

### Paper vs Live Trading
```bash
# Paper trading (safe)
export USE_PAPER=True
python robotrading.py

# Live trading (real money)
export USE_PAPER=False
python robotrading.py
```

### Custom Trade Size
```bash
# Trade 5 shares per signal
export SHARES_PER_TRADE=5
python robotrading.py
```

## 🔒 Security Notes

### Paper Trading
- ✅ **Safe**: No real money at risk
- ✅ **Realistic**: Uses real market data
- ✅ **Testing**: Perfect for strategy validation

### Live Trading
- ⚠️ **Real Money**: Actual funds at risk
- ⚠️ **Account Approval**: Requires IBKR verification
- ⚠️ **Compliance**: Follow trading regulations
- ⚠️ **Monitoring**: Watch positions closely

## 📈 Performance

### IBKR Advantages
- **Lower Commissions**: Competitive pricing
- **Global Markets**: Access to international exchanges
- **Advanced Tools**: Professional trading platform
- **Reliability**: Established broker with strong infrastructure

### Alpaca Advantages
- **Simplicity**: Easy API setup
- **Developer-Friendly**: Modern REST API
- **Fast Execution**: Optimized for algorithmic trading
- **Free API**: No additional costs

## 🆘 Support

### IBKR Resources
- [IBKR API Documentation](https://interactivebrokers.github.io/tws-api/)
- [IBKR Campus](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/)
- [IBKR Support](https://www.interactivebrokers.com/en/support/)

### Bot Issues
- Check `alerts.log` for detailed error messages
- Run `test_ibkr.py` to diagnose connection issues
- Verify TWS/Gateway is running and configured correctly

## 🎉 Success!

Once everything is set up, your trading bot will:
1. **Connect** to IBKR automatically
2. **Fetch** top-performing stocks
3. **Analyze** technical indicators
4. **Execute** trades based on signals
5. **Send** email notifications
6. **Log** all activities

The bot runs daily at 9:30 AM (weekdays only) and provides the same functionality as the Alpaca version with the added benefits of IBKR's professional trading infrastructure.

Happy trading! 🚀