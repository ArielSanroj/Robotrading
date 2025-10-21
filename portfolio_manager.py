"""
Portfolio Manager - Gestión de asignación de cartera
Maneja la distribución: 60% renta variable, 30% renta fija, 10% cripto
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class AssetClass(Enum):
    """Clases de activos soportadas"""
    EQUITY = "equity"      # Renta variable (acciones)
    FIXED_INCOME = "fixed_income"  # Renta fija (bonos)
    CRYPTO = "crypto"      # Criptomonedas

@dataclass
class AssetAllocation:
    """Configuración de asignación de activos"""
    equity: float = 0.60      # 60% renta variable
    fixed_income: float = 0.30  # 30% renta fija
    crypto: float = 0.10      # 10% cripto
    
    def __post_init__(self):
        # Validar que las asignaciones sumen 100%
        total = self.equity + self.fixed_income + self.crypto
        if abs(total - 1.0) > 0.01:  # Tolerancia de 1%
            raise ValueError(f"Las asignaciones deben sumar 100%, actual: {total*100:.1f}%")

@dataclass
class Position:
    """Posición en un activo"""
    symbol: str
    asset_class: AssetClass
    quantity: float
    current_price: float
    market_value: float
    allocation_percentage: float

class PortfolioManager:
    """Gestor de cartera con límites de asignación por clase de activo"""
    
    def __init__(self, allocation: AssetAllocation = None):
        self.allocation = allocation or AssetAllocation()
        self.positions: Dict[str, Position] = {}
        self.total_portfolio_value = 0.0
        
        # Símbolos por clase de activo
        self.equity_symbols = set()  # Se llenará con las acciones del S&P 500
        self.fixed_income_symbols = {
            'TLT',  # iShares 20+ Year Treasury Bond ETF
            'IEF',  # iShares 7-10 Year Treasury Bond ETF
            'SHY',  # iShares 1-3 Year Treasury Bond ETF
            'BND',  # Vanguard Total Bond Market ETF
            'AGG',  # iShares Core U.S. Aggregate Bond ETF
        }
        self.crypto_symbols = {
            'BTC-USD',  # Bitcoin
            'ETH-USD',  # Ethereum
            'ADA-USD',  # Cardano
            'SOL-USD',  # Solana
            'DOT-USD',  # Polkadot
        }
        
        logger.info(f"Portfolio Manager inicializado con asignaciones: "
                   f"Equity: {self.allocation.equity*100:.1f}%, "
                   f"Fixed Income: {self.allocation.fixed_income*100:.1f}%, "
                   f"Crypto: {self.allocation.crypto*100:.1f}%")
    
    def update_portfolio_value(self, total_value: float):
        """Actualiza el valor total de la cartera"""
        self.total_portfolio_value = total_value
        logger.info(f"Valor total de cartera actualizado: ${total_value:,.2f}")
    
    def update_positions(self, positions_data: List[Dict]):
        """Actualiza las posiciones desde el broker"""
        self.positions.clear()
        
        for pos_data in positions_data:
            symbol = pos_data['symbol']
            quantity = pos_data['qty']
            market_value = pos_data['market_value']
            
            # Determinar clase de activo
            asset_class = self._get_asset_class(symbol)
            if asset_class is None:
                logger.warning(f"No se pudo determinar clase de activo para {symbol}")
                continue
            
            # Calcular precio actual y porcentaje de asignación
            current_price = market_value / quantity if quantity != 0 else 0
            allocation_pct = market_value / self.total_portfolio_value if self.total_portfolio_value > 0 else 0
            
            position = Position(
                symbol=symbol,
                asset_class=asset_class,
                quantity=quantity,
                current_price=current_price,
                market_value=market_value,
                allocation_percentage=allocation_pct
            )
            
            self.positions[symbol] = position
        
        logger.info(f"Posiciones actualizadas: {len(self.positions)} activos")
    
    def _get_asset_class(self, symbol: str) -> Optional[AssetClass]:
        """Determina la clase de activo basada en el símbolo"""
        if symbol in self.equity_symbols:
            return AssetClass.EQUITY
        elif symbol in self.fixed_income_symbols:
            return AssetClass.FIXED_INCOME
        elif symbol in self.crypto_symbols:
            return AssetClass.CRYPTO
        else:
            # Asumir que es equity si no se reconoce
            logger.warning(f"Símbolo no reconocido {symbol}, asumiendo equity")
            return AssetClass.EQUITY
    
    def get_current_allocation(self) -> Dict[AssetClass, float]:
        """Obtiene la asignación actual por clase de activo"""
        allocation = {asset_class: 0.0 for asset_class in AssetClass}
        
        for position in self.positions.values():
            allocation[position.asset_class] += position.allocation_percentage
        
        return allocation
    
    def get_allocation_status(self) -> Dict[str, any]:
        """Obtiene el estado de asignación de la cartera"""
        current = self.get_current_allocation()
        target = {
            AssetClass.EQUITY: self.allocation.equity,
            AssetClass.FIXED_INCOME: self.allocation.fixed_income,
            AssetClass.CRYPTO: self.allocation.crypto
        }
        
        status = {}
        for asset_class in AssetClass:
            current_pct = current[asset_class] * 100
            target_pct = target[asset_class] * 100
            difference = current_pct - target_pct
            
            status[asset_class.value] = {
                'current': current_pct,
                'target': target_pct,
                'difference': difference,
                'within_limits': abs(difference) <= 5.0  # Tolerancia del 5%
            }
        
        return status
    
    def can_trade_asset_class(self, asset_class: AssetClass, trade_value: float) -> Tuple[bool, str]:
        """
        Verifica si se puede realizar un trade en una clase de activo específica
        
        Returns:
            Tuple[bool, str]: (puede_tradear, razón)
        """
        if self.total_portfolio_value <= 0:
            return False, "Valor de cartera no disponible"
        
        current_allocation = self.get_current_allocation()
        target_allocation = {
            AssetClass.EQUITY: self.allocation.equity,
            AssetClass.FIXED_INCOME: self.allocation.fixed_income,
            AssetClass.CRYPTO: self.allocation.crypto
        }
        
        # Calcular nueva asignación después del trade
        new_allocation_pct = (current_allocation[asset_class] * self.total_portfolio_value + trade_value) / self.total_portfolio_value
        target_pct = target_allocation[asset_class]
        
        # Verificar si excede el límite (con tolerancia del 5%)
        max_allowed = target_pct + 0.05
        if new_allocation_pct > max_allowed:
            return False, f"Excedería límite de {asset_class.value} ({new_allocation_pct*100:.1f}% > {max_allowed*100:.1f}%)"
        
        return True, "OK"
    
    def get_available_buying_power(self, asset_class: AssetClass) -> float:
        """Calcula el poder de compra disponible para una clase de activo"""
        if self.total_portfolio_value <= 0:
            return 0.0
        
        current_allocation = self.get_current_allocation()
        target_allocation = {
            AssetClass.EQUITY: self.allocation.equity,
            AssetClass.FIXED_INCOME: self.allocation.fixed_income,
            AssetClass.CRYPTO: self.allocation.crypto
        }
        
        current_value = current_allocation[asset_class] * self.total_portfolio_value
        target_value = target_allocation[asset_class] * self.total_portfolio_value
        
        # Permitir hasta 5% por encima del target
        max_value = target_value * 1.05
        available = max(0, max_value - current_value)
        
        return available
    
    def get_recommended_trade_size(self, symbol: str, asset_class: AssetClass, current_price: float) -> int:
        """Calcula el tamaño recomendado de trade basado en asignaciones y reglas de inversión"""
        available_power = self.get_available_buying_power(asset_class)
        
        if available_power <= 0:
            return 0
        
        # REGLA DE INVERSIÓN: Solo usar lo que está disponible
        # Para cuentas pequeñas (< $100), ser más conservador
        if self.total_portfolio_value < 100:
            # Máximo 20% del valor total por trade para cuentas pequeñas
            max_trade_value = self.total_portfolio_value * 0.20
        else:
            # Máximo 10% del valor disponible por trade para cuentas más grandes
            max_trade_value = available_power * 0.10
        
        # Calcular cantidad máxima de acciones que se pueden comprar
        max_shares = int(max_trade_value / current_price)
        
        # REGLA DE INVERSIÓN: Mínimo 1 acción, máximo basado en fondos disponibles
        recommended_shares = max(1, min(max_shares, 10))  # Máximo 10 acciones para cuentas pequeñas
        
        # REGLA DE INVERSIÓN: No invertir si el trade excede el 50% del valor total
        trade_value = recommended_shares * current_price
        if trade_value > self.total_portfolio_value * 0.5:
            logger.warning(f"Trade muy grande para {symbol}: ${trade_value:.2f} > 50% del valor total")
            return 0
        
        logger.info(f"Trade recomendado para {symbol}: {recommended_shares} acciones "
                   f"(${trade_value:.2f}) - {trade_value/self.total_portfolio_value*100:.1f}% del total")
        
        return recommended_shares
    
    def get_portfolio_summary(self) -> Dict:
        """Obtiene un resumen completo de la cartera"""
        allocation_status = self.get_allocation_status()
        
        summary = {
            'total_value': self.total_portfolio_value,
            'positions_count': len(self.positions),
            'allocation_status': allocation_status,
            'positions_by_class': {}
        }
        
        # Agrupar posiciones por clase de activo
        for asset_class in AssetClass:
            positions = [p for p in self.positions.values() if p.asset_class == asset_class]
            summary['positions_by_class'][asset_class.value] = {
                'count': len(positions),
                'total_value': sum(p.market_value for p in positions),
                'positions': [
                    {
                        'symbol': p.symbol,
                        'quantity': p.quantity,
                        'value': p.market_value,
                        'allocation_pct': p.allocation_percentage * 100
                    }
                    for p in positions
                ]
            }
        
        return summary
    
    def log_portfolio_status(self):
        """Registra el estado actual de la cartera"""
        summary = self.get_portfolio_summary()
        
        logger.info("=" * 60)
        logger.info("ESTADO DE CARTERA")
        logger.info("=" * 60)
        logger.info(f"Valor Total: ${summary['total_value']:,.2f}")
        logger.info(f"Posiciones: {summary['positions_count']}")
        logger.info("")
        
        for asset_class in AssetClass:
            status = summary['allocation_status'][asset_class.value]
            class_data = summary['positions_by_class'][asset_class.value]
            
            logger.info(f"{asset_class.value.upper()}:")
            logger.info(f"  Asignación: {status['current']:.1f}% / {status['target']:.1f}% "
                       f"(diff: {status['difference']:+.1f}%)")
            logger.info(f"  Posiciones: {class_data['count']} (${class_data['total_value']:,.2f})")
            
            if class_data['positions']:
                for pos in class_data['positions']:
                    logger.info(f"    {pos['symbol']}: {pos['quantity']} @ ${pos['value']:,.2f} "
                               f"({pos['allocation_pct']:.1f}%)")
            logger.info("")
        
        logger.info("=" * 60)