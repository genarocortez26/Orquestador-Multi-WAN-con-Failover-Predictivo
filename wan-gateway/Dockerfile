FROM python:3.11-slim

# FIX del error de build: "tc" NO es un paquete, viene dentro de iproute2.
# También se quitó inetutils-traceroute (solo servía para debug manual).
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iptables \
    iputils-ping \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.* uvicorn==0.32.*
COPY gateway.py .

CMD ["python", "gateway.py"]
