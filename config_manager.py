"""
Configuration management with schema validation
Supports multiple broker credentials and multi-recipient alerts
"""

import os
import json
import yaml
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class EmailConfig:
    """Email configuration"""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 465
    use_ssl: bool = True
    username: str = ""
    password: str = ""
    recipients: List[str] = field(default_factory=list)
    enabled: bool = True

@dataclass
class BrokerConfig:
    """Broker configuration"""
    name: str
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    paper_trading: bool = True
    enabled: bool = True

@dataclass
class APIConfig:
    """External API configuration"""
    alpha_vantage_key: str = ""
    slickcharts_timeout: int = 10
    yfinance_timeout: int = 10
    cache_duration: int = 300  # 5 minutes

@dataclass
class TradingConfig:
    """Trading configuration"""
    shares_per_trade: int = 10
    max_positions_per_asset: int = 5
    profit_taking_threshold: float = 2.0
    stop_loss_threshold: float = -5.0
    equity_allocation: float = 0.6
    bond_allocation: float = 0.3
    crypto_allocation: float = 0.1

@dataclass
class StopLossConfig:
    """Advanced stop-loss configuration"""
    enabled: bool = True
    trailing_percent: float = 5.0
    atr_multiplier: float = 2.0
    atr_period: int = 14
    regime_aware: bool = True
    high_vol_threshold: float = 0.5
    high_vol_tightening: float = 0.6
    intraday_check_interval: int = 15
    min_hold_time: int = 30

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "json"  # json or text
    file_path: str = "trading_bot.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    rotation: str = "size"  # size or time

@dataclass
class HealthCheckConfig:
    """Health check configuration"""
    enabled: bool = True
    port: int = 8080
    check_interval: int = 60  # seconds
    timeout: int = 30  # seconds

@dataclass
class Config:
    """Main configuration class"""
    email: EmailConfig = field(default_factory=EmailConfig)
    brokers: List[BrokerConfig] = field(default_factory=list)
    api: APIConfig = field(default_factory=APIConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    stop_loss: StopLossConfig = field(default_factory=StopLossConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    
    # Environment overrides
    environment: str = "development"
    debug: bool = False

class ConfigManager:
    """Configuration manager with validation and environment overrides"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self.config = Config()
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file and environment variables"""
        # Load .env file first
        load_dotenv()
        
        # Load from YAML/JSON file if it exists
        if os.path.exists(self.config_path):
            self._load_from_file()
        
        # Override with environment variables
        self._load_from_env()
        
        # Validate configuration
        self._validate_config()
    
    def _load_from_file(self):
        """Load configuration from YAML or JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            self._update_config_from_dict(data)
            logger.info(f"Configuration loaded from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_path}: {e}")
            raise
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Email configuration
        if os.getenv("GMAIL_ADDRESS"):
            self.config.email.username = os.getenv("GMAIL_ADDRESS")
        if os.getenv("GMAIL_APP_PASSWORD"):
            self.config.email.password = os.getenv("GMAIL_APP_PASSWORD")
        if os.getenv("RECIPIENT_EMAIL"):
            self.config.email.recipients = [os.getenv("RECIPIENT_EMAIL")]
        
        # API configuration
        if os.getenv("ALPHA_VANTAGE_KEY"):
            self.config.api.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY")
        
        # Broker configuration
        if os.getenv("IBKR_HOST") or os.getenv("IBKR_PORT") or os.getenv("IBKR_CLIENT_ID"):
            broker = BrokerConfig(
                name="IBKR",
                host=os.getenv("IBKR_HOST", "127.0.0.1"),
                port=int(os.getenv("IBKR_PORT", "7497")),
                client_id=int(os.getenv("IBKR_CLIENT_ID", "1")),
                paper_trading=os.getenv("USE_PAPER", "True").lower() == "true"
            )
            self.config.brokers = [broker]
        
        # Trading configuration
        if os.getenv("SHARES_PER_TRADE"):
            self.config.trading.shares_per_trade = int(os.getenv("SHARES_PER_TRADE"))
        
        # Environment
        self.config.environment = os.getenv("ENVIRONMENT", "development")
        self.config.debug = os.getenv("DEBUG", "false").lower() == "true"
    
    def _update_config_from_dict(self, data: Dict[str, Any]):
        """Update configuration from dictionary"""
        if "email" in data:
            email_data = data["email"]
            self.config.email = EmailConfig(
                smtp_server=email_data.get("smtp_server", self.config.email.smtp_server),
                smtp_port=email_data.get("smtp_port", self.config.email.smtp_port),
                use_ssl=email_data.get("use_ssl", self.config.email.use_ssl),
                username=email_data.get("username", self.config.email.username),
                password=email_data.get("password", self.config.email.password),
                recipients=email_data.get("recipients", self.config.email.recipients),
                enabled=email_data.get("enabled", self.config.email.enabled)
            )
        
        if "brokers" in data:
            self.config.brokers = []
            for broker_data in data["brokers"]:
                broker = BrokerConfig(
                    name=broker_data["name"],
                    host=broker_data.get("host", "127.0.0.1"),
                    port=broker_data.get("port", 7497),
                    client_id=broker_data.get("client_id", 1),
                    paper_trading=broker_data.get("paper_trading", True),
                    enabled=broker_data.get("enabled", True)
                )
                self.config.brokers.append(broker)
        
        if "api" in data:
            api_data = data["api"]
            self.config.api = APIConfig(
                alpha_vantage_key=api_data.get("alpha_vantage_key", ""),
                slickcharts_timeout=api_data.get("slickcharts_timeout", 10),
                yfinance_timeout=api_data.get("yfinance_timeout", 10),
                cache_duration=api_data.get("cache_duration", 300)
            )
        
        if "trading" in data:
            trading_data = data["trading"]
            self.config.trading = TradingConfig(
                shares_per_trade=trading_data.get("shares_per_trade", 10),
                max_positions_per_asset=trading_data.get("max_positions_per_asset", 5),
                profit_taking_threshold=trading_data.get("profit_taking_threshold", 2.0),
                stop_loss_threshold=trading_data.get("stop_loss_threshold", -5.0),
                equity_allocation=trading_data.get("equity_allocation", 0.6),
                bond_allocation=trading_data.get("bond_allocation", 0.3),
                crypto_allocation=trading_data.get("crypto_allocation", 0.1)
            )
        
        if "stop_loss" in data:
            stop_loss_data = data["stop_loss"]
            self.config.stop_loss = StopLossConfig(
                enabled=stop_loss_data.get("enabled", True),
                trailing_percent=stop_loss_data.get("trailing_percent", 5.0),
                atr_multiplier=stop_loss_data.get("atr_multiplier", 2.0),
                atr_period=stop_loss_data.get("atr_period", 14),
                regime_aware=stop_loss_data.get("regime_aware", True),
                high_vol_threshold=stop_loss_data.get("high_vol_threshold", 0.5),
                high_vol_tightening=stop_loss_data.get("high_vol_tightening", 0.6),
                intraday_check_interval=stop_loss_data.get("intraday_check_interval", 15),
                min_hold_time=stop_loss_data.get("min_hold_time", 30)
            )
        
        if "logging" in data:
            logging_data = data["logging"]
            self.config.logging = LoggingConfig(
                level=logging_data.get("level", "INFO"),
                format=logging_data.get("format", "json"),
                file_path=logging_data.get("file_path", "trading_bot.log"),
                max_file_size=logging_data.get("max_file_size", 10 * 1024 * 1024),
                backup_count=logging_data.get("backup_count", 5),
                rotation=logging_data.get("rotation", "size")
            )
    
    def _validate_config(self):
        """Validate configuration and provide clear error messages"""
        errors = []
        
        # Validate email configuration
        if self.config.email.enabled:
            if not self.config.email.username:
                errors.append("Email username is required when email is enabled")
            if not self.config.email.password:
                errors.append("Email password is required when email is enabled")
            if not self.config.email.recipients:
                errors.append("At least one email recipient is required when email is enabled")
        
        # Validate broker configuration
        if not self.config.brokers:
            errors.append("At least one broker configuration is required")
        
        enabled_brokers = [b for b in self.config.brokers if b.enabled]
        if not enabled_brokers:
            errors.append("At least one broker must be enabled")
        
        # Validate trading configuration
        total_allocation = (
            self.config.trading.equity_allocation + 
            self.config.trading.bond_allocation + 
            self.config.trading.crypto_allocation
        )
        if abs(total_allocation - 1.0) > 0.01:
            errors.append(f"Portfolio allocations must sum to 1.0, got {total_allocation}")
        
        if self.config.trading.shares_per_trade <= 0:
            errors.append("Shares per trade must be positive")
        
        # Validate API configuration
        if not self.config.api.alpha_vantage_key:
            logger.warning("Alpha Vantage API key not provided - cross-checking will be disabled")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def get_broker_config(self, name: str) -> Optional[BrokerConfig]:
        """Get broker configuration by name"""
        for broker in self.config.brokers:
            if broker.name.lower() == name.lower() and broker.enabled:
                return broker
        return None
    
    def get_active_brokers(self) -> List[BrokerConfig]:
        """Get list of active broker configurations"""
        return [broker for broker in self.config.brokers if broker.enabled]
    
    def save_config(self, path: Optional[str] = None):
        """Save current configuration to file"""
        save_path = path or self.config_path
        
        # Convert config to dictionary
        config_dict = {
            "email": {
                "smtp_server": self.config.email.smtp_server,
                "smtp_port": self.config.email.smtp_port,
                "use_ssl": self.config.email.use_ssl,
                "username": self.config.email.username,
                "password": "***REDACTED***" if self.config.email.password else "",
                "recipients": self.config.email.recipients,
                "enabled": self.config.email.enabled
            },
            "brokers": [
                {
                    "name": broker.name,
                    "host": broker.host,
                    "port": broker.port,
                    "client_id": broker.client_id,
                    "paper_trading": broker.paper_trading,
                    "enabled": broker.enabled
                }
                for broker in self.config.brokers
            ],
            "api": {
                "alpha_vantage_key": "***REDACTED***" if self.config.api.alpha_vantage_key else "",
                "slickcharts_timeout": self.config.api.slickcharts_timeout,
                "yfinance_timeout": self.config.api.yfinance_timeout,
                "cache_duration": self.config.api.cache_duration
            },
            "trading": {
                "shares_per_trade": self.config.trading.shares_per_trade,
                "max_positions_per_asset": self.config.trading.max_positions_per_asset,
                "profit_taking_threshold": self.config.trading.profit_taking_threshold,
                "stop_loss_threshold": self.config.trading.stop_loss_threshold,
                "equity_allocation": self.config.trading.equity_allocation,
                "bond_allocation": self.config.trading.bond_allocation,
                "crypto_allocation": self.config.trading.crypto_allocation
            },
            "logging": {
                "level": self.config.logging.level,
                "format": self.config.logging.format,
                "file_path": self.config.logging.file_path,
                "max_file_size": self.config.logging.max_file_size,
                "backup_count": self.config.logging.backup_count,
                "rotation": self.config.logging.rotation
            },
            "environment": self.config.environment,
            "debug": self.config.debug
        }
        
        try:
            with open(save_path, 'w') as f:
                if save_path.endswith('.yaml') or save_path.endswith('.yml'):
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                else:
                    json.dump(config_dict, f, indent=2)
            
            logger.info(f"Configuration saved to {save_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration to {save_path}: {e}")
            raise

# Global config manager instance
config_manager = ConfigManager()

# Convenience functions
def get_config() -> Config:
    """Get the current configuration"""
    return config_manager.config

def get_broker_config(name: str) -> Optional[BrokerConfig]:
    """Get broker configuration by name"""
    return config_manager.get_broker_config(name)

def get_email_config() -> EmailConfig:
    """Get email configuration"""
    return config_manager.config.email

def get_trading_config() -> TradingConfig:
    """Get trading configuration"""
    return config_manager.config.trading