"""
Test script for IBKR integration
Run this to verify your IBKR connection and configuration
"""

import os
import logging
from dotenv import load_dotenv
from ibkr_client import IBKRTradingClientSync

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ibkr_connection():
    """Test IBKR connection and basic functionality"""
    
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    paper = os.getenv("USE_PAPER", "True").lower() == "true"
    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "7497" if paper else "7496"))
    client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))
    
    logger.info("=" * 50)
    logger.info("IBKR Connection Test")
    logger.info("=" * 50)
    logger.info(f"Mode: {'Paper Trading' if paper else 'Live Trading'}")
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Client ID: {client_id}")
    logger.info("=" * 50)
    
    # Initialize client
    try:
        client = IBKRTradingClientSync(paper=paper)
        logger.info("✓ IBKR client initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize IBKR client: {e}")
        return False
    
    # Test connection
    try:
        if client.connect():
            logger.info("✓ Successfully connected to IBKR")
        else:
            logger.error("✗ Failed to connect to IBKR")
            logger.error("Make sure TWS or IB Gateway is running with API enabled")
            return False
    except Exception as e:
        logger.error(f"✗ Connection error: {e}")
        return False
    
    # Test account summary
    try:
        summary = client.get_account_summary()
        if summary:
            logger.info("✓ Account summary retrieved:")
            for key, value in summary.items():
                if key in ['TotalCashValue', 'NetLiquidation', 'BuyingPower']:
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("⚠ No account summary data")
    except Exception as e:
        logger.error(f"✗ Error getting account summary: {e}")
    
    # Test positions
    try:
        positions = client.get_positions()
        logger.info(f"✓ Retrieved {len(positions)} positions")
        for pos in positions[:3]:  # Show first 3 positions
            logger.info(f"  {pos['symbol']}: {pos['qty']} shares")
    except Exception as e:
        logger.error(f"✗ Error getting positions: {e}")
    
    # Test market data
    try:
        market_data = client.get_market_data('AAPL')
        if market_data:
            logger.info(f"✓ Market data for AAPL: ${market_data['last_price']}")
        else:
            logger.warning("⚠ No market data for AAPL")
    except Exception as e:
        logger.error(f"✗ Error getting market data: {e}")
    
    # Test market hours
    try:
        is_open = client.is_market_open()
        logger.info(f"✓ Market status: {'Open' if is_open else 'Closed'}")
    except Exception as e:
        logger.error(f"✗ Error checking market status: {e}")
    
    # Cleanup
    try:
        client.disconnect()
        logger.info("✓ Disconnected from IBKR")
    except Exception as e:
        logger.error(f"✗ Error disconnecting: {e}")
    
    logger.info("=" * 50)
    logger.info("Test completed!")
    logger.info("=" * 50)
    
    return True

def print_setup_instructions():
    """Print setup instructions for IBKR"""
    print("\n" + "=" * 60)
    print("IBKR SETUP INSTRUCTIONS")
    print("=" * 60)
    print("1. Download and install TWS or IB Gateway from:")
    print("   https://www.interactivebrokers.com/en/trading/ib-api.php")
    print()
    print("2. Enable API access in TWS/Gateway:")
    print("   - File > Global Configuration > API > Settings")
    print("   - Check 'Enable ActiveX and Socket Clients'")
    print(f"   - Set Socket Port: {'7497' if os.getenv('USE_PAPER', 'True').lower() == 'true' else '7496'}")
    print("   - Add trusted IP: 127.0.0.1")
    print()
    print("3. Start TWS/Gateway and log in")
    print()
    print("4. Run this test script:")
    print("   python test_ibkr.py")
    print()
    print("5. If successful, update your .env file:")
    print("   BROKER=IBKR")
    print("   USE_PAPER=True  # or False for live trading")
    print("=" * 60)

if __name__ == "__main__":
    print_setup_instructions()
    
    # Check if .env exists
    if not os.path.exists('.env'):
        logger.warning("No .env file found. Please create one based on .env.example")
        exit(1)
    
    # Run test
    success = test_ibkr_connection()
    
    if success:
        logger.info("🎉 IBKR integration test completed successfully!")
        logger.info("You can now set BROKER=IBKR in your .env file")
    else:
        logger.error("❌ IBKR integration test failed")
        logger.error("Please check the setup instructions above")