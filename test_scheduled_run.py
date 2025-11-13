#!/usr/bin/env python3
"""
Test script to schedule a trading run in 50 minutes
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timedelta
import schedule

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robotrading_improved import run_bot_robust, initialize_ibkr, shutdown_flag
from config_manager import get_config
from logging_config import setup_logging, get_trading_logger
from health_check import HealthCheckServer, HealthChecker

logger = setup_logging(level="INFO", format_type="json")
trading_logger = get_trading_logger("test_scheduler")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down test scheduler...")
    shutdown_flag.set()

def main():
    """Main entry point for test scheduled run"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Calculate time 50 minutes from now
    now = datetime.now()
    target_time = now + timedelta(minutes=50)
    target_time_str = target_time.strftime("%H:%M")
    
    logger.info(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Scheduling test trading run at: {target_time.strftime('%Y-%m-%d %H:%M:%S')} (in 50 minutes)")
    
    # Schedule the test run
    schedule.every().day.at(target_time_str).do(run_test_session)
    
    # Also schedule a one-time run using schedule's every() with a delay
    # We'll use a more precise approach
    def schedule_test_run():
        """Schedule the test run at the exact time"""
        run_test_session()
    
    # Calculate seconds until target time
    seconds_until_run = (target_time - datetime.now()).total_seconds()
    logger.info(f"Test run will execute in {seconds_until_run:.0f} seconds ({seconds_until_run/60:.1f} minutes)")
    
    # Initialize IBKR connection
    logger.info("Initializing IBKR connection...")
    if not initialize_ibkr():
        logger.error("Failed to initialize IBKR, but continuing with test")
    
    # Start health check server if enabled
    config = get_config()
    health_checker = HealthChecker()
    health_server = None
    if config.health_check.enabled:
        try:
            health_server = HealthCheckServer(health_checker, config.health_check.port)
            health_server.start()
            logger.info(f"Health check server started on port {config.health_check.port}")
        except OSError as e:
            if "Address already in use" in str(e):
                logger.warning(f"Health check port {config.health_check.port} already in use, skipping health server")
            else:
                raise
    
    # Main loop - check every minute for scheduled runs
    logger.info("Waiting for scheduled test run...")
    logger.info("Press Ctrl+C to cancel")
    
    try:
        while not shutdown_flag.is_set():
            # Check if it's time to run
            current_time = datetime.now()
            if current_time >= target_time:
                logger.info("=" * 60)
                logger.info("TEST RUN TIME REACHED - Starting trading session")
                logger.info("=" * 60)
                run_test_session()
                logger.info("Test run completed. Exiting...")
                break
            
            # Calculate remaining time
            remaining = (target_time - current_time).total_seconds()
            if remaining > 0:
                minutes_remaining = remaining / 60
                if minutes_remaining <= 1 or int(minutes_remaining) % 10 == 0:
                    logger.info(f"Waiting... {minutes_remaining:.1f} minutes remaining until test run")
            
            # Run any pending scheduled jobs
            schedule.run_pending()
            
            # Sleep for 1 second
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in test scheduler: {e}")
    finally:
        if health_server:
            health_server.stop()
        logger.info("Test scheduler stopped")

def run_test_session():
    """Run a test trading session"""
    logger.info("=" * 60)
    logger.info("STARTING TEST TRADING SESSION")
    logger.info("=" * 60)
    
    try:
        # Run health check
        config = get_config()
        health_checker = HealthChecker()
        health_results = health_checker.run_all_checks({
            "alpha_vantage_key": config.api.alpha_vantage_key,
            "email": {
                "enabled": config.email.enabled,
                "smtp_server": config.email.smtp_server,
                "smtp_port": config.email.smtp_port,
                "username": config.email.username,
                "password": config.email.password
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
        })
        
        logger.info(f"Health check results: {health_results}")
        
        # Ensure IBKR connection
        if not initialize_ibkr():
            logger.error("IBKR connection failed, but attempting to run bot anyway")
        
        # Run the trading bot
        logger.info("Executing trading bot...")
        results = run_bot_robust()
        
        logger.info("=" * 60)
        logger.info("TEST TRADING SESSION COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Results: {results}")
        
        return results
        
    except Exception as e:
        logger.error(f"Test session failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
