"""
EEA-2026-ANT: core/nlp_sensor.py
Procesamiento de Lenguaje Natural (FinBERT) ejecutado en GPU para análisis de noticias.
"""
import logging

log = logging.getLogger("EEA-2026")

try:
    import torch
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    log.warning("Transformers no detectado. El NLPSensor no funcionará localmente.")

class NLPSensor:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.pipeline = None
        self.device = "cpu"
        self._initialize()

    def _initialize(self):
        if not TRANSFORMERS_AVAILABLE:
            return
            
        try:
            device_id = 0 if torch.cuda.is_available() else -1
            if device_id == 0:
                self.device = "cuda"
                log.info(f"[NLP] [FinBERT] Cargando modelo NLP en GPU: {torch.cuda.get_device_name(0)}")
            else:
                log.info("[NLP] [FinBERT] Cargando modelo NLP en CPU.")

            # Cargar FinBERT (ProsusAI)
            self.pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert", device=device_id)
            log.info("✅ [FinBERT] Modelo ProsusAI/finbert cargado exitosamente.")
        except Exception as e:
            log.error(f"❌ [FinBERT] Error cargando modelo: {e}")

    def analyze_headlines(self, headlines):
        """
        Analiza una lista de textos en lote y devuelve un score de sentimiento.
        Retorna: score (float 0.0 - 1.0) donde 0.0 es Pánico y 1.0 es Euforia.
        """
        if not self.pipeline or not headlines:
            return 0.5

        try:
            # Procesar todo de una vez (Batch)
            results = self.pipeline(headlines)
            
            score = 0.0
            valid_count = 0
            
            for res in results:
                label = res['label']
                conf = res['score']
                
                if label == 'positive':
                    score += conf
                    valid_count += 1
                elif label == 'negative':
                    score -= conf
                    valid_count += 1
            
            if valid_count == 0:
                return 0.5
                
            # Normalizar de [-1, 1] a [0, 1]
            avg_score = score / valid_count
            final_score = (avg_score + 1.0) / 2.0
            
            return round(final_score, 2)

        except Exception as e:
            log.error(f"Error analizando titulares con FinBERT: {e}")
            return 0.5
