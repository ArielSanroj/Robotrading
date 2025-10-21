# 🤖 Robotrading - Multi-Asset Portfolio Management

## 🎯 **Nueva Funcionalidad: Gestión de Cartera Multi-Activos**

El bot ahora gestiona automáticamente una cartera diversificada con asignaciones específicas:

- **📈 60% Renta Variable** (Acciones del S&P 500)
- **🏦 30% Renta Fija** (ETFs de bonos)
- **₿ 10% Criptomonedas** (Principales criptos)

## 🚀 **Características Principales**

### **1. Gestión Automática de Asignaciones**
- ✅ Respeta límites de asignación por clase de activo
- ✅ Calcula automáticamente el tamaño de trades basado en asignaciones disponibles
- ✅ Previene exceder límites de exposición
- ✅ Rebalanceo automático de la cartera

### **2. Trading Multi-Activos**
- **Renta Variable**: Análisis HMM de acciones del S&P 500
- **Renta Fija**: Trading de ETFs de bonos con análisis técnico específico
- **Criptomonedas**: Trading 24/7 de principales criptos

### **3. Protecciones Avanzadas**
- ✅ Validación de poder de compra antes de cada trade
- ✅ Verificación de asignaciones en tiempo real
- ✅ Trading solo en horarios de mercado (excepto crypto)
- ✅ Límites de exposición por clase de activo

## 📁 **Nuevos Archivos**

### **Módulos de Gestión**
- `portfolio_manager.py` - Gestión central de asignaciones
- `crypto_trader.py` - Trading de criptomonedas
- `bond_trader.py` - Trading de renta fija

### **Scripts de Utilidad**
- `setup_live_trading.py` - Configuración para trading en vivo
- `portfolio_monitor.py` - Monitoreo en tiempo real de la cartera

## ⚙️ **Configuración**

### **1. Variables de Entorno (.env)**
```env
# Trading Mode
USE_PAPER=False  # Cambiado a LIVE trading

# Portfolio Allocation (automático)
EQUITY_ALLOCATION=60      # 60% Renta Variable
FIXED_INCOME_ALLOCATION=30  # 30% Renta Fija  
CRYPTO_ALLOCATION=10      # 10% Criptomonedas

# Crypto Trading (opcional)
CRYPTO_API_KEY=your_crypto_api_key
CRYPTO_API_SECRET=your_crypto_api_secret
```

### **2. Configuración Rápida**
```bash
# Configurar trading en vivo
python setup_live_trading.py

# Monitorear cartera
python portfolio_monitor.py
```

## 🎯 **Estrategia de Inversión**

### **Renta Variable (60%)**
- **Selección**: Top 15 acciones S&P 500 por rendimiento YTD
- **Análisis**: Modelo HMM para detectar regímenes de volatilidad
- **Señales**: BUY en baja volatilidad, SELL en alta volatilidad
- **Límite**: Máximo 5 posiciones simultáneas

### **Renta Fija (30%)**
- **Instrumentos**: ETFs de bonos del Tesoro y corporativos
- **Análisis**: RSI, MACD, medias móviles específicas para bonos
- **Señales**: Basadas en tendencia, yield y volatilidad
- **Horario**: Solo en horario de mercado

### **Criptomonedas (10%)**
- **Instrumentos**: BTC, ETH, ADA, SOL, DOT, MATIC, AVAX, LINK, UNI, ATOM
- **Análisis**: RSI, MACD, Bollinger Bands, análisis de volumen
- **Señales**: Combinación de múltiples indicadores técnicos
- **Horario**: Trading 24/7

## 📊 **Monitoreo de Cartera**

### **Estado de Asignaciones**
```
📈 EQUITY: 58.2% | Objetivo: 60.0% | Diferencia: -1.8% ✅
🏦 FIXED_INCOME: 31.5% | Objetivo: 30.0% | Diferencia: +1.5% ✅
₿ CRYPTO: 10.3% | Objetivo: 10.0% | Diferencia: +0.3% ✅
```

### **Posiciones Detalladas**
```
📊 EQUITY (3 posiciones, $45,230.50):
   NVDA: 10 @ $15,230.50 (33.7%)
   AAPL: 15 @ $12,450.00 (27.5%)
   MSFT: 8 @ $17,550.00 (38.8%)

📊 FIXED_INCOME (2 posiciones, $22,150.00):
   TLT: 25 @ $15,200.00 (68.6%)
   IEF: 20 @ $6,950.00 (31.4%)

📊 CRYPTO (1 posición, $7,500.00):
   BTC-USD: 0.15 @ $7,500.00 (100.0%)
```

## 🛡️ **Sistema de Protecciones**

### **Límites de Asignación**
- ✅ Máximo 5% de desviación del objetivo por clase de activo
- ✅ Bloqueo automático de trades que excedan límites
- ✅ Cálculo dinámico del tamaño de trades

### **Validaciones de Trading**
- ✅ Verificación de poder de compra disponible
- ✅ Validación de precios de múltiples fuentes
- ✅ Verificación de horarios de mercado
- ✅ Prevención de trades duplicados

### **Gestión de Riesgo**
- ✅ Diversificación automática entre clases de activos
- ✅ Límites de exposición por posición
- ✅ Monitoreo continuo de asignaciones
- ✅ Alertas por email para trades importantes

## 🚀 **Uso del Sistema**

### **1. Configuración Inicial**
```bash
# 1. Configurar trading en vivo
python setup_live_trading.py

# 2. Verificar configuración
python portfolio_monitor.py

# 3. Ejecutar bot
python robotrading.py
```

### **2. Monitoreo Diario**
```bash
# Ver estado de cartera
python portfolio_monitor.py

# Revisar logs
tail -f alerts.log
```

### **3. Configuración Avanzada**
```python
# Modificar asignaciones (en portfolio_manager.py)
allocation = AssetAllocation(
    equity=0.60,        # 60% renta variable
    fixed_income=0.30,  # 30% renta fija
    crypto=0.10         # 10% cripto
)
```

## 📈 **Ventajas del Sistema Multi-Activos**

### **1. Diversificación Automática**
- Reduce riesgo mediante exposición a múltiples clases de activos
- Rebalanceo automático mantiene asignaciones objetivo
- Protección contra volatilidad de mercados específicos

### **2. Gestión Inteligente de Riesgo**
- Límites automáticos previenen sobre-exposición
- Validaciones múltiples antes de cada trade
- Monitoreo continuo de asignaciones

### **3. Optimización de Rendimientos**
- Aprovecha oportunidades en múltiples mercados
- Trading 24/7 en criptomonedas
- Análisis técnico específico por clase de activo

### **4. Automatización Completa**
- Sin intervención manual requerida
- Gestión automática de asignaciones
- Ejecución automática de trades

## ⚠️ **Consideraciones Importantes**

### **Trading en Vivo**
- 🔥 **DINERO REAL**: El bot usa dinero real de tu cuenta
- ⚠️ **RIESGO**: Las pérdidas son reales
- 📊 **MONITOREO**: Revisa regularmente el estado de la cartera
- 🛡️ **PROTECCIÓN**: El sistema tiene múltiples protecciones integradas

### **Requisitos del Sistema**
- Cuenta de broker configurada (IBKR recomendado)
- Fondos suficientes para diversificación
- Conexión estable a internet
- Monitoreo regular de logs y alertas

## 🎉 **¡Listo para Trading en Vivo!**

El sistema está completamente configurado para:

1. ✅ **Gestionar automáticamente** una cartera diversificada
2. ✅ **Respetar límites** de asignación por clase de activo
3. ✅ **Ejecutar trades** en múltiples mercados
4. ✅ **Proteger contra** sobre-exposición y riesgos
5. ✅ **Monitorear** el estado de la cartera en tiempo real

**¡Tu bot de trading multi-activos está listo para operar con dinero real!** 🚀