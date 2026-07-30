"""Clasificación de tráfico (RF2) y motor de decisión por flujo (RF3, RF6)."""
import logging

log = logging.getLogger("decision")

# Topes de normalización: llevan cada métrica a [0,1] para poder combinarlas.
_CAP_LAT_MS = 300.0
_CAP_JIT_MS = 50.0


def classify(flow: dict, tc: dict) -> str:
    """Clase del flujo por puertos/protocolo, decidida UNA vez al nacer el flujo.

    NOTA: se eliminó la reclasificación de 'bulk' por duración de conexión
    (bulk_min_duration_seconds). Reclasificar un flujo vivo obliga a re-marcarlo y
    moverlo de WAN a mitad de sesión, rompiéndola. La clasificación estática por
    puerto es determinística, explicable en la defensa y suficiente (RF2).
    """
    port = flow["dport"]
    if flow["proto"] == "udp":
        if port in tc["voip_ports_udp"] or tc["voip_rtp_range_start"] <= port <= tc["voip_rtp_range_end"]:
            return "voip"
    else:  # tcp
        if port in tc["web_ports_tcp"]:
            return "web"
        if port in tc["bulk_ports_tcp"]:
            return "bulk"
    return "other"


def _violates_hard_limits(metrics: dict, limits: dict) -> bool:
    if not limits:
        return False
    if limits.get("max_loss_pct") is not None and metrics["loss_pct"] > limits["max_loss_pct"]:
        return True
    if limits.get("max_latency_ms") is not None and metrics["latency_ms"] > limits["max_latency_ms"]:
        return True
    if limits.get("max_jitter_ms") is not None and metrics["jitter_ms"] > limits["max_jitter_ms"]:
        return True
    return False


def score_wan(metrics: dict, wan_cfg: dict, weights: dict, max_cost: float) -> float:
    """Puntaje en [0,1]: 1 = enlace ideal. Penaliza cada métrica normalizada por su peso."""
    pen = (
        weights["latency"] * min(metrics["latency_ms"] / _CAP_LAT_MS, 1.0)
        + weights["jitter"] * min(metrics["jitter_ms"] / _CAP_JIT_MS, 1.0)
        + weights["loss"] * min(metrics["loss_pct"] / 100.0, 1.0)
        + weights["cost"] * (wan_cfg["cost"] / max_cost)
    )
    return round(1.0 - pen, 4)


def choose_wan(tclass: str, monitors: dict, cfg: dict) -> tuple[str | None, str]:
    """Elige la mejor WAN para una clase. Devuelve (wan_id, motivo)."""
    policy = cfg["_policies_by_class"][tclass]
    max_cost = max(w["cost"] for w in cfg["wans"])

    candidatas = []
    for wid, mon in monitors.items():
        if mon.status == "down":
            continue
        m = mon.metrics()
        if _violates_hard_limits(m, policy.get("hard_limits", {})):
            continue
        candidatas.append((wid, score_wan(m, cfg["_wans_by_id"][wid], policy["weights"], max_cost)))

    if not candidatas:
        # Todas violan límites o están caídas: elegir la "menos mala" entre las vivas
        vivas = [(wid, score_wan(mon.metrics(), cfg["_wans_by_id"][wid], policy["weights"], max_cost))
                 for wid, mon in monitors.items() if mon.status != "down"]
        if not vivas:
            return None, "sin_wan_disponible"
        wid = max(vivas, key=lambda x: x[1])[0]
        return wid, "todas_violan_limites:menos_mala"

    # Preferencia declarada de la política, si esa WAN es candidata válida
    pref = policy.get("preferred_wan")
    if pref and any(wid == pref for wid, _ in candidatas):
        return pref, "preferred_wan"

    wid = max(candidatas, key=lambda x: x[1])[0]
    return wid, "mejor_score"
