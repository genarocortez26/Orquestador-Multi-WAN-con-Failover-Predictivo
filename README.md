# Orquestador Multi-WAN con Failover Predictivo

Plano de control que reparte el tráfico de una PyME entre dos enlaces WAN según **la clase de cada flujo** y la calidad medida de cada enlace, con failover reactivo y un modelo de detección de anomalías que anticipa la degradación antes de que cruce los umbrales.

Stack: Python (FastAPI, asyncio, scikit-learn) · Linux policy-based routing (iptables, conntrack, ip rule) · Docker Compose · Prometheus

---

## El problema

Una PyME con dos conexiones a internet, una de fibra y una de cable, normalmente usa una y deja la otra de respaldo. Cuando la principal se cae, alguien la cambia a mano o un router hace failover y corta todas las sesiones abiertas.

Dos cosas quedan sin resolver:

1. **No todo el tráfico necesita lo mismo.** Una llamada VoIP se rompe con 20 ms de jitter; una descarga de backup no se entera. Mandar los dos por el mismo enlace desperdicia el bueno o arruina la llamada.
2. **El failover reactivo llega tarde por definición.** Cuando el umbral se cruza, la llamada ya se cortó. Un enlace que se degrada progresivamente da señales antes de caer.

Este orquestador ataca las dos: decide **por flujo** según política, y usa la pendiente de las métricas para migrar antes del corte.

## Arquitectura

```
        cliente-pyme                    ┌──────────────┐
      192.168.10.10                     │ wan1-gateway │──┐
             │                        ┌─│  (fibra)     │  │
             │ LAN                    │ └──────────────┘  │   servidor
      ┌──────┴───────┐                │                   ├── externo
      │ orquestador  │────────────────┤ ┌──────────────┐  │
      │ 192.168.10.1 │   2 WANs       └─│ wan2-gateway │──┘
      └──────┬───────┘                  │  (cable)     │
             │                          └──────────────┘
      Prometheus + API
```

Seis contenedores sobre cuatro redes bridge separadas, simulando LAN, dos enlaces WAN e internet. El cliente genera tráfico VoIP, web y bulk contra el servidor externo.

**El plano de datos no pasa por Python.** El orquestador solo configura reglas: tablas de routing por WAN, `ip rule` por fwmark, y `CONNMARK --restore-mark` para que el kernel enrute cada paquete por donde corresponde. Ningún paquete atraviesa el proceso. Eso mantiene el throughput en el kernel y limita al orquestador al plano de control.

## Cómo decide

**Clasificación (una vez, al nacer el flujo).** Por puerto y protocolo: VoIP (SIP 5060/5061, IAX 4569, rango RTP 10000-20000), web (80/443/8080/8443), bulk (21/22/873/9000), y el resto como `other`.

La clasificación es estática a propósito. Reclasificar un flujo vivo obliga a re-marcarlo y moverlo de WAN a mitad de sesión, lo que la rompe.

**Puntaje por enlace.** Cada política pondera latencia, jitter, pérdida y costo con pesos distintos:

| Clase | Latencia | Jitter | Pérdida | Costo | Límites duros |
|---|---|---|---|---|---|
| VoIP | 0,40 | 0,40 | 0,15 | 0,05 | ≤2% pérdida, ≤100 ms, ≤10 ms jitter |
| Web | 0,50 | 0,10 | 0,30 | 0,10 | ≤10% pérdida, ≤300 ms |
| Bulk | 0,10 | 0,05 | 0,20 | 0,65 | ≤20% pérdida |

Las métricas se normalizan a [0,1] contra topes fijos y el puntaje es `1 − penalización`. Los límites duros descartan candidatos antes de comparar puntajes: un enlace con 3% de pérdida no compite para VoIP aunque tenga la mejor latencia.

Si ningún enlace cumple los límites, elige el menos malo entre los vivos y registra el motivo. Preferí que el sistema degrade de forma explicable antes que dejar el flujo sin salida.

## Failover predictivo

**Isolation Forest** entrenado solo con ventanas de comportamiento normal, o sea detección de anomalías no supervisada. Las features son media, desvío y **pendiente** de latencia, jitter y pérdida sobre una ventana móvil de 20 muestras.

La pendiente es lo que da la capacidad anticipatoria. Una rampa de degradación tiene pendiente positiva mientras los valores absolutos todavía están dentro de los umbrales reactivos: ahí es donde el modelo dispara y el umbral fijo todavía no.

El umbral no se eligió a ojo. `train_model.py` imprime la distribución de scores de los dos regímenes y el valor se fija en la brecha entre el p95 de lo normal y el p05 de las rampas, que es donde no hay falsos positivos ni negativos. Además exige 3 ciclos anómalos consecutivos antes de migrar, para no reaccionar a un pico aislado.

**El ML es un diferenciador, no una dependencia.** Si no hay modelo en `/models`, el predictor se desactiva con un log claro y el sistema sigue funcionando con failover reactivo. Preferí eso a que el orquestador no arranque por falta de un `.pkl`.

## Cómo correrlo

En el host, antes de levantar (los módulos de kernel no se cargan desde un contenedor):

```bash
sudo modprobe nf_conntrack xt_mark iptable_mangle iptable_nat
```

Después:

```bash
docker compose up --build
docker compose exec orchestrator python train_model.py
docker compose restart orchestrator
```

- API y estado: `http://localhost:8080`
- Prometheus: `http://localhost:9090`

Requiere Linux con esos módulos disponibles. En Docker Desktop sobre macOS o Windows el marcado de conexiones no funciona igual.

## Decisiones descartadas

El `config.yaml` y los módulos dejan documentado, en comentarios, lo que se probó y se sacó. Vale la pena leerlo porque las razones son la parte interesante:

- **Reentrenamiento online del modelo.** Un swap de modelo en caliente durante un failover deja al sistema decidiendo con dos modelos distintos en la misma ventana, y entrenar dentro del proceso compite por CPU con el plano de control justo cuando más se lo necesita.
- **Garbage collector propio de flujos.** El escaneo de conntrack ya refleja solo los flujos vivos; mantener un timeout paralelo era estado duplicado.
- **`SYS_MODULE` en el contenedor.** Cargar módulos de kernel desde un contenedor es mala práctica y encima no funciona en Docker Desktop.
- **Nombre de interfaz por configuración.** En Docker el orden de conexión de las redes no es determinístico, así que `eth1` no siempre es la misma WAN. Se detecta en runtime por subred del gateway.

## Notas de seguridad

Todos los comandos externos se invocan con lista de argumentos, nunca con `shell=True`. Los campos que se le pasan a `conntrack` vienen de parsear su propia salida, o sea de datos que en última instancia llegan de la red, y con shell habría superficie de inyección de comandos. Está documentado en `routing.py` con el ejemplo de qué no hacer.

## Limitaciones

- **El modelo aprende degradaciones sintéticas**, generadas por `train_model.py`, no capturas de enlaces reales. Es lo que permite entrenar sin montar un laboratorio, pero significa que las anomalías que detecta son las que se le enseñaron.
- **Dos WANs.** El diseño escala a N por configuración, pero solo se probó con dos.
- **Clasificación por puerto.** No hay inspección de protocolo, así que VoIP en puertos no estándar cae en `other`.
- **La migración preventiva solo mueve flujos VoIP.** Es la clase que más sufre la degradación, pero es una decisión de alcance, no un límite técnico.

## Contexto

TP final de Redes de Datos — Universidad de Belgrano.
