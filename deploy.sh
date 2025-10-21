#!/bin/bash

# Trading Bot Deployment Script
# Supports systemd service, Docker, and manual deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="trading-bot"
USER="trading"
GROUP="trading"
INSTALL_DIR="/opt/trading-bot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
}

create_user() {
    if ! id "$USER" &>/dev/null; then
        log "Creating user $USER"
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$USER"
    else
        log "User $USER already exists"
    fi
}

install_dependencies() {
    log "Installing system dependencies"
    
    # Update package list
    apt-get update
    
    # Install Python and system dependencies
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        gcc \
        g++ \
        curl \
        wget \
        git
    
    # Install Python packages
    log "Installing Python dependencies"
    pip3 install -r "$SCRIPT_DIR/requirements.txt"
}

deploy_files() {
    log "Deploying application files"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy application files
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    
    # Create necessary directories
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/cache"
    
    # Set permissions
    chown -R "$USER:$GROUP" "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/scheduler_service.py"
}

install_systemd_service() {
    log "Installing systemd service"
    
    # Copy service file
    cp "$SCRIPT_DIR/trading-bot.service" /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable "$SERVICE_NAME"
    
    log "Systemd service installed and enabled"
}

setup_environment() {
    log "Setting up environment"
    
    # Create .env file if it doesn't exist
    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        cat > "$INSTALL_DIR/.env" << EOF
# Trading Bot Environment Variables
# Copy this file and fill in your actual values

# Email Configuration
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@example.com

# API Keys
ALPHA_VANTAGE_KEY=your-alpha-vantage-key

# IBKR Configuration
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
USE_PAPER=True

# Trading Configuration
SHARES_PER_TRADE=10

# Environment
ENVIRONMENT=production
DEBUG=false
EOF
        chown "$USER:$GROUP" "$INSTALL_DIR/.env"
        chmod 600 "$INSTALL_DIR/.env"
        warn "Please edit $INSTALL_DIR/.env with your actual configuration values"
    fi
}

start_service() {
    log "Starting $SERVICE_NAME service"
    
    systemctl start "$SERVICE_NAME"
    
    # Wait a moment and check status
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "Service started successfully"
    else
        error "Failed to start service"
    fi
}

stop_service() {
    log "Stopping $SERVICE_NAME service"
    
    systemctl stop "$SERVICE_NAME" || true
}

status_service() {
    log "Service status:"
    systemctl status "$SERVICE_NAME" --no-pager
}

show_logs() {
    log "Recent service logs:"
    journalctl -u "$SERVICE_NAME" --no-pager -n 50
}

health_check() {
    log "Running health check"
    
    # Wait for service to start
    sleep 5
    
    # Check if health endpoint is responding
    if curl -s http://localhost:8080/health > /dev/null; then
        log "Health check passed"
        curl -s http://localhost:8080/health | jq .
    else
        warn "Health check failed - service may not be ready yet"
    fi
}

docker_deploy() {
    log "Deploying with Docker"
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Build and start with docker-compose
    cd "$SCRIPT_DIR"
    docker-compose up -d --build
    
    log "Docker deployment completed"
    log "Health check available at: http://localhost:8080/health"
}

show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install     Install the trading bot service"
    echo "  start       Start the service"
    echo "  stop        Stop the service"
    echo "  restart     Restart the service"
    echo "  status      Show service status"
    echo "  logs        Show service logs"
    echo "  health      Run health check"
    echo "  docker      Deploy with Docker"
    echo "  uninstall   Remove the service"
    echo ""
}

uninstall() {
    log "Uninstalling $SERVICE_NAME"
    
    # Stop and disable service
    systemctl stop "$SERVICE_NAME" || true
    systemctl disable "$SERVICE_NAME" || true
    
    # Remove service file
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    
    # Remove application files
    rm -rf "$INSTALL_DIR"
    
    # Remove user (optional)
    read -p "Remove user $USER? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        userdel "$USER" || true
    fi
    
    log "Uninstallation completed"
}

# Main script logic
case "${1:-}" in
    install)
        check_root
        create_user
        install_dependencies
        deploy_files
        install_systemd_service
        setup_environment
        log "Installation completed successfully"
        warn "Please edit $INSTALL_DIR/.env with your configuration before starting the service"
        ;;
    start)
        check_root
        start_service
        health_check
        ;;
    stop)
        check_root
        stop_service
        ;;
    restart)
        check_root
        stop_service
        start_service
        health_check
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs
        ;;
    health)
        health_check
        ;;
    docker)
        docker_deploy
        ;;
    uninstall)
        check_root
        uninstall
        ;;
    *)
        show_usage
        exit 1
        ;;
esac