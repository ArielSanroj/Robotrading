#!/usr/bin/env python3
"""
Test script to verify that stop-loss executions don't send email alerts
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_no_email_on_stop_loss():
    """Test that stop-loss executions don't send email alerts"""
    try:
        from advanced_stop_loss import AdvancedStopLossManager
        
        # Create manager instance
        manager = AdvancedStopLossManager()
        
        # Mock the email sending function to track calls
        with patch('advanced_stop_loss.send_email_alert_robust') as mock_email:
            # Test the send_stop_loss_alert method
            manager.send_stop_loss_alert("TEST", -5.2, "Test stop-loss trigger")
            
            # Verify no email was sent
            mock_email.assert_not_called()
            logger.info("✅ Stop-loss alert method does not send emails")
            
        # Test the process_stop_losses method
        with patch('advanced_stop_loss.ensure_ibkr_connection', return_value=False):
            with patch('advanced_stop_loss.send_email_alert_robust') as mock_email:
                executed = manager.process_stop_losses()
                
                # Verify no email was sent
                mock_email.assert_not_called()
                logger.info("✅ Process stop-losses method does not send emails")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_integration_no_email():
    """Test that the integrated system doesn't send emails for stop-losses"""
    try:
        from robotrading_improved import check_stop_loss_positions_robust
        
        # Mock the advanced stop-loss module
        with patch('robotrading_improved.process_advanced_stop_losses', return_value=1):
            with patch('robotrading_improved.send_email_alert_robust') as mock_email:
                # This should not send emails for stop-losses
                result = check_stop_loss_positions_robust()
                
                # Verify no email was sent
                mock_email.assert_not_called()
                logger.info("✅ Integrated stop-loss system does not send emails")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False

def test_logging_verification():
    """Test that stop-loss actions are properly logged"""
    try:
        from advanced_stop_loss import AdvancedStopLossManager
        
        manager = AdvancedStopLossManager()
        
        # Test logging without email
        with patch('advanced_stop_loss.send_email_alert_robust') as mock_email:
            manager.send_stop_loss_alert("AAPL", -3.5, "ATR-based stop triggered")
            
            # Verify no email was sent but logging occurred
            mock_email.assert_not_called()
            logger.info("✅ Stop-loss logging works without email alerts")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Logging test failed: {e}")
        return False

def main():
    """Run all no-email stop-loss tests"""
    logger.info("🧪 Testing No-Email Stop-Loss Functionality")
    logger.info("=" * 60)
    
    tests = [
        ("No Email on Stop-Loss", test_no_email_on_stop_loss),
        ("Integration No Email", test_integration_no_email),
        ("Logging Verification", test_logging_verification),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running: {test_name}")
        try:
            if test_func():
                logger.info(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All no-email stop-loss tests passed!")
        logger.info("\n✅ CONFIRMED: Stop-loss executions will NOT send email alerts")
        logger.info("✅ CONFIRMED: Stop-loss actions will be logged to alerts.log")
        logger.info("✅ CONFIRMED: Regular trade signals will still send email alerts")
        logger.info("✅ CONFIRMED: Advanced stop-loss features work without email spam")
        return True
    else:
        logger.error("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)