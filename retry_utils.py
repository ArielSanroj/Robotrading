"""
Retry and backoff utilities for external API calls
Provides exponential backoff with jitter and circuit breaker patterns
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    """Retry strategies for different types of failures"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.strategy = strategy
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit state"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.config.circuit_breaker_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def on_success(self):
        """Handle successful execution"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.circuit_breaker_threshold:
            self.state = CircuitState.OPEN

def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt"""
    if config.strategy == RetryStrategy.FIXED:
        delay = config.base_delay
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay * attempt
    else:  # EXPONENTIAL
        delay = config.base_delay * (config.backoff_multiplier ** attempt)
    
    # Apply jitter to prevent thundering herd
    if config.jitter:
        jitter_factor = random.uniform(0.5, 1.5)
        delay *= jitter_factor
    
    return min(delay, config.max_delay)

def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    exceptions: Tuple[Exception, ...] = (Exception,),
    circuit_breaker: bool = True
):
    """
    Decorator for retrying function calls with exponential backoff and circuit breaker
    
    Args:
        config: Retry configuration
        exceptions: Tuple of exceptions to retry on
        circuit_breaker: Whether to use circuit breaker pattern
    """
    if config is None:
        config = RetryConfig()
    
    circuit_breakers = {} if circuit_breaker else None
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get circuit breaker for this function
            breaker = None
            if circuit_breakers is not None:
                func_key = f"{func.__module__}.{func.__name__}"
                if func_key not in circuit_breakers:
                    circuit_breakers[func_key] = CircuitBreaker(config)
                breaker = circuit_breakers[func_key]
            
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                # Check circuit breaker
                if breaker and not breaker.can_execute():
                    logger.warning(f"Circuit breaker OPEN for {func.__name__}, skipping retry")
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
                
                try:
                    result = func(*args, **kwargs)
                    if breaker:
                        breaker.on_success()
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if breaker:
                        breaker.on_failure()
                    
                    if attempt == config.max_retries:
                        logger.error(f"Max retries ({config.max_retries}) exceeded for {func.__name__}: {e}")
                        break
                    
                    delay = calculate_delay(attempt + 1, config)
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
                    time.sleep(delay)
            
            # Re-raise the last exception if all retries failed
            raise last_exception
        
        return wrapper
    return decorator

# Pre-configured retry decorators for different use cases
def retry_api_call(max_retries: int = 3, base_delay: float = 1.0):
    """Retry decorator for API calls"""
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=30.0,
        backoff_multiplier=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL
    )
    return retry_with_backoff(
        config=config,
        exceptions=(ConnectionError, TimeoutError, requests.exceptions.RequestException),
        circuit_breaker=True
    )

def retry_ibkr_call(max_retries: int = 5, base_delay: float = 2.0):
    """Retry decorator for IBKR calls"""
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=60.0,
        backoff_multiplier=1.5,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL
    )
    return retry_with_backoff(
        config=config,
        exceptions=(Exception,),  # IBKR can raise various exceptions
        circuit_breaker=True
    )

def retry_smtp_call(max_retries: int = 2, base_delay: float = 5.0):
    """Retry decorator for SMTP calls"""
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=30.0,
        backoff_multiplier=2.0,
        jitter=False,  # No jitter for SMTP to avoid overwhelming server
        strategy=RetryStrategy.EXPONENTIAL
    )
    return retry_with_backoff(
        config=config,
        exceptions=(smtplib.SMTPException, ConnectionError, TimeoutError),
        circuit_breaker=False  # Don't use circuit breaker for email
    )

# Import requests and smtplib for exception handling
import requests
import smtplib