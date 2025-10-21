"""
Interactive Brokers (IBKR) Trading Client
Provides the same interface as Alpaca for seamless broker switching
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, time
import os
from dotenv import load_dotenv
from ib_insync import IB, Stock, MarketOrder, util
from ib_insync.objects import Position, PortfolioItem

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class IBKRTradingClient:
    """
    Interactive Brokers trading client that mirrors Alpaca's interface
    """
    
    def __init__(self, paper: bool = True):
        """
        Initialize IBKR client
        
        Args:
            paper: If True, use paper trading (port 7497), else live trading (port 7496)
        """
        self.paper = paper
        self.ib = IB()
        self.connected = False
        self.account_id = None
        
        # Configuration from environment
        self.host = os.getenv('IBKR_HOST', '127.0.0.1')
        self.port = 7497 if paper else 7496
        self.client_id = int(os.getenv('IBKR_CLIENT_ID', 1))
        
        logger.info(f"IBKR client initialized for {'Paper' if paper else 'Live'} trading")
    
    async def connect(self) -> bool:
        """
        Connect to IBKR TWS/Gateway
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connected:
                logger.info("Already connected to IBKR")
                return True
                
            # Connect to IBKR
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            
            # Wait for connection to be established
            await asyncio.sleep(2)
            
            if self.ib.isConnected():
                self.connected = True
                # Get account info
                accounts = self.ib.managedAccounts()
                if accounts:
                    self.account_id = accounts[0]
                    logger.info(f"Connected to IBKR {'Paper' if self.paper else 'Live'} mode. Account: {self.account_id}")
                else:
                    logger.warning("Connected but no managed accounts found")
                
                return True
            else:
                logger.error("Failed to establish connection to IBKR")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to IBKR: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IBKR"""
        try:
            if self.connected:
                self.ib.disconnect()
                self.connected = False
                logger.info("Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Error disconnecting from IBKR: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to IBKR"""
        return self.connected and self.ib.isConnected()
    
    async def get_account_summary(self) -> Dict[str, Any]:
        """
        Get account summary information
        
        Returns:
            Dict containing account balance and equity information
        """
        try:
            if not self.is_connected():
                await self.connect()
            
            if not self.account_id:
                logger.error("No account ID available")
                return {}
            
            # Get account summary
            summary = self.ib.accountSummary(self.account_id)
            
            result = {}
            for item in summary:
                result[item.tag] = item.value
            
            logger.info(f"Account summary retrieved: {len(result)} items")
            return result
            
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions
        
        Returns:
            List of position dictionaries
        """
        try:
            if not self.is_connected():
                await self.connect()
            
            positions = self.ib.positions()
            
            result = []
            for pos in positions:
                if pos.position != 0:  # Only non-zero positions
                    result.append({
                        'symbol': pos.contract.symbol,
                        'qty': pos.position,
                        'market_value': pos.marketValue,
                        'average_cost': pos.averageCost,
                        'unrealized_pnl': pos.unrealizedPNL
                    })
            
            logger.info(f"Retrieved {len(result)} positions")
            return result
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for a specific symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Position dictionary or None if not found
        """
        try:
            positions = await self.get_positions()
            for pos in positions:
                if pos['symbol'] == symbol:
                    return pos
            return None
            
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current market data for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Market data dictionary or None if failed
        """
        try:
            if not self.is_connected():
                await self.connect()
            
            # Create stock contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            
            # Wait for data
            await asyncio.sleep(1)
            
            if ticker.last and ticker.last > 0:
                result = {
                    'symbol': symbol,
                    'last_price': ticker.last,
                    'bid': ticker.bid,
                    'ask': ticker.ask,
                    'volume': ticker.volume
                }
                
                # Cancel market data request
                self.ib.cancelMktData(contract)
                
                logger.info(f"Market data for {symbol}: {result['last_price']}")
                return result
            else:
                logger.warning(f"No market data available for {symbol}")
                self.ib.cancelMktData(contract)
                return None
                
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None
    
    async def is_market_open(self) -> bool:
        """
        Check if market is currently open or recently closed (within 30 minutes)
        
        Returns:
            bool: True if market is open or recently closed, False otherwise
        """
        try:
            # Use time-based market hours check (more reliable than market data)
            current_time = datetime.now().time()
            
            # Market hours: 9:30 AM - 4:00 PM ET (weekdays only)
            # Allow trading up to 30 minutes after close for end-of-day signals
            market_open = time(9, 30)
            market_close = time(16, 30)  # Extended to 4:30 PM for closing signals
            
            is_weekday = datetime.now().weekday() < 5
            is_market_hours = market_open <= current_time <= market_close
            
            market_open_status = is_weekday and is_market_hours
            
            logger.info(f"Market status: {'Open' if market_open_status else 'Closed'}")
            logger.info(f"Current time: {current_time}, Weekday: {is_weekday}")
            
            return market_open_status
                
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False
    
    async def submit_order(self, symbol: str, qty: int, side: str, order_type: str = 'MKT') -> Optional[str]:
        """
        Submit an order to IBKR
        
        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'BUY' or 'SELL'
            order_type: Order type ('MKT' for market order)
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            if not self.is_connected():
                await self.connect()
            
            # Create stock contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Create market order
            if side.upper() == 'BUY':
                order = MarketOrder('BUY', qty)
            elif side.upper() == 'SELL':
                order = MarketOrder('SELL', qty)
            else:
                logger.error(f"Invalid order side: {side}")
                return None
            
            # Submit order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait for order to be processed
            await asyncio.sleep(1)
            
            if trade.orderStatus.status in ['Submitted', 'Filled', 'PartiallyFilled']:
                order_id = str(trade.order.orderId)
                logger.info(f"Order submitted: {side} {qty} shares of {symbol}. Order ID: {order_id}")
                return order_id
            else:
                logger.error(f"Order failed: {trade.orderStatus.status}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting order for {symbol}: {e}")
            return None
    
    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of an order
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status dictionary or None if not found
        """
        try:
            if not self.is_connected():
                await self.connect()
            
            trades = self.ib.trades()
            for trade in trades:
                if str(trade.order.orderId) == order_id:
                    return {
                        'order_id': order_id,
                        'status': trade.orderStatus.status,
                        'filled': trade.orderStatus.filled,
                        'remaining': trade.orderStatus.remaining,
                        'avg_fill_price': trade.orderStatus.avgFillPrice
                    }
            
            logger.warning(f"Order {order_id} not found")
            return None
            
        except Exception as e:
            logger.error(f"Error getting order status for {order_id}: {e}")
            return None

# Synchronous wrapper for compatibility with existing code
class IBKRTradingClientSync:
    """
    Synchronous wrapper for IBKR client to match Alpaca's synchronous interface
    """
    
    def __init__(self, paper: bool = True):
        self.client = IBKRTradingClient(paper)
        self.paper = paper
        self._loop = None
    
    def _get_loop(self):
        """Get or create event loop"""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    def connect(self) -> bool:
        """Connect to IBKR (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.connect())
    
    def disconnect(self):
        """Disconnect from IBKR (synchronous)"""
        self.client.disconnect()
        if self._loop and not self._loop.is_closed():
            self._loop.close()
    
    def is_connected(self) -> bool:
        """Check if connected (synchronous)"""
        return self.client.is_connected()
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.get_account_summary())
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.get_positions())
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for symbol (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.get_position(symbol))
    
    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market data (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.get_market_data(symbol))
    
    def is_market_open(self) -> bool:
        """Check if market is open (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.is_market_open())
    
    def submit_order(self, symbol: str, qty: int, side: str, order_type: str = 'MKT') -> Optional[str]:
        """Submit order (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.submit_order(symbol, qty, side, order_type))
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status (synchronous)"""
        loop = self._get_loop()
        return loop.run_until_complete(self.client.get_order_status(order_id))