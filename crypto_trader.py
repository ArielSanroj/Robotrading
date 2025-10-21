"""
Crypto Trader - Módulo para trading de criptomonedas
Integra con APIs de exchanges para trading de crypto (10% de la cartera)
"""

import logging
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

class CryptoTrader:
    """Trader especializado en criptomonedas"""
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.binance.com"  # Binance API (gratuita)
        
        # Criptomonedas soportadas (símbolos de Yahoo Finance)
        self.supported_cryptos = {
            'BTC-USD': 'Bitcoin',
            'ETH-USD': 'Ethereum', 
            'ADA-USD': 'Cardano',
            'SOL-USD': 'Solana',
            'DOT-USD': 'Polkadot',
            'MATIC-USD': 'Polygon',
            'AVAX-USD': 'Avalanche',
            'LINK-USD': 'Chainlink',
            'UNI-USD': 'Uniswap',
            'ATOM-USD': 'Cosmos'
        }
        
        logger.info(f"Crypto Trader inicializado con {len(self.supported_cryptos)} criptomonedas soportadas")
    
    def get_crypto_data(self, symbol: str, period: str = '1y') -> Optional[pd.DataFrame]:
        """
        Obtiene datos históricos de criptomonedas usando Yahoo Finance
        
        Args:
            symbol: Símbolo de la cripto (ej: 'BTC-USD')
            period: Período de datos ('1y', '6mo', '3mo', etc.)
        
        Returns:
            DataFrame con datos OHLCV o None si falla
        """
        try:
            if symbol not in self.supported_cryptos:
                logger.warning(f"Criptomoneda no soportada: {symbol}")
                return None
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                logger.warning(f"No se obtuvieron datos para {symbol}")
                return None
            
            # Criptomonedas operan 24/7, filtrar datos válidos
            data = data.dropna()
            
            logger.info(f"Datos obtenidos para {symbol}: {len(data)} días")
            return data
            
        except Exception as e:
            logger.error(f"Error obteniendo datos para {symbol}: {e}")
            return None
    
    def get_crypto_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene el precio actual de una criptomoneda
        
        Args:
            symbol: Símbolo de la cripto (ej: 'BTC-USD')
        
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
                logger.info(f"Precio actual de {symbol}: ${price:,.2f}")
                return float(price)
            else:
                logger.warning(f"No se pudo obtener precio para {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo precio para {symbol}: {e}")
            return None
    
    def generate_crypto_signals(self, symbols: List[str], period: str = '1y') -> Dict[str, int]:
        """
        Genera señales de trading para criptomonedas usando análisis técnico
        
        Args:
            symbols: Lista de símbolos de crypto
            period: Período de datos históricos
        
        Returns:
            Dict con símbolo -> señal (1=BUY, -1=SELL, 0=HOLD)
        """
        signals = {}
        
        for symbol in symbols:
            try:
                data = self.get_crypto_data(symbol, period)
                if data is None or len(data) < 50:  # Mínimo 50 días de datos
                    logger.warning(f"Datos insuficientes para {symbol}")
                    signals[symbol] = 0
                    continue
                
                # Análisis técnico para crypto
                signal = self._analyze_crypto_technical(data)
                signals[symbol] = signal
                
                logger.info(f"Señal para {symbol}: {'BUY' if signal == 1 else 'SELL' if signal == -1 else 'HOLD'}")
                
            except Exception as e:
                logger.error(f"Error generando señal para {symbol}: {e}")
                signals[symbol] = 0
        
        return signals
    
    def _analyze_crypto_technical(self, data: pd.DataFrame) -> int:
        """
        Análisis técnico específico para criptomonedas
        
        Args:
            data: DataFrame con datos OHLCV
        
        Returns:
            Señal: 1=BUY, -1=SELL, 0=HOLD
        """
        try:
            # Calcular indicadores técnicos
            close = data['Close']
            
            # 1. RSI (Relative Strength Index)
            rsi = self._calculate_rsi(close, 14)
            current_rsi = rsi.iloc[-1]
            
            # 2. MACD
            macd_line, signal_line, histogram = self._calculate_macd(close)
            macd_signal = 1 if macd_line.iloc[-1] > signal_line.iloc[-1] else -1
            
            # 3. Media móvil exponencial
            ema_20 = close.ewm(span=20).mean()
            ema_50 = close.ewm(span=50).mean()
            ma_signal = 1 if ema_20.iloc[-1] > ema_50.iloc[-1] else -1
            
            # 4. Volatilidad (Bollinger Bands)
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(close, 20, 2)
            current_price = close.iloc[-1]
            bb_position = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
            
            # 5. Tendencia de volumen
            volume_sma = data['Volume'].rolling(20).mean()
            volume_trend = 1 if data['Volume'].iloc[-1] > volume_sma.iloc[-1] else -1
            
            # Combinar señales
            signals = []
            
            # RSI: Comprar en oversold, vender en overbought
            if current_rsi < 30:
                signals.append(1)  # BUY
            elif current_rsi > 70:
                signals.append(-1)  # SELL
            else:
                signals.append(0)  # HOLD
            
            # MACD
            signals.append(macd_signal)
            
            # Media móvil
            signals.append(ma_signal)
            
            # Bollinger Bands: Comprar cerca del lower band
            if bb_position < 0.2:
                signals.append(1)  # BUY
            elif bb_position > 0.8:
                signals.append(-1)  # SELL
            else:
                signals.append(0)  # HOLD
            
            # Volumen
            signals.append(volume_trend)
            
            # Decisión final: mayoría de señales
            buy_signals = sum(1 for s in signals if s == 1)
            sell_signals = sum(1 for s in signals if s == -1)
            
            if buy_signals > sell_signals and buy_signals >= 3:
                return 1  # BUY
            elif sell_signals > buy_signals and sell_signals >= 3:
                return -1  # SELL
            else:
                return 0  # HOLD
                
        except Exception as e:
            logger.error(f"Error en análisis técnico: {e}")
            return 0
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula el RSI (Relative Strength Index)"""
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
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2):
        """Calcula las Bandas de Bollinger"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band
    
    def get_top_crypto_performers(self, num_cryptos: int = 5) -> List[Tuple[str, float]]:
        """
        Obtiene las criptomonedas con mejor rendimiento en los últimos 30 días
        
        Args:
            num_cryptos: Número de criptos a retornar
        
        Returns:
            Lista de tuplas (símbolo, rendimiento_30d)
        """
        performers = []
        
        for symbol in self.supported_cryptos.keys():
            try:
                data = self.get_crypto_data(symbol, '1mo')
                if data is None or len(data) < 20:
                    continue
                
                # Calcular rendimiento de 30 días
                current_price = data['Close'].iloc[-1]
                price_30d_ago = data['Close'].iloc[-20] if len(data) >= 20 else data['Close'].iloc[0]
                performance = ((current_price - price_30d_ago) / price_30d_ago) * 100
                
                performers.append((symbol, performance))
                
            except Exception as e:
                logger.error(f"Error calculando rendimiento para {symbol}: {e}")
                continue
        
        # Ordenar por rendimiento descendente
        performers.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Top {min(num_cryptos, len(performers))} criptomonedas por rendimiento:")
        for i, (symbol, perf) in enumerate(performers[:num_cryptos]):
            logger.info(f"  {i+1}. {symbol}: {perf:+.2f}%")
        
        return performers[:num_cryptos]
    
    def validate_crypto_trade(self, symbol: str, quantity: float, price: float) -> Tuple[bool, str]:
        """
        Valida si un trade de crypto es válido
        
        Args:
            symbol: Símbolo de la crypto
            quantity: Cantidad a tradear
            price: Precio por unidad
        
        Returns:
            Tuple[bool, str]: (es_válido, razón)
        """
        try:
            # Verificar que la crypto esté soportada
            if symbol not in self.supported_cryptos:
                return False, f"Criptomoneda no soportada: {symbol}"
            
            # Verificar precio válido
            if price <= 0:
                return False, "Precio inválido"
            
            # Verificar cantidad válida
            if quantity <= 0:
                return False, "Cantidad inválida"
            
            # Verificar que el mercado esté activo (crypto opera 24/7)
            # Pero verificamos que tengamos datos recientes
            current_price = self.get_crypto_price(symbol)
            if current_price is None:
                return False, "No se puede obtener precio actual"
            
            # Verificar que el precio no esté muy desactualizado (máximo 5% de diferencia)
            price_diff = abs(price - current_price) / current_price
            if price_diff > 0.05:
                return False, f"Precio muy desactualizado (diff: {price_diff*100:.1f}%)"
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Error validando trade de crypto: {e}")
            return False, f"Error de validación: {e}"
    
    def get_crypto_market_summary(self) -> Dict:
        """Obtiene un resumen del mercado de criptomonedas"""
        summary = {
            'total_cryptos': len(self.supported_cryptos),
            'top_performers': [],
            'market_status': '24/7 Active',
            'last_updated': datetime.now().isoformat()
        }
        
        try:
            # Obtener top 5 performers
            top_performers = self.get_top_crypto_performers(5)
            summary['top_performers'] = [
                {
                    'symbol': symbol,
                    'name': self.supported_cryptos[symbol],
                    'performance_30d': perf
                }
                for symbol, perf in top_performers
            ]
        except Exception as e:
            logger.error(f"Error obteniendo resumen del mercado crypto: {e}")
        
        return summary