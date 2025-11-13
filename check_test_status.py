#!/usr/bin/env python3
"""
Quick status check for the test scheduled run
"""

import subprocess
import json
from datetime import datetime, timedelta
import sys

def check_status():
    """Check the status of the test scheduled run"""
    
    # Check if process is running
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        if "test_scheduled_run.py" in result.stdout:
            print("✅ Test scheduler is RUNNING")
            
            # Extract PID
            for line in result.stdout.split('\n'):
                if 'test_scheduled_run.py' in line and 'grep' not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        print(f"   Process ID: {pid}")
        else:
            print("❌ Test scheduler is NOT running")
            return
    except Exception as e:
        print(f"Error checking process: {e}")
        return
    
    # Calculate expected run time
    now = datetime.now()
    # The script started around 09:41:42, so run should be at 10:31:42
    # But let's calculate from when it actually started
    expected_run = now + timedelta(minutes=50)
    
    # Try to read the log to get actual scheduled time
    try:
        with open("logs/trading_bot.log", "r") as f:
            lines = f.readlines()
            for line in reversed(lines[-100:]):  # Check last 100 lines
                if "Scheduling test trading run at:" in line:
                    # Extract time from log
                    try:
                        log_data = json.loads(line)
                        msg = log_data.get("message", "")
                        if "Scheduling test trading run at:" in msg:
                            # Extract time from message
                            time_str = msg.split("at:")[1].split("(")[0].strip()
                            print(f"   Scheduled run time: {time_str}")
                            break
                    except:
                        pass
    except Exception as e:
        print(f"   Could not read log file: {e}")
        print(f"   Expected run time (approx): {expected_run.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Calculate time remaining
    # Assuming it started at 09:41:42, run should be at 10:31:42
    start_time = datetime.now().replace(hour=9, minute=41, second=42, microsecond=0)
    if datetime.now() < start_time:
        # If current time is before start, adjust
        start_time = start_time - timedelta(days=1)
    
    run_time = start_time + timedelta(minutes=50)
    remaining = (run_time - datetime.now()).total_seconds() / 60
    
    if remaining > 0:
        print(f"   ⏰ Time remaining: {remaining:.1f} minutes")
        print(f"   📅 Run will execute at: {run_time.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"   ⚠️  Scheduled time has passed. Run should have executed.")
    
    print("\n📊 To monitor logs in real-time:")
    print("   tail -f logs/trading_bot.log | grep -E '(TEST|trading session|Starting|completed)'")

if __name__ == "__main__":
    check_status()
