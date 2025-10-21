#!/bin/bash

# Robotrading Continuous Runner Script
# This script runs the trading bot continuously in the background

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/robotrading.log"
PID_FILE="$SCRIPT_DIR/robotrading.pid"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

start_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Trading bot is already running (PID: $PID)"
            return 0
        else
            warn "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi
    
    log "Starting trading bot..."
    cd "$SCRIPT_DIR"
    
    # Start the bot in background
    nohup python3 scheduler_service.py > "$LOG_FILE" 2>&1 &
    PID=$!
    
    # Save PID
    echo $PID > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 3
    if ps -p $PID > /dev/null 2>&1; then
        log "Trading bot started successfully (PID: $PID)"
        log "Logs: $LOG_FILE"
        log "Health check: http://localhost:8080/health"
        return 0
    else
        error "Failed to start trading bot"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Stopping trading bot (PID: $PID)..."
            kill $PID
            sleep 2
            if ps -p $PID > /dev/null 2>&1; then
                warn "Bot didn't stop gracefully, forcing kill..."
                kill -9 $PID
            fi
            rm -f "$PID_FILE"
            log "Trading bot stopped"
        else
            warn "Trading bot is not running"
            rm -f "$PID_FILE"
        fi
    else
        warn "No PID file found, bot may not be running"
    fi
}

status_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Trading bot is running (PID: $PID)"
            log "Logs: $LOG_FILE"
            log "Health check: http://localhost:8080/health"
            return 0
        else
            error "Trading bot is not running (stale PID file)"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        error "Trading bot is not running"
        return 1
    fi
}

show_logs() {
    if [ -f "$LOG_FILE" ]; then
        log "Recent logs (last 20 lines):"
        tail -20 "$LOG_FILE"
    else
        error "Log file not found: $LOG_FILE"
    fi
}

restart_bot() {
    log "Restarting trading bot..."
    stop_bot
    sleep 2
    start_bot
}

case "${1:-}" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the trading bot"
        echo "  stop    - Stop the trading bot"
        echo "  restart - Restart the trading bot"
        echo "  status  - Check if the bot is running"
        echo "  logs    - Show recent logs"
        exit 1
        ;;
esac