"""Carga y validación de config.yaml (única fuente de configuración, RNF sin hardcodeo)."""
import os
import sys
import yaml

REQUIRED_TOP = ["orchestrator", "wans", "thresholds", "policies", "ml", "api", "traffic_classification"]


def load_config() -> dict:
    path = os.environ.get("CONFIG_PATH", "/app/config.yaml")
    try:
        with open(path) as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError:
        sys.exit(f"[config] No existe {path}. Montar config.yaml en el contenedor.")
    except yaml.YAMLError as e:
        sys.exit(f"[config] YAML inválido: {e}")

    faltantes = [k for k in REQUIRED_TOP if k not in cfg]
    if faltantes:
        sys.exit(f"[config] Faltan secciones: {faltantes}")
    if len(cfg["wans"]) < 2:
        sys.exit("[config] Se requieren al menos 2 WANs definidas.")
    marks = [w["fwmark"] for w in cfg["wans"]]
    if len(set(marks)) != len(marks):
        sys.exit("[config] Los fwmark de las WANs deben ser únicos.")

    # índice de políticas por clase para acceso O(1)
    cfg["_policies_by_class"] = {p["traffic_class"]: p for p in cfg["policies"]}
    cfg["_wans_by_id"] = {w["id"]: w for w in cfg["wans"]}
    return cfg
