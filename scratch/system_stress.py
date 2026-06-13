import asyncio
import aiohttp
import time

async def stress_test_api(url, requests=100):
    print(f"🚀 Iniciando estrés sobre {url} ({requests} peticiones)...")
    async with aiohttp.ClientSession() as session:
        tasks = []
        start_time = time.time()
        for i in range(requests):
            tasks.append(session.get(url))
        
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        success = [r for r in responses if r.status == 200]
        blocked = [r for r in responses if r.status == 429]
        
        print(f"✅ Completado en {end_time - start_time:.2f}s")
        print(f"📈 Exitosas: {len(success)}")
        print(f"🛡️ Bloqueadas (Rate Limit): {len(blocked)}")

if __name__ == "__main__":
    # URL local con API Key para pasar el filtro @require_api_key
    API_KEY = "EEA-ADMIN-2026-X7"
    URL = f"http://localhost:5055/api/backtest?key={API_KEY}"
    asyncio.run(stress_test_api(URL))
