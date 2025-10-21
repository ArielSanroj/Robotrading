"""
Health check system for API connectivity and credentials verification
Provides HTTP endpoints and CLI checks
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import requests
import smtplib
from datetime import datetime, timedelta
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import yfinance as yf
from ib_insync import IB

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Result of a health check"""
    service: str
    status: HealthStatus
    message: str
    response_time: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

class HealthChecker:
    """Health checker for various services"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.results: Dict[str, HealthCheckResult] = {}
        self._lock = threading.Lock()
    
    def check_slickcharts(self) -> HealthCheckResult:
        """Check Slickcharts connectivity"""
        start_time = time.time()
        service = "slickcharts"
        
        try:
            url = "https://www.slickcharts.com/sp500/performance"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="Slickcharts is accessible",
                    response_time=response_time,
                    timestamp=datetime.now(),
                    details={"status_code": response.status_code, "content_length": len(response.content)}
                )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Slickcharts returned status {response.status_code}",
                    response_time=response_time,
                    timestamp=datetime.now(),
                    details={"status_code": response.status_code}
                )
                
        except requests.exceptions.Timeout:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message="Slickcharts request timed out",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"Slickcharts check failed: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
    
    def check_yfinance(self) -> HealthCheckResult:
        """Check Yahoo Finance connectivity"""
        start_time = time.time()
        service = "yfinance"
        
        try:
            # Test with a common symbol
            ticker = yf.Ticker("AAPL")
            data = ticker.history(period="1d")
            response_time = time.time() - start_time
            
            if not data.empty:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="Yahoo Finance is accessible",
                    response_time=response_time,
                    timestamp=datetime.now(),
                    details={"test_symbol": "AAPL", "data_points": len(data)}
                )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.DEGRADED,
                    message="Yahoo Finance returned empty data",
                    response_time=response_time,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"Yahoo Finance check failed: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
    
    def check_alpha_vantage(self, api_key: str) -> HealthCheckResult:
        """Check Alpha Vantage API connectivity"""
        start_time = time.time()
        service = "alpha_vantage"
        
        if not api_key:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNKNOWN,
                message="Alpha Vantage API key not provided",
                response_time=0,
                timestamp=datetime.now()
            )
        
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={api_key}"
            response = requests.get(url, timeout=self.timeout)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                if "Global Quote" in data:
                    return HealthCheckResult(
                        service=service,
                        status=HealthStatus.HEALTHY,
                        message="Alpha Vantage API is accessible",
                        response_time=response_time,
                        timestamp=datetime.now(),
                        details={"status_code": response.status_code, "has_data": True}
                    )
                else:
                    return HealthCheckResult(
                        service=service,
                        status=HealthStatus.DEGRADED,
                        message="Alpha Vantage API returned no data",
                        response_time=response_time,
                        timestamp=datetime.now(),
                        details={"status_code": response.status_code, "response": data}
                    )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Alpha Vantage returned status {response.status_code}",
                    response_time=response_time,
                    timestamp=datetime.now(),
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"Alpha Vantage check failed: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
    
    def check_smtp(self, smtp_server: str, smtp_port: int, username: str, password: str) -> HealthCheckResult:
        """Check SMTP connectivity"""
        start_time = time.time()
        service = "smtp"
        
        if not all([smtp_server, username, password]):
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNKNOWN,
                message="SMTP credentials not provided",
                response_time=0,
                timestamp=datetime.now()
            )
        
        try:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=self.timeout) as smtp:
                smtp.login(username, password)
                response_time = time.time() - start_time
                
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="SMTP server is accessible",
                    response_time=response_time,
                    timestamp=datetime.now(),
                    details={"server": smtp_server, "port": smtp_port}
                )
                
        except smtplib.SMTPAuthenticationError:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message="SMTP authentication failed",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"SMTP check failed: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
    
    def check_ibkr(self, host: str, port: int, client_id: int) -> HealthCheckResult:
        """Check IBKR connectivity"""
        start_time = time.time()
        service = "ibkr"
        
        try:
            ib = IB()
            ib.connect(host, port, clientId=client_id, timeout=self.timeout)
            response_time = time.time() - start_time
            
            if ib.isConnected():
                # Get account info to verify connection
                account = ib.accountSummary()
                ib.disconnect()
                
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.HEALTHY,
                    message="IBKR is accessible",
                    response_time=response_time,
                    timestamp=datetime.now(),
                    details={"host": host, "port": port, "client_id": client_id, "account_items": len(account)}
                )
            else:
                return HealthCheckResult(
                    service=service,
                    status=HealthStatus.UNHEALTHY,
                    message="IBKR connection failed",
                    response_time=response_time,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return HealthCheckResult(
                service=service,
                status=HealthStatus.UNHEALTHY,
                message=f"IBKR check failed: {str(e)}",
                response_time=time.time() - start_time,
                timestamp=datetime.now()
            )
    
    def run_all_checks(self, config: Dict[str, Any]) -> Dict[str, HealthCheckResult]:
        """Run all health checks"""
        results = {}
        
        # Check external APIs
        results["slickcharts"] = self.check_slickcharts()
        results["yfinance"] = self.check_yfinance()
        
        # Check Alpha Vantage if API key provided
        alpha_vantage_key = config.get("alpha_vantage_key", "")
        results["alpha_vantage"] = self.check_alpha_vantage(alpha_vantage_key)
        
        # Check SMTP if credentials provided
        smtp_config = config.get("email", {})
        if smtp_config.get("enabled", False):
            results["smtp"] = self.check_smtp(
                smtp_config.get("smtp_server", "smtp.gmail.com"),
                smtp_config.get("smtp_port", 465),
                smtp_config.get("username", ""),
                smtp_config.get("password", "")
            )
        
        # Check IBKR if configured
        brokers = config.get("brokers", [])
        for broker in brokers:
            if broker.get("enabled", False) and broker.get("name", "").lower() == "ibkr":
                results["ibkr"] = self.check_ibkr(
                    broker.get("host", "127.0.0.1"),
                    broker.get("port", 7497),
                    broker.get("client_id", 1)
                )
                break
        
        with self._lock:
            self.results.update(results)
        
        return results
    
    def get_overall_status(self) -> Tuple[HealthStatus, str]:
        """Get overall health status"""
        with self._lock:
            if not self.results:
                return HealthStatus.UNKNOWN, "No health checks performed"
            
            unhealthy_count = sum(1 for result in self.results.values() if result.status == HealthStatus.UNHEALTHY)
            degraded_count = sum(1 for result in self.results.values() if result.status == HealthStatus.DEGRADED)
            total_count = len(self.results)
            
            if unhealthy_count == 0 and degraded_count == 0:
                return HealthStatus.HEALTHY, f"All {total_count} services are healthy"
            elif unhealthy_count == 0:
                return HealthStatus.DEGRADED, f"{degraded_count} services degraded, {total_count - degraded_count} healthy"
            else:
                return HealthStatus.UNHEALTHY, f"{unhealthy_count} services unhealthy, {degraded_count} degraded"

class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints"""
    
    def __init__(self, health_checker: HealthChecker, *args, **kwargs):
        self.health_checker = health_checker
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health":
            self._handle_health_check()
        elif self.path == "/health/detailed":
            self._handle_detailed_health_check()
        elif self.path == "/metrics":
            self._handle_metrics()
        else:
            self._handle_not_found()
    
    def _handle_health_check(self):
        """Handle basic health check"""
        status, message = self.health_checker.get_overall_status()
        
        response = {
            "status": status.value,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        http_status = 200 if status == HealthStatus.HEALTHY else 503
        self._send_json_response(response, http_status)
    
    def _handle_detailed_health_check(self):
        """Handle detailed health check"""
        with self.health_checker._lock:
            results = dict(self.health_checker.results)
        
        response = {
            "overall_status": self.health_checker.get_overall_status()[0].value,
            "services": {
                service: {
                    "status": result.status.value,
                    "message": result.message,
                    "response_time": result.response_time,
                    "timestamp": result.timestamp.isoformat(),
                    "details": result.details
                }
                for service, result in results.items()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        self._send_json_response(response)
    
    def _handle_metrics(self):
        """Handle metrics endpoint"""
        # This would integrate with the metrics collector
        response = {
            "message": "Metrics endpoint not implemented yet",
            "timestamp": datetime.now().isoformat()
        }
        self._send_json_response(response)
    
    def _handle_not_found(self):
        """Handle 404"""
        response = {
            "error": "Not found",
            "message": "Available endpoints: /health, /health/detailed, /metrics"
        }
        self._send_json_response(response, 404)
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

class HealthCheckServer:
    """Health check HTTP server"""
    
    def __init__(self, health_checker: HealthChecker, port: int = 8080):
        self.health_checker = health_checker
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the health check server"""
        def handler(*args, **kwargs):
            return HealthCheckHandler(self.health_checker, *args, **kwargs)
        
        self.server = HTTPServer(("", self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        logger.info(f"Health check server started on port {self.port}")
        logger.info(f"Endpoints: http://localhost:{self.port}/health")
        logger.info(f"Detailed: http://localhost:{self.port}/health/detailed")
    
    def stop(self):
        """Stop the health check server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Health check server stopped")

def run_health_check(config: Dict[str, Any], detailed: bool = False) -> Dict[str, Any]:
    """Run health check and return results"""
    checker = HealthChecker()
    results = checker.run_all_checks(config)
    
    if detailed:
        return {
            "overall_status": checker.get_overall_status()[0].value,
            "services": {
                service: {
                    "status": result.status.value,
                    "message": result.message,
                    "response_time": result.response_time,
                    "timestamp": result.timestamp.isoformat(),
                    "details": result.details
                }
                for service, result in results.items()
            }
        }
    else:
        status, message = checker.get_overall_status()
        return {
            "status": status.value,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

# CLI function
def main():
    """CLI entry point for health checks"""
    import argparse
    from config_manager import get_config
    
    parser = argparse.ArgumentParser(description="Trading bot health check")
    parser.add_argument("--detailed", action="store_true", help="Show detailed results")
    parser.add_argument("--server", action="store_true", help="Start HTTP server")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    
    args = parser.parse_args()
    
    config = get_config()
    config_dict = {
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
    }
    
    if args.server:
        checker = HealthChecker()
        server = HealthCheckServer(checker, args.port)
        server.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
    else:
        results = run_health_check(config_dict, args.detailed)
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()