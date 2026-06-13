import psutil
import logging

log = logging.getLogger("EEA-2026")

class SentinelAgent:
    def __init__(self, aid="Sentinel-Hardware"):
        self.aid = aid
        log.info(f"[{self.aid}] [GUARD] Centinela de hardware activado (Sin LLM - Alta velocidad).")

    def get_system_health(self):
        """Monitorea el consumo real de la computadora local"""
        try:
            # Lee la CPU y la RAM de tu PC
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            
            # Límites térmicos y de memoria
            status = "WARNING" if cpu > 85 or ram > 90 else "NOMINAL"
            
            return {
                "cpu": f"{cpu}%", 
                "ram": f"{ram}%", 
                "status": status
            }
        except Exception as e:
            log.error(f"[{self.aid}] Error leyendo sensores: {e}")
            return {"cpu": "NOMINAL", "ram": "0%", "status": "BOOTING"}