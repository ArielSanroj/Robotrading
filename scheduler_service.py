"""
External scheduler service for trading bot deployment
Supports cron jobs, systemd services, and Docker containers
"""

import os
import sys
import time
import signal
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import schedule
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robotrading_improved import run_bot_robust, initialize_ibkr, shutdown_flag
from config_manager import get_config
from logging_config import setup_logging, get_trading_logger
from health_check import HealthCheckServer, HealthChecker

logger = setup_logging(level="INFO", format_type="json")
trading_logger = get_trading_logger("scheduler")

class TradingScheduler:
    """Scheduler service for trading bot"""
    
    def __init__(self):
        self.config = get_config()
        self.running = False
        self.health_server = None
        self.health_checker = HealthChecker()
        self.last_run = None
        self.run_count = 0
        self.error_count = 0
        
    def setup_schedule(self):
        """Set up trading schedule"""
        # Morning session: 9:00 AM EST (14:00 UTC)
        schedule.every().monday.at("14:00").do(self.run_morning_session)
        schedule.every().tuesday.at("14:00").do(self.run_morning_session)
        schedule.every().wednesday.at("14:00").do(self.run_morning_session)
        schedule.every().thursday.at("14:00").do(self.run_morning_session)
        schedule.every().friday.at("14:00").do(self.run_morning_session)
        
        # Afternoon session: 3:30 PM EST (20:30 UTC)
        schedule.every().monday.at("20:30").do(self.run_afternoon_session)
        schedule.every().tuesday.at("20:30").do(self.run_afternoon_session)
        schedule.every().wednesday.at("20:30").do(self.run_afternoon_session)
        schedule.every().thursday.at("20:30").do(self.run_afternoon_session)
        schedule.every().friday.at("20:30").do(self.run_afternoon_session)
        
        logger.info("Trading schedule configured:")
        logger.info("  Morning sessions: 9:00 AM EST (14:00 UTC)")
        logger.info("  Afternoon sessions: 3:30 PM EST (20:30 UTC)")
        logger.info("  Weekdays only")
    
    def run_morning_session(self):
        """Run morning trading session"""
        self._run_session("MORNING")
    
    def run_afternoon_session(self):
        """Run afternoon trading session"""
        self._run_session("AFTERNOON")
    
    def _run_session(self, session_type: str):
        """Run a trading session"""
        if shutdown_flag.is_set():
            logger.info("Shutdown flag set, skipping session")
            return
        
        logger.info(f"Starting {session_type} trading session")
        start_time = datetime.now()
        
        try:
            # Check if market is open (basic check)
            if not self._is_market_open():
                logger.info("Market appears to be closed, skipping session")
                return
            
            # Run health check
            if not self._run_health_check():
                logger.warning("Health check failed, but continuing with session")
            
            # Run the trading bot
            results = run_bot_robust()
            
            # Log results
            duration = datetime.now() - start_time
            self.run_count += 1
            self.last_run = start_time
            
            trading_logger.logger.info(
                f"Trading session completed",
                extra={
                    "event_type": "session_completed",
                    "session_type": session_type,
                    "duration_seconds": duration.total_seconds(),
                    "success": True
                }
            )
            
            logger.info(f"{session_type} session completed in {duration}")
            
        except Exception as e:
            self.error_count += 1
            duration = datetime.now() - start_time
            
            trading_logger.logger.error(
                f"Trading session failed",
                extra={
                    "event_type": "session_failed",
                    "session_type": session_type,
                    "duration_seconds": duration.total_seconds(),
                    "error": str(e)
                }
            )
            
            logger.error(f"{session_type} session failed after {duration}: {e}")
    
    def _is_market_open(self) -> bool:
        """Basic market hours check"""
        now = datetime.now()
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's during market hours (9:30 AM - 4:00 PM EST)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def _run_health_check(self) -> bool:
        """Run health check before trading"""
        try:
            health_results = self.health_checker.run_all_checks({
                "alpha_vantage_key": self.config.api.alpha_vantage_key,
                "email": {
                    "enabled": self.config.email.enabled,
                    "smtp_server": self.config.email.smtp_server,
                    "smtp_port": self.config.email.smtp_port,
                    "username": self.config.email.username,
                    "password": self.config.email.password
                },
                "brokers": [
                    {
                        "name": broker.name,
                        "enabled": broker.enabled,
                        "host": broker.host,
                        "port": broker.port,
                        "client_id": broker.client_id
                    }
                    for broker in self.config.brokers
                ]
            })
            
            # Check if any critical services are unhealthy
            critical_services = ['slickcharts', 'yfinance', 'ibkr']
            unhealthy_services = [
                service for service, result in health_results.items()
                if service in critical_services and result.status.value == 'unhealthy'
            ]
            
            if unhealthy_services:
                logger.warning(f"Critical services unhealthy: {unhealthy_services}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def start_health_server(self):
        """Start health check HTTP server"""
        if self.config.health_check.enabled:
            self.health_server = HealthCheckServer(
                self.health_checker, 
                self.config.health_check.port
            )
            self.health_server.start()
    
    def stop_health_server(self):
        """Stop health check HTTP server"""
        if self.health_server:
            self.health_server.stop()
    
    def start(self):
        """Start the scheduler service"""
        logger.info("Starting trading scheduler service")
        
        # Set up schedule
        self.setup_schedule()
        
        # Start health server
        self.start_health_server()
        
        # Initialize IBKR connection
        if not initialize_ibkr():
            logger.error("Failed to initialize IBKR, scheduler will start but trading may fail")
        
        self.running = True
        
        # Main loop
        try:
            while self.running and not shutdown_flag.is_set():
                schedule.run_pending()
                
                # Run intraday stop-loss checks
                try:
                    from advanced_stop_loss import run_intraday_stop_loss_check
                    executed_stop_losses = run_intraday_stop_loss_check()
                    if executed_stop_losses > 0:
                        logger.info(f"Intraday stop-loss check: {executed_stop_losses} positions sold")
                except ImportError:
                    # Advanced stop-loss not available, skip
                    pass
                except Exception as e:
                    logger.error(f"Error in intraday stop-loss check: {e}")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the scheduler service"""
        logger.info("Stopping trading scheduler service")
        self.running = False
        self.stop_health_server()
        
        # Send final summary
        try:
            from robotrading_improved import send_trading_summary_robust
            send_trading_summary_robust()
        except Exception as e:
            logger.error(f"Failed to send final summary: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            "running": self.running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "next_run": self._get_next_run_time(),
            "health_status": self.health_checker.get_overall_status()[0].value
        }
    
    def _get_next_run_time(self) -> Optional[str]:
        """Get next scheduled run time"""
        next_run = schedule.next_run()
        return next_run.isoformat() if next_run else None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down scheduler...")
    shutdown_flag.set()

def main():
    """Main entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start scheduler
    scheduler = TradingScheduler()
    
    try:
        scheduler.start()
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()