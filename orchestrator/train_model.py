"""Entrenamiento OFFLINE del predictor (RF5).

Genera datos sintéticos que imitan lo que produce el monitor (ventanas de latencia,
jitter y pérdida) en dos regímenes: comportamiento normal y rampas de degradación
progresiva. Entrena un IsolationForest solo con lo NORMAL (detección de anomalías
no supervisada) e imprime la distribución de scores de ambos regímenes para
calibrar ml.anomaly_threshold en config.yaml.

Uso:
    docker compose exec orchestrator python train_model.py
(genera /models/predictor.pkl y /models/scaler.pkl en el volumen ml-models;
 luego: docker compose restart orchestrator)

Simplificación deliberada respecto al plan original: no hace falta levantar el
entorno y degradar gateways reales para juntar datos; el monitor produce series
numéricas simples que podemos sintetizar directamente con el mismo formato.
Limitación (documentada en el informe): el modelo aprende degradaciones sintéticas,
no patrones de enlaces reales. Trabajo futuro: entrenar con capturas de producción.
"""
import os

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

WINDOW = 20          # debe coincidir con ml.feature_window de config.yaml
RNG = np.random.default_rng(42)


def ventana_normal() -> np.ndarray:
    """Enlace sano: latencia baja estable, jitter chico, pérdida ~0."""
    base_lat = RNG.uniform(1.0, 30.0)
    lat = base_lat + RNG.normal(0, base_lat * 0.05, WINDOW)
    jit = np.abs(RNG.normal(0.5, 0.3, WINDOW))
    loss = np.zeros(WINDOW)
    if RNG.random() < 0.1:                      # pérdida esporádica aislada, normal
        loss[RNG.integers(0, WINDOW)] = 5.0
    return np.vstack([lat, jit, loss])


def ventana_rampa() -> np.ndarray:
    """Degradación progresiva: la latencia/jitter/pérdida CRECEN dentro de la ventana.
    Es el patrón que el predictor debe detectar ANTES de los umbrales reactivos."""
    base_lat = RNG.uniform(5.0, 40.0)
    pendiente = RNG.uniform(1.0, 6.0)           # ms por muestra
    x = np.arange(WINDOW)
    lat = base_lat + pendiente * x + RNG.normal(0, 2, WINDOW)
    jit = np.abs(RNG.normal(1, 0.5, WINDOW)) + 0.3 * pendiente * x
    loss = np.clip(0.15 * pendiente * x + RNG.normal(0, 0.5, WINDOW), 0, 100)
    return np.vstack([lat, jit, loss])


def features(v: np.ndarray) -> list[float]:
    """Debe ser IDÉNTICO a app.predictor._features: media, desvío y pendiente de cada serie."""
    x = np.arange(v.shape[1])
    out = []
    for serie in v:
        out += [serie.mean(), serie.std(), float(np.polyfit(x, serie, 1)[0])]
    return out


def main():
    X_norm = np.array([features(ventana_normal()) for _ in range(3000)])
    X_anom = np.array([features(ventana_rampa()) for _ in range(600)])

    scaler = StandardScaler().fit(X_norm)
    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,     # % de outliers esperado DENTRO del set normal
        random_state=42,
    ).fit(scaler.transform(X_norm))

    # score como lo calcula el orquestador: -decision_function (mayor = más anómalo)
    s_norm = -model.decision_function(scaler.transform(X_norm))
    s_anom = -model.decision_function(scaler.transform(X_anom))
    print(f"score normal : p50={np.percentile(s_norm,50):+.3f}  p95={np.percentile(s_norm,95):+.3f}  max={s_norm.max():+.3f}")
    print(f"score rampa  : p05={np.percentile(s_anom,5):+.3f}  p50={np.percentile(s_anom,50):+.3f}")
    print("=> elegir ml.anomaly_threshold ENTRE el p95 normal y el p05 de rampa "
          "(margen sin falsos positivos ni falsos negativos)")

    models_dir = os.environ.get("MODELS_PATH", "/models")
    os.makedirs(models_dir, exist_ok=True)
    joblib.dump(model, os.path.join(models_dir, "predictor.pkl"))
    joblib.dump(scaler, os.path.join(models_dir, "scaler.pkl"))
    print(f"modelo y scaler guardados en {models_dir}/")


if __name__ == "__main__":
    main()
