import os
import requests
import logging

log = logging.getLogger("EEA-2026")

class MacroSensor:
    def __init__(self, aid="Macro-Radar"):
        self.aid = aid
        self.cg_key = os.getenv("COINGECKO_API_KEY")
        log.info(f"[{self.aid}] 🌍 Radar Macroeconómico On-Chain activado.")

    def get_fear_and_greed_index(self):
        """Lee el sentimiento mundial del mercado Crypto."""
        try:
            res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            res.raise_for_status()
            data = res.json()["data"][0]
            
            valor = int(data["value"])
            clasificacion = data["value_classification"]
            
            log.info(f"[{self.aid}] Índice Macro: {valor}/100 ({clasificacion})")
            return {"value": valor, "status": clasificacion}
        except Exception as e:
            log.warning(f"[{self.aid}] Fallo al leer Fear & Greed Index: {e}")
            return {"value": 50, "status": "Neutral"}

    def get_coingecko_volume(self, ticker):
        """Usa tu nueva API de CoinGecko para ver si hay volumen real o falso."""
        if not self.cg_key:
            return {"volume": 0, "status": "Sin API de CoinGecko"}

        # Diccionario traductor de símbolos a IDs de CoinGecko
        cg_ids = {"BTC-USD": "bitcoin", "ETH-USD": "ethereum", "DOGE-USD": "dogecoin"}
        coin_id = cg_ids.get(ticker)
        
        if not coin_id:
            return {"volume": 0, "status": "No Crypto"}

        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_vol=true"
            headers = {"x_cg_demo_api_key": self.cg_key}
            
            res = requests.get(url, headers=headers, timeout=5)
            res.raise_for_status()
            
            data = res.json()
            volumen_24h = data[coin_id].get("usd_24h_vol", 0)
            log.info(f"[{self.aid}] Volumen 24h {ticker} (CoinGecko): ${volumen_24h:,.2f}")
            
            return {"volume": volumen_24h, "status": "OK"}
        except Exception as e:
            log.warning(f"[{self.aid}] Error leyendo CoinGecko: {e}")
            return {"volume": 0, "status": "Error de Red"}