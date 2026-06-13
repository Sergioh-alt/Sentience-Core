"""
EEA-2026-ANT: stress_test_latency.py
Stress Test de Latencia para el Core i3 10th Gen.
Simula el procesamiento de 50 activos simultáneos en el Córtex para medir el Event Loop.
"""
import asyncio
import time
import random

async def simulate_agent_task(ticker):
    """Simula una llamada a LLM o descarga de datos (100-300ms)"""
    start = time.perf_counter()
    await asyncio.sleep(random.uniform(0.1, 0.3))
    return time.perf_counter() - start

async def run_stress_test(num_assets=50):
    print(f"--- Iniciando Stress Test: {num_assets} activos simultaneos ---")
    print(f"Hardware: Core i3 10th Gen (20GB RAM)")
    
    start_total = time.perf_counter()
    tasks = [simulate_agent_task(f"TICKER_{i}") for i in range(num_assets)]
    results = await asyncio.gather(*tasks)
    end_total = time.perf_counter()
    
    total_time = end_total - start_total
    avg_task = sum(results) / len(results)
    
    print("\n" + "="*40)
    print(f"RESULTADOS:")
    print(f"Tiempo Total: {total_time:.2f} segundos")
    print(f"Latencia Media por Agente: {avg_task:.2f}s")
    print(f"Capacidad de Respuesta: {'EXCELENTE' if total_time < 2 else 'DEGRADACION'}")
    print("="*40)
    
if __name__ == "__main__":
    asyncio.run(run_stress_test(50))
