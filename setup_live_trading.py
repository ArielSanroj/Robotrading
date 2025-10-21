"""
Setup Live Trading - Script de configuración para trading en vivo
Configura el bot para salir del modo paper y activar trading con dinero real
"""

import os
import logging
from dotenv import load_dotenv, set_key

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_live_trading():
    """Configura el bot para trading en vivo"""
    
    print("=" * 60)
    print("CONFIGURACIÓN DE TRADING EN VIVO")
    print("=" * 60)
    print()
    print("⚠️  ADVERTENCIA: Esta configuración activará trading con DINERO REAL")
    print("   Asegúrate de haber probado el bot en modo paper trading primero")
    print()
    
    # Verificar que existe .env
    if not os.path.exists('.env'):
        print("❌ No se encontró archivo .env")
        print("   Por favor copia .env.example a .env y configura las variables")
        return False
    
    # Cargar variables actuales
    load_dotenv()
    
    # Verificar configuración actual
    current_paper = os.getenv("USE_PAPER", "True").lower() == "true"
    current_broker = os.getenv("BROKER", "ALPACA")
    
    print(f"Configuración actual:")
    print(f"  - Broker: {current_broker}")
    print(f"  - Modo Paper: {'SÍ' if current_paper else 'NO'}")
    print()
    
    if not current_paper:
        print("✅ El bot ya está configurado para trading en vivo")
        return True
    
    # Confirmar cambio
    print("¿Estás seguro de que quieres cambiar a trading en vivo?")
    print("Esto significa que el bot usará DINERO REAL de tu cuenta")
    print()
    
    while True:
        response = input("Escribe 'SI' para confirmar o 'NO' para cancelar: ").strip().upper()
        if response == 'SI':
            break
        elif response == 'NO':
            print("❌ Configuración cancelada")
            return False
        else:
            print("Por favor responde 'SI' o 'NO'")
    
    try:
        # Cambiar a trading en vivo
        set_key('.env', 'USE_PAPER', 'False')
        
        # Si usa IBKR, cambiar puerto a live
        if current_broker == 'IBKR':
            set_key('.env', 'IBKR_PORT', '7496')
            print("✅ Puerto IBKR cambiado a 7496 (live trading)")
        
        print("✅ Configuración actualizada para trading en vivo")
        print()
        print("NUEVA CONFIGURACIÓN:")
        print(f"  - Broker: {current_broker}")
        print(f"  - Modo Paper: NO (LIVE TRADING)")
        if current_broker == 'IBKR':
            print(f"  - Puerto IBKR: 7496 (live)")
        print()
        
        # Mostrar asignaciones de cartera
        print("ASIGNACIONES DE CARTERA:")
        print("  - Renta Variable (Acciones): 60%")
        print("  - Renta Fija (Bonos/ETFs): 30%")
        print("  - Criptomonedas: 10%")
        print()
        
        # Mostrar instrucciones finales
        print("INSTRUCCIONES FINALES:")
        print("1. Asegúrate de que tu broker esté configurado correctamente")
        print("2. Verifica que tienes fondos suficientes en tu cuenta")
        print("3. El bot respetará los límites de asignación automáticamente")
        print("4. Monitorea los logs en 'alerts.log' para seguimiento")
        print("5. El bot operará diariamente a las 4:00 PM (días hábiles)")
        print()
        
        print("🚀 ¡Configuración completada! El bot está listo para trading en vivo")
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando configuración: {e}")
        return False

def verify_live_setup():
    """Verifica que la configuración de live trading esté correcta"""
    
    print("=" * 60)
    print("VERIFICACIÓN DE CONFIGURACIÓN LIVE")
    print("=" * 60)
    
    load_dotenv()
    
    # Verificar variables críticas
    use_paper = os.getenv("USE_PAPER", "True").lower() == "true"
    broker = os.getenv("BROKER", "ALPACA")
    shares_per_trade = int(os.getenv("SHARES_PER_TRADE", "10"))
    
    print(f"✅ Modo Paper: {'SÍ' if use_paper else 'NO'}")
    print(f"✅ Broker: {broker}")
    print(f"✅ Acciones por trade: {shares_per_trade}")
    
    if use_paper:
        print("⚠️  El bot está en modo PAPER - no usará dinero real")
    else:
        print("🔥 El bot está en modo LIVE - usará dinero real")
    
    # Verificar configuración específica del broker
    if broker == "IBKR":
        ibkr_port = int(os.getenv("IBKR_PORT", "7497"))
        print(f"✅ Puerto IBKR: {ibkr_port} ({'Paper' if ibkr_port == 7497 else 'Live'})")
        
        if not use_paper and ibkr_port == 7497:
            print("⚠️  ADVERTENCIA: Modo live pero puerto paper (7497)")
        elif use_paper and ibkr_port == 7496:
            print("⚠️  ADVERTENCIA: Modo paper pero puerto live (7496)")
    
    # Verificar variables de email
    gmail = os.getenv("GMAIL_ADDRESS")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("RECIPIENT_EMAIL")
    
    if all([gmail, gmail_pass, recipient]):
        print("✅ Configuración de email: OK")
    else:
        print("❌ Configuración de email: INCOMPLETA")
    
    print()
    return not use_paper

def show_portfolio_allocation():
    """Muestra la configuración de asignación de cartera"""
    
    print("=" * 60)
    print("CONFIGURACIÓN DE ASIGNACIÓN DE CARTERA")
    print("=" * 60)
    
    print("El bot gestiona automáticamente una cartera diversificada:")
    print()
    print("📈 RENTA VARIABLE (60%)")
    print("   - Acciones del S&P 500 con mejor rendimiento YTD")
    print("   - Análisis técnico con modelo HMM")
    print("   - Máximo 5 posiciones simultáneas")
    print()
    print("🏦 RENTA FIJA (30%)")
    print("   - ETFs de bonos del Tesoro (TLT, IEF, SHY)")
    print("   - ETFs de bonos corporativos (BND, AGG)")
    print("   - Análisis técnico específico para bonos")
    print()
    print("₿ CRIPTOMONEDAS (10%)")
    print("   - Principales criptos (BTC, ETH, ADA, SOL, DOT)")
    print("   - Trading 24/7 con análisis técnico")
    print("   - Verificación de precios en tiempo real")
    print()
    print("🛡️  PROTECCIONES:")
    print("   - Límites automáticos de asignación por clase de activo")
    print("   - Verificación de poder de compra antes de trades")
    print("   - Validación de precios de múltiples fuentes")
    print("   - Trading solo en horarios de mercado (excepto crypto)")
    print()

if __name__ == "__main__":
    print("🤖 ROBOTRADING - CONFIGURACIÓN LIVE TRADING")
    print()
    
    while True:
        print("Selecciona una opción:")
        print("1. Configurar trading en vivo")
        print("2. Verificar configuración actual")
        print("3. Mostrar asignación de cartera")
        print("4. Salir")
        print()
        
        choice = input("Opción (1-4): ").strip()
        
        if choice == "1":
            setup_live_trading()
        elif choice == "2":
            verify_live_setup()
        elif choice == "3":
            show_portfolio_allocation()
        elif choice == "4":
            print("¡Hasta luego!")
            break
        else:
            print("Opción inválida. Por favor selecciona 1-4.")
        
        print()
        input("Presiona Enter para continuar...")
        print("\n" + "="*60 + "\n")