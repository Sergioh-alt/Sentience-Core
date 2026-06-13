"""
EEA-2026-ANT: core/deep_learning_sensor.py
Red Neuronal LSTM entrenada en GPU (PyTorch) para predicciones matemáticas directas.
Utiliza el DataFrame existente para evitar saturar la red.
"""
import logging
import numpy as np
import pandas as pd

log = logging.getLogger("EEA-2026")

try:
    import torch
    import torch.nn as nn
    from sklearn.preprocessing import MinMaxScaler
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    log.warning("PyTorch no detectado. El DeepLearningSensor correrá en modo simulado.")

if TORCH_AVAILABLE:
    class PriceLSTM(nn.Module):
        def __init__(self, input_size=1, hidden_layer_size=64, output_size=1):
            super().__init__()
            self.hidden_layer_size = hidden_layer_size
            self.lstm = nn.LSTM(input_size, hidden_layer_size, batch_first=True)
            self.linear = nn.Linear(hidden_layer_size, output_size)

        def forward(self, input_seq):
            lstm_out, _ = self.lstm(input_seq)
            predictions = self.linear(lstm_out[:, -1, :])
            return predictions

class DeepLearningSensor:
    def __init__(self):
        self.device = "cpu"
        self.models = {}
        
        if TORCH_AVAILABLE:
            if torch.cuda.is_available():
                self.device = "cuda"
                log.info(f"[DL] [DeepLearning] PyTorch detecto CUDA: {torch.cuda.get_device_name(0)}")
            else:
                log.info("[DL] [DeepLearning] PyTorch usando CPU.")

    def get_prediction(self, ticker, df: pd.DataFrame):
        """
        Toma el DataFrame histórico (df), entrena una LSTM súper rápida en GPU,
        y predice la siguiente vela.
        Retorna: {"prediction": "BULLISH"|"BEARISH", "confidence": float}
        """
        if not TORCH_AVAILABLE or df is None or df.empty:
            return {"prediction": "NEUTRAL", "confidence": 0.0}

        try:
            # Usar la columna Close del DF que ya tenemos en memoria
            if 'Close' not in df.columns:
                return {"prediction": "NEUTRAL", "confidence": 0.0}

            data = df['Close'].values.reshape(-1, 1)
            
            # Limpiar NaNs por si acaso
            data = data[~np.isnan(data)].reshape(-1, 1)

            seq_length = 60 # 60 velas históricas
            if len(data) <= seq_length:
                 return {"prediction": "NEUTRAL", "confidence": 0.0}

            # 1. Escalar datos a rango [-1, 1] para la Red Neuronal
            scaler = MinMaxScaler(feature_range=(-1, 1))
            data_normalized = scaler.fit_transform(data)

            # Tomar máximo las últimas 500 velas para que el entrenamiento tome milisegundos
            train_data = data_normalized[-500:] if len(data_normalized) > 500 else data_normalized

            # 2. Preparar los Tensors para PyTorch
            xs, ys = [], []
            for i in range(len(train_data) - seq_length):
                xs.append(train_data[i:(i + seq_length)])
                ys.append(train_data[i + seq_length])

            X = torch.tensor(np.array(xs), dtype=torch.float32).to(self.device)
            y = torch.tensor(np.array(ys), dtype=torch.float32).to(self.device)

            # 3. Inicializar o recuperar el modelo para este Ticker
            if ticker not in self.models:
                model = PriceLSTM().to(self.device)
                optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
                criterion = nn.MSELoss()
                
                # Entrenamiento flash en GPU (15 épocas)
                model.train()
                for _ in range(15):
                    optimizer.zero_grad()
                    y_pred = model(X)
                    loss = criterion(y_pred, y)
                    loss.backward()
                    optimizer.step()
                
                self.models[ticker] = model
            
            model = self.models[ticker]
            model.eval()

            # 4. Predecir el futuro (la siguiente vela)
            last_sequence_np = np.array([data_normalized[-seq_length:]])
            last_sequence = torch.tensor(last_sequence_np, dtype=torch.float32).to(self.device)
            
            with torch.no_grad():
                pred_normalized = model(last_sequence)
            
            pred_price = scaler.inverse_transform(pred_normalized.cpu().numpy())[0][0]
            current_price = data[-1][0]
            
            # 5. Lógica de Confianza Matemática
            diff_pct = (pred_price - current_price) / current_price
            
            # Umbral de movimiento significativo (ej: 0.1%)
            threshold = 0.001 
            
            if diff_pct > threshold:
                prediction = "BULLISH"
                # Mapeo agresivo de confianza: si predice un 1% de subida, es 99% confiado
                confidence = min(99.0, 50.0 + (abs(diff_pct) * 100 * 40))
            elif diff_pct < -threshold:
                prediction = "BEARISH"
                confidence = min(99.0, 50.0 + (abs(diff_pct) * 100 * 40))
            else:
                prediction = "NEUTRAL"
                confidence = 0.0
                
            return {"prediction": prediction, "confidence": round(confidence, 2), "pred_price": round(float(pred_price), 4)}

        except Exception as e:
            log.error(f"Error en DeepLearningSensor para {ticker}: {e}")
            return {"prediction": "NEUTRAL", "confidence": 0.0}
