import sys
import os
from unittest.mock import MagicMock
import logging

# Añadir el path del proyecto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.orderbook_sensor import OrderBookSensor

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("STRESS-TEST")

def run_spoofing_stress_test():
    log.info("🧪 Iniciando Prueba de Estrés: Detector de Spoofing")
    
    # Mock del router
    mock_router = MagicMock()
    sensor = OrderBookSensor(mock_router)
    
    symbol = "BTC-USD"
    
    # ESCENARIO 1: Aparece un muro gigante
    log.info("1. Simulando aparición de muro de 50 BTC ($3.5M)...")
    mock_router.exchange.fetch_order_book.return_value = {
        'bids': [[70000.0, 50.0], [69990.0, 0.1]],
        'asks': [[70100.0, 0.1], [70200.0, 0.1]]
    }
    
    res1 = sensor.analyze_imbalance(symbol)
    log.info(f"Resultado Ciclo 1: Ratio={res1['ratio']}, Spoofing={res1['spoofing']}")
    
    # ESCENARIO 2: El muro desaparece súbitamente
    log.info("2. Simulando desaparición súbita del muro (SPOOFING)...")
    mock_router.exchange.fetch_order_book.return_value = {
        'bids': [[69990.0, 0.1]], # El muro de 70000.0 ya no está
        'asks': [[70100.0, 0.1], [70200.0, 0.1]]
    }
    
    res2 = sensor.analyze_imbalance(symbol)
    log.info(f"Resultado Ciclo 2: Ratio={res2['ratio']}, Spoofing={res2['spoofing']}")
    
    if res2['spoofing']:
        log.info("✅ PRUEBA EXITOSA: El detector identificó la manipulación.")
    else:
        log.error("❌ PRUEBA FALLIDA: El detector ignoró la desaparición del muro.")

if __name__ == "__main__":
    run_spoofing_stress_test()
