"""
Bond Trader - Módulo para trading de renta fija
Maneja ETFs de bonos y instrumentos de renta fija (30% de la cartera)
"""

import logging
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

class BondTrader:
    """Trader especializado en instrumentos de renta fija"""
    
    def __init__(self):
        # ETFs de bonos más populares y líquidos
        self.bond_etfs = {
            # Bonos del Tesoro de largo plazo
            'TLT': {
                'name': 'iShares 20+ Year Treasury Bond ETF',
                'duration': 'Long-term',
                'type': 'Treasury',
                'target_allocation': 0.40  # 40% del 30% de renta fija
            },
            'IEF': {
                'name': 'iShares 7-10 Year Treasury Bond ETF', 
                'duration': 'Intermediate-term',
                'type': 'Treasury',
                'target_allocation': 0.30  # 30% del 30% de renta fija
            },
            'SHY': {
                'name': 'iShares 1-3 Year Treasury Bond ETF',
                'duration': 'Short-term', 
                'type': 'Treasury',
                'target_allocation': 0.20  # 20% del 30% de renta fija
            },
            # Bonos corporativos
            'BND': {
                'name': 'Vanguard Total Bond Market ETF',
                'duration': 'Broad',
                'type': 'Corporate',
                'target_allocation': 0.10  # 10% del 30% de renta fija
            },
            'AGG': {
                'name': 'iShares Core U.S. Aggregate Bond ETF',
                'duration': 'Broad',
                'type': 'Corporate', 
                'target_allocation': 0.00  # Reserva
            }
        }
        
        logger.info(f"Bond Trader inicializado con {len(self.bond_etfs)} ETFs de bonos")
    
    def get_bond_data(self, symbol: str, period: str = '1y') -> Optional[pd.DataFrame]:
        """
        Obtiene datos históricos de ETFs de bonos
        
        Args:
            symbol: Símbolo del ETF de bono
            period: Período de datos históricos
        
        Returns:
            DataFrame con datos OHLCV o None si falla
        """
        try:
            if symbol not in self.bond_etfs:
                logger.warning(f"ETF de bono no soportado: {symbol}")
                return None
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                logger.warning(f"No se obtuvieron datos para {symbol}")
                return None
            
            # Filtrar datos válidos
            data = data.dropna()
            
            logger.info(f"Datos obtenidos para {symbol}: {len(data)} días")
            return data
            
        except Exception as e:
            logger.error(f"Error obteniendo datos para {symbol}: {e}")
            return None
    
    def get_bond_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene el precio actual de un ETF de bono
        
        Args:
            symbol: Símbolo del ETF
        
        Returns:
            Precio actual o None si falla
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Intentar diferentes campos de precio
            price = (info.get('regularMarketPrice') or 
                    info.get('currentPrice') or 
                    info.get('previousClose'))
            
            if price and price > 0:
                logger.info(f"Precio actual de {symbol}: ${price:.2f}")
                return float(price)
            else:
                logger.warning(f"No se pudo obtener precio para {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo precio para {symbol}: {e}")
            return None
    
    def get_bond_yield(self, symbol: str) -> Optional[float]:
        """
        Obtiene el yield (rendimiento) de un ETF de bono
        
        Args:
            symbol: Símbolo del ETF
        
        Returns:
            Yield anual o None si falla
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Buscar yield en diferentes campos
            yield_value = (info.get('yield') or 
                          info.get('dividendYield') or 
                          info.get('trailingAnnualDividendYield'))
            
            if yield_value and yield_value > 0:
                # Convertir a porcentaje si es necesario
                if yield_value < 1:
                    yield_value = yield_value * 100
                
                logger.info(f"Yield de {symbol}: {yield_value:.2f}%")
                return float(yield_value)
            else:
                logger.warning(f"No se pudo obtener yield para {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo yield para {symbol}: {e}")
            return None
    
    def generate_bond_signals(self, symbols: List[str], period: str = '1y') -> Dict[str, int]:
        """
        Genera señales de trading para ETFs de bonos
        
        Args:
            symbols: Lista de símbolos de ETFs
            period: Período de datos históricos
        
        Returns:
            Dict con símbolo -> señal (1=BUY, -1=SELL, 0=HOLD)
        """
        signals = {}
        
        for symbol in symbols:
            try:
                data = self.get_bond_data(symbol, period)
                if data is None or len(data) < 50:
                    logger.warning(f"Datos insuficientes para {symbol}")
                    signals[symbol] = 0
                    continue
                
                # Análisis específico para bonos
                signal = self._analyze_bond_technical(data, symbol)
                signals[symbol] = signal
                
                logger.info(f"Señal para {symbol}: {'BUY' if signal == 1 else 'SELL' if signal == -1 else 'HOLD'}")
                
            except Exception as e:
                logger.error(f"Error generando señal para {symbol}: {e}")
                signals[symbol] = 0
        
        return signals
    
    def _analyze_bond_technical(self, data: pd.DataFrame, symbol: str) -> int:
        """
        Análisis técnico específico para bonos
        
        Args:
            data: DataFrame con datos OHLCV
            symbol: Símbolo del ETF
        
        Returns:
            Señal: 1=BUY, -1=SELL, 0=HOLD
        """
        try:
            close = data['Close']
            
            # 1. Análisis de tendencia con medias móviles
            sma_20 = close.rolling(20).mean()
            sma_50 = close.rolling(50).mean()
            sma_200 = close.rolling(200).mean()
            
            # 2. RSI para detectar sobrecompra/sobreventa
            rsi = self._calculate_rsi(close, 14)
            current_rsi = rsi.iloc[-1]
            
            # 3. MACD para momentum
            macd_line, signal_line, histogram = self._calculate_macd(close)
            
            # 4. Análisis de volatilidad
            volatility = close.pct_change().rolling(20).std()
            current_vol = volatility.iloc[-1]
            avg_vol = volatility.mean()
            
            # 5. Análisis de yield (si está disponible)
            current_yield = self.get_bond_yield(symbol)
            
            signals = []
            
            # Tendencia de medias móviles
            if sma_20.iloc[-1] > sma_50.iloc[-1] > sma_200.iloc[-1]:
                signals.append(1)  # BUY - tendencia alcista
            elif sma_20.iloc[-1] < sma_50.iloc[-1] < sma_200.iloc[-1]:
                signals.append(-1)  # SELL - tendencia bajista
            else:
                signals.append(0)  # HOLD - tendencia lateral
            
            # RSI
            if current_rsi < 30:
                signals.append(1)  # BUY - oversold
            elif current_rsi > 70:
                signals.append(-1)  # SELL - overbought
            else:
                signals.append(0)  # HOLD
            
            # MACD
            if macd_line.iloc[-1] > signal_line.iloc[-1]:
                signals.append(1)  # BUY
            else:
                signals.append(-1)  # SELL
            
            # Volatilidad (bonos con baja volatilidad son más atractivos)
            if current_vol < avg_vol * 0.8:
                signals.append(1)  # BUY - baja volatilidad
            elif current_vol > avg_vol * 1.2:
                signals.append(-1)  # SELL - alta volatilidad
            else:
                signals.append(0)  # HOLD
            
            # Yield (bonos con yield alto son más atractivos)
            if current_yield and current_yield > 3.0:  # Yield > 3%
                signals.append(1)  # BUY
            elif current_yield and current_yield < 1.0:  # Yield < 1%
                signals.append(-1)  # SELL
            else:
                signals.append(0)  # HOLD
            
            # Decisión final
            buy_signals = sum(1 for s in signals if s == 1)
            sell_signals = sum(1 for s in signals if s == -1)
            
            # Para bonos, ser más conservador - requerir más señales
            if buy_signals >= 3 and buy_signals > sell_signals:
                return 1  # BUY
            elif sell_signals >= 3 and sell_signals > buy_signals:
                return -1  # SELL
            else:
                return 0  # HOLD
                
        except Exception as e:
            logger.error(f"Error en análisis técnico de bonos: {e}")
            return 0
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula el RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calcula el MACD"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def get_bond_performance(self, symbol: str, period: str = '1mo') -> Optional[float]:
        """
        Calcula el rendimiento de un ETF de bono en un período
        
        Args:
            symbol: Símbolo del ETF
            period: Período ('1mo', '3mo', '6mo', '1y')
        
        Returns:
            Rendimiento en porcentaje o None si falla
        """
        try:
            data = self.get_bond_data(symbol, period)
            if data is None or len(data) < 2:
                return None
            
            initial_price = data['Close'].iloc[0]
            final_price = data['Close'].iloc[-1]
            performance = ((final_price - initial_price) / initial_price) * 100
            
            return performance
            
        except Exception as e:
            logger.error(f"Error calculando rendimiento para {symbol}: {e}")
            return None
    
    def get_top_bond_performers(self, num_bonds: int = 3) -> List[Tuple[str, float]]:
        """
        Obtiene los ETFs de bonos con mejor rendimiento en los últimos 30 días
        
        Args:
            num_bonds: Número de ETFs a retornar
        
        Returns:
            Lista de tuplas (símbolo, rendimiento_30d)
        """
        performers = []
        
        for symbol in self.bond_etfs.keys():
            try:
                performance = self.get_bond_performance(symbol, '1mo')
                if performance is not None:
                    performers.append((symbol, performance))
                    
            except Exception as e:
                logger.error(f"Error calculando rendimiento para {symbol}: {e}")
                continue
        
        # Ordenar por rendimiento descendente
        performers.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Top {min(num_bonds, len(performers))} ETFs de bonos por rendimiento:")
        for i, (symbol, perf) in enumerate(performers[:num_bonds]):
            bond_info = self.bond_etfs[symbol]
            logger.info(f"  {i+1}. {symbol} ({bond_info['name']}): {perf:+.2f}%")
        
        return performers[:num_bonds]
    
    def get_bond_allocation_recommendation(self) -> Dict[str, float]:
        """
        Obtiene recomendación de asignación basada en condiciones del mercado
        
        Returns:
            Dict con símbolo -> porcentaje recomendado
        """
        recommendations = {}
        
        try:
            # Obtener rendimientos recientes
            performers = self.get_top_bond_performers(len(self.bond_etfs))
            performer_dict = dict(performers)
            
            # Asignar pesos basados en rendimiento y tipo de bono
            total_weight = 0
            
            for symbol, bond_info in self.bond_etfs.items():
                base_weight = bond_info['target_allocation']
                performance = performer_dict.get(symbol, 0)
                
                # Ajustar peso basado en rendimiento (máximo ±20% del peso base)
                performance_factor = 1 + (performance / 100) * 0.2
                performance_factor = max(0.8, min(1.2, performance_factor))  # Limitar entre 0.8 y 1.2
                
                adjusted_weight = base_weight * performance_factor
                recommendations[symbol] = adjusted_weight
                total_weight += adjusted_weight
            
            # Normalizar para que sume 1.0
            if total_weight > 0:
                for symbol in recommendations:
                    recommendations[symbol] = recommendations[symbol] / total_weight
            
            logger.info("Recomendaciones de asignación de bonos:")
            for symbol, weight in recommendations.items():
                bond_info = self.bond_etfs[symbol]
                logger.info(f"  {symbol}: {weight*100:.1f}% ({bond_info['name']})")
            
        except Exception as e:
            logger.error(f"Error generando recomendaciones de asignación: {e}")
            # Usar asignaciones por defecto
            for symbol, bond_info in self.bond_etfs.items():
                recommendations[symbol] = bond_info['target_allocation']
        
        return recommendations
    
    def validate_bond_trade(self, symbol: str, quantity: float, price: float) -> Tuple[bool, str]:
        """
        Valida si un trade de bono es válido
        
        Args:
            symbol: Símbolo del ETF
            quantity: Cantidad a tradear
            price: Precio por unidad
        
        Returns:
            Tuple[bool, str]: (es_válido, razón)
        """
        try:
            # Verificar que el ETF esté soportado
            if symbol not in self.bond_etfs:
                return False, f"ETF de bono no soportado: {symbol}"
            
            # Verificar precio válido
            if price <= 0:
                return False, "Precio inválido"
            
            # Verificar cantidad válida
            if quantity <= 0:
                return False, "Cantidad inválida"
            
            # Verificar que el mercado esté abierto (bonos operan en horario de mercado)
            current_time = datetime.now()
            if current_time.weekday() >= 5:  # Fin de semana
                return False, "Mercado de bonos cerrado (fin de semana)"
            
            # Verificar precio actual
            current_price = self.get_bond_price(symbol)
            if current_price is None:
                return False, "No se puede obtener precio actual"
            
            # Verificar que el precio no esté muy desactualizado (máximo 2% de diferencia)
            price_diff = abs(price - current_price) / current_price
            if price_diff > 0.02:
                return False, f"Precio muy desactualizado (diff: {price_diff*100:.1f}%)"
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Error validando trade de bono: {e}")
            return False, f"Error de validación: {e}"
    
    def get_bond_market_summary(self) -> Dict:
        """Obtiene un resumen del mercado de bonos"""
        summary = {
            'total_etfs': len(self.bond_etfs),
            'top_performers': [],
            'market_status': 'Market Hours Only',
            'last_updated': datetime.now().isoformat()
        }
        
        try:
            # Obtener top performers
            top_performers = self.get_top_bond_performers(3)
            summary['top_performers'] = [
                {
                    'symbol': symbol,
                    'name': self.bond_etfs[symbol]['name'],
                    'performance_30d': perf,
                    'type': self.bond_etfs[symbol]['type']
                }
                for symbol, perf in top_performers
            ]
        except Exception as e:
            logger.error(f"Error obteniendo resumen del mercado de bonos: {e}")
        
        return summary