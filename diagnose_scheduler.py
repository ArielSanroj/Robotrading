#!/usr/bin/env python3
"""
Diagnostic tool to check why scheduler didn't run yesterday
"""

import json
from datetime import datetime, timedelta
import subprocess
import sys

def check_scheduler_status():
    """Check current scheduler status"""
    print("=" * 70)
    print("SCHEDULER DIAGNOSTIC REPORT")
    print("=" * 70)
    
    # Check if scheduler is running
    print("\n1. SCHEDULER PROCESS STATUS:")
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        scheduler_running = "scheduler_service.py" in result.stdout
        if scheduler_running:
            print("   ✅ Scheduler process is RUNNING")
            for line in result.stdout.split('\n'):
                if 'scheduler_service.py' in line and 'grep' not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        start_time = ' '.join(parts[8:10]) if len(parts) > 9 else 'Unknown'
                        print(f"      PID: {pid}, Started: {start_time}")
        else:
            print("   ❌ Scheduler process is NOT running")
    except Exception as e:
        print(f"   ⚠️  Error checking process: {e}")
    
    # Check logs from yesterday
    print("\n2. YESTERDAY'S LOGS (Nov 12, 2025):")
    try:
        with open("logs/trading_bot.log", "r") as f:
            lines = f.readlines()
            yesterday_logs = []
            for line in lines:
                try:
                    log_entry = json.loads(line)
                    timestamp = log_entry.get("timestamp", "")
                    if "2025-11-12" in timestamp:
                        message = log_entry.get("message", "")
                        if any(keyword in message.lower() for keyword in 
                               ["session", "scheduler", "starting", "market", "trading"]):
                            yesterday_logs.append((timestamp, message))
                except:
                    pass
            
            if yesterday_logs:
                print(f"   Found {len(yesterday_logs)} relevant log entries:")
                for ts, msg in yesterday_logs[:10]:  # Show first 10
                    print(f"      {ts}: {msg[:80]}")
            else:
                print("   ⚠️  No trading session logs found for Nov 12")
                print("   This suggests the scheduler did not trigger any sessions")
    except Exception as e:
        print(f"   ⚠️  Error reading logs: {e}")
    
    # Check market hours logic
    print("\n3. MARKET HOURS CHECK:")
    yesterday_1030 = datetime(2025, 11, 12, 10, 30)
    is_weekday = yesterday_1030.weekday() < 5
    market_open_time = yesterday_1030.replace(hour=9, minute=30)
    market_close_time = yesterday_1030.replace(hour=16, minute=0)
    in_market_hours = market_open_time <= yesterday_1030 <= market_close_time
    
    print(f"   Nov 12, 2025 at 10:30 AM:")
    print(f"      Is weekday: {is_weekday} ✅" if is_weekday else f"      Is weekday: {is_weekday} ❌")
    print(f"      In market hours (9:30-16:00): {in_market_hours} ✅" if in_market_hours else f"      In market hours (9:30-16:00): {in_market_hours} ❌")
    
    # Recommendations
    print("\n4. RECOMMENDATIONS:")
    if not scheduler_running:
        print("   ❌ Start the scheduler: python3 scheduler_service.py")
    else:
        print("   ✅ Scheduler is running")
        print("   ⚠️  If it didn't run yesterday, possible causes:")
        print("      1. Scheduler was restarted after 10:30 AM")
        print("      2. Unhandled exception in scheduler loop")
        print("      3. Timezone mismatch")
        print("      4. Schedule library issue")
    
    print("\n5. NEXT STEPS:")
    print("   - Check scheduler logs for errors")
    print("   - Verify scheduler is running continuously")
    print("   - Monitor today's scheduled runs (10:30 AM and 3:30 PM)")
    print("   - Check: tail -f logs/trading_bot.log | grep -E '(SCHEDULER|session|Starting)'")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_scheduler_status()
