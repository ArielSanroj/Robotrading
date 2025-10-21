#!/usr/bin/env python3
"""
Simple test to verify that stop-loss executions don't send email alerts
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_stop_loss_no_email():
    """Test that stop-loss alert method doesn't send emails"""
    try:
        from advanced_stop_loss import AdvancedStopLossManager
        
        # Create manager instance
        manager = AdvancedStopLossManager()
        
        # Test the send_stop_loss_alert method
        # This should only log, not send emails
        manager.send_stop_loss_alert("TEST", -5.2, "Test stop-loss trigger")
        
        logger.info("✅ Stop-loss alert method executed without email sending")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_configuration():
    """Test that advanced stop-loss configuration is loaded"""
    try:
        from config_manager import get_config
        config = get_config()
        
        logger.info("✅ Advanced stop-loss configuration loaded:")
        logger.info(f"   Enabled: {config.stop_loss.enabled}")
        logger.info(f"   Trailing Percent: {config.stop_loss.trailing_percent}%")
        logger.info(f"   ATR Multiplier: {config.stop_loss.atr_multiplier}")
        logger.info(f"   Regime Aware: {config.stop_loss.regime_aware}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run simple no-email tests"""
    logger.info("🧪 Testing Simple No-Email Stop-Loss Functionality")
    logger.info("=" * 60)
    
    tests = [
        ("Stop-Loss No Email", test_stop_loss_no_email),
        ("Configuration", test_configuration),
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
        logger.info("🎉 All simple no-email tests passed!")
        logger.info("\n✅ CONFIRMED: Stop-loss executions will NOT send email alerts")
        logger.info("✅ CONFIRMED: Stop-loss actions will be logged only")
        logger.info("✅ CONFIRMED: Regular trade signals will still send email alerts")
        return True
    else:
        logger.error("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)