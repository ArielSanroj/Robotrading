"""
Portfolio Monitor - Monitoreo en tiempo real de la cartera
Muestra el estado actual de asignaciones y posiciones
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from portfolio_manager import PortfolioManager, AssetClass
from crypto_trader import CryptoTrader
from bond_trader import BondTrader
from ibkr_client import IBKRTradingClientSync

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def monitor_portfolio():
    """Monitorea el estado actual de la cartera"""
    
    print("=" * 80)
    print("🤖 ROBOTRADING - MONITOR DE CARTERA")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Cargar configuración
    load_dotenv()
    use_paper = os.getenv("USE_PAPER", "True").lower() == "true"
    broker = os.getenv("BROKER", "ALPACA")
    
    print(f"🔧 Configuración:")
    print(f"   - Broker: {broker}")
    print(f"   - Modo: {'PAPER' if use_paper else 'LIVE'}")
    print()
    
    try:
        # Inicializar gestores
        portfolio_manager = PortfolioManager()
        crypto_trader = CryptoTrader()
        bond_trader = BondTrader()
        
        # Conectar al broker si es IBKR
        if broker == "IBKR":
            client = IBKRTradingClientSync(paper=use_paper)
            if not client.connect():
                print("❌ No se pudo conectar al broker IBKR")
                return False
            
            # Obtener datos de la cuenta
            account_summary = client.get_account_summary()
            positions_data = client.get_positions()
            
            # Actualizar gestor de cartera
            if account_summary:
                total_value = float(account_summary.get('NetLiquidation', 0))
                portfolio_manager.update_portfolio_value(total_value)
                print(f"💰 Valor total de cartera: ${total_value:,.2f}")
            
            if positions_data:
                portfolio_manager.update_positions(positions_data)
                print(f"📊 Posiciones activas: {len(positions_data)}")
            
            client.disconnect()
        else:
            print("⚠️  Solo se soporta monitoreo completo con IBKR")
            print("   Para otros brokers, revisa los logs en 'alerts.log'")
            return False
        
        # Mostrar estado de asignación
        print()
        print("📈 ESTADO DE ASIGNACIÓN DE CARTERA")
        print("-" * 50)
        
        allocation_status = portfolio_manager.get_allocation_status()
        
        for asset_class in AssetClass:
            status = allocation_status[asset_class.value]
            current = status['current']
            target = status['target']
            diff = status['difference']
            within_limits = status['within_limits']
            
            # Emoji basado en estado
            if within_limits:
                emoji = "✅"
            elif abs(diff) > 10:
                emoji = "⚠️"
            else:
                emoji = "📊"
            
            print(f"{emoji} {asset_class.value.upper()}:")
            print(f"   Actual: {current:.1f}% | Objetivo: {target:.1f}% | Diferencia: {diff:+.1f}%")
            print()
        
        # Mostrar posiciones por clase de activo
        print("💼 POSICIONES DETALLADAS")
        print("-" * 50)
        
        summary = portfolio_manager.get_portfolio_summary()
        
        for asset_class in AssetClass:
            class_data = summary['positions_by_class'][asset_class.value]
            count = class_data['count']
            total_value = class_data['total_value']
            
            if count > 0:
                print(f"📊 {asset_class.value.upper()} ({count} posiciones, ${total_value:,.2f}):")
                for pos in class_data['positions']:
                    print(f"   {pos['symbol']}: {pos['quantity']} @ ${pos['value']:,.2f} ({pos['allocation_pct']:.1f}%)")
                print()
            else:
                print(f"📊 {asset_class.value.upper()}: Sin posiciones")
                print()
        
        # Mostrar recomendaciones de trading
        print("🎯 RECOMENDACIONES DE TRADING")
        print("-" * 50)
        
        for asset_class in AssetClass:
            available_power = portfolio_manager.get_available_buying_power(asset_class)
            if available_power > 0:
                print(f"💰 {asset_class.value.upper()}: ${available_power:,.2f} disponible para compras")
            else:
                print(f"🚫 {asset_class.value.upper()}: Sin poder de compra disponible")
        
        print()
        
        # Mostrar resumen de mercados
        print("🌍 RESUMEN DE MERCADOS")
        print("-" * 50)
        
        # Crypto market summary
        crypto_summary = crypto_trader.get_crypto_market_summary()
        print(f"₿ Criptomonedas: {crypto_summary['total_cryptos']} activos, mercado 24/7")
        if crypto_summary['top_performers']:
            print("   Top performers:")
            for crypto in crypto_summary['top_performers'][:3]:
                print(f"   - {crypto['symbol']}: {crypto['performance_30d']:+.2f}%")
        
        print()
        
        # Bond market summary
        bond_summary = bond_trader.get_bond_market_summary()
        print(f"🏦 Bonos: {bond_summary['total_etfs']} ETFs, horario de mercado")
        if bond_summary['top_performers']:
            print("   Top performers:")
            for bond in bond_summary['top_performers'][:3]:
                print(f"   - {bond['symbol']}: {bond['performance_30d']:+.2f}%")
        
        print()
        
        # Alertas y advertencias
        print("⚠️  ALERTAS Y ADVERTENCIAS")
        print("-" * 50)
        
        alerts = []
        
        # Verificar asignaciones fuera de límites
        for asset_class in AssetClass:
            status = allocation_status[asset_class.value]
            if not status['within_limits']:
                alerts.append(f"⚠️  {asset_class.value.upper()} fuera de límites: {status['current']:.1f}% vs {status['target']:.1f}%")
        
        # Verificar si hay posiciones
        if summary['positions_count'] == 0:
            alerts.append("ℹ️  No hay posiciones activas en la cartera")
        
        # Verificar modo de trading
        if use_paper:
            alerts.append("ℹ️  Modo PAPER activo - no se usa dinero real")
        else:
            alerts.append("🔥 Modo LIVE activo - se usa dinero real")
        
        if alerts:
            for alert in alerts:
                print(alert)
        else:
            print("✅ No hay alertas - cartera en buen estado")
        
        print()
        print("=" * 80)
        print("✅ Monitoreo completado")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ Error en monitoreo: {e}")
        logger.error(f"Error en monitoreo de cartera: {e}")
        return False

def show_help():
    """Muestra ayuda sobre el monitoreo"""
    
    print("=" * 80)
    print("📖 AYUDA - MONITOR DE CARTERA")
    print("=" * 80)
    print()
    print("Este monitor te permite:")
    print()
    print("📊 VERIFICAR ASIGNACIONES:")
    print("   - Muestra el porcentaje actual vs objetivo para cada clase de activo")
    print("   - Indica si las asignaciones están dentro de los límites permitidos")
    print("   - Calcula la diferencia entre asignación actual y objetivo")
    print()
    print("💼 REVISAR POSICIONES:")
    print("   - Lista todas las posiciones activas por clase de activo")
    print("   - Muestra cantidad, valor y porcentaje de cada posición")
    print("   - Identifica posiciones vacías en alguna clase de activo")
    print()
    print("🎯 OBTENER RECOMENDACIONES:")
    print("   - Calcula el poder de compra disponible para cada clase de activo")
    print("   - Sugiere cuánto dinero se puede invertir sin exceder límites")
    print()
    print("🌍 MONITOREAR MERCADOS:")
    print("   - Resumen de rendimiento de criptomonedas")
    print("   - Resumen de rendimiento de ETFs de bonos")
    print("   - Estado general de los mercados")
    print()
    print("⚠️  RECIBIR ALERTAS:")
    print("   - Asignaciones fuera de límites")
    print("   - Falta de posiciones en alguna clase de activo")
    print("   - Estado del modo de trading (paper vs live)")
    print()
    print("🔧 REQUISITOS:")
    print("   - Archivo .env configurado correctamente")
    print("   - Broker IBKR conectado (para monitoreo completo)")
    print("   - TWS o IB Gateway ejecutándose (si usa IBKR)")
    print()

if __name__ == "__main__":
    print("🤖 ROBOTRADING - MONITOR DE CARTERA")
    print()
    
    while True:
        print("Selecciona una opción:")
        print("1. Monitorear cartera")
        print("2. Mostrar ayuda")
        print("3. Salir")
        print()
        
        choice = input("Opción (1-3): ").strip()
        
        if choice == "1":
            monitor_portfolio()
        elif choice == "2":
            show_help()
        elif choice == "3":
            print("¡Hasta luego!")
            break
        else:
            print("Opción inválida. Por favor selecciona 1-3.")
        
        print()
        input("Presiona Enter para continuar...")
        print("\n" + "="*80 + "\n")