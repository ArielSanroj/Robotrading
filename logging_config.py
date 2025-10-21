"""
Structured logging configuration with JSON format and rotation
Supports Prometheus-friendly metrics
"""

import json
import logging
import logging.handlers
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import threading
from collections import defaultdict, Counter

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def __init__(self, include_extra_fields: bool = True):
        super().__init__()
        self.include_extra_fields = include_extra_fields
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if self.include_extra_fields:
            for key, value in record.__dict__.items():
                if key not in log_entry and not key.startswith('_'):
                    log_entry[key] = value
        
        return json.dumps(log_entry, default=str)

class MetricsCollector:
    """Collects Prometheus-friendly metrics from log events"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = defaultdict(int)
        self._gauges = {}
        self._histograms = defaultdict(list)
        self._start_time = time.time()
    
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1):
        """Increment a counter metric"""
        with self._lock:
            key = f"{name}{self._format_labels(labels)}"
            self._counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value"""
        with self._lock:
            key = f"{name}{self._format_labels(labels)}"
            self._gauges[key] = value
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a histogram metric value"""
        with self._lock:
            key = f"{name}{self._format_labels(labels)}"
            self._histograms[key].append(value)
    
    def _format_labels(self, labels: Optional[Dict[str, str]]) -> str:
        """Format labels for metric key"""
        if not labels:
            return ""
        return "{" + ",".join(f"{k}={v}" for k, v in sorted(labels.items())) + "}"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics in Prometheus format"""
        with self._lock:
            metrics = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values) if values else 0,
                        "max": max(values) if values else 0,
                        "avg": sum(values) / len(values) if values else 0
                    }
                    for name, values in self._histograms.items()
                },
                "uptime_seconds": time.time() - self._start_time
            }
            return metrics
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._start_time = time.time()

# Global metrics collector
metrics_collector = MetricsCollector()

class TradingLogger:
    """Enhanced logger for trading operations with structured logging"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.metrics = metrics_collector
    
    def log_trade_signal(self, symbol: str, action: str, asset_class: str, confidence: float = 0.0, **kwargs):
        """Log a trade signal with structured data"""
        self.logger.info(
            f"Trade signal generated",
            extra={
                "event_type": "trade_signal",
                "symbol": symbol,
                "action": action,
                "asset_class": asset_class,
                "confidence": confidence,
                **kwargs
            }
        )
        self.metrics.increment_counter("trade_signals_total", {
            "action": action,
            "asset_class": asset_class
        })
    
    def log_trade_execution(self, symbol: str, action: str, quantity: int, price: float, 
                          order_id: str = None, **kwargs):
        """Log a trade execution with structured data"""
        self.logger.info(
            f"Trade executed",
            extra={
                "event_type": "trade_execution",
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "price": price,
                "order_id": order_id,
                "value": quantity * price,
                **kwargs
            }
        )
        self.metrics.increment_counter("trades_executed_total", {
            "action": action,
            "symbol": symbol
        })
        self.metrics.observe_histogram("trade_value", quantity * price, {
            "action": action,
            "symbol": symbol
        })
    
    def log_api_call(self, service: str, endpoint: str, status_code: int, 
                    duration: float, **kwargs):
        """Log an API call with structured data"""
        level = logging.INFO if 200 <= status_code < 400 else logging.WARNING
        self.logger.log(
            level,
            f"API call to {service}",
            extra={
                "event_type": "api_call",
                "service": service,
                "endpoint": endpoint,
                "status_code": status_code,
                "duration_seconds": duration,
                **kwargs
            }
        )
        self.metrics.increment_counter("api_calls_total", {
            "service": service,
            "status_code": str(status_code)
        })
        self.metrics.observe_histogram("api_call_duration_seconds", duration, {
            "service": service
        })
    
    def log_portfolio_update(self, total_value: float, equity_value: float, 
                           bond_value: float, crypto_value: float, **kwargs):
        """Log portfolio update with structured data"""
        self.logger.info(
            f"Portfolio updated",
            extra={
                "event_type": "portfolio_update",
                "total_value": total_value,
                "equity_value": equity_value,
                "bond_value": bond_value,
                "crypto_value": crypto_value,
                "equity_pct": (equity_value / total_value * 100) if total_value > 0 else 0,
                "bond_pct": (bond_value / total_value * 100) if total_value > 0 else 0,
                "crypto_pct": (crypto_value / total_value * 100) if total_value > 0 else 0,
                **kwargs
            }
        )
        self.metrics.set_gauge("portfolio_total_value", total_value)
        self.metrics.set_gauge("portfolio_equity_value", equity_value)
        self.metrics.set_gauge("portfolio_bond_value", bond_value)
        self.metrics.set_gauge("portfolio_crypto_value", crypto_value)
    
    def log_error(self, error_type: str, message: str, **kwargs):
        """Log an error with structured data"""
        self.logger.error(
            message,
            extra={
                "event_type": "error",
                "error_type": error_type,
                **kwargs
            }
        )
        self.metrics.increment_counter("errors_total", {
            "error_type": error_type
        })
    
    def log_session_start(self, session_type: str, **kwargs):
        """Log session start with structured data"""
        self.logger.info(
            f"Trading session started",
            extra={
                "event_type": "session_start",
                "session_type": session_type,
                **kwargs
            }
        )
        self.metrics.increment_counter("sessions_started_total", {
            "session_type": session_type
        })
    
    def log_session_end(self, session_type: str, total_trades: int, 
                       profit_loss: float, **kwargs):
        """Log session end with structured data"""
        self.logger.info(
            f"Trading session ended",
            extra={
                "event_type": "session_end",
                "session_type": session_type,
                "total_trades": total_trades,
                "profit_loss": profit_loss,
                **kwargs
            }
        )
        self.metrics.increment_counter("sessions_completed_total", {
            "session_type": session_type
        })
        self.metrics.observe_histogram("session_profit_loss", profit_loss, {
            "session_type": session_type
        })

def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: str = "trading_bot.log",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up structured logging with rotation
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format (json or text)
        log_file: Log file path
        max_file_size: Maximum log file size in bytes
        backup_count: Number of backup files to keep
        console_output: Whether to output to console
    
    Returns:
        Configured logger
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Set up formatter
    if format_type.lower() == "json":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Set up file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_file_size,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Set up console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Set up specific loggers
    trading_logger = TradingLogger("trading")
    
    # Log startup
    trading_logger.logger.info("Logging system initialized", extra={
        "event_type": "system_startup",
        "log_level": level,
        "format_type": format_type,
        "log_file": log_file
    })
    
    return trading_logger.logger

def get_metrics() -> Dict[str, Any]:
    """Get current metrics in Prometheus format"""
    return metrics_collector.get_metrics()

def reset_metrics():
    """Reset all metrics"""
    metrics_collector.reset()

# Convenience function to get a trading logger
def get_trading_logger(name: str) -> TradingLogger:
    """Get a trading logger instance"""
    return TradingLogger(name)